"""FINTECH OCR: read-only advisory risk assessment for invoice review.

Rules in this module DO NOT certify invoice legality, perform an official tax
lookup, alter approval/validation states, or expose other users' invoice IDs.
They are intentionally separate from deterministic arithmetic validation.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Invoice, InvoiceFile


def _tax(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"[\s-]", "", value.strip())
    return digits if re.fullmatch(r"\d{10}(?:\d{3})?", digits) else None


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _ascii(value: str | None) -> str:
    normal = unicodedata.normalize("NFKD", _clean(value).replace("đ", "d"))
    return "".join(c for c in normal if not unicodedata.combining(c))


def _risk(code: str, message: str, *, duplicates: int = 0) -> dict:
    flag = {"code": code, "severity": "warning", "message": message}
    if duplicates:
        flag["matched_count"] = duplicates
    return flag


def assess_invoice_risks(db: Session, invoice: Invoice, *, role: str = "employee") -> dict:
    """Read-only. No ORM writes, no schema changes, no tax authority lookups.

    Employee checks only compare with their own invoices. Accountant/Admin
    checks can detect duplicates across the organization. Never return
    matched invoice IDs or owners.
    """
    flags = []
    # Employees see only their own invoices; reviewers can check across users.
    own_only = role == "employee"
    owner_id = None
    if own_only:
        owner_id = invoice.source_file.uploaded_by
    # Exact bytes, independent of file name/extension. Distinct upload records only.
    file_obj = invoice.source_file
    if file_obj and file_obj.checksum_sha256:
        query = (select(Invoice.id)
                 .join(InvoiceFile, Invoice.file_id == InvoiceFile.id)
                 .where(Invoice.id != invoice.id,
                        InvoiceFile.checksum_sha256 == file_obj.checksum_sha256))
        if own_only:
            query = query.where(InvoiceFile.uploaded_by == owner_id)
        matching_files = db.scalars(query).all()
        if matching_files:
            flags.append(_risk(
                "DUPLICATE-FILE",
                "File có nội dung giống hệt file đã được tải lên trước đó; cần kiểm tra trùng lặp.",
                duplicates=len(matching_files),
            ))

    # Use a conservative composite key; never match on invoice number alone.
    seller_tax = _tax(invoice.seller_tax_code)
    number = _clean(invoice.invoice_number)
    symbol = _clean(invoice.invoice_symbol)
    if seller_tax and number and symbol and invoice.invoice_date:
        query = (select(Invoice)
                 .join(InvoiceFile, Invoice.file_id == InvoiceFile.id)
                 .where(Invoice.id != invoice.id,
                        Invoice.invoice_date == invoice.invoice_date,
                        Invoice.invoice_number.is_not(None),
                        Invoice.invoice_symbol.is_not(None),
                        Invoice.seller_tax_code.is_not(None)))
        if own_only:
            query = query.where(InvoiceFile.uploaded_by == owner_id)
        candidates = db.scalars(query).all()
        # Normalize codes and display spacing for compatibility with scanned docs.
        same = [
            other for other in candidates
            if _tax(other.seller_tax_code) == seller_tax
            and _clean(other.invoice_number) == number
            and _clean(other.invoice_symbol) == symbol
        ]
        if same:
            flags.append(_risk(
                "DUPLICATE-INVOICE",
                "Có hóa đơn khác trùng MST người bán, ký hiệu, số và ngày lập; cần đối chiếu chứng từ.",
                duplicates=len(same),
            ))

    buyer_tax = _tax(invoice.buyer_tax_code)
    if (seller_tax and buyer_tax and seller_tax == buyer_tax
            and invoice.seller_name and invoice.buyer_name
            and _ascii(invoice.seller_name) != _ascii(invoice.buyer_name)):
        flags.append(_risk(
            "SAME-TAX-CODE",
            "MST người mua và người bán trùng nhau nhưng tên đơn vị khác; cần đối chiếu bản gốc.",
        ))

    # Missing optional fields trigger REVIEW advice, not statutory invalidity.
    if invoice.document_type == "einvoice":
        missing = []
        if invoice.subtotal is None:
            missing.append("tiền trước thuế")
        if invoice.vat_amount is None:
            missing.append("tiền VAT")
        if missing:
            flags.append(_risk(
                "INCOMPLETE-FINANCIAL",
                "Chưa trích xuất: " + ", ".join(missing) + "; cần đối chiếu chứng từ gốc.",
            ))
        if not invoice.invoice_symbol:
            flags.append(_risk("MISSING-SYMBOL", "Chưa có ký hiệu hóa đơn; cần kiểm tra bản gốc."))

    return {
        "invoice_id": invoice.id,
        "assessment_type": "advisory",
        "scope": "own_invoices" if own_only else "organization",
        "has_flags": bool(flags),
        "flags": flags,
        "confidence_note": "Confidence trong bản MVP là tỷ lệ trường có dữ liệu, không phải độ chính xác OCR.",
        "tax_lookup_performed": False,
        "review_note": "Cảnh báo rủi ro không phải xác nhận hóa đơn giả, trùng thanh toán hoặc kết luận thuế.",
    }
