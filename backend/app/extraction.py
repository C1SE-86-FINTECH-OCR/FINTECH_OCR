"""FINTECH OCR: OCR v5, conservative invoice field extraction and financial checks.

Compatible public functions: money, text_from_file, classify, extract_fields, validate.
OCR output is a *draft* and must be reviewed before approval/tax lookup.
No external AI/API and no changes to the database are performed here.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import pytesseract

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


def money(raw):
    """Read Vietnamese/English formatted amounts; return float for existing ORM API."""
    if raw is None or str(raw).strip() == "":
        return None
    s = re.sub(r"[^\d,.-]", "", str(raw))
    if not s or s in ("-", ".", ","):
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif s.count(",") > 1:
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
        return round(float(value), 2)
    except (InvalidOperation, ValueError, OverflowError):
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
    # Providers commonly emit both spellings; keep aliases explicit rather
    # than trying to infer subtotal from line items or total arithmetic.
    subtotal = node_text(root, ("TgTCThue", "TgTCTHue"))
    vat_amount = node_text(root, "TgTThue")
    if symbol:
        lines.append("Ký hiệu: " + symbol)
    if number:
        lines.append("Số hóa đơn: " + number)
    if issued:
        lines.append("Ngày: " + issued)
    for seller_node in root.iter():
        if _xml_local_tag(seller_node.tag).lower() == "nban":
            seller_name = node_text(seller_node, "Ten")
            seller_tax = node_text(seller_node, "MST")
            if seller_name:
                lines.append("Đơn vị bán hàng: " + seller_name)
            if seller_tax:
                lines.append("Mã số thuế: " + seller_tax)
            break
    for buyer_node in root.iter():
        if _xml_local_tag(buyer_node.tag).lower() == "nmua":
            buyer_name = node_text(buyer_node, "Ten")
            buyer_tax = node_text(buyer_node, "MST")
            if buyer_name:
                lines.append("Tên đơn vị: " + buyer_name)
            if buyer_tax:
                lines.append("Mã số thuế: " + buyer_tax)
            break
    if subtotal:
        lines.append("Cộng tiền hàng: " + subtotal)
    if vat_amount:
        lines.append("Tiền thuế GTGT: " + vat_amount)
    if total:
        lines.append("Tổng tiền thanh toán: " + total)
    if _xml_has_invoice_structure(root):
        lines.append("Cấu trúc hóa đơn điện tử XML: HDon/DLHDon")
    # Keep other human-readable text for audit/troubleshooting.
    content = " ".join(t.strip() for t in root.itertext() if t and t.strip())
    return ("\n".join(lines) + "\n" + content)[:60000]


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
    amount = find_index(("thanh tien", "line total", "amount"))
    if description is None or amount is None or description == amount:
        return None
    return {
        "description": description,
        "amount": amount,
        "unit": find_index(("don vi tinh", "dvt", "unit of measure")),
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
    ))


def _ocr_numeric_cell(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return money(value)


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
        if len(cells) < 3 or not re.fullmatch(r"\s*\d{1,3}[.)]?\s*", cells[0]):
            continue
        row_no = int(re.sub(r"\D", "", cells[0]))
        if row_no < 1 or _is_summary_or_party_line(" ".join(cells)):
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
        if not description or amount is None:
            continue
        if len(description) > 2000:
            continue
        unit = cells[unit_index].strip()[:30] or None if unit_index is not None and unit_index < len(cells) else None
        quantity = _ocr_numeric_cell(cells[quantity_index]) if quantity_index is not None and quantity_index < len(cells) else None
        unit_price = _ocr_numeric_cell(cells[unit_price_index]) if unit_price_index is not None and unit_price_index < len(cells) else None
        key = (row_no, description, unit, quantity, unit_price, amount)
        if key in seen:
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
    return result


def _ocr_item_table_fragment(raw_text: str) -> str:
    """Keep only a clearly headed item table from a secondary OCR layout pass."""
    lines = raw_text.splitlines()
    for index, line in enumerate(lines):
        cells = _ocr_table_cells(line)
        if not cells or not _line_item_header(cells):
            continue
        fragment = [line]
        for candidate in lines[index + 1:]:
            if not candidate.strip():
                continue
            row_cells = _ocr_table_cells(candidate)
            if row_cells and re.fullmatch(r"\s*\d{1,3}[.)]?\s*", row_cells[0]):
                fragment.append(candidate)
                continue
            if _is_summary_or_party_line(candidate):
                break
            # A wrapped continuation cannot be mapped to table columns safely.
            break
        return "\n".join(fragment)
    return ""


def extract_line_items(data: bytes, ext: str, raw_text: str | None = None) -> list[dict]:
    """Extract XML rows or conservative, explicitly delimited OCR table rows.

    XML continues to use the confirmed HDon/DLHDon/NDHDon/DSHHDVu/HHDVu
    mapping. Raster/PDF text must include a delimited table header (or the
    narrow 3-cell row shape) and an explicit amount; missing values stay None.
    """
    extension = ext.lower().lstrip(".")
    if extension in ("jpg", "jpeg", "png", "pdf"):
        return _extract_ocr_line_items(raw_text)
    if extension != "xml":
        return []
    root = _parse_xml(data)

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
        amount = money(raw_amount)
        # A row without both identifying text and an explicit amount is not a
        # valid persisted invoice item; never synthesize a line from totals.
        if not description or amount is None:
            continue
        result.append({
            "line_no": len(result) + 1,
            "description": description[:2000],
            "unit": None,
            "quantity": None,
            "unit_price": None,
            "amount": Decimal(str(amount)),
        })
    return result


def _prepare_image(image):
    from PIL import Image, ImageOps
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.load()
    if image.width * image.height > 30_000_000:
        raise ValueError("Ảnh quá lớn để xử lý OCR (trên 30 MP)")
    # Small screenshots/scans (e.g., 556 x 551) are hard to read at native size.
    # Enlarge but cap pixel count to avoid large memory allocations.
    shortest = min(image.size)
    scale = min(3.0, max(1.0, 1600 / max(1, shortest)))
    if scale > 1.05 and image.width * image.height * scale * scale <= 24_000_000:
        image = image.resize(
            (round(image.width * scale), round(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
    return image


def _amount_from_total_row_ocr(fragment: str) -> int | None:
    """Interpret digits seen inside a cropped TOTAL row, not generic page text.

    Thousands separators may be dot/comma; mixed separators are accepted only
    when groups have exactly three digits. This avoids confusing a VAT amount
    with a computed total and never fills a number from words alone.
    """
    candidates = re.findall(
        r"(?<![0-9])(?:[0-9]{1,3}(?:[.,][0-9]{3}){1,4}|[0-9]{4,12})(?![0-9])",
        fragment,
    )
    numbers = []
    for candidate in candidates:
        digits = re.sub(r"[.,]", "", candidate)
        if digits.isdigit():
            value = int(digits)
            if 0 < value <= 9_999_999_999_999:
                numbers.append(value)
    # A crop with multiple plausible values is ambiguous; don't guess.
    return numbers[0] if len(set(numbers)) == 1 else None


def _recover_total_from_image(image) -> int | None:
    """Conservatively recover a total from a spatially labelled invoice row.

    Procedure: locate a near-match to the 'total payment' label using Tesseract
    boxes, OCR two overlapping numeric regions on the SAME line, then require
    both regions to agree. No amount is synthesized by VAT arithmetic.
    """
    from PIL import Image, ImageOps

    try:
        data = pytesseract.image_to_data(
            image,
            lang="vie+eng",
            config="--psm 11",
            output_type=pytesseract.Output.DICT,
            timeout=35,
        )
    except (pytesseract.TesseractError, RuntimeError):
        return None  # Best effort; standard fields remain available.

    groups = {}
    for index, word in enumerate(data.get("text", [])):
        if not word or not word.strip():
            continue
        group = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        groups.setdefault(group, []).append(index)

    target_labels = (
        "tong tien thanh toan", "tong cong thanh toan", "tong thanh toan",
        "tong tien phai thanh toan", "grand total", "total amount", "amount due",
    )
    for group in groups.values():
        label = _plain(" ".join(data["text"][i] for i in group))
        # Reject other rows such as 'tiền thuế GTGT' and 'hình thức thanh toán'.
        if not ("toan" in label or "total" in label or "amount due" in label):
            continue
        similarity = max(SequenceMatcher(None, label.strip(" :;.,"), target).ratio()
                         for target in target_labels)
        if similarity < 0.77:
            continue

        top = min(int(data["top"][i]) for i in group)
        bottom = max(int(data["top"][i]) + int(data["height"][i]) for i in group)
        height = max(9, bottom - top)
        # No columns -> never OCR any arbitrary number from the page.
        right = int(image.width * 0.95)
        values = []
        for left_fraction in (0.65, 0.82):
            left = int(image.width * left_fraction)
            y0 = max(0, int(top - height * 0.35))
            y1 = min(image.height, int(top + height * 1.15))
            if right <= left or y1 <= y0:
                continue
            crop = ImageOps.autocontrast(image.crop((left, y0, right, y1)).convert("L"))
            # Upscale tiny line crops; keep dimensions capped.
            if crop.width * crop.height < 2_000_000:
                crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
            try:
                result = pytesseract.image_to_string(
                    crop,
                    lang="eng",
                    config="--psm 11 -c tessedit_char_whitelist=0123456789.,",
                    timeout=12,
                )
            except (pytesseract.TesseractError, RuntimeError):
                continue
            found = _amount_from_total_row_ocr(result)
            if found is not None:
                values.append(found)
        # Require the two different crop widths to support the SAME amount.
        if len(values) == 2 and values[0] == values[1]:
            return values[0]
    return None





def _money_from_numeric_crop(raw: str) -> int | None:
    """A single amount from a right-hand invoice cell, never a nearby date/code.

    Crop must already be anchored to a labelled financial row. Mixed thousand
    separators are tolerated because Tesseract often confuses dots and commas.
    """
    candidates = re.findall(
        r"(?<![\d])(?:\d{1,3}(?:[.,]\d{3}){1,4}|\d{4,12})(?![\d])",
        raw or "",
    )
    parsed = {int(re.sub(r"[.,]", "", candidate)) for candidate in candidates}
    if len(parsed) != 1:
        return None
    value = next(iter(parsed))
    return value if 0 < value <= 9_999_999_999_999 else None


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


def _recover_financial_rows_from_image(image, missing: set[str]) -> dict[str, int]:
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

    findings: dict[str, set[int]] = {}
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


def _consistent_recovered_amounts(existing: dict, recovered: dict[str, int]) -> dict[str, int]:
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


def _ocr_image(image) -> str:
    image = _prepare_image(image)
    # PSM 11 works well on invoices with mixed column layouts and small labels.
    try:
        text = pytesseract.image_to_string(image, lang="vie+eng", config="--psm 11", timeout=35)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError("Tesseract OCR engine is unavailable") from exc
    # Use a second page-layout pass only if the first pass did not identify core fields.
    extracted = extract_fields(text, "png")
    core_count = sum(bool(extracted.get(k)) for k in (
        "invoice_number", "invoice_date", "seller_name", "seller_tax_code"
    ))
    if core_count < 3:
        alternative = pytesseract.image_to_string(image, lang="vie+eng", config="--psm 6", timeout=35)
        other = extract_fields(alternative, "png")
        other_count = sum(bool(other.get(k)) for k in (
            "invoice_number", "invoice_date", "seller_name", "seller_tax_code"
        ))
        if other_count > core_count:
            text = alternative
        elif other_count == core_count and len(alternative.strip()) > len(text.strip()) * 1.3:
            text = alternative
    # In many Vietnamese invoice templates the issued date sits above the
    # seller block; cropping that header reduces interference from the table.
    if extract_fields(text, "png")["invoice_date"] is None and image.height >= 500:
        header = image.crop((
            int(image.width * 0.25), int(image.height * 0.07),
            image.width, int(image.height * 0.23),
        ))
        header_text = pytesseract.image_to_string(
            header, lang="vie+eng", config="--psm 6", timeout=25
        )
        if _get_date(_lines(header_text)) is not None:
            text = header_text + "\n" + text
    # A targeted lower-page pass helps to recover VAT/total labels embedded
    # inside dense tabular invoice sections; never invent financial numbers.
    fields = extract_fields(text, "png")
    if (fields["total_amount"] is None or fields["vat_rate"] is None) and \
            fields["document_type"] == "einvoice" and image.height >= 500:
        bottom = image.crop((0, int(image.height * 0.46), image.width, int(image.height * 0.79)))
        bottom_text = pytesseract.image_to_string(
            bottom, lang="vie+eng", config="--psm 6", timeout=25
        )
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
    )
    if has_item_header and not _extract_ocr_line_items(text):
        try:
            table_pass = pytesseract.image_to_string(
                image, lang="vie+eng", config="--psm 6", timeout=35
            )
        except (pytesseract.TesseractError, RuntimeError):
            table_pass = ""
        fragment = _ocr_item_table_fragment(table_pass) if table_pass else ""
        if fragment and _extract_ocr_line_items(fragment):
            text += "\n" + fragment
    return text[:60000]


def text_from_file(data: bytes, ext: str) -> tuple[str, str]:
    """Return (raw_text, method); raise on OCR failure instead of silently returning ''."""
    ext = ext.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext == "xml":
        return _xml_text(data), "xml"
    if ext == "pdf":
        import fitz
        from PIL import Image
        with fitz.open(stream=data, filetype="pdf") as pdf:
            pages = list(pdf)[:12]
            text = "\n".join(page.get_text() for page in pages)
            if len(text.strip()) > 40:
                return text[:60000], "pdf-text"
            ocr_pages = []
            for page in pages[:3]:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_pages.append(_ocr_image(img))
            return "\n".join(ocr_pages)[:60000], "pdf-ocr"
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
        "hoa don gia tri gia tang", "hoa don dien tu", "vat invoice"
    )):
        return "einvoice"
    if any(x in low for x in ("hoa don ban le", "bill", "receipt", "phieu thu")):
        return "bill"
    return "unknown"


def _lines(raw: str):
    # Keep original and accent-insensitive forms side by side.
    lines = [" ".join(line.split()) for line in raw.splitlines() if line.strip()]
    return [(s, _plain(s)) for s in lines]


def _get_date(lines) -> date | None:
    # Prefer the heading date over "Ngày chuyển đổi" / signing dates below tables.
    for original, plain in lines[:24]:
        if "chuyen doi" in plain or "ky ngay" in plain:
            continue
        if not re.search(r"\b(?:ngay|x?gay|date|issued)\b", plain):
            continue
        m = re.search(r"\b(?:ngay|x?gay|date|issued)\s*[:;,.-]?\s*(\d{1,2})\s*(?:thang)\s*(\d{1,2})\s*(?:nam|nm|ndm)\s*(\d{4})\b", plain)
        if m:
            try:
                return date(int(m[3]), int(m[2]), int(m[1]))
            except ValueError:
                continue
        m = re.search(r"\b(?:ngay|x?gay|date|issued)(?:\s+lap)?\s*[:;,.-]?\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", plain)
        if m:
            try:
                return date(int(m[3]), int(m[2]), int(m[1]))
            except ValueError:
                continue
        m = re.search(r"\b(?:ngay|x?gay|date|issued)(?:\s+lap)?\s*[:;,.-]?\s*(\d{4})-(\d{2})-(\d{2})\b", plain)
        if m:
            try:
                return date(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                continue
    return None


def _invoice_number(lines) -> str | None:
    for original, plain in lines[:20]:
        # Explicit invoice numbers take precedence over "Mẫu số"/"Ký hiệu".
        for pattern in (
            r"(?:^|\s)(?:so\s+hoa\s+don|so\s+hdon|invoice\s*(?:no\.?|number))\s*[:;.#]?\s*([a-z0-9/-]{4,32})\b",
            r"(?:^|\s)so\s*[:;.]\s*([0-9oOilI]{4,16})\b",
        ):
            m = re.search(pattern, plain)
            if m:
                candidate = m[1].upper()
                # Convert OCR O/I/L only for wholly numeric-looking invoice numbers.
                if re.fullmatch(r"[0-9OIL]{4,16}", candidate):
                    candidate = candidate.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))
                if any(ch.isdigit() for ch in candidate) and 4 <= len(candidate) <= 32:
                    return candidate
    return None


def _seller_and_tax(lines) -> tuple[str | None, str | None]:
    seller = None
    seller_index = None
    buyer_index = len(lines)
    for idx, (original, plain) in enumerate(lines[:40]):
        if re.search(r"\b(?:nguoi mua|don vi mua|ten don vi|buyer)\b", plain):
            buyer_index = idx
            break
    for idx, (original, plain) in enumerate(lines[:buyer_index]):
        m = re.search(r"\b(?:don|ben|d[a-z]{2,4})\s+vi\s+ban\s+hang\s*[:;]?\s*(.{4,120})$", plain)
        if m:
            # Take original string after matching label length, preserving accents.
            tail = original[len(original) - len(m[1]):].strip(" :;.,")
            if re.search(r"[A-Za-zÀ-ỹ]", tail):
                seller, seller_index = tail[:150], idx
                break
        m = re.search(r"\b(?:seller|supplier)\s*[:;]\s*(.{4,120})$", plain)
        if m:
            seller = original[len(original) - len(m[1]):].strip(" :;.,")[:150]
            seller_index = idx
            break
    tax_codes = []
    for idx, (_original, plain) in enumerate(lines[: max(40, buyer_index)]):
        match = re.search(r"\b(?:ma\s+so\s+thue|mst|tax\s*code)\s*[:;]?\s*(\d{10}(?:-?\d{3})?)\b", plain)
        if match:
            tax_codes.append((idx, match[1]))
    tax = None
    if seller_index is not None:
        for idx, code in tax_codes:
            if seller_index < idx < buyer_index and idx <= seller_index + 8:
                tax = code
                break
    if tax is None:
        for idx, code in tax_codes:
            if idx < buyer_index:
                tax = code
                break
    return seller, tax


def _amount_and_vat(lines) -> tuple[float | None, float | None]:
    total = None
    vat = None
    for _original, plain in lines:
        if vat is None:
            m = re.search(r"\b(?:thue\s+suat(?:\s+gtgt)?|vat\s*rate)\s*[:;]?\s*(\d{1,2}(?:[.,]\d+)?)\s*%", plain)
            if m:
                try:
                    v = float(m[1].replace(",", "."))
                    if 0 <= v <= 30:
                        vat = v
                except ValueError:
                    pass
        if total is not None:
            continue
        m = re.search(
            r"\b(?:tong\s+(?:tien\s+)?(?:thanh\s+toan|cong\s+thanh\s+toan)|tong\s+cong(?:\s+tien)?|tong\s+tien\s+phai\s+thanh\s+toan|total\s+amount|amount\s+due|grand\s+total|total)\s*[:;]?\s*([0-9][0-9.,]{3,20})\b",
            plain,
        )
        if m:
            total = money(m[1])
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
    start = None
    for idx, (_original, plain) in enumerate(lines[:60]):
        if re.search(r"\b(?:ho\s+ten\s+nguoi\s+mua\s+hang|ten\s+don\s+vi|don\s+vi\s+mua\s+hang|buyer(?:\s+name)?)\s*[:;]", plain):
            start = idx
            break
    if start is None:
        return None, None
    end = min(len(lines), start + 18)
    for idx in range(start + 1, end):
        if re.search(r"\b(?:stt|cong\s+tien\s+hang|thue\s+suat|tong\s+tien\s+thanh\s+toan)\b", lines[idx][1]):
            end = idx
            break
    company = None
    person = None
    tax = None
    for original, plain in lines[start:end]:
        company_match = re.search(
            r"\b(?:ten\s+don\s+vi|don\s+vi\s+mua\s+hang|buyer\s+name|buyer\s+company)\s*[:;]\s*(.{3,140})$",
            plain,
        )
        person_match = re.search(
            r"\b(?:ho\s+ten\s+nguoi\s+mua\s+hang|buyer)\s*[:;]\s*(.{3,140})$",
            plain,
        )
        if company_match:
            company = original[-len(company_match[1]):].strip(' :;.,')[:150]
        elif person_match and person is None:
            person = original[-len(person_match[1]):].strip(' :;.,')[:150]
        if tax is None:
            tax_match = re.search(
                r"\b(?:ma\s+so\s+thue|mst|buyer\s+tax\s+code|tax\s+code)\s*[:;]?\s*(\d{10}(?:-?\d{3})?)\b",
                plain,
            )
            if tax_match:
                tax = tax_match[1]
    return company or person, tax


def _financial_amounts(lines) -> tuple[float | None, float | None]:
    """Read explicitly labelled subtotal and VAT paid; no automatic guessing."""
    subtotal = vat_amount = None
    for _original, plain in lines:
        for field, pattern in (
            ("subtotal", r"\b(?:cong\s+tien\s+hang|tien\s+hang\s+truoc\s+thue|subtotal|tien\s+truoc\s+thue)\s*[:;]?\s*([0-9][0-9.,]{2,20})\b"),
            ("vat", r"\b(?:tien\s+thue\s+gtgt|tien\s+thue\s+vat|vat\s+amount|tong\s+tien\s+thue)\s*[:;]?\s*([0-9][0-9.,]{2,20})\b"),
        ):
            match = re.search(pattern, plain)
            if match:
                number = money(match[1])
                if field == "subtotal" and subtotal is None:
                    subtotal = number
                if field == "vat" and vat_amount is None:
                    vat_amount = number
    return subtotal, vat_amount


def _qr_url(raw: str) -> str | None:
    for url in re.findall(r"https?://[^\s<>\"']{5,200}", raw, re.I):
        url = url.rstrip(".,;)")
        parsed = urlparse(url)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            return url
    return None


def extract_fields(raw: str, ext: str) -> dict:
    lines = _lines(raw or "")
    number = _invoice_number(lines)
    issued = _get_date(lines)
    seller, seller_tax = _seller_and_tax(lines)
    total, vat_rate = _amount_and_vat(lines)
    subtotal, vat_amount = _financial_amounts(lines)
    buyer, buyer_tax = _buyer_and_tax(lines)
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
        "document_type": classify(ext, raw or ""),
    }
    # Not a calibrated AI/OCR probability, only a ratio of five populated fields.
    essential = ("invoice_number", "invoice_date", "seller_name", "seller_tax_code", "total_amount")
    fields["confidence_score"] = round(sum(fields[k] is not None for k in essential) / 5, 2)
    return fields


def validate(invoice, items=None) -> list[tuple[str, bool, str]]:
    tests = []
    tests.append(("INV-NO", bool(invoice.invoice_number), "Thiếu số hóa đơn"))
    tests.append(("DATE", bool(invoice.invoice_date), "Thiếu ngày lập hóa đơn"))
    tax = (invoice.seller_tax_code or "").replace("-", "")
    tests.append((
        "TAX-CODE",
        bool(re.fullmatch(r"\d{10}(?:\d{3})?", tax)),
        "Thiếu hoặc sai định dạng mã số thuế người bán",
    ))
    tests.append((
        "TOTAL",
        invoice.total_amount is not None and float(invoice.total_amount) >= 0,
        "Thiếu tổng tiền thanh toán",
    ))
    buyer_tax = (getattr(invoice, "buyer_tax_code", None) or "").replace("-", "")
    tests.append((
        "BUYER-TAX", bool(re.fullmatch(r"\d{10}(?:\d{3})?", buyer_tax)),
        "Thiếu hoặc sai định dạng mã số thuế người mua",
    ))
    subtotal = getattr(invoice, "subtotal", None)
    vat_amount = getattr(invoice, "vat_amount", None)
    rate = getattr(invoice, "vat_rate", None)
    rate_value = Decimal(str(rate)) if rate is not None else None
    if rate_value is not None:
        supported_rates = {Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10")}
        rate_valid = rate_value.is_finite() and rate_value in supported_rates
        tests.append((
            "VAT-RATE",
            rate_valid,
            "VAT rate must be one of 0, 5, 8 or 10 percent",
        ))
    if subtotal is not None and vat_amount is not None and invoice.total_amount is not None:
        # Absolute tolerance for VND values; does not certify legal validity.
        valid = abs(Decimal(str(subtotal)) + Decimal(str(vat_amount)) - Decimal(str(invoice.total_amount))) < 2
        tests.append(("ARITH", valid, "Tổng tiền không bằng tiền trước thuế + VAT"))
    if subtotal is not None and vat_amount is not None and rate_value is not None:
        if rate_value.is_finite():
            expected = Decimal(str(subtotal)) * rate_value / 100
            valid = abs(expected - Decimal(str(vat_amount))) < 2
        else:
            valid = False
        tests.append(("VAT-ARITH", valid, "Tiền VAT không khớp thuế suất trên tiền trước thuế (hóa đơn một thuế suất)"))
    if items is not None:
        amounts = [getattr(item, "amount", item.get("amount") if isinstance(item, dict) else None) for item in items]
        if not items or subtotal is None or any(amount is None for amount in amounts):
            valid = False
        else:
            item_total = sum((Decimal(str(amount)) for amount in amounts), Decimal("0"))
            valid = abs(item_total - Decimal(str(subtotal))) < 2
        tests.append(("ITEM-SUM", valid, "Tổng các dòng hàng không khớp tiền trước thuế"))
    else:
        tests.append(("ITEM-SUM", False, "Thiếu danh sách dòng hàng để đối chiếu tiền trước thuế"))
    return tests


# Task bridges: keep the main parser contracts; new finance observations are independent.
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from .invoice_financials import current_document_text
_coverage_observations=ContextVar('ocr_extraction_coverage',default=None)
MAX_OCR_PAGES=12
MAX_OCR_TEXT_CHARS=60_000
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


def _coverage_finding(code, reason, **details):
    observations = _coverage_observations.get()
    if observations is not None:
        finding = {'code': code, 'reason': reason, 'incomplete': True,
                   'requires_review': True, **details}
        if finding not in observations:
            observations.append(finding)


@contextmanager
def capture_extraction_coverage():
    observations = []
    token = _coverage_observations.set(observations)
    try:
        yield observations
    finally:
        _coverage_observations.reset(token)


def currency_observation(raw):
    """Use explicit printed currency labels; never infer USD from a '$' sign."""
    plain=_plain(raw or '')
    codes=set(re.findall(r'\b(?:don vi tien te|tien te|currency|dvtte)\s*(?:\([^\n)]{0,35}\)\s*)?[:：]?\s*([a-z]{3})\b',plain))
    if len(codes)>1:return {'state':'conflicting','codes':sorted(code.upper() for code in codes)}
    if codes:return {'state':'observed','code':next(iter(codes)).upper()}
    return {'state':'not_observed'}


def _observed_vat_rates(lines):
    rates = set()
    for _original, plain in lines:
        for match in re.finditer(r'\b(?:thue\s+suat(?:\s+gtgt)?|vat\s*rate)\s*[:;]?\s*(\d{1,2}(?:[.,]\d+)?)\s*%', plain):
            rate = Decimal(match[1].replace(',', '.'))
            if 0 <= rate <= 100:
                rates.add(rate)
    return rates


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


def _spatial_quantity(cell: str) -> Decimal | None:
    value = " ".join((cell or "").split()).strip()
    if re.fullmatch(r"\d{1,8}(?:[.,]\d{1,4})?", value):
        # Quantity separators are decimal marks, not VND thousands groups.
        return Decimal(value.replace(',', '.'))
    return None


_legacy_main_total_recovery=_recover_total_from_image
def _recover_total_from_image(image) -> Decimal | None:
    """Recover only from a labelled, spatially bounded cell and two OCR reads.

    Dense invoices can put VAT and payable totals in adjacent columns. The old
    fixed 65%/82% crops mixed these cells and cut the rightmost printed digits.
    Their rejection was safe but prevented a valid total from being extracted.
    """
    from PIL import Image,ImageOps
    had_label=False
    bounded_attempted=False
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
            bounded_attempted=True
            attempts+=1
            crop=ImageOps.autocontrast(image.crop(bounds).convert('L'))
            if crop.width*crop.height<=1_000_000:crop=crop.resize((crop.width*3,crop.height*3),Image.Resampling.LANCZOS)
            crop=ImageOps.expand(crop,border=8,fill='white')
            values=[]
            for mode in (7,13):
                try:
                    literal=pytesseract.image_to_string(crop,lang='eng',config=f'--psm {mode} -c tessedit_char_whitelist=0123456789.,%',timeout=12)
                except (pytesseract.TesseractError,RuntimeError):continue
                value=_decimal_money(literal.strip())
                if value is not None:values.append(value)
            if len(values)==2 and values[0]==values[1]:findings.add(values[0])
            if attempts>=3:break
        if len(findings)>1:return None
        if len(findings)==1:return next(iter(findings))
    return None if bounded_attempted else _legacy_main_total_recovery(image)


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
