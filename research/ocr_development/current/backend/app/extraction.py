"""FINTECH OCR: OCR v5, conservative invoice field extraction and financial checks.

Compatible public functions: money, text_from_file, classify, extract_fields, validate.
OCR output is a *draft* and must be reviewed before approval/tax lookup.
No external AI/API and no changes to the database are performed here.
"""
from __future__ import annotations

import io
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from urllib.parse import urlparse

import pytesseract
from .invoice_financials import (party_name_allowed, amount_literal, item_description_boundary, amount_in_words,
                                financial_heading, current_document_text, document_semantics,
                                party_name_literal, REFERENCE_ANCHOR, correction_statement,
                                SELLER_NAME_LABEL, BUYER_NAME_LABEL, party_section_role)

MAX_OCR_PAGES = 12
MAX_OCR_TEXT_CHARS = 60_000
_coverage_observations = ContextVar('ocr_extraction_coverage', default=None)


@contextmanager
def capture_extraction_coverage():
    observations = []
    token = _coverage_observations.set(observations)
    try:
        yield observations
    finally:
        _coverage_observations.reset(token)


def _coverage_finding(code, reason, **details):
    observations = _coverage_observations.get()
    if observations is not None:
        finding = {'code': code, 'reason': reason, 'incomplete': True,
                   'requires_review': True, **details}
        if finding not in observations:
            observations.append(finding)


def _bounded_ocr_text(text, stage):
    if len(text) <= MAX_OCR_TEXT_CHARS:
        return text
    # Never present a cut-off identifier/amount as if it were a complete token.
    boundary = max(0, text.rfind('\n', 0, MAX_OCR_TEXT_CHARS + 1))
    retained = text[:boundary]
    _coverage_finding('OCR_TEXT_LIMIT_REACHED',
        f'Văn bản OCR vượt {MAX_OCR_TEXT_CHARS} ký tự; chỉ giữ {len(retained)} ký tự trên các dòng hoàn chỉnh. Các trường hoặc dòng hàng phía sau có thể chưa được trích xuất.',
        stage=stage, text_limit=MAX_OCR_TEXT_CHARS, recognized_characters=len(text), retained_characters=len(retained))
    return retained

# Project source may live on D: even when Tesseract executable lives on C:.
_tesseract_cmd = os.environ.get("TESSERACT_CMD", "").strip()
if not _tesseract_cmd and os.name == "nt":
    for _candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(_candidate).is_file():
            _tesseract_cmd = _candidate
            break
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd


def _decimal_money(raw):
    """Parse printed money without losing cents through a binary float."""
    if raw is None or str(raw).strip() == "":
        return None
    s = re.sub(r'^\s*(?:VND|VNĐ|₫)\s*|\s*(?:VND|VNĐ|dong|đ|d|₫)\s*$', '', str(raw), flags=re.I).strip()
    if re.search(r'\s', s):
        if not re.fullmatch(r'-?\d{1,3}(?:\s+\d{3})+(?:[.,]\d{1,2})?', s):
            return None
        s = ''.join(s.split())
    if not re.fullmatch(r'-?\d+(?:[.,]\d+)*', s):
        return None
    if not s or s in ("-", ".", ","):
        return None
    if "," in s and "." in s:
        decimal_sep = ',' if s.rfind(',') > s.rfind('.') else '.'
        grouped, fraction = s.rsplit(decimal_sep, 1)
        thousands_sep = '.' if decimal_sep == ',' else ','
        if not re.fullmatch(rf'-?\d{{1,3}}(?:{re.escape(thousands_sep)}\d{{3}})+', grouped) or not 1 <= len(fraction) <= 2:
            return None
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(".") > 1:
        if not re.fullmatch(r'-?\d{1,3}(?:\.\d{3})+', s):
            return None
        s = s.replace(".", "")
    elif s.count(",") > 1:
        if not re.fullmatch(r'-?\d{1,3}(?:,\d{3})+', s):
            return None
        s = s.replace(",", "")
    elif "," in s:
        a, b = s.rsplit(",", 1)
        s = (a + b) if len(b) == 3 else (a + "." + b)
    elif "." in s:
        a, b = s.rsplit(".", 1)
        s = (a + b) if len(b) == 3 else s
    try:
        value = Decimal(s)
        if not value.is_finite() or value < 0 or value > Decimal("9999999999999999"):
            return None
        return value
    except (InvalidOperation, ValueError, OverflowError):
        return None


def money(raw):
    """Compatibility entry point for XML/legacy callers requiring float."""
    value = _decimal_money(raw)
    return round(float(value), 2) if value is not None else None


def _xml_decimal(raw, tag, *, quantity=False):
    """XML decimal literals use '.' as a decimal point, not VND grouping.

    Keep missing/zero distinct and decline unsupported database precision;
    never round source values silently or pass money through binary floats.
    """
    if raw is None or not str(raw).strip():
        return None
    literal = str(raw).strip()
    if len(literal) > 100:
        return None
    try:
        value = (Decimal(literal) if re.fullmatch(r'\+?\d+(?:\.\d+)?', literal)
                 else _spatial_quantity(literal) if quantity else _decimal_money(literal))
        limit = Decimal('999999999999999.999') if quantity else Decimal('9999999999999999.99')
        quantum = Decimal('.001') if quantity else Decimal('.01')
        if value is None or not value.is_finite() or value < 0 or value > limit:
            return None
        if value != value.quantize(quantum):
            _coverage_finding('XML_NUMERIC_PRECISION_UNSUPPORTED',
                              'Giá trị XML vượt độ chính xác cột hiện có; giữ nguồn, không làm tròn hoặc tự điền.', field=tag)
            return None
        return value
    except (InvalidOperation, ValueError, TypeError):
        return None


def _plain(s: str) -> str:
    # PyMuPDF can expose visible PDF hyphens as U+00AD soft hyphens; keep the
    # separator recognizable so invoice identifiers such as OCR-2026-001 parse.
    s = unicodedata.normalize("NFKD", s.replace("\u00ad", "-").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _xml_local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(data: bytes):
    """Parse XML while tolerating a UTF-8 BOM/blank lines before its declaration.

    Some desktop editors prepend a newline before ``<?xml ...?>``. XML requires
    the declaration at byte zero, but trimming only a leading BOM/whitespace is
    safe and keeps the uploaded source bytes untouched on disk.
    """
    normalized = data.removeprefix(b"\xef\xbb\xbf").lstrip(b" \t\r\n")
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", normalized, re.I):
        raise ValueError("XML có DTD/entity không được chấp nhận")
    return ET.fromstring(normalized)


def _xml_has_invoice_structure(root) -> bool:
    """Recognize the HDon/DLHDon e-invoice structure, not the .xml suffix."""
    if _xml_local_tag(root.tag).lower() != "hdon":
        return False
    tags = {_xml_local_tag(node.tag).lower() for node in root.iter()}
    has_header = "dlhdon" in tags and bool(tags & {"shdon", "nlap", "khhdon"})
    has_party = bool(tags & {"nban", "nmua"})
    has_financial_or_lines = bool(tags & {
        "tgtttbso", "tgtcthue", "tgttthue", "dshhdvu", "hhdvu",
    })
    return has_header and has_party and has_financial_or_lines


def _xml_text(data: bytes) -> str:
    # ElementTree does not fetch external entities; reject DTD/ENTITY explicitly.
    root = _parse_xml(data)

    def node_text(parent, tag):
        names = (tag,) if isinstance(tag, str) else tag
        wanted = {name.lower() for name in names}
        for node in parent.iter():
            if _xml_local_tag(node.tag).lower() in wanted and node.text and node.text.strip():
                return node.text.strip()
        return None

    lines = []
    number = node_text(root, "SHDon")
    issued = node_text(root, "NLap")
    total = node_text(root, "TgTTTBSo")
    symbol = node_text(root, "KHHDon")
    currency = node_text(root, "DVTTe")
    if currency and re.fullmatch(r'[A-Za-z]{3}',currency.strip()):
        lines.append('Đơn vị tiền tệ: '+currency.strip().upper())
    # Providers commonly emit both spellings; keep aliases explicit rather
    # than trying to infer subtotal from line items or total arithmetic.
    subtotal = node_text(root, ("TgTCThue", "TgTCTHue"))
    vat_amount = node_text(root, "TgTThue")
    if symbol:
        lines.append("Ký hiệu: " + symbol)
    if number:
        lines.append("Số hóa đơn: " + number)
    if issued:
        try:
            issued = datetime.fromisoformat(issued.replace('Z', '+00:00')).date().isoformat()
        except ValueError:
            pass  # Preserve an unsupported literal for review, not a guessed date.
        lines.append("Ngày: " + issued)
    for seller_node in root.iter():
        if _xml_local_tag(seller_node.tag).lower() == "nban":
            seller_name = node_text(seller_node, "Ten")
            seller_tax = node_text(seller_node, "MST")
            if seller_name:
                lines.append("Đơn vị bán hàng: " + seller_name)
            if seller_tax:
                lines.append("Mã số thuế người bán: " + seller_tax)
            break
    for buyer_node in root.iter():
        if _xml_local_tag(buyer_node.tag).lower() == "nmua":
            buyer_name = node_text(buyer_node, "Ten")
            buyer_tax = node_text(buyer_node, "MST")
            if buyer_name:
                lines.append("Đơn vị mua hàng: " + buyer_name)
            if buyer_tax:
                lines.append("Mã số thuế người mua: " + buyer_tax)
            break
    for label, tag, literal in (("Cộng tiền hàng", 'TgTCThue', subtotal),
                                 ("Tiền thuế GTGT", 'TgTThue', vat_amount),
                                 ("Tổng tiền thanh toán", 'TgTTTBSo', total)):
        number = _xml_decimal(literal, tag)
        if number is not None:
            lines.append(label + ': ' + format(number, '.2f'))
    if _xml_has_invoice_structure(root):
        lines.append("Cấu trúc hóa đơn điện tử XML: HDon/DLHDon")
    for node in root.iter():
        if _xml_local_tag(node.tag).lower() == 'thhdvu' and node.text and node.text.strip():
            lines.append(node.text.strip())  # Keep correction descriptions as independent source rows.
    # Keep other human-readable text for audit/troubleshooting.
    content = " ".join(t.strip() for t in root.itertext() if t and t.strip())
    raw = "\n".join(lines) + "\n" + content
    if len(raw) > 60000:
        _coverage_finding('DOCUMENT_TEXT_LIMIT_REACHED',
                          'Văn bản XML vượt giới hạn lưu bằng chứng; giữ tệp nguồn và các dòng XML đã đọc, cần xem xét.')
    return raw[:60000]


def _ocr_table_cells(line: str) -> list[str] | None:
    if "|" in line:
        return [cell.strip() for cell in line.split("|")]
    if "\t" in line:
        return [cell.strip() for cell in line.split("\t")]
    return None


def _line_item_header(cells: list[str]) -> dict[str, int] | None:
    labels = [_plain(cell).strip(" :#.;") for cell in cells]

    def find_index(terms: tuple[str, ...]) -> int | None:
        return next((i for i, label in enumerate(labels) if any(term in label for term in terms)), None)

    description = find_index(("ten hang hoa", "ten hang", "dien giai", "description", "item name", "product"))
    amount = next((i for i, label in enumerate(labels)
                   if re.search(r'\b(?:thanh tien|line total|net amount)\b', label)
                   or re.fullmatch(r'amount(?:\s*\([^)]*\))?', label)), None)
    if description is None or amount is None or description == amount:
        return None
    return {
        "description": description,
        "amount": amount,
        "ordinal": next((i for i, label in enumerate(labels) if re.fullmatch(r'stt|no', label)), None),
        "unit": next((i for i, label in enumerate(labels) if re.fullmatch(r'unit|uom', label)),
                     find_index(("don vi tinh", "dvt", "unit of measure"))),
        "quantity": find_index(("so luong", "quantity", "qty", "sl")),
        "unit_price": find_index(("don gia", "unit price", "price")),
    }


def _is_summary_or_party_line(text: str) -> bool:
    plain = _plain(text)
    return bool(re.search(
        r"\b(?:subtotal|grand total|total amount|amount due|cong tien hang|tong tien|tong cong|"
        r"tien thue|thue suat|vat amount|tax amount|ma so thue|seller|supplier|buyer|"
        r"don vi ban hang|ten don vi)\b",
        plain,
    ) or re.match(r'^(?:chiet khau|giam gia|discount|phu phi|phu thu|surcharge|service charge)\b', plain))


def _is_item_table_boundary(text: str) -> bool:
    """Recognize summary/metadata that closes an OCR item-table region."""
    if _is_summary_or_party_line(text):
        return True
    plain = _plain(text)
    return bool(re.match(
        r"^\s*(?:ky\s+hieu|so\s+hoa\s+don|invoice\s+(?:no|number|symbol)|"
        r"dien\s+thoai|phone|tel|so\s+tai\s+khoan|tai\s+khoan|bank\s+account|"
        r"dia\s+chi|address|website|email|ghi\s+chu|phuong\s+thuc\s+thanh\s+toan)\b\s*[:;]",
        plain,
    ))


def _is_unstructured_item_header(line: str) -> bool:
    """Find a table header in a plain Tesseract text pass with lost cell borders."""
    plain = _plain(line)
    has_position = bool(re.search(r"\bstt\b|\bno\s*\.?\b", plain))
    has_description = bool(re.search(
        r"\b(?:ten\s+hang(?:\s+hoa)?|ten\s+san\s+pham|hang\s+hoa|"
        r"dien\s+giai|description|item\s+name|product|goods|service)\b", plain
    ))
    has_amount = bool(re.search(r"\b(?:thanh\s+tien|line\s+total|amount)\b", plain))
    return has_position and has_description and has_amount


def _parse_unstructured_item_row(line: str, line_no: int) -> dict | None:
    """Parse a numbered row only after a table header established its context.

    Unseparated 4-digit identifiers (e.g. laptop model numbers) are not treated
    as money. Unit/quantity are read only when a unit token visibly separates
    them from the description; otherwise they remain unknown.
    """
    row = re.match(r"^\s*\d{1,3}[.)]?\s+(.+?)\s*$", line)
    if not row:
        return None
    body = row.group(1).strip()
    amount_pattern = re.compile(
        r"(?<!\d)(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{5,}(?:[.,]\d{1,2})?)(?!\d)"
    )
    amounts = list(amount_pattern.finditer(body))
    if not amounts:
        return None
    amount = _decimal_money(amounts[-1].group(0))
    if amount is None:
        return None

    unit_price = _decimal_money(amounts[-2].group(0)) if len(amounts) >= 2 else None
    description_end = amounts[-2].start() if len(amounts) >= 2 else amounts[-1].start()
    prefix = body[:description_end].rstrip()
    unit = quantity = None
    if len(amounts) >= 2:
        # Units provide a reliable boundary between model/name digits and qty.
        suffix = re.match(
            r"(?s)^(?P<description>.+?)\s+(?P<unit>[^\W\d_][\w./-]{0,19})\s+"
            r"(?P<quantity>\d+(?:[.,]\d+)?)\s*$",
            prefix,
            re.UNICODE,
        )
        if suffix:
            prefix = suffix.group("description").rstrip()
            unit = suffix.group("unit")[:30]
            quantity = _spatial_quantity(suffix.group("quantity"))

    description = " ".join(prefix.split()).strip(" \t:;.,-")
    if len(re.sub(r"[^a-z]", "", _plain(description))) < 3:
        return None
    return {
        "line_no": line_no,
        "description": description[:2000],
        "unit": unit,
        "quantity": quantity,
        "unit_price": unit_price,
        "amount": Decimal(str(amount)),
    }


def _extract_unstructured_table_items(raw_text: str) -> list[dict]:
    """Read plain OCR rows only within an explicitly headed item table."""
    lines = raw_text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if _is_unstructured_item_header(line)), None)
    if header_index is None:
        return []

    row_groups = []
    current = None
    for line in lines[header_index + 1:]:
        cleaned = " ".join(line.split()).strip()
        if not cleaned:
            continue
        if _is_item_table_boundary(cleaned):
            break
        if item_description_boundary(cleaned):
            if current:
                row_groups.append(current)
                current = None
            continue
        numbered = re.match(r"^\s*\d{1,3}[.)]?\s+", cleaned)
        if numbered:
            if current:
                row_groups.append(current)
            current = cleaned
        elif current:
            # OCR may wrap a long product name onto the next physical text row.
            # It remains attached only while we are inside the headed table.
            current += " " + cleaned
    if current:
        row_groups.append(current)

    items = []
    for row in row_groups:
        item = _parse_unstructured_item_row(row, len(items) + 1)
        if item:
            items.append(item)
    return items


def _spatial_lines(words) -> list[list[tuple[float, float, float, float, str]]]:
    """Cluster OCR/PDF words into visual rows using their bounding boxes."""
    ordered = sorted(words, key=lambda word: (word[1], word[0]))
    rows: list[list[tuple[float, float, float, float, str]]] = []
    for word in ordered:
        if not word[4] or not str(word[4]).strip():
            continue
        if rows and abs(word[1] - sum(item[1] for item in rows[-1]) / len(rows[-1])) <= max(2.5, (word[3] - word[1]) * 0.32):
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda word: word[0]) for row in rows]


def _spatial_header_center(row, patterns: tuple[str, ...]) -> float | None:
    ordered = sorted(row, key=lambda word: word[0])
    matches = []
    for start in range(len(ordered)):
        for width in range(1, min(7, len(ordered) - start) + 1):
            window = ordered[start:start + width]
            phrase = " ".join(_plain(str(word[4])) for word in window)
            if any(re.search(pattern, phrase) for pattern in patterns):
                matches.append((width, start, window))
    if not matches:
        return None
    # The shortest matching span avoids absorbing preceding labels such as
    # "STT" when locating the adjacent "Tên hàng" column.
    _width, _start, match_words = min(matches, key=lambda entry: (entry[0], entry[1]))
    return (min(word[0] for word in match_words) + max(word[2] for word in match_words)) / 2


def _spatial_money(cell: str) -> Decimal | None:
    """Read a whole table cell, rejecting formulas and OCR-split digit groups."""
    value = " ".join((cell or "").split()).strip()
    if re.fullmatch(r"(?:\d{1,3}(?:[.,]\d{3})+|\d{4,}|0)(?:[.,]\d{1,2})?", value):
        return _decimal_money(value)
    return None


def _spatial_quantity(cell: str) -> Decimal | None:
    value = " ".join((cell or "").split()).strip()
    if re.fullmatch(r"\d{1,8}(?:[.,]\d{1,4})?", value):
        # Quantity separators are decimal marks, not VND thousands groups.
        return Decimal(value.replace(',', '.'))
    return None


def _extract_spatial_table_items(words) -> list[dict]:
    """Read a headed table from PDF text or Tesseract word-box coordinates."""
    rows = _spatial_lines(words)
    header = None
    for index, row in enumerate(rows):
        joined = _plain(" ".join(str(word[4]) for word in row))
        if not (re.search(r"\b(?:ten\s+hang|description|goods|product)\b", joined)
                and re.search(r"\b(?:thanh\s+tien|amount|line\s+total)\b", joined)):
            continue
        unit_labels = [word for n, word in enumerate(row)
                       if not re.fullmatch(r'unit\s+price', _plain(str(word[4])))
                       and not (_plain(str(word[4])) == 'unit' and n + 1 < len(row)
                                and _plain(str(row[n + 1][4])) == 'price')]
        amount_labels = [word for n, word in enumerate(row)
                         if not re.fullmatch(r'(?:tax|vat)\s+amount', _plain(str(word[4])))
                         and not (_plain(str(word[4])) == 'amount' and n > 0
                                  and _plain(str(row[n - 1][4])) in ('tax', 'vat'))]
        centers = {
            "row": _spatial_header_center(row, (r"\bstt\b", r"\bno\b")),
            "description": _spatial_header_center(row, (r"ten\s+hang", r"description", r"goods", r"product")),
            "unit": _spatial_header_center(unit_labels, (r"don\s+vi\s+tinh", r"\bdvt\b", r"\buom\b", r"\bunit\b")),
            "quantity": _spatial_header_center(row, (r"so\s+luong", r"\bquantity\b", r"\bqty\b", r"\bsl\b")),
            "unit_price": _spatial_header_center(row, (r"don\s+gia", r"unit\s+price", r"\bprice\b")),
            "amount": _spatial_header_center(amount_labels, (r"thanh\s+tien", r"line\s+total", r"\bamount\b")),
        }
        if centers["description"] is not None and centers["amount"] is not None:
            header = (index, centers)
            break
    if header is None:
        return []

    header_index, centers = header
    output = []
    pending = None

    def cell_text(row, kind):
        center = centers.get(kind)
        if center is None:
            return ""
        previous = [v for v in centers.values() if v is not None and v < center]
        following = [v for v in centers.values() if v is not None and v > center]
        left = (max(previous) + center) / 2 if previous else float("-inf")
        right = (min(following) + center) / 2 if following else float("inf")
        if kind == 'description' and previous and max(previous) == centers.get('row'):
            left = centers['row'] + 5
        selected = [w for w in row if left <= (w[0] + w[2]) / 2 < right]
        return " ".join(str(word[4]) for word in selected).strip()

    def flush():
        nonlocal pending
        if pending and pending["description"].strip() and pending["amount"] is not None:
            output.append({
                "line_no": len(output) + 1,
                "description": " ".join(pending["description"].split())[:2000],
                "unit": pending["unit"] or None,
                "quantity": pending["quantity"],
                "unit_price": pending["unit_price"],
                "amount": Decimal(str(pending["amount"])),
            })
        pending = None

    for row_index, row in enumerate(rows[header_index + 1:], header_index + 1):
        line = " ".join(str(word[4]) for word in row)
        if item_description_boundary(line) and not _is_summary_or_party_line(line):
            flush()
            continue
        if _is_summary_or_party_line(line):
            flush()
            terminal = re.search(r'\b(?:tong (?:cong )?(?:tien )?(?:phai )?thanh toan|grand total|amount due|'
                                 r'so tien (?:viet )?bang chu|nguoi mua|nguoi ban|buyer|seller|ma so thue)\b', _plain(line))
            later_product = any((centers['row'] is None or re.fullmatch(r'\d{1,6}', cell_text(later, 'row')))
                                and _spatial_money(cell_text(later, 'amount')) is not None
                                and re.search(r'[^\W\d_]{2}', cell_text(later, 'description'))
                                and not _is_summary_or_party_line(' '.join(str(word[4]) for word in later))
                                for later in rows[row_index + 1:])
            if terminal or not later_product:
                break
            continue
        row_number = cell_text(row, "row")
        numbered = bool(re.fullmatch(r"\d{1,6}", row_number.strip()))
        unnumbered = (centers['row'] is None and _spatial_money(cell_text(row, 'amount')) is not None
                      and re.search(r'[^\W\d_]{2}', cell_text(row, 'description')))
        if numbered or unnumbered:
            flush()
            pending = {
                "description": cell_text(row, "description"),
                "unit": cell_text(row, "unit"),
                "quantity": _spatial_quantity(cell_text(row, "quantity")),
                "unit_price": _spatial_money(cell_text(row, "unit_price")),
                "amount": _spatial_money(cell_text(row, "amount")),
            }
        elif pending:
            continuation = cell_text(row, "description")
            if continuation and not item_description_boundary(continuation):
                pending["description"] = (pending["description"] + " " + continuation).strip()
            for kind in ("unit", "quantity", "unit_price", "amount"):
                if pending[kind] in (None, ""):
                    value = cell_text(row, kind)
                    if kind == "unit":
                        pending[kind] = value
                    elif value:
                        pending[kind] = _spatial_quantity(value) if kind == "quantity" else _spatial_money(value)
    flush()
    return output


def _extract_staggered_table_items(words, header_words=()) -> list[dict]:
    """Recover staggered headers and lines with an unreadable ordinal column."""
    if not words:
        return []
    labels = {
        "description": (r"\b(?:ten\s+hang|dien\s+giai|description|item\s+name|product|goods)\b",),
        "unit": (r"\b(?:don\s+vi\s+tinh|dvt|unit)\b",),
        "quantity": (r"\b(?:so\s*luong|quantity|qty|sl)\b",),
        "unit_price": (r"\b(?:don\s+gia|unit\s+price|price)\b",),
        "amount": (r"\b(?:thanh\s+tien|line\s+total|amount)\b",),
    }
    height = max(1, median(w[3] - w[1] for w in words))
    ordered = sorted(words, key=lambda w: w[1])
    for index, word in enumerate(ordered):
        if not re.search(r"\b(?:ten|dien|description|item|product|goods)\b", _plain(word[4])):
            continue
        # Use a bounded band because centered labels and currency captions
        # often sit on different visual baselines in the same table header.
        top = word[1] - 1.6 * height
        bottom = word[1] + 1.4 * height
        band = [
            w for w in ordered[max(0, index - 80):index + 80]
            if top <= w[1] <= bottom and re.search(r"[a-z]", _plain(w[4]))
            and _plain(w[4]).strip(" ()[]") not in {"vnd", "vnđ", "usd"}
        ]
        centers = {kind: _spatial_header_center(band, patterns) for kind, patterns in labels.items()}
        desc, qty, price, amount = (centers[k] for k in ("description", "quantity", "unit_price", "amount"))
        if None not in (desc, qty, price, amount) and desc < qty < price < amount:
            break
    else:
        return []

    unit = centers["unit"]
    if unit is None:
        # OCR layouts disagree on short labels such as "ĐVT". For the same
        # prepared image, reuse a label from the other pass in this header band.
        unit = _spatial_header_center([w for w in header_words if top <= w[1] <= bottom], labels["unit"])
    if unit is None or not desc < unit < qty:
        unit = None
    desc_right = desc + 0.75 * ((unit if unit is not None else qty) - desc)
    qty_left = (unit + qty) / 2 if unit is not None else desc_right
    price_left, amount_left = (qty + price) / 2, (price + amount) / 2
    ordinal = _spatial_header_center(band, (r"\b(?:stt|no)\b",))
    desc_left = ordinal + (desc - ordinal) * 0.18 if ordinal is not None and ordinal < desc else 0

    def xmid(w):
        return (w[0] + w[2]) / 2

    def ymid(w):
        return (w[1] + w[3]) / 2

    def description(words):
        return " ".join(w[4] for w in sorted(words, key=lambda w: w[0]) if re.search(r"\w", w[4]))

    body = [w for w in ordered if w[1] > bottom]
    # A subtotal can be split across baselines. Detect the label across rows
    # and before analyzing amounts, so summary cells cannot become products.
    rows = _spatial_lines(body)
    for index, row in enumerate(rows):
        row_text = " ".join(w[4] for w in row)
        following = rows[index + 1] if index + 1 < len(rows) else []
        if following and following[0][1] - row[0][1] <= 1.3 * height:
            near_text = row_text + " " + " ".join(w[4] for w in following)
        else:
            near_text = row_text
        if (_is_item_table_boundary(row_text) or _is_summary_or_party_line(near_text)
                or re.search(r"\b(?:tien\s+hang|tong\s+thanh\s+toan|sub\s*total)\b", _plain(row_text))):
            body = [w for w in body if w[1] < row[0][1]]
            break

    result = []
    last_row_y = bottom
    anchors = [w for w in body if xmid(w) >= amount_left and _spatial_money(w[4]) is not None]
    for anchor in anchors:
        y = ymid(anchor)
        if y - last_row_y < height * 0.75:
            continue
        row = [w for w in body if abs(ymid(w) - y) <= 0.76 * height]
        price_words = [w for w in row if price_left <= xmid(w) < amount_left and _spatial_money(w[4]) is not None]
        qty_words = [w for w in row if qty_left <= xmid(w) < price_left and _spatial_quantity(w[4]) is not None]
        if len(price_words) > 1 or len(qty_words) > 1 or not (price_words or qty_words):
            continue
        name_words = [w for w in row if desc_left <= xmid(w) < desc_right]
        name = description(name_words)
        if len(re.sub(r"[^a-z]", "", _plain(name))) < 3 or _is_item_table_boundary(name):
            continue
        unit_text = description([w for w in row if desc_right <= xmid(w) < qty_left])
        # Keep adjacent wrapped name text, stopping before the next amount
        # row. A specifications-only line is retained in raw OCR evidence.
        next_y = min((ymid(w) for w in anchors if ymid(w) > y + height), default=y + 4 * height)
        for continuation in _spatial_lines([
            w for w in body if desc_left <= xmid(w) < desc_right
            and y + 0.76 * height < ymid(w) < min(next_y - height, y + 2.4 * height)
        ]):
            tail = description(continuation)
            if item_description_boundary(tail):
                break
            if tail and not re.match(r"^\S*\d\S*(?:/\S+){2,}", tail) and not _is_item_table_boundary(tail):
                name += " " + tail
        result.append({
            "line_no": len(result) + 1,
            "description": name[:2000],
            "unit": unit_text[:30] or None,
            "quantity": _spatial_quantity(qty_words[0][4]) if qty_words else None,
            "unit_price": _spatial_money(price_words[0][4]) if price_words else None,
            "amount": Decimal(str(_spatial_money(anchor[4]))),
        })
        last_row_y = y
    return result


def _image_spatial_items(image, observed=None, word_filter=None) -> list[dict]:
    boxes = _tesseract_word_boxes(image)
    if observed is not None:
        observed['words'] = boxes
    primary = word_filter(boxes) if word_filter else boxes
    items = _extract_spatial_table_items(primary)
    if items:
        return items
    alternative = _tesseract_word_boxes(image, psm=11)
    items = _extract_staggered_table_items(word_filter(alternative) if word_filter else alternative, primary)
    if items and observed is not None:
        observed['words'] = alternative
    return items


def _extract_spatial_items_from_file(data: bytes, extension: str, page_texts=None) -> list[dict]:
    """Use embedded PDF word boxes or a local Tesseract layout pass as fallback."""
    try:
        if extension == "pdf":
            from .ocr_pdf import extract_pdf
            _raw, _fields, rows, _method, _evidence = extract_pdf(data, page_texts=page_texts)
            return [{key: value for key, value in row.items() if key != 'page'} for row in rows]
        if extension in ("jpg", "jpeg", "png"):
            from PIL import Image
            with Image.open(io.BytesIO(data)) as source:
                return _image_spatial_items(_prepare_image(source))
    except (ImportError, ValueError, RuntimeError, OSError, pytesseract.TesseractError) as exc:
        _coverage_finding('ITEM_LAYOUT_UNAVAILABLE',
            'Không hoàn tất đọc vị trí bảng hàng; kết quả dùng nhánh văn bản dự phòng và có thể thiếu dòng hàng.',
            error_type=type(exc).__name__)
        return []
    return []


def _tesseract_word_boxes(image, psm=6) -> list[tuple[float, float, float, float, str]]:
    data = pytesseract.image_to_data(
        image, lang="vie+eng", config=f"--psm {psm}", output_type=pytesseract.Output.DICT, timeout=35
    )
    return [
        (float(data["left"][i]), float(data["top"][i]),
         float(data["left"][i] + data["width"][i]),
         float(data["top"][i] + data["height"][i]), str(data["text"][i]))
        for i in range(len(data.get("text", []))) if str(data["text"][i]).strip()
    ]


def _ocr_numeric_cell(value: str | None, *, quantity=False) -> Decimal | None:
    if value is None or not value.strip():
        return None
    if quantity:
        return _spatial_quantity(value)
    # The strict parser rejects model/phone labels instead of stripping letters.
    return _decimal_money(value)


def _extract_ocr_line_items(raw_text: str | None) -> list[dict]:
    """Parse only explicitly delimited OCR table rows with a visible amount.

    A recognized table header maps quantity/unit-price columns. Without that
    header, only the unambiguous `row number | description | amount` shape is
    accepted. Free-form OCR text is never treated as a product row.
    """
    if not raw_text:
        return []
    header = None
    result = []
    seen: set[tuple] = set()
    for line in raw_text.splitlines():
        cells = _ocr_table_cells(line)
        if not cells:
            continue
        detected = _line_item_header(cells)
        if detected:
            header = detected
            continue
        ordinal = header.get('ordinal') if header is not None else 0
        if len(cells) < (2 if header is not None else 3):
            continue
        row_no = None
        if ordinal is not None:
            if ordinal >= len(cells) or not re.fullmatch(r'\s*\d{1,6}[.)]?\s*', cells[ordinal]):
                continue
            row_no = int(re.sub(r'\D', '', cells[ordinal]))
            if row_no < 1:
                continue
        if _is_summary_or_party_line(' '.join(cells)):
            continue

        if header is None:
            # This shape exposes a description and a final amount only; do not
            # guess whether any intermediate numeric value is quantity/price.
            if len(cells) != 3:
                continue
            description_index, amount_index = 1, 2
            unit_index = quantity_index = unit_price_index = None
        else:
            description_index = header["description"]
            amount_index = header["amount"]
            unit_index = header["unit"]
            quantity_index = header["quantity"]
            unit_price_index = header["unit_price"]
            if max(description_index, amount_index) >= len(cells):
                continue

        description = " ".join(cells[description_index].split()).strip(" \t:;.,")
        amount = _ocr_numeric_cell(cells[amount_index])
        if not description or amount is None or item_description_boundary(description):
            continue
        if len(description) > 2000:
            continue
        unit = cells[unit_index].strip()[:30] or None if unit_index is not None and unit_index < len(cells) else None
        quantity = _ocr_numeric_cell(cells[quantity_index], quantity=True) if quantity_index is not None and quantity_index < len(cells) else None
        unit_price = _ocr_numeric_cell(cells[unit_price_index]) if unit_price_index is not None and unit_price_index < len(cells) else None
        key = (row_no, description, unit, quantity, unit_price, amount)
        if row_no is not None and key in seen:
            continue
        seen.add(key)
        result.append({
            "line_no": len(result) + 1,
            "description": description,
            "unit": unit,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": Decimal(str(amount)),
        })
    if result:
        return result

    # Tesseract's plain-text page layout drops table borders. Use row numbers
    # only after a product-table header and stop at the first financial or
    # metadata section; never run the broad receipt fallback on VAT invoices.
    table_items = _extract_unstructured_table_items(raw_text)
    if table_items:
        return table_items

    plain = _plain(raw_text)
    explicit_receipt = bool(re.search(
        r"\b(?:pos\s+receipt|cash\s+receipt|retail\s+bill|hoa\s+don\s+ban\s+le|"
        r"receipt\s+(?:no|number)|bill\s+(?:no|number))\b",
        plain,
    ))
    tax_invoice = bool(re.search(
        r"\b(?:hoa\s+don\s+gia\s+tri\s+gia\s+tang|hoa\s+don\s+dien\s+tu|"
        r"vat\s+invoice|tax\s+invoice)\b",
        plain,
    ))
    return _extract_receipt_line_items(raw_text) if explicit_receipt and not tax_invoice else []


def _extract_receipt_line_items(raw_text: str) -> list[dict]:
    """Read conservative thermal-receipt rows with an explicit trailing amount.

    Receipt OCR commonly loses table borders and produces no tabs or pipes.
    This fallback accepts a final VND-like amount only when the remaining text
    looks like a product description. Quantity and unit price remain null
    unless the receipt explicitly shows ``N x name unit-price line-total``.
    """
    amount_pattern = re.compile(
        r"(?<![\d.,])(?:\d{1,3}(?:[.,]\d{3}){1,4}|\d{1,12})(?!\d)"
    )
    excluded = re.compile(
        r"\b(?:subtotal|grand total|total amount|amount due|total|tong|cong tien|"
        r"thue|vat|tax|payment|cash|change|discount|giam gia|phu phi|"
        r"receipt|invoice|hoa don|bill|pos|cashier|date|ngay|time|gio|"
        r"address|dia chi|phone|tel|mst|ma so thue|thank you|cam on|"
        r"invoice number|bill number|receipt number|transaction id|"
        r"lookup|tra cuu|reference|powered by|website|email|hotline|"
        r"amount received|tendered|tien khach dua|tien thua|"
        r"table|ban so|order no|cashier no|customer copy)\b"
    )
    result = []
    for source_line in raw_text.splitlines():
        line = " ".join(source_line.split()).strip()
        if not line or "|" in line or "\t" in source_line:
            continue
        plain = _plain(line)
        if excluded.search(plain) or _is_summary_or_party_line(line):
            continue

        matches = list(amount_pattern.finditer(line))
        if not matches:
            continue
        last = matches[-1]
        amount = _decimal_money(last.group(0))
        if amount is None:
            continue
        description = line[:last.start()].strip(" \t:;.-")
        quantity = unit_price = None

        # Read quantity/price only when all three parts are explicitly printed.
        if len(matches) >= 2:
            item_prefix = line[:matches[-2].start()].strip()
            quantity_before_name = re.match(
                r"^\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(.+?)\s*$", item_prefix, re.I
            )
            quantity_after_name = re.match(
                r"^\s*(.+?)\s+(\d+(?:[.,]\d+)?)\s*[x×]\s*$", item_prefix, re.I
            )
            quantity_match = quantity_before_name or quantity_after_name
            if quantity_match:
                if quantity_before_name:
                    quantity = _spatial_quantity(quantity_match.group(1))
                    description = quantity_match.group(2).strip(" \t:;.-")
                else:
                    quantity = _spatial_quantity(quantity_match.group(2))
                    description = quantity_match.group(1).strip(" \t:;.-")
                unit_price = _decimal_money(matches[-2].group(0))

        if len(re.sub(r"[^a-z]", "", _plain(description))) < 3:
            continue
        # Date-like strings and phone numbers are not product rows.
        if re.search(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b", description):
            continue
        result.append({
            "line_no": len(result) + 1,
            "description": description[:2000],
            "unit": None,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": Decimal(str(amount)),
        })
    return result


def _ocr_item_table_fragment(raw_text: str) -> str:
    """Keep only a clearly headed item table from a secondary OCR layout pass."""
    lines = raw_text.splitlines()
    for index, line in enumerate(lines):
        cells = _ocr_table_cells(line)
        if not ((cells and _line_item_header(cells)) or _is_unstructured_item_header(line)):
            continue
        fragment = [line]
        in_item_rows = False
        for candidate in lines[index + 1:]:
            if not candidate.strip():
                continue
            if _is_item_table_boundary(candidate):
                break
            row_cells = _ocr_table_cells(candidate)
            numbered = bool(
                row_cells and re.fullmatch(r"\s*\d{1,3}[.)]?\s*", row_cells[0])
            ) or bool(re.match(r"^\s*\d{1,3}[.)]?\s+\S", candidate))
            if numbered:
                in_item_rows = True
                fragment.append(candidate)
                continue
            if in_item_rows:
                # Keep wrapped product names and OCR-separated numeric columns
                # only after a numbered row and before the table's summary.
                fragment.append(candidate)
        return "\n".join(fragment)
    return ""


def descriptive_adjustment_items(raw_text):
    context = document_semantics(raw_text or '')
    if context['kind'] != 'adjustment':
        return []
    return [{'line_no': n, 'description': entry['text'][:2000], 'unit': None, 'quantity': None,
             'unit_price': None, 'amount': None, 'page': entry['page'], 'source_line': entry['line']}
            for n, entry in enumerate((entry for entry in context['descriptions'] if entry['non_financial_target']), 1)]


def extract_line_items(data: bytes, ext: str, raw_text: str | None = None) -> list[dict]:
    """Extract XML rows or conservative, explicitly delimited OCR table rows.

    XML continues to use the confirmed HDon/DLHDon/NDHDon/DSHHDVu/HHDVu
    mapping. Raster/PDF text must include a delimited table header (or the
    narrow 3-cell row shape) and an explicit amount; missing values stay None.
    """
    extension = ext.lower().lstrip(".")
    if extension in ("jpg", "jpeg", "png", "pdf"):
        if extension == 'pdf':
            page_texts = raw_text.split('\f') if raw_text is not None else None
            return _extract_spatial_items_from_file(data, extension, page_texts=page_texts)
        text_items = _extract_ocr_line_items(raw_text)
        if text_items:
            return text_items
        description_items = descriptive_adjustment_items(raw_text)
        if description_items:
            return description_items
        spatial_items = _extract_spatial_items_from_file(data, extension)
        if spatial_items:
            return spatial_items
        return _extract_ocr_line_items(raw_text)
    if extension != "xml":
        return []
    root = _parse_xml(data)
    descriptive_document = document_semantics(raw_text if raw_text is not None else _xml_text(data))['kind'] == 'adjustment'

    def local_tag(tag):
        return _xml_local_tag(tag)

    def child_text(parent, tag):
        # Direct children keep similarly named header and nested tax fields
        # from being mistaken for line-item values.
        for node in list(parent):
            if local_tag(node.tag).lower() == tag.lower() and node.text and node.text.strip():
                return node.text.strip()
        return None

    result = []
    for detail in root.iter():
        if local_tag(detail.tag).lower() != "hhdvu":
            continue
        description = child_text(detail, "THHDVu")
        raw_amount = child_text(detail, "ThTien")
        amount = _xml_decimal(raw_amount, 'ThTien')
        # Ordinary rows require an amount; an explicitly observed correction
        # description may stand alone. Never synthesize a line from totals.
        if not description or (amount is None and not (descriptive_document and correction_statement(description))):
            continue
        result.append({
            "line_no": len(result) + 1,
            "description": description[:2000],
            "unit": (child_text(detail, 'DVTinh') or '')[:30] or None,
            "quantity": _xml_decimal(child_text(detail, 'SLuong'), 'SLuong', quantity=True),
            "unit_price": _xml_decimal(child_text(detail, 'DGia'), 'DGia'),
            "amount": amount,
        })
    return result


def _projection_score(image) -> float:
    """Score horizontal text-line alignment for conservative deskewing."""
    from PIL import ImageOps

    gray = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    binary = gray.point(lambda value: 0 if value < 170 else 255)
    row_ink = [binary.crop((0, y, binary.width, y + 1)).histogram()[0] for y in range(binary.height)]
    if not row_ink:
        return 0.0
    mean = sum(row_ink) / len(row_ink)
    # Ignore nearly blank or near-solid images where alignment is not measurable.
    if mean < binary.width * 0.002 or mean > binary.width * 0.65:
        return 0.0
    return sum((count - mean) ** 2 for count in row_ink) / max(mean, 1.0)


def _deskew_small_angle(image):
    """Correct only a measurable, small text skew; leave ambiguous images alone.

    The estimate uses horizontal ink projections on a small grayscale proxy,
    avoiding an additional OCR engine or runtime dependency. It is deliberately
    limited to +/-5 degrees so page orientation remains the OSD pass's job.
    """
    from PIL import Image

    proxy = image.convert("L")
    proxy.thumbnail((700, 700), Image.Resampling.LANCZOS)
    baseline = _projection_score(proxy)
    if baseline <= 0:
        return image
    candidates = []
    for tenth_degrees in range(-50, 51, 5):
        if tenth_degrees == 0:
            continue
        angle = tenth_degrees / 10
        rotated = proxy.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=255)
        candidates.append((_projection_score(rotated), angle))
    if not candidates:
        return image
    best_score, best_angle = max(candidates)
    # Require a clear improvement and non-trivial measured skew to avoid adding
    # artifacts to already aligned photos, tables, or decorative backgrounds.
    if best_score < baseline * 1.06:
        return image
    # Do not cut off edge text/money columns when correcting document skew.
    from math import cos, sin, radians, ceil
    angle = radians(best_angle)
    out_width = ceil(abs(image.width * cos(angle)) + abs(image.height * sin(angle))) + 2
    out_height = ceil(abs(image.height * cos(angle)) + abs(image.width * sin(angle))) + 2
    if out_width * out_height > 30_000_000:
        return image
    return image.rotate(best_angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor="white")


def _prepare_image(image):
    from PIL import Image, ImageOps
    from .ocr_preprocessing import normalize_image, preprocess
    image = normalize_image(image)
    image.load()
    if image.width * image.height > 30_000_000:
        raise ValueError("Ảnh quá lớn để xử lý OCR (trên 30 MP)")
    image, _opencv_observation = preprocess(image)
    # Small screenshots/scans (e.g., 556 x 551) are hard to read at native size.
    # Enlarge but cap pixel count to avoid large memory allocations.
    shortest = min(image.size)
    scale = min(3.0, max(1.0, 1600 / max(1, shortest)))
    if scale > 1.05 and image.width * image.height * scale * scale <= 24_000_000:
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
    # Normalize low-contrast photos/scans before estimating skew. Keep a neutral
    # grayscale image: color is not required by Tesseract for these fields.
    gray = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    gray = _deskew_small_angle(gray)
    return gray.convert("RGB")


def _amount_from_total_row_ocr(fragment: str) -> Decimal | None:
    """Interpret digits seen inside a cropped TOTAL row, not generic page text.

    Thousands separators may be dot/comma; mixed separators are accepted only
    when groups have exactly three digits. This avoids confusing a VAT amount
    with a computed total and never fills a number from words alone.
    """
    return _money_from_numeric_crop(fragment)


def _payable_label_words(row):
    """Match a payment label, not the neighbouring numeric cells or VAT header."""
    label=[w for w in row if not re.fullmatch(r"[\d.,%|()]+", str(w[4]).strip())]
    plain=" ".join(_plain(str(w[4])) for w in label)
    if _financial_row_kind(plain) in ('vat_amount','subtotal'):return []
    tokens=set(re.findall(r"[a-z]+",plain))
    if not ('tong' in tokens or {'cong','tien','thanh','toan'}<=tokens or {'grand','total'}<=tokens or {'total','amount'}<=tokens or {'amount','due'}<=tokens):
        return []
    targets=('tong tien thanh toan','tong cong thanh toan','tong cong tien thanh toan','tong thanh toan','tong tien phai thanh toan','grand total','total amount','amount due')
    candidates=[(SequenceMatcher(None," ".join(_plain(str(w[4])) for w in label[start:start+size]).strip('():;.,'),target).ratio(),start,size)
               for start in range(len(label)) for size in range(2,min(9,len(label)-start+1)) for target in targets]
    score,start,size=max(candidates,default=(0,0,0))
    return label[start:start+size] if score>=.77 else []


def _total_cell_bounds(image,row,label):
    """Use actual table borders or OCR word boxes; never fixed page columns."""
    top=min(w[1] for w in label);bottom=max(w[3] for w in label)
    height=max(9,bottom-top);label_right=max(w[2] for w in label)
    y0,y1=max(0,int(top-height*.25)),min(image.height,int(bottom+height*.2))
    # Long vertical rules survive across neighbouring rows, unlike digit stems.
    try:
        import cv2
        import numpy as np
        band_top=max(0,int(top-height*2));band_bottom=min(image.height,int(bottom+height*2))
        band=np.asarray(image.crop((0,band_top,image.width,band_bottom)).convert('L'))
        binary=cv2.threshold(band,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
        rules=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((max(18,int(band.shape[0]*.65)),1),np.uint8))
        xs=np.where((rules>0).sum(axis=0)>=band.shape[0]*.65)[0]
        groups=[]
        for x in xs:
            if groups and x-groups[-1][-1]<=3:groups[-1].append(int(x))
            else:groups.append([int(x)])
        borders=[sum(g)/len(g) for g in groups]
        if len(borders)>=2:
            left,right=borders[-2:]
            if left>label_right and image.width*.045<=right-left<=image.width*.5:
                return (int(left)+3,y0,min(image.width,int(right)-2),y1)
    except Exception:
        # Optional geometric recovery must never discard the primary OCR text.
        pass
    candidates=[w for w in row if w[0]>label_right and _money_from_numeric_crop(str(w[4])) is not None]
    if not candidates:return None
    word=max(candidates,key=lambda w:w[2]);pad=max(2,int(height*.2))
    return (max(int(label_right)+1,int(word[0])-pad),y0,min(image.width,int(word[2])+pad),y1)


def _recover_total_from_image(image) -> Decimal | None:
    """Recover only from a labelled, spatially bounded cell and two OCR reads.

    Dense invoices can put VAT and payable totals in adjacent columns. The old
    fixed 65%/82% crops mixed these cells and cut the rightmost printed digits.
    Their rejection was safe but prevented a valid total from being extracted.
    """
    from PIL import Image,ImageOps
    had_label=False
    for psm in (11,6):
        if psm==6 and not had_label:break
        try:words=_tesseract_word_boxes(image,psm=psm)
        except (pytesseract.TesseractError,RuntimeError):continue
        findings=set();attempts=0
        for row in _spatial_lines(words):
            label=_payable_label_words(row)
            if not label:continue
            had_label=True
            bounds=_total_cell_bounds(image,row,label)
            if bounds is None:continue
            left,top,right,bottom=bounds
            if right<=left or bottom<=top:continue
            attempts+=1
            crop=ImageOps.autocontrast(image.crop(bounds).convert('L'))
            if crop.width*crop.height<=1_000_000:crop=crop.resize((crop.width*3,crop.height*3),Image.Resampling.LANCZOS)
            crop=ImageOps.expand(crop,border=8,fill='white')
            values=[]
            for mode in (7,13):
                try:
                    literal=pytesseract.image_to_string(crop,lang='eng',config=f'--psm {mode} -c tessedit_char_whitelist=0123456789.,%',timeout=12)
                except (pytesseract.TesseractError,RuntimeError):continue
                value=_amount_from_total_row_ocr(literal)
                if value is not None:values.append(value)
            if len(values)==2 and values[0]==values[1]:findings.add(values[0])
            if attempts>=3:break
        if len(findings)>1:return None
        if len(findings)==1:return next(iter(findings))
    return None


def _money_from_numeric_crop(raw: str) -> Decimal | None:
    """A single amount from a right-hand invoice cell, never a nearby date/code.

    Crop must already be anchored to a labelled financial row. Mixed thousand
    separators are tolerated because Tesseract often confuses dots and commas.
    """
    # These crops use a digits/punctuation OCR whitelist. Parse the complete
    # literal instead of discarding short numbers/zero or stripping decimals.
    # Empty text, partial tokens and multiple different readings stay unknown.
    lines = [line.strip() for line in (raw or '').splitlines() if line.strip()]
    parsed = [_decimal_money(line) for line in lines]
    if not parsed or any(value is None for value in parsed) or len(set(parsed)) != 1:
        return None
    value = parsed[0]
    return value if value <= Decimal('9999999999999') else None


def _financial_row_kind(label: str) -> str | None:
    """Identify labels; don't assume all Vietnamese invoices share a layout."""
    s = re.sub(r"[^a-z0-9 ]", " ", _plain(label))
    s = " ".join(s.split())
    if any(t in s for t in ("tong tien thanh toan", "tong thanh toan", "grand total", "total amount")):
        return "total_amount"
    if any(t in s for t in ("thue suat", "vat rate", "so tien viet bang", "bang chu")):
        return None
    if any(t in s for t in ("tien thue gtgt", "tien thue vat", "vat amount", "tax amount", "tong tien thue")):
        return "vat_amount"
    if any(t in s for t in ("cong tien hang", "tong tien hang", "tien hang truoc thue", "tien truoc thue", "subtotal")):
        return "subtotal"
    # Minor accented OCR mistakes, e.g. 'Công tiễn hing' in the test image.
    for kind, known in (
        ("subtotal", ("cong tien hang", "tong tien hang")),
        ("vat_amount", ("tien thue gtgt",)),
    ):
        if max(SequenceMatcher(None, s, t).ratio() for t in known) >= 0.77:
            return kind
    return None


def _recover_financial_rows_from_image(image, missing: set[str]) -> dict[str, Decimal]:
    """Recover subtotal and VAT from spatially aligned labelled table rows.

    Uses page OCR word coordinates and a *right-side* column, then independently
    reads 3 small crop variants. Requires >=2 matching readings; ambiguous rows
    stay empty. No financial value is inferred from arithmetic alone.
    """
    if not missing:
        return {}
    from PIL import ImageOps
    try:
        data = pytesseract.image_to_data(
            image, lang="vie+eng", config="--psm 11",
            output_type=pytesseract.Output.DICT, timeout=35,
        )
    except (pytesseract.TesseractError, RuntimeError):
        return {}
    groups = {}
    for idx, word in enumerate(data.get("text", [])):
        if not word or not word.strip():
            continue
        key = (data["block_num"][idx], data["par_num"][idx], data["line_num"][idx])
        groups.setdefault(key, []).append(idx)

    findings: dict[str, set[Decimal]] = {}
    for indices in groups.values():
        words = [data["text"][i] for i in indices]
        kind = _financial_row_kind(" ".join(words))
        if kind not in missing:
            continue
        top = min(int(data["top"][i]) for i in indices)
        bottom = max(int(data["top"][i]) + int(data["height"][i]) for i in indices)
        right_of_label = max(int(data["left"][i]) + int(data["width"][i]) for i in indices)
        # This method applies only when labelled totals are in a left-hand
        # column and the values occupy a separate column to the right.
        if right_of_label >= image.width * 0.78:
            continue
        y0, y1 = max(0, top - 5), min(image.height, bottom + 11)
        if y1 - y0 < 12:
            continue
        readings = []
        for left_frac, threshold, psm in ((.84, None, 11), (.84, 160, 7), (.86, 160, 11)):
            x0, x1 = max(int(image.width * left_frac), right_of_label + 12), int(image.width * .935)
            if x1 <= x0 + 30:
                continue
            patch = ImageOps.autocontrast(image.crop((x0, y0, x1, y1)).convert("L"))
            if threshold is not None:
                patch = patch.point(lambda value: 255 if value > threshold else 0)
            try:
                raw_amount = pytesseract.image_to_string(
                    patch, lang="eng",
                    config=f"--psm {psm} -c tessedit_char_whitelist=0123456789.,",
                    timeout=8,
                )
            except (pytesseract.TesseractError, RuntimeError):
                continue
            value = _money_from_numeric_crop(raw_amount)
            if value is not None:
                readings.append(value)
        if readings:
            from collections import Counter
            counter = Counter(readings)
            value, count = counter.most_common(1)[0]
            if count >= 2 and count > sum(n for other, n in counter.items() if other != value):
                findings.setdefault(kind, set()).add(value)
    # A financial label repeated with different accepted amounts is ambiguous.
    return {kind: next(iter(values)) for kind, values in findings.items() if len(values) == 1}


def _consistent_recovered_amounts(existing: dict, recovered: dict[str, Decimal]) -> dict[str, Decimal]:
    """Avoid populating OCR numbers that contradict an already read total.

    Do not manufacture a missing VAT/subtotal using a formula. Arithmetic may
    reject contradictory reads but must never be a source of OCR values.
    """
    selected = {k: v for k, v in recovered.items() if existing.get(k) is None}
    if not selected:
        return {}
    total = existing.get("total_amount")
    subtotal = selected.get("subtotal", existing.get("subtotal"))
    vat = selected.get("vat_amount", existing.get("vat_amount"))
    if total is not None and subtotal is not None and vat is not None:
        if abs(Decimal(str(subtotal)) + Decimal(str(vat)) - Decimal(str(total))) >= Decimal("2"):
            return {}
    return selected


def _ocr_image(image, *, prepared=False) -> str:
    if not prepared:
        image = _prepare_image(image)
    # PSM 11 works well on invoices with mixed column layouts and small labels.
    try:
        text = pytesseract.image_to_string(image, lang="vie+eng", config="--psm 11", timeout=35)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError("Tesseract OCR engine is unavailable") from exc
    def optional_read(raster, stage, *, psm, timeout):
        """A failed enhancement must not erase a usable primary OCR read."""
        try:
            return pytesseract.image_to_string(
                raster, lang="vie+eng", config=f"--psm {psm}", timeout=timeout
            )
        except (pytesseract.TesseractError, RuntimeError, OSError) as exc:
            # No successful text to retain: propagate the OCR failure normally.
            if not any(char.isalnum() for char in text):
                raise
            _coverage_finding(
                'OCR_OPTIONAL_READ_FAILED',
                'Không hoàn tất lượt OCR bổ sung; giữ văn bản đã đọc, cần đối chiếu các trường còn thiếu.',
                stage=stage, error_type=type(exc).__name__,
            )
            return ""

    # Use a second page-layout pass only if the first pass did not identify core fields.
    def core_field_count(raw_text):
        fields = extract_fields(raw_text, "png")
        keys = ["invoice_number", "invoice_date", "seller_name"]
        if fields["document_type"] != "bill":
            keys.append("seller_tax_code")
        return sum(fields.get(key) is not None and fields.get(key) != '' for key in keys)

    core_count = core_field_count(text)
    missing_payment = extract_fields(text, "png").get('total_amount') is None
    if core_count < 3 or missing_payment:
        alternative = optional_read(image, 'page_layout', psm=6, timeout=35)
        other_count = core_field_count(alternative)
        payment_recovered = missing_payment and extract_fields(alternative, "png").get('total_amount') is not None
        if other_count > core_count or (payment_recovered and other_count >= core_count):
            text = alternative
        elif other_count == core_count and len(alternative.strip()) > len(text.strip()) * 1.3:
            text = alternative
            core_count = other_count
        if other_count > core_count:
            core_count = other_count

    # Tesseract's orientation pass is relatively expensive, so run it only
    # when both standard page layouts failed to recover enough identifying data.
    if core_count < 3:
        try:
            osd = pytesseract.image_to_osd(
                image, lang="osd", output_type=pytesseract.Output.DICT, timeout=10
            )
            rotation = int(osd.get("rotate", 0)) % 360
            orientation_conf = float(osd.get("orientation_conf", 0) or 0)
        except (pytesseract.TesseractError, RuntimeError, ValueError, TypeError):
            rotation = 0
            orientation_conf = 0
        if rotation in (90, 180, 270) and orientation_conf >= 1:
            rotated = image.rotate(-rotation, expand=True)
            corrected = optional_read(rotated, 'orientation_readback', psm=11, timeout=35)
            corrected_count = core_field_count(corrected)
            if corrected_count > core_count or (
                corrected_count == core_count
                and len(corrected.strip()) > len(text.strip()) * 1.3
            ):
                image, text, core_count = rotated, corrected, corrected_count
    # In many Vietnamese invoice templates the issued date sits above the
    # seller block; cropping that header reduces interference from the table.
    if extract_fields(text, "png")["invoice_date"] is None and image.height >= 500:
        header = image.crop((
            int(image.width * 0.25), int(image.height * 0.07),
            image.width, int(image.height * 0.23),
        ))
        header_text = optional_read(header, 'date_header', psm=6, timeout=25)
        if _get_date(_lines(header_text)) is not None:
            text = header_text + "\n" + text
    # A targeted lower-page pass helps to recover VAT/total labels embedded
    # inside dense tabular invoice sections; never invent financial numbers.
    fields = extract_fields(text, "png")
    if (fields["total_amount"] is None or fields["vat_rate"] is None) and \
            fields["document_type"] == "einvoice" and image.height >= 500:
        bottom = image.crop((0, int(image.height * 0.46), image.width, int(image.height * 0.79)))
        bottom_text = optional_read(bottom, 'financial_footer', psm=6, timeout=25)
        # Keep only content relevant to the invoice for the extra OCR pass.
        if re.search(r"(?:thue|tong|suat|thanh toan|total)", _plain(bottom_text)):
            text += "\n" + bottom_text
    # When the table is unreadable in a full-page pass, only recover a
    # TOTAL value if a labelled row is found and two crops agree.
    if extract_fields(text, "png")["total_amount"] is None:
        recovered_total = _recover_total_from_image(image)
        if recovered_total is not None:
            text += f"\nTổng tiền thanh toán: {recovered_total:,}".replace(",", ".")
    fields = extract_fields(text, "png")
    missing = {k for k in ("subtotal", "vat_amount") if fields[k] is None}
    if missing and fields["document_type"] == "einvoice":
        amounts = _recover_financial_rows_from_image(image, missing)
        amounts = _consistent_recovered_amounts(fields, amounts)
        labels = {"subtotal": "Cộng tiền hàng", "vat_amount": "Tiền thuế GTGT"}
        for key, value in amounts.items():
            # Append labelled OCR evidence for the existing extract_fields parser.
            text += f"\n{labels[key]}: {value}"
    # Sparse PSM 11 can split a dense multi-row table into disconnected blocks.
    # Retry only when a recognizable table header exists but no safe line row
    # was parsed; append only the alternative table fragment, never its totals.
    has_item_header = any(
        (cells := _ocr_table_cells(line)) and _line_item_header(cells)
        for line in text.splitlines()
    ) or any(_is_unstructured_item_header(line) for line in text.splitlines())
    # Sparse PSM 11 frequently loses the complete table header. Retry the
    # page for any likely tax invoice with no safe rows; the secondary pass is
    # still accepted only when it contains an explicit table header and row.
    if (has_item_header or classify("png", text) == "einvoice") and not _extract_ocr_line_items(text):
        table_pass = optional_read(image, 'item_table', psm=6, timeout=35)
        fragment = _ocr_item_table_fragment(table_pass) if table_pass else ""
        if fragment and _extract_ocr_line_items(fragment):
            text += "\n" + fragment
    return _bounded_ocr_text(_reread_vietnamese_seller(image, text), 'image_ocr')


def _reread_vietnamese_seller(image, text: str) -> str:
    """Recover accents from the seller's printed line, without guessing letters."""
    from PIL import ImageOps

    seller, tax = _seller_and_tax(_lines(text))
    if not seller or not tax or not seller.isascii() or not re.match(
        r"^(?:cong ty|doanh nghiep|ho kinh doanh|chi nhanh)\b", _plain(seller)
    ):
        return text
    expected = _plain(seller)
    try:
        boxes = _tesseract_word_boxes(image.crop((0, 0, image.width, image.height // 2)), psm=11)
        # Use the original upper half for coordinates. Split off neighboring
        # metadata on the same baseline by matching the exact words of the name.
        count = len(expected.split())
        for row in _spatial_lines(boxes):
            for start in range(len(row) - count + 1):
                name = row[start:start + count]
                if _plain(" ".join(w[4] for w in name)) != expected:
                    continue
                height = median(w[3] - w[1] for w in name)
                pad = max(2, int(height * 0.35))
                crop = image.crop((
                    max(0, int(min(w[0] for w in name)) - pad),
                    max(0, int(min(w[1] for w in name)) - pad),
                    min(image.width, int(max(w[2] for w in name)) + pad),
                    min(image.height, int(max(w[3] for w in name)) + pad),
                ))
                reread = pytesseract.image_to_string(
                    ImageOps.expand(crop, border=pad, fill="white"),
                    lang="vie+eng", config="--psm 7", timeout=10,
                ).strip()
                if _plain(reread) == expected:
                    return text.replace(seller, reread, 1)
    except (pytesseract.TesseractError, OSError, RuntimeError):
        pass
    return text


def text_from_file(data: bytes, ext: str) -> tuple[str, str]:
    """Return (raw_text, method); raise on OCR failure instead of silently returning ''."""
    ext = ext.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext == "xml":
        return _xml_text(data), "xml"
    if ext == "pdf":
        from .ocr_pdf import extract_pdf
        raw, _fields, _items, method, _evidence = extract_pdf(data, include_items=False)
        return raw, method
    if ext in ("jpg", "png"):
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            return _ocr_image(image), "image-ocr"
    raise ValueError("Định dạng không được hỗ trợ: " + ext)


def classify(ext: str, text: str) -> str:
    low = _plain(text)
    extension = ext.lower().lstrip(".")
    if extension == "xml":
        return "einvoice" if "cau truc hoa don dien tu xml" in low else "unknown"
    if any(x in low for x in (
        "hoa don gia tri gia tang", "hoa don dien tu", "hoa don dieu chinh", "hoa don thay the", "vat invoice", "tax invoice"
    )):
        return "einvoice"
    if re.search(
        r"\b(?:hoa don ban hang|hoa don ban le|phieu thu|phieu thanh toan|receipt|cash receipt|"
        r"retail bill|bill|receipt no|receipt number|pos receipt)\b",
        low,
    ) or re.search(r"\bpos\b", low):
        return "bill"
    # Some e-invoices lose the prominent title in OCR. Classify only when an
    # explicit tax identifier, invoice number, issue date, and tax evidence
    # independently support an electronic/tax invoice; a file extension or a
    # lone tax code is never sufficient.
    lines = _lines(text)
    has_tax_identifier = bool(re.search(
        r"\b(?:ma\s+so\s+thue|mst|tax\s*code)\s*[:;]?\s*\d{10}(?:-?\d{3})?\b", low
    ))
    has_invoice_number = _invoice_number(lines) is not None
    has_issue_date = _get_date(lines) is not None
    has_tax_evidence = bool(re.search(
        r"\b(?:thue\s+(?:gtgt|vat)|vat\s+(?:amount|rate)|tax\s+invoice|invoice\s+symbol)\b", low
    ))
    if has_tax_identifier and has_invoice_number and has_issue_date and has_tax_evidence:
        return "einvoice"
    # Borderless thermal receipts often omit a type heading. Require multiple
    # independent receipt signals, including an explicit total and item rows.
    has_total = bool(re.search(r"\b(?:tong cong|tong tien|total|amount due)\b", low))
    has_payment = bool(re.search(r"\b(?:cash|tien mat|payment|thanh toan|change|tien thua)\b", low))
    has_items = bool(_extract_ocr_line_items(text))
    if has_total and has_payment and has_items:
        return "bill"
    return "unknown"


def _lines(raw: str):
    # Keep original and accent-insensitive forms side by side.
    lines = [" ".join(unicodedata.normalize('NFC', line).split()) for line in raw.splitlines() if line.strip()]
    return [(s, _plain(s)) for s in lines]


def _header_date_literals(text):
    """Unlabelled dates only on an independently labelled invoice-ID row."""
    plain = _plain(text)
    if REFERENCE_ANCHOR.search(plain) or correction_statement(text):
        return []
    if (not re.search(r'\b(?:so hoa don|hoa don so|invoice (?:no\.?|number))\b', plain)
            or not re.search(r'\b(?:ky hieu|invoice series|series|serial)\b', plain)
            or re.search(r'\b(?:ngay (?:thanh toan|dat hang|giao hang|ky|sinh|het han)|payment date|order date|delivery date|due date|signed)\b', plain)):
        return []
    observed = []
    for match in re.finditer(r'(?<!\S)(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{4})(?=\s|$|[|;,])', text):
        before = _plain(text[:match.start()])
        if re.search(r'\b(?:so hoa don|hoa don so|invoice (?:no\.?|number)|ky hieu(?: hoa don)?|invoice series|series|serial)\s*[:#]?\s*$', before):
            continue  # A date-shaped invoice ID/series is not another field.
        parts = re.split(r'[/.-]', re.sub(r'\s+', '', match[0]))
        year, month, day = parts if len(parts[0]) == 4 else parts[::-1]
        try:
            value = date(int(year), int(month), int(day))
        except ValueError:
            continue
        observed.append((match.start(), match.end(), value))
    return observed


def _get_date(lines) -> date | None:
    # Prefer the heading date over "Ngày chuyển đổi" / signing dates below tables.
    eligible = lines[:60]
    explicit = re.compile(r'\b(?:ngay\s+(?:lap|hoa don|phat hanh)|invoice\s+date|issue(?:d)?\s+date|issued)\b')
    prefix = r'\b(?:(?:invoice|issue(?:d)?)\s+date|ngay|x?gay|date|issued)(?:\s+(?:lap|hoa don|phat hanh|on))?\s*(?:\([^)]*\)\s*)?[:;,.-]?\s*'
    patterns = (
        (prefix + r'(\d{1,2})\s*thang\s*(\d{1,2})\s*(?:nam|nm|ndm)\s*(\d{4})\b', (3, 2, 1)),
        (prefix + r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b', (3, 2, 1)),
        (prefix + r'(\d{4})-(\d{2})-(\d{2})\b', (1, 2, 3)),
    )
    for preferred in (True, False):
        observed = set()
        for original, plain in eligible:
            for pattern, order in patterns:
                for match in re.finditer(pattern, plain):
                    # Scope exclusions to this date label, not the whole row:
                    # issue and payment/order dates can be printed side by side.
                    before = plain[max(0, match.start() - 35):match.start()].rstrip(' :;：')
                    if re.search(r'(?:chuyen doi|ky|signed|due|delivery|order|payment|birth|expiry)\s*$', before):
                        continue
                    if bool(explicit.search(match[0])) != preferred:
                        continue
                    try:
                        observed.add(date(*(int(match[index]) for index in order)))
                    except ValueError:
                        continue
        if observed:
            return next(iter(observed)) if len(observed) == 1 else None
    contextual = {value for original, _plain_text in lines[:60]
                  for _start, _end, value in _header_date_literals(original)}
    if contextual:
        return next(iter(contextual)) if len(contextual) == 1 else None
    return None


def _party_lines(lines):
    """Separate explicit inline fields without manufacturing column ownership.

    Plain text has no reliable assignment for two unqualified tax cells in one
    physical row. Retain those in raw OCR, but let the spatial path own them.
    """
    labels = re.compile(r'\b(?:' + SELLER_NAME_LABEL + r'|' + BUYER_NAME_LABEL + r'|ten don vi|(?:ma so thue|mst)(?: (?:nguoi |don vi )?(?:ban|mua))?|(?:(?:seller|buyer|supplier|customer) )?tax (?:code|id)|dia chi|address|dien thoai|phone|email|tai khoan|bank account)\s*(?:\([^)]*\)\s*)?[:：]')
    result = []
    for original, plain in lines:
        matches = list(labels.finditer(plain))
        if len(matches) < 2:
            result.append((original, plain))
            continue
        # Map folded offsets back to the original characters; never truncate
        # accented names by slicing with normalized string lengths.
        offsets = [n for n, character in enumerate(original) for _ in _plain(character)]
        generic_tax = [m for m in matches if re.fullmatch(r'(?:ma so thue|mst|tax (?:code|id))\s*[:：]', m[0])]
        if matches[0].start():
            prefix = original[:offsets[matches[0].start()]].strip(' |')
            if prefix:
                result.append((prefix, _plain(prefix)))
        for n, match in enumerate(matches):
            if len(generic_tax) > 1 and match in generic_tax:
                continue
            start = offsets[match.start()]
            stop = offsets[matches[n + 1].start()] if n + 1 < len(matches) else len(original)
            value = original[start:stop].strip(' |')
            result.append((value, _plain(value)))
    return result


def _invoice_number(lines, document_type=None) -> str | None:
    # Rank labels across the header. Never rewrite printed I/O/L into digits.
    labels = [r'so\s+hoa\s+don|hoa\s+don\s+so|so\s+hdon|so\s+hd|invoice\s*(?:no\.?|number)|invoice(?=\s*#)']
    if document_type != 'einvoice':
        labels.append(r'so\s+(?:bill|phieu)|bill\s*(?:no\.?|number)|receipt\s*(?:no\.?|number)')
    if document_type == 'bill':
        labels.append(r'transaction\s*(?:id|no\.?)')
    labels.append(r'so(?=\s*[:;.])')
    for label in labels:
        candidates = set()
        for _original, plain in lines[:60]:
            anchor = r'^\s*' if label == r'so(?=\s*[:;.])' else r'(?:^|\s)'
            pattern = anchor + r'(?:' + label + r')(?:\s*[:;.#]\s*|\s+)([a-z0-9][a-z0-9/._-]{0,49})(?![a-z0-9/._-])'
            for match in re.finditer(pattern, plain):
                candidate = match[1].upper().rstrip('.')
                if any(ch.isdigit() for ch in candidate):
                    candidates.add(candidate)
        if candidates:
            return next(iter(candidates)) if len(candidates) == 1 else None
    return None


def _seller_and_tax(lines) -> tuple[str | None, str | None]:
    lines = _party_lines(lines)
    seller = None
    seller_index = None
    buyer_index = len(lines)
    section = None
    for idx, (original, plain) in enumerate(lines[:40]):
        heading = party_section_role(original)
        if heading:
            section = heading
        if (heading == 'buyer'
                or re.search(r"\b(?:nguoi mua(?: hang)?|don vi mua(?: hang)?|buyer)\b", plain)
                or (section != 'seller' and re.match(r'\s*ten don vi(?!\s+ban\b)\s*[:：]', plain))):
            buyer_index = idx
            break
    # Role labels also occur at the bottom of e-invoices. Stop looking for
    # explicit seller names at the first payment summary or signature block.
    seller_end = next((idx for idx, (original, plain) in enumerate(lines) if amount_in_words(original) or financial_heading(original) or re.match(
        r"^[\s|(]*(?:cong\s+tien\s+hang|tong\s+(?:tien|cong|thanh\s+toan)|"
        r"subtotal|grand\s+total|total\s+(?:amount|payment)|so\s+tien\s+(?:viet\s+)?bang\s+chu|amount\s+in\s+words|"
        r"(?:da\s+)?ky\s+dien\s+tu|chu\s+ky(?:\s+so)?)\b", plain
    )), len(lines))

    def role_or_metadata(value: str) -> bool:
        plain = _plain(value).strip(" :;.,()")
        return bool(
            not plain or not party_name_allowed(value)
            or re.fullmatch(
                r"(?:nguoi mua(?: hang)?|nguoi ban(?: hang)?|seller|buyer|supplier|"
                r"ky(?:,?\s*ghi ro ho ten)?|ghi ro ho ten|signature|customer|"
                r"giam doc|ke toan truong|dai dien|thu truong don vi|director)",
                plain,
            )
            or re.search(
                r"\b(?:ky\s*,?\s*ghi\s+ro\s+ho\s+ten|ghi\s+ro\s+ho\s+ten|"
                r"ky\s+(?:dien\s+tu|so)|chu\s+ky|digitally\s+signed|signed\s+by)\b",
                plain,
            )
            or (not re.match(r'^(?:tong cong ty|cong ty|company|ho kinh doanh|doanh nghiep)\b', plain) and re.match(
                r"^\s*(?:subtotal|grand\s+total|total|tong|cong\s+tien|thue|vat|"
                r"payment|cash|change|discount|receipt|invoice|bill|pos|date|ngay|time|"
                r"so\s+hoa\s+don|invoice\s+(?:no|number|symbol)|ky\s+hieu|"
                r"dien\s+thoai|phone|tel|tai\s+khoan|bank\s+account|dia\s+chi|address|"
                r"hoa\s+don|ma\s+so\s+thue|mst)\b",
                plain,
            ))
        )

    for idx, (original, plain) in enumerate(lines[:min(80, seller_end)]):
        seller_label = SELLER_NAME_LABEL
        bare_seller = party_section_role(original) == 'seller' or bool(re.fullmatch(seller_label + r'\s*(?:\([^)]*\)\s*)?[:;：]?\s*', plain))
        m = None if bare_seller else re.search(
            r'^\s*' + seller_label + r'\s*(?:\([^)]*\)\s*)?(?:[:;：]\s*|\s+)(.{3,255})$',
            plain,
        )
        if m and not role_or_metadata(m[1]):
            # Take original string after matching label length, preserving accents.
            tail = original[len(original) - len(m[1]):].strip(" :;.,\u00a0")
            if re.search(r"[A-Za-zÀ-ỹ]", tail):
                seller, seller_index = tail, idx
                break
        if bare_seller:
            for next_idx in range(idx + 1, min(seller_end, idx + 4)):
                next_original, next_plain = lines[next_idx]
                if party_section_role(next_original) == 'buyer' or re.match(r'\s*(?:nguoi mua|don vi mua|buyer|customer)\b', next_plain):
                    break
                if re.search(r"\b(?:ma\s+so\s+thue|mst|tax\s*code)\b", next_plain):
                    continue
                next_original = party_name_literal(next_original)
                if (not role_or_metadata(next_original)
                        and re.search(r"[^\W\d_]", next_original, re.UNICODE)
                        and 3 <= len(next_original.strip(" :;.,\u00a0")) <= 255):
                    seller, seller_index = next_original.strip(" :;.,\u00a0"), idx
                    break
            if seller:
                break
    tax_codes = []
    for idx, (_original, plain) in enumerate(lines[:80]):
        explicit_buyer = bool(re.search(r'\b(?:nguoi\s+mua|don\s+vi\s+mua|buyer|customer)\b', plain))
        explicit_seller = bool(re.search(r'\b(?:' + SELLER_NAME_LABEL + r')\b', plain))
        if explicit_buyer or (idx >= buyer_index and not explicit_seller):
            continue
        match = re.search(
            r"\b(?:ma\s+so\s+thue(?:\s+nguoi\s+(?:ban|mua))?|mst(?:\s+nguoi\s+(?:ban|mua))?|tax\s*code)"
            r"\s*[:;]?\s*(\d{10}(?:-?\d{3})?)\b",
            plain,
        )
        if not match and re.search(
            r"^\s*(?:ma\s+so\s+thue(?:\s+nguoi\s+(?:ban|mua))?|mst(?:\s+nguoi\s+(?:ban|mua))?|tax\s*code)\s*[:;]?\s*$",
            plain,
        ):
            for next_idx in range(idx + 1, min(len(lines), idx + 3)):
                standalone = re.fullmatch(r"\s*(\d{10}(?:-?\d{3})?)\s*", lines[next_idx][1])
                if standalone:
                    explicit_seller = bool(re.search(r"\b(?:nguoi\s+ban|seller|supplier)\b", plain))
                    tax_codes.append((idx, standalone[1], explicit_seller))
                    break
        if match:
            explicit_seller = bool(re.search(r"\b(?:nguoi\s+ban|seller|supplier)\b", plain))
            tax_codes.append((idx, match[1], explicit_seller))
    tax = None
    if seller_index is not None:
        explicit = [(idx, code) for idx, code, marked_seller in tax_codes if marked_seller]
        nearby = [(abs(idx - seller_index), idx, code) for idx, code, _marked_seller in tax_codes if abs(idx - seller_index) <= 12]
        if explicit:
            tax = min(explicit, key=lambda entry: abs(entry[0] - seller_index))[1]
        elif nearby:
            _distance, _idx, tax = min(nearby, key=lambda entry: (entry[0], entry[1] < seller_index))
    if tax is None:
        for idx, code, _marked_seller in tax_codes:
            if idx < buyer_index:
                tax = code
                break

    # If OCR attached a signature/role label to the seller marker, use the
    # legal-name candidate in the seller header instead. A nearby tax code or
    # a company-form keyword anchors this fallback; arbitrary body text is not
    # promoted to a supplier name.
    if seller is None or role_or_metadata(seller):
        seller = None
        header_end = min(buyer_index, seller_end, 40)
        tax_anchor = next((idx for idx, code, _marked in tax_codes if idx < buyer_index), None)
        candidates = []
        # A tax-code anchor is required: bills can contain many plausible
        # merchant/customer/item strings, so they continue through their
        # dedicated receipt-header logic instead.
        if tax_anchor is not None:
            for idx, (original, plain) in enumerate(lines[:header_end]):
                if role_or_metadata(original) or re.search(
                    r"\b(?:don\s+vi\s+ban\s+hang|nguoi\s+ban\s+hang|seller|supplier|"
                    r"ten\s+don\s+vi|ma\s+so\s+thue|mst|buyer|nguoi\s+mua)\b",
                    plain,
                ):
                    continue
                candidate = original.strip(" :;.,\u00a0")
                letters = re.sub(r"[^a-z]", "", plain)
                if len(letters) < 5 or len(candidate) > 255:
                    continue
                company_form = bool(re.search(
                    r"\b(?:cong\s+ty|co\s+phan|tnhh|doanh\s+nghiep|chi\s+nhanh|"
                    r"ho\s+kinh\s+doanh|corporation|company|limited|\bltd\b|\binc\b)\b",
                    plain,
                ))
                distance = abs(tax_anchor - idx)
                candidates.append((not company_form, distance, idx, candidate))
        if candidates:
            _not_company_form, _distance, _idx, seller = min(candidates)
    return seller, tax


def _observed_vat_rates(lines):
    rates = set()
    for _original, plain in lines:
        for match in re.finditer(r'\b(?:thue\s+suat(?:\s+gtgt)?|vat\s*rate)\s*[:;]?\s*(\d{1,2}(?:[.,]\d+)?)\s*%', plain):
            rate = Decimal(match[1].replace(',', '.'))
            if 0 <= rate <= 100:
                rates.add(rate)
    return rates


def _amount_and_vat(lines) -> tuple[Decimal | None, Decimal | None]:
    total = None
    vat = None
    rates = _observed_vat_rates(lines)
    total_candidates: list[tuple[int, Decimal]] = []
    for _original, plain in lines:
        # A receipt may contain subtotal, tax, cash received, change, and a
        # final payable row. Prefer explicit payable labels over generic
        # "Total" and reject tender/change rows instead of taking the first
        # amount-like word encountered on the page.
        if re.search(r"\b(?:cash\s+(?:received|tendered)|amount\s+received|change|tien\s+(?:khach\s+dua|tra lai|thua))\b", plain):
            continue
        label_patterns = (
            (5, r"\b(?:tong\s+tien\s+(?:phai\s+)?thanh\s+toan|tong\s+cong\s+thanh\s+toan|tong\s+thanh\s+toan|grand\s+total|amount\s+due|total\s+payment)\b"),
            (4, r"\b(?:total\s+amount|total\s+due|payable\s+amount)\b"),
            (3, r"\b(?:tong\s+cong(?:\s+tien)?|tong\s+tien)\b"),
            (1, r"\btotal\b"),
        )
        labelled = next(((priority, match) for priority, pattern in label_patterns
                         if (match := re.search(pattern, plain))), None)
        if labelled is None:
            continue
        label_priority, label = labelled
        if label_priority < 3 and re.search(r'\b(?:subtotal|tien hang|tien thue|vat|tax)\b', plain):
            continue
        tail = plain[label.end():].strip(' :;=|')
        value = _decimal_money(tail)
        if value is not None:
            total_candidates.append((label_priority, value))

    if total_candidates:
        best_priority = max(priority for priority, _value in total_candidates)
        best_values = {value for priority, value in total_candidates if priority == best_priority}
        # If equally specific total labels conflict, keep the field empty rather
        # than guessing which one is the actual amount paid.
        if len(best_values) == 1:
            total = next(iter(best_values))
    vat = next(iter(rates)) if len(rates) == 1 else None
    return total, vat



def _invoice_symbol(lines) -> str | None:
    """Use only an explicit invoice-symbol label, never the template-model number."""
    for _original, plain in lines[:35]:
        match = re.search(
            r"\b(?:ky\s+hieu(?:\s+hoa\s+don)?|invoice\s+symbol)\s*[:;.]?\s*([a-z0-9][a-z0-9/-]{2,24})\b",
            plain,
        )
        if match:
            candidate = match[1].upper()
            if candidate not in ("HOA", "DON", "MAU") and any(x.isdigit() for x in candidate):
                return candidate
    return None


def _buyer_and_tax(lines) -> tuple[str | None, str | None]:
    """Extract buyer fields inside the buyer block, not from seller fields."""
    lines = _party_lines(lines)
    start = None
    for idx, (_original, plain) in enumerate(lines[:60]):
        if re.search(
            r"\b(?:ho\s+ten\s+nguoi\s+mua\s+hang|ten\s+nguoi\s+mua(?:\s+hang)?|"
            r"nguoi\s+mua(?:\s+hang)?|don\s+vi\s+mua(?:\s+hang)?|"
            r"ben\s+mua|buyer(?:\s+name)?|customer(?:\s+name)?)\s*[:;]?",
            plain,
        ):
            start = idx
            break
    if start is None:
        return None, None
    end = min(len(lines), start + 18)
    for idx in range(start + 1, end):
        if (party_section_role(lines[idx][0]) == 'seller'
                or amount_in_words(lines[idx][0]) or financial_heading(lines[idx][0])
                or re.search(r"\b(?:stt|cong\s+tien\s+hang|thue\s+suat|tong\s+tien\s+thanh\s+toan)\b", lines[idx][1])
                or re.match(r'\s*(?:(?:ten )?don vi ban(?: hang)?|nguoi ban(?: hang)?|seller|supplier)\s*[:;：]', lines[idx][1])):
            end = idx
            break
    company = None
    person = None
    tax = None
    company_label = r'(?:(?:ten\s+)?don\s+vi\s+mua(?:\s+hang)?|ben\s+mua|ten\s+don\s+vi(?!\s+(?:mua|ban)\b)|buyer\s+(?:name|company))'
    person_label = r'(?:(?:ho\s+ten\s+|ten\s+)?nguoi\s+mua(?:\s+hang)?|buyer|customer(?:\s+name)?)'
    def suitable_name(value):
        value = value.strip(' :;.,()')
        return (party_name_allowed(value) and bool(re.search(r'[^\W\d_]', value)) and not re.match(
            r'^(?:dia chi|address|dien thoai|phone|email|tai khoan|bank account|'
            r'ma so thue|mst|tax (?:code|id)|da ky|ky dien tu|chu ky|signature|signed|nguoi ban)\b', _plain(value)))
    for idx, (original, plain) in enumerate(lines[start:end], start):
        bare_company = bool(re.fullmatch(company_label + r'\s*[:;：]?\s*', plain))
        bare_person = bool(re.fullmatch(person_label + r'\s*[:;：]?\s*', plain))
        company_match = None if bare_company else re.match(
            r'^' + company_label + r'(?:\s*[:;：]\s*|\s+)(.{3,140})$', plain)
        person_match = None if bare_person or bare_company else re.match(
            r'^' + person_label + r'(?:\s*[:;：]\s*|\s+)(.{3,140})$', plain)
        if company_match and suitable_name(company_match[1]):
            company = original[-len(company_match[1]):].strip(' :;.,')[:150]
        elif person_match and person is None and suitable_name(person_match[1]):
            person = original[-len(person_match[1]):].strip(' :;.,')[:150]
        elif bare_company:
            for next_idx in range(idx + 1, min(end, idx + 4)):
                next_original, next_plain = lines[next_idx]
                if _is_item_table_boundary(next_original) or re.match(
                        r'\s*(?:dia chi|address|dien thoai|phone|email|tai khoan|bank account|nguoi ban|seller)\b', next_plain):
                    break
                if re.search(r"\b(?:ma\s+so\s+thue|mst|tax\s*code)\b", next_plain):
                    break
                if re.search(
                    r"\b(?:ten\s+nguoi\s+mua|nguoi\s+mua|ho\s+ten|buyer(?:\s+name)?)\b",
                    next_plain,
                ):
                    continue
                if len(next_original.strip()) >= 3 and suitable_name(next_original):
                    company = next_original.strip()[:150]
                    break
        elif person is None and bare_person:
            for next_idx in range(idx + 1, min(end, idx + 4)):
                next_original, next_plain = lines[next_idx]
                if _is_item_table_boundary(next_original) or re.match(
                        r'\s*(?:dia chi|address|dien thoai|phone|email|tai khoan|bank account|nguoi ban|seller)\b', next_plain):
                    break
                if re.search(r"\b(?:ten\s+don\s+vi|don\s+vi\s+mua\s+hang|buyer\s+name)\b", next_plain):
                    continue
                if re.search(r"\b(?:ma\s+so\s+thue|mst|tax\s*code)\b", next_plain):
                    break
                if len(next_original.strip()) >= 3 and suitable_name(next_original):
                    person = next_original.strip()[:150]
                    break
        if tax is None:
            tax_match = re.search(
                r"\b(?:ma\s+so\s+thue(?:\s+nguoi\s+mua)?|mst(?:\s+nguoi\s+mua)?|"
                r"buyer\s+tax\s+code|tax\s+code)\s*[:;]?\s*(\d{10}(?:-?\d{3})?)\b",
                plain,
            )
            if tax_match:
                tax = tax_match[1]
            elif re.search(
                r"^\s*(?:ma\s+so\s+thue(?:\s+nguoi\s+mua)?|mst(?:\s+nguoi\s+mua)?|"
                r"buyer\s+tax\s+code|tax\s+code)\s*[:;]?\s*$",
                plain,
            ):
                for next_idx in range(idx + 1, min(end, idx + 3)):
                    if re.search(r'\b(?:seller|supplier|nguoi ban|don vi ban)\b', lines[next_idx][1]):
                        break
                    standalone = re.fullmatch(r"\s*(\d{10}(?:-?\d{3})?)\s*", lines[next_idx][1])
                    if standalone:
                        tax = standalone[1]
                        break
    return company or person, tax


def _receipt_seller(lines) -> str | None:
    """Use a plausible top-of-receipt merchant line when no seller label exists."""
    headings = (
        "hoa don", "receipt", "cash bill", "retail bill", "pos", "bill no",
        "receipt no", "invoice", "customer copy", "ban le",
    )
    excluded = re.compile(
        r"\b(?:date|ngay|time|gio|address|dia chi|phone|tel|tax|mst|subtotal|"
        r"total|tong|cong|thue|vat|cash|payment|change|discount|cashier|"
        r"transaction|receipt|invoice|bill|pos)\b"
    )
    for original, plain in lines[:10]:
        if not party_name_allowed(original) or any(term in plain for term in headings) or excluded.search(plain):
            continue
        letters = re.sub(r"[^a-z]", "", plain)
        digits = re.sub(r"\D", "", original)
        if len(letters) < 3 or len(digits) > 5 or len(original) > 160:
            continue
        return original.strip(" \t:;.-")[:150] or None
    return None


def _financial_amounts(lines) -> tuple[Decimal | None, Decimal | None]:
    """Read explicitly labelled subtotal and VAT paid; no automatic guessing."""
    candidates = {'subtotal': [], 'vat': []}
    for _original, plain in lines:
        for field, priority, pattern in (
            ('subtotal', 3, r'\b(?:(?:tong )?tien (?:hang )?sau (?:chiet khau|giam gia)|net subtotal|subtotal after discount)\b'),
            ('subtotal', 2, r'\b(?:(?:tong )?tien hang truoc (?:chiet khau|giam gia)|gross subtotal|subtotal before discount)\b'),
            ('subtotal', 2, r'\b(?:tong tien (?:hang )?truoc thue|total before tax)\b'),
            ('subtotal', 1, r'\b(?:cong tien hang|tong tien hang|tien hang truoc thue|tam tinh|subtotal|tien truoc thue)\b'),
            ('vat', 2, r'\b(?:tong tien thue(?: gtgt| vat)?|total (?:vat|tax)(?: amount)?)\b'),
            ('vat', 1, r'\b(?:tien thue gtgt|tien thue vat|vat amount)\b'),
        ):
            match = re.search(pattern, plain)
            if match:
                tail = plain[match.end():].strip(' :;=')
                number = _decimal_money(tail)
                if field == 'vat' and number is None:
                    number, _printed_rate = amount_literal(tail, _decimal_money)
                if number is not None:
                    candidates[field].append((priority, number))
    def selected(values):
        if not values:
            return None
        priority = max(rank for rank, value in values)
        observed = {value for rank, value in values if rank == priority}
        return next(iter(observed)) if len(observed) == 1 else None
    # Never add page subtotals or tax groups to manufacture a document total.
    return selected(candidates['subtotal']), selected(candidates['vat'])


def _qr_url(raw: str) -> str | None:
    for url in re.findall(r"https?://[^\s<>\"']{5,200}", raw, re.I):
        url = url.rstrip(".,;)")
        parsed = urlparse(url)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            return url
    return None


def _printed_sales_bill_fields(lines):
    """Explicit Vietnamese sales-bill labels; only source literals, not VAT assumptions."""
    heading = next((n for n, (_, plain) in enumerate(lines[:30])
                    if re.fullmatch(r'hoa don ban hang|hoa don ban le|phieu ban hang', plain.strip(' :|.-'))), None)
    if heading is None:
        return {}
    result = {'document_type': 'bill'}
    def unique(values):
        values = {value for value in values if value is not None}
        return next(iter(values)) if len(values) == 1 else None
    # Standalone ID directly below the actual receipt title, not a phone or SKU.
    identifiers = [m[0] for original, _ in lines[heading+1:heading+3]
                   if (m := re.fullmatch(r'(?:HD|HB|BH)[- ]?\d{4,20}', original.strip(), re.I))]
    result['invoice_number'] = unique(identifiers)
    dates = []
    for original, _ in lines[heading+1:heading+5]:
        match = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?', original)
        if match:
            try:
                dates.append(date(int(match[3]), int(match[2]), int(match[1])))
            except ValueError:
                continue
    result['invoice_date'] = unique(dates)
    result['seller_name'] = unique(original for original, plain in lines[:heading]
        if re.match(r'^(?:npp|nha phan phoi|cua hang|ho kinh doanh)\s+\S', plain)
        and party_name_allowed(original))
    result['buyer_name'] = unique(original[m.end():].strip() for original, plain in lines[heading+1:heading+15]
        if (m := re.match(r'^(?:ten kh|ten khach hang|khach hang)\s*[:：]\s*', plain))
        and party_name_allowed(original[m.end():].strip()))
    def labelled(pattern):
        return [(n, value) for n, (_, plain) in enumerate(lines[heading+1:], heading+1)
                if (m := re.fullmatch('(?:' + pattern + r')\s*[:：]?\s*(.+)', plain.strip(' |')))
                and (value := _decimal_money(m[1])) is not None]
    payable = labelled(r'thanh toan|tong thanh toan|tong tien thanh toan')
    gross = labelled(r'tong cong')
    discount = labelled(r'giam|giam gia|chiet khau')
    result['total_amount'] = unique(v for _, v in payable)
    # Only an explicitly printed total-before-discount is a receipt subtotal.
    if len(gross) == len(discount) == len(payable) == 1 and gross[0][0] < discount[0][0] < payable[0][0]:
        result['subtotal'] = gross[0][1]
    return {k: v for k, v in result.items() if v is not None}


def currency_observation(raw):
    """Use explicit printed currency labels; never infer USD from a '$' sign."""
    plain=_plain(raw or '')
    codes=set(re.findall(r'\b(?:don vi tien te|tien te|currency|dvtte)\s*(?:\([^\n)]{0,35}\)\s*)?[:：]?\s*([a-z]{3})\b',plain))
    if len(codes)>1:return {'state':'conflicting','codes':sorted(code.upper() for code in codes)}
    if codes:return {'state':'observed','code':next(iter(codes)).upper()}
    return {'state':'not_observed'}


def extract_fields(raw: str, ext: str) -> dict:
    lines = _lines(current_document_text(raw or ''))
    document_type = classify(ext, raw or "")
    number = _invoice_number(lines, document_type=document_type)
    issued = _get_date(lines)
    labelled_date_present = any(re.search(r'\b(?:ngay|date|issued)\b.*\d', plain)
                                for _original, plain in lines[:60])
    if issued is None and document_type == "bill" and not labelled_date_present:
        for original, _plain_line in lines[:12]:
            match = re.fullmatch(
                r"\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\s*",
                original,
            )
            if match:
                try:
                    issued = date(int(match[3]), int(match[2]), int(match[1]))
                    break
                except ValueError:
                    continue
    seller, seller_tax = _seller_and_tax(lines)
    if seller is None and document_type == "bill":
        seller = _receipt_seller(lines)
    total, vat_rate = _amount_and_vat(lines)
    subtotal, vat_amount = _financial_amounts(lines)
    buyer, buyer_tax = _buyer_and_tax(lines)
    seller = party_name_literal(seller)
    buyer = party_name_literal(buyer)
    if buyer_tax and buyer_tax == seller_tax:
        # Text flattening can move the seller's tax cell into a buyer block.
        # An equal identifier is accepted here only with its own explicit
        # buyer-tax label; spatial Final can establish independent cells later.
        independent = any(re.search(
            r'\b(?:(?:ma so thue|mst) (?:nguoi |don vi )?mua|(?:buyer|customer) tax (?:code|id))\s*[:;：]?\s*' + re.escape(buyer_tax) + r'\b', plain)
            for _original, plain in lines)
        if not independent:
            buyer_tax = None
    fields = {
        "invoice_number": number,
        "invoice_symbol": _invoice_symbol(lines),
        "invoice_date": issued,
        "seller_name": seller,
        "seller_tax_code": seller_tax,
        "buyer_name": buyer,
        "buyer_tax_code": buyer_tax,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total_amount": total,
        "vat_rate": vat_rate,
        "qr_url": _qr_url(raw or ""),
        "document_type": document_type,
    }
    currency=currency_observation(raw)
    if currency['state']=='observed':fields['currency']=currency['code']
    fields.update(_printed_sales_bill_fields(lines))
    document_type = fields["document_type"]
    # This is a completeness ratio, not OCR accuracy. Retail receipts do not
    # require a seller tax code; electronic/unknown documents keep the stricter set.
    essential = ("invoice_number", "invoice_date", "seller_name", "total_amount")
    if document_type != "bill":
        essential = essential[:3] + ("seller_tax_code",) + essential[3:]
    fields["confidence_score"] = round(sum(fields[k] is not None for k in essential) / len(essential), 2)
    return fields


def validate(invoice, items=None, financial_context=None) -> list[tuple[str, bool, str]]:
    def finite_decimal(value):
        try:
            result = Decimal(str(value)) if value is not None else None
            return result if result is not None and result.is_finite() else None
        except (InvalidOperation, ValueError, TypeError):
            return None
    from .invoice_financials import non_financial_adjustment
    financial_fields = {key: getattr(invoice, key, None) for key in ('subtotal', 'vat_amount', 'total_amount', 'vat_rate')}
    financial_rows = [{key: item.get(key) if isinstance(item, dict) else getattr(item, key, None)
                      for key in ('description', 'quantity', 'unit_price', 'amount')} for item in (items or [])]
    information_only = non_financial_adjustment(financial_fields, financial_rows, financial_context)
    tests = []
    tests.append(("INV-NO", bool((invoice.invoice_number or '').strip()), "Thiếu số hóa đơn"))
    tests.append(("DATE", bool(invoice.invoice_date), "Thiếu ngày lập hóa đơn"))
    tests.append(('SELLER-NAME', bool(getattr(invoice, 'seller_name', None)) and party_name_allowed(invoice.seller_name),
                  'Thiếu tên người bán hoặc giá trị đang là số tiền bằng chữ/tiêu đề/thông tin ngoài vùng người bán.'))
    if getattr(invoice, 'buyer_name', None):
        tests.append(('BUYER-NAME', party_name_allowed(invoice.buyer_name),
                      'Tên người mua đang chứa thông tin sai loại trường; cần đối chiếu vùng người mua.'))
    is_bill = getattr(invoice, "document_type", None) == "bill"
    seller_tax_present = bool((invoice.seller_tax_code or "").strip())
    tax = re.sub(r'[\s-]', '', invoice.seller_tax_code or '')
    tests.append((
        "TAX-CODE",
        (is_bill and not seller_tax_present) or bool(re.fullmatch(r"\d{10}(?:\d{3})?", tax)),
        "Thiếu hoặc sai định dạng mã số thuế người bán",
    ))
    tests.append((
        "TOTAL",
        (information_only and invoice.total_amount is None)
        or (finite_decimal(invoice.total_amount) is not None and finite_decimal(invoice.total_amount) >= 0),
        "Thiếu tổng tiền thanh toán",
    ))
    buyer_tax_value = getattr(invoice, "buyer_tax_code", None)
    buyer_tax_present = bool((buyer_tax_value or "").strip())
    buyer_tax = re.sub(r'[\s-]', '', buyer_tax_value or '')
    tests.append((
        "BUYER-TAX", (is_bill and not buyer_tax_present) or bool(re.fullmatch(r"\d{10}(?:\d{3})?", buyer_tax)),
        "Thiếu hoặc sai định dạng mã số thuế người mua",
    ))
    subtotal = getattr(invoice, "subtotal", None)
    vat_amount = getattr(invoice, "vat_amount", None)
    rate = getattr(invoice, "vat_rate", None)
    rate_value = finite_decimal(rate)
    if rate is not None:
        supported_rates = {Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10")}
        rate_valid = rate_value is not None and rate_value in supported_rates
        tests.append((
            "VAT-RATE",
            rate_valid,
            "VAT rate must be one of 0, 5, 8 or 10 percent",
        ))
    if financial_context is not None:
        from .invoice_financials import arithmetic_rules
        try:
            return tests + arithmetic_rules(financial_fields, financial_rows, financial_context)
        except Exception:
            return tests + [('FINANCIAL-CONTEXT', False,
                             'Chưa kiểm tra được phạm vi tài chính; giữ dữ liệu nguồn và cần xem xét.')]
    if subtotal is not None and vat_amount is not None and invoice.total_amount is not None:
        # Absolute tolerance for VND values; does not certify legal validity.
        values = [finite_decimal(value) for value in (subtotal, vat_amount, invoice.total_amount)]
        valid = all(value is not None for value in values) and abs(values[0] + values[1] - values[2]) < 2
        tests.append(("ARITH", valid, "Tổng tiền không bằng tiền trước thuế + VAT"))
    if subtotal is not None and vat_amount is not None and rate is not None:
        base, observed_tax = finite_decimal(subtotal), finite_decimal(vat_amount)
        if base is not None and observed_tax is not None and rate_value is not None:
            expected = base * rate_value / 100
            valid = abs(expected - observed_tax) < 2
        else:
            valid = False
        tests.append(("VAT-ARITH", valid, "Tiền VAT không khớp thuế suất trên tiền trước thuế (hóa đơn một thuế suất)"))
    if items is not None:
        amounts = [getattr(item, "amount", item.get("amount") if isinstance(item, dict) else None) for item in items]
        normalized = [finite_decimal(amount) for amount in amounts]
        base = finite_decimal(subtotal)
        if not items or base is None or any(amount is None for amount in normalized):
            valid = False
        else:
            item_total = sum(normalized, Decimal('0'))
            valid = abs(item_total - base) < 2
        tests.append(("ITEM-SUM", valid, "Tổng các dòng hàng không khớp tiền trước thuế"))
    else:
        tests.append(("ITEM-SUM", False, "Thiếu danh sách dòng hàng để đối chiếu tiền trước thuế"))
    return tests
