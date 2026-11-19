"""Literal, accent-insensitive invoice lookup with deterministic relevance ranking."""
import unicodedata
from sqlalchemy import case, func, or_
from .models import Invoice


def normalize_search(value):
    value = str(value or '').casefold().replace('đ', 'd')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', value)
                            if not unicodedata.combining(c)).split())


def apply_invoice_search(query, db, search):
    term = normalize_search(search)
    if not term:
        return query, None
    if db.get_bind().dialect.name == 'sqlite':
        db.connection().connection.driver_connection.create_function(
            'invoice_search_normalize', 1, normalize_search, deterministic=True)
        folded = lambda column: func.invoice_search_normalize(column)
    else:
        # PostgreSQL translate avoids requiring an unaccent extension/migration.
        accented = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        plain = ''.join(normalize_search(c) for c in accented)
        folded = lambda column: func.translate(func.lower(func.coalesce(column, '')), accented, plain)
    number, supplier, tax = [folded(column) for column in
                             (Invoice.invoice_number, Invoice.seller_name, Invoice.seller_tax_code)]
    # Every word must match; each may appear in a different searchable field.
    # SQLAlchemy escapes %, _ and / so typed text cannot act as a wildcard.
    for token in dict.fromkeys(term.split()):
        query = query.where(or_(*(field.contains(token, autoescape=True)
                                for field in (number, supplier, tax))))
    rank = case((number == term, 0), (tax == term, 1),
                (number.startswith(term, autoescape=True), 2),
                (supplier == term, 3), (supplier.startswith(term, autoescape=True), 4), else_=5)
    return query, rank
