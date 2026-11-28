"""Explicit document labels for Final; no merchant templates or inferred cells."""
import re
from decimal import Decimal, InvalidOperation
from app.invoice_financials import amount_literal, reference_line_indices, PAGE_FINANCIAL_SUMMARY

from . import pipeline_v4 as context
from .table_v3 import number, row_evidence


LABELS = {
    'invoice_number': r'so hoa don|hoa don so|so hd|invoice (?:no\.?|number)',
    'receipt_number': r'so phieu|so bill|receipt (?:no\.?|number)|bill (?:no\.?|number)',
    'invoice_symbol': r'ky hieu(?: hoa don)?|invoice series|series|serial',
    'invoice_date': r'ngay(?: lap| hoa don| phat hanh)?|issue date|invoice date|date',
    'subtotal_net': r'(?:tong )?tien (?:hang )?sau (?:chiet khau|giam gia)|net subtotal|subtotal after discount',
    'subtotal_gross': r'(?:tong )?tien hang truoc (?:chiet khau|giam gia)|gross subtotal|subtotal before discount',
    'subtotal': r'cong tien hang|tong tien hang|tien truoc thue|tam tinh|subtotal|sub total|total before tax',
    'vat_amount': r'tien thue(?: gtgt| vat)?|thue gtgt|vat amount|tax amount',
    'vat_rate': r'thue suat(?: gtgt| vat)?|vat rate|tax rate',
    'total_amount': r'tong (?:cong )?(?:tien )?(?:phai )?thanh toan|tong tien phai tra|grand total|amount due|total payable|total amount|total payment',
    'currency': r'dong tien thanh toan|currency|loai tien|tien te|don vi tien te',
}
ADJUSTMENTS = {
    'discount': r'giam gia|chiet khau|discount',
    'surcharge': r'phu thu(?: dich vu)?|phu phi(?: dich vu)?|surcharge|service charge',
    'cash_tendered': r'tien khach(?: dua| tra)?|tien nhan|cash tendered|amount tendered|cash received',
    'change': r'tien thua|tien tra lai|change',
}
MONETARY_FIELDS = frozenset(('subtotal', 'subtotal_net', 'subtotal_gross', 'vat_amount', 'total_amount'))


def monetary_observations(read):
    """One source-backed financial-cell reader for Final and local PDF text.

    Return source lines/IDs unchanged; do not infer a cell from another amount,
    typography confidence, arithmetic or the document's adjustment subtype.
    """
    from .source_links_v8_final import following_value, token_ids_for_span
    source_lines = read.lines
    related = reference_line_indices([line.text for line in source_lines])
    lines = [line for index, line in enumerate(source_lines) if index not in related]
    observations = []
    for line in lines:
        spec = document_label(line.text)
        if (not spec or spec[0] not in MONETARY_FIELDS
                or PAGE_FINANCIAL_SUMMARY.search(context.plain(line.text))
                or re.search(r'\(\s*(?:page|trang)\b', context.plain(line.text))):
            continue
        key, literal = spec
        value_line = line
        ids = line.ids
        if literal:
            start = line.text.rfind(literal)
            ids = token_ids_for_span(line, start, start + len(literal))
        value = observed_value(key, literal)
        empty_or_unit = (not literal.strip(' |:：') or bool(re.fullmatch(
            r'\(?\s*(?:VND|VNĐ|USD|EUR|đ|₫)\s*\)?', literal.strip(' |:：'), re.I)))
        if value is None and empty_or_unit:
            following = following_value(read, line, lines, read.size[1])
            if following is not None:
                value_line, literal, ids = following, following.text, following.ids
                value = observed_value(key, literal)
        if value is not None:
            observations.append({'key': key, 'value': value, 'line': value_line, 'ids': ids,
                                 'literal': literal, 'label_ids': line.ids})
    return observations


def inline_invoice_date_observations(read, boundary):
    """Keep a printed date on a number/series row, with original token spans."""
    from app.extraction import _header_date_literals
    from .source_links_v8_final import token_ids_for_span
    observations = []
    for line in read.lines:
        if line.y >= boundary:
            continue
        for start, end, value in _header_date_literals(line.text):
            ids = token_ids_for_span(line, start, end)
            if ids:
                observations.append((line, value, ids, line.text[start:end]))
    return observations


def target_observations(document_type, observations):
    """Group labels by destination before resolving competing identifiers."""
    grouped = {key: values for key, values in observations.items() if key not in ('receipt_number', 'subtotal_net', 'subtotal_gross')}
    for alias, priority in (('subtotal_net', 4), ('subtotal_gross', 3)):
        if observations.get(alias):
            grouped.setdefault('subtotal', []).extend({**value, 'priority': priority} for value in observations[alias])
    receipts = observations.get('receipt_number', [])
    if receipts and document_type != 'einvoice':
        grouped['invoice_number'] = [*grouped.get('invoice_number', []), *receipts]
    return grouped


def document_label(text):
    parts = re.split('[:：]', text, maxsplit=1)
    label = context.plain(re.sub(r'\([^)]*\)', '', parts[0])).strip(' .;|')
    for key, pattern in LABELS.items():
        if re.fullmatch(pattern, label):
            return key, parts[1].strip() if len(parts) == 2 else ''
        if len(parts) == 1:
            # Common receipt layout: label and right-hand value share a line
            # without punctuation. Match a complete known label, never a
            # substring of an arbitrary product or company name.
            match = re.match(r'^(?:' + pattern + r')\s+(.+)$', context.plain(text))
            if match:
                # Folded and original offsets can differ for combining marks;
                # use the original trailing words, not folded string offsets.
                count = len(match[1].split())
                literal = ' '.join(text.split()[-count:])
                if observed_value(key, literal) is not None:
                    return key, literal
    return None


def observed_value(key, literal):
    """Normalize the labelled literal, not a value derived from other fields."""
    text = literal.strip()
    if key in ('invoice_number', 'receipt_number'):
        return text if (re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9/._-]{0,49}', text)
                        and re.search(r'\d', text)) else None
    if key == 'invoice_symbol':
        return text if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9/_-]{0,39}', text) else None
    if key == 'invoice_date':
        if re.fullmatch(r'\d{1,2}\s+thang\s+\d{1,2}\s+nam\s+\d{4}', context.plain(text)):
            return context.date_value('Ngày ' + text)
        return context.date_value(text)
    if key == 'currency':
        return text.upper() if re.fullmatch(r'[A-Za-z]{3}', text) else None
    if key in ('subtotal', 'subtotal_net', 'subtotal_gross', 'vat_amount', 'total_amount', 'vat_rate'):
        text = text.strip(' |:：')
        text = re.sub(r'\s*(?:VND|VNĐ|đ|₫)\s*$', '', text, flags=re.I).strip()
        if key == 'vat_rate':
            text = text.rstrip('%').strip()
        if key == 'vat_amount' and '%' in text:
            value, _rate = amount_literal(text, lambda literal: number(literal, 'amount'))
            return value if value is not None and value.is_finite() and value >= 0 else None
        # Do not fold a rate and its amount or two competing numbers into one.
        if key != 'vat_rate' and re.fullmatch(r'\d{1,3}(?:[ \u00a0\u202f]+\d{3})+', text):
            text = ''.join(text.split())
        if not re.fullmatch(r'\d[\d.,]*', text):
            return None
        value = number(text + '%' if key == 'vat_rate' else text, key)
        if value is None:
            return None
        try:
            value = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
        if not value.is_finite() or value < 0 or (key == 'vat_rate' and value > 100):
            return None
        return value
    return None


def identity(value, *, name=False):
    if name:
        return context.plain(str(value))
    if isinstance(value, Decimal):
        return str(value.normalize())
    return str(value).casefold()


def financial_observations(reads, page):
    """Keep discount/cash/change evidence separate from goods and payable.

    Rates/multiple values remain literal observations; no amount is calculated.
    These observations do not add columns or alter Validation/Approval/Lookup.
    """
    observations = []
    seen = set()
    for read in reads:
        for line in read.lines:
            text = context.plain(line.text)
            for role, pattern in ADJUSTMENTS.items():
                match = re.match(r'^(?:' + pattern + r')\b', text)
                if not match:
                    continue
                # A product name can start with "Discount". Only publish a
                # financial observation when the rest is numeric/currency.
                tail = re.sub(r'\b(?:vnd|dong)\b|(?<=\d)d\b|\bd\b|₫', '', text[match.end():])
                if not re.search(r'\d', tail) or not re.fullmatch(r'[\d\s.,:：()+/%−–-]*', tail):
                    continue
                amounts, rates = [], []
                for token in re.finditer(r'([+-]?(?:\d{1,3}(?:[ \u00a0\u202f]+\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)*))(\s*%)?', tail.replace('−', '-')):
                    if token[2]:
                        value = number(token[1] + '%', 'vat_rate')
                        if value is not None:
                            rates.append(value)
                    else:
                        amounts.append(number(token[1], 'amount'))
                # Several untyped numbers could be columns or fragments.
                # Parentheses may carry an accounting sign. Keep the literal
                # and its geometry rather than presenting a guessed amount.
                if len(amounts) != 1 or amounts[0] is None or re.search(r'\(\s*[+-]?\d|–', tail):
                    amounts = []
                parts = row_evidence(read.boxes, {'source': line.ids})['source']
                signature = (role, line.text, tuple(tuple(p) for part in parts for p in part['polygon']))
                if signature in seen:
                    continue
                seen.add(signature)
                observations.append({'role': role, 'page': page, 'read': read.tag,
                                     'raw_text': line.text, 'evidence': parts,
                                     'observed_amounts': amounts, 'observed_rates': rates,
                                     'requires_review': True})
    return observations
