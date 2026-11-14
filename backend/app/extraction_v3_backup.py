"""FINTECH OCR: offline OCR, conservative invoice field extraction, basic validation.

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
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _xml_text(data: bytes) -> str:
    # ElementTree does not fetch external entities; reject DTD/ENTITY explicitly.
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise ValueError("XML có DTD/entity không được chấp nhận")
    root = ET.fromstring(data)

    def local_tag(tag):
        return tag.rsplit("}", 1)[-1]

    def node_text(parent, tag):
        for node in parent.iter():
            if local_tag(node.tag).lower() == tag.lower() and node.text and node.text.strip():
                return node.text.strip()
        return None

    lines = []
    number = node_text(root, "SHDon")
    issued = node_text(root, "NLap")
    total = node_text(root, "TgTTTBSo")
    if number:
        lines.append("Số hóa đơn: " + number)
    if issued:
        lines.append("Ngày: " + issued)
    for seller_node in root.iter():
        if local_tag(seller_node.tag) == "NBan":
            seller_name = node_text(seller_node, "Ten")
            seller_tax = node_text(seller_node, "MST")
            if seller_name:
                lines.append("Đơn vị bán hàng: " + seller_name)
            if seller_tax:
                lines.append("Mã số thuế: " + seller_tax)
            break
    if total:
        lines.append("Tổng tiền thanh toán: " + total)
    # Keep other human-readable text for audit/troubleshooting.
    content = " ".join(t.strip() for t in root.itertext() if t and t.strip())
    return ("\n".join(lines) + "\n" + content)[:60000]


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


def _ocr_image(image) -> str:
    image = _prepare_image(image)
    # PSM 11 works well on invoices with mixed column layouts and small labels.
    text = pytesseract.image_to_string(image, lang="vie+eng", config="--psm 11", timeout=35)
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
    if ext.lower() == "xml" or any(x in low for x in (
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
    fields = {
        "invoice_number": number,
        "invoice_date": issued,
        "seller_name": seller,
        "seller_tax_code": seller_tax,
        "total_amount": total,
        "vat_rate": vat_rate,
        "qr_url": _qr_url(raw or ""),
        "document_type": classify(ext, raw or ""),
    }
    # Not a calibrated AI/OCR probability, only a ratio of five populated fields.
    essential = ("invoice_number", "invoice_date", "seller_name", "seller_tax_code", "total_amount")
    fields["confidence_score"] = round(sum(fields[k] is not None for k in essential) / 5, 2)
    return fields


def validate(invoice) -> list[tuple[str, bool, str]]:
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
    if (getattr(invoice, "subtotal", None) is not None and
            getattr(invoice, "vat_amount", None) is not None and
            invoice.total_amount is not None):
        valid = abs(float(invoice.subtotal) + float(invoice.vat_amount) - float(invoice.total_amount)) < 2
        tests.append(("ARITH", valid, "Tổng tiền không bằng tiền trước thuế + VAT"))
    return tests
