"""Experimental coordinate parser. No imports from the upload service."""

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
import re
from statistics import median

from app import extraction as baseline
from .layout import reading_rows, rectangle


ALIASES = {
    "ordinal": r"stt|no\.?|#",
    "description": r"ten hang(?: hoa)?|hang hoa(?: dich vu)?|dien giai|mo ta|description|item(?: name)?|product",
    "unit": r"don vi tinh|dvt|unit|uom",
    "quantity": r"so luong|soluong|sl|qty|quantity",
    "unit_price": r"don gia|unit price|price",
    "amount": r"thanh tien|line total|amount|net amount",
    "vat_rate": r"thue suat(?: gtgt)?|vat rate|vat %|vat \(%\)|tax rate",
    "vat_amount": r"tien thue|vat amount|tax amount",
}
STOP = re.compile(
    r"^(?:sub\s*total|total(?: amount| payment| due)?|amount due|grand total|"
    r"cong tien hang|tong(?: cong| tien| thanh toan)|tien truoc thue|payment method|"
    r"tien khach dua|tien thua|amount tendered|cash received|change|"
    r"tien thue(?: gtgt)?|thue suat(?: gtgt)?|vat(?: amount| rate)?|tax(?: amount| rate)?)"
    r"(?:$|[:\s]+\d|:)"
)
CONTINUED = re.compile(r"^(?:trang tiep theo|tiep theo|continued(?: on next page)?|carry forward)(?:$|[\s:])")
METADATA = re.compile(
    r"^(?:ngay|date|nguoi ban|nguoi mua|ma so thue|dien thoai|dia chi|"
    r"invoice no|seller|buyer|address|phone|ma don hang|ma giao dich|so giao dich|"
    r"transaction id|order id|page \d+|trang \d+)\b"
)


@dataclass(frozen=True)
class Header:
    bottom: float
    # centers normalized to page width, for continuation pages
    centers: dict[str, float]
    indices: tuple[int, ...]


def plain(text):
    return " ".join(baseline._plain(text).split()).strip(" :|;")


def center(box):
    x0, y0, x1, y1, _ = box.word
    return (x0 + x1) / 2, (y0 + y1) / 2


def height(boxes):
    return max(3.0, median(b.word[3] - b.word[1] for b in boxes) if boxes else 3.0)


def text_of(boxes, indices):
    return " ".join(boxes[i].text for i in indices)


def header_spans(boxes, h):
    """Produce exact header-label spans on local baselines without crossing columns."""
    spans = []
    compiled = {name: re.compile(pattern) for name, pattern in ALIASES.items()}
    x_order = sorted(range(len(boxes)), key=lambda i: boxes[i].word[0])
    for index, first in enumerate(x_order):
        x, y = center(boxes[first])
        local = [first]
        for other in x_order[index + 1:index + 28]:
            a, b = center(boxes[other])
            if a - x > 10 * h:
                break
            if abs(b - y) <= 0.65 * h:
                local.append(other)
        for n in range(1, min(len(local), 5) + 1):
            ids = tuple(local[:n])
            if any(boxes[j].word[0] - boxes[i].word[2] > 1.8 * h for i, j in zip(ids, ids[1:])):
                break
            label = plain(text_of(boxes, ids))
            for role, pattern in compiled.items():
                if pattern.fullmatch(label):
                    spans.append((role, ids))
    return spans


def find_header(boxes, width, h):
    spans = header_spans(boxes, h)
    for _, description in (entry for entry in spans if entry[0] == "description"):
        y = median(center(boxes[i])[1] for i in description)
        # A header may span multiple physical baselines. Require distinct
        # label spans and at least two separate numeric roles.
        band = [(k, ids) for k, ids in spans if abs(median(center(boxes[i])[1] for i in ids) - y) <= 3.1 * h]
        roles = {"description": description}
        used = set(description)
        for role in ("vat_rate", "vat_amount", "unit_price", "amount", "quantity", "unit", "ordinal"):
            candidates = [ids for k, ids in band if k == role and not used.intersection(ids)]
            if candidates:
                ids = min(candidates, key=lambda items: (abs(median(center(boxes[i])[1] for i in items) - y), -len(items)))
                roles[role] = ids
                used.update(ids)
        if "amount" not in roles or not ({"unit_price", "quantity"} & roles.keys()):
            continue
        centers = {
            k: (min(boxes[i].word[0] for i in ids) + max(boxes[i].word[2] for i in ids)) / (2 * width)
            for k, ids in roles.items()
        }
        # Avoid accepting text blocks with overlapping monetary columns.
        positions = sorted(centers.values())
        if any((b - a) * width < 0.8 * h for a, b in zip(positions, positions[1:])):
            continue
        return Header(max(boxes[i].word[3] for i in used), centers, tuple(sorted(used)))
    return None


def column_index(header, x, width):
    ordered = sorted(header.centers, key=header.centers.get)
    x = x / width
    for left, right in zip(ordered, ordered[1:]):
        a, b = header.centers[left], header.centers[right]
        # Description and ordinal cells are typically left-aligned, unlike
        # centered titles. Allow the description to extend towards its gutter.
        if left == "ordinal" and right == "description":
            boundary = a + 0.20 * (b - a)
        elif left == "description":
            boundary = a + 0.76 * (b - a)
        else:
            boundary = (a + b) / 2
        if x < boundary:
            return left
    return ordered[-1]


def number(text, role):
    text = text.strip()
    if role == "vat_rate":
        match = re.fullmatch(r"(\d{1,2}(?:[.,]\d+)?|100)\s*%", text)
        return Decimal(match[1].replace(",", ".")) if match else None
    if role == "quantity":
        return Decimal(text.replace(",", ".")) if re.fullmatch(r"\d{1,8}(?:[.,]\d{1,3})?", text) else None
    if not re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)*|\d{1,3}(?:\s+\d{3})+)", text):
        return None
    value = text.replace(" ", "")
    for separator in (".", ","):
        if value.count(separator) > 1 and value[-3:].isdigit() and re.fullmatch(
            rf"[+-]?\d{{1,3}}(?:{re.escape(separator)}\d{{3}})+", value
        ):
            return Decimal(value.replace(separator, ""))
    if "." in value and "," in value:
        decimal_sep = "." if value.rfind(".") > value.rfind(",") else ","
        groups, tail = value.rsplit(decimal_sep, 1)
        thousands = "," if decimal_sep == "." else "."
        if not re.fullmatch(rf"[+-]?\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+", groups) or len(tail) > 2:
            return None
        return Decimal(groups.replace(thousands, "") + "." + tail)
    if re.fullmatch(r"[+-]?\d+[.,]\d{3}", value):
        return Decimal(value.replace(",", "").replace(".", ""))
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d{1,2})?", value):
        return Decimal(value.replace(",", "."))
    return None


def group_cells(boxes, indices, header, width):
    cells = {}
    for i in sorted(indices, key=lambda index: boxes[index].word[0]):
        role = column_index(header, center(boxes[i])[0], width)
        cells.setdefault(role, []).append(i)
    return cells


def cell_text(boxes, cells, role):
    return text_of(boxes, cells.get(role, ())).strip(" |")


def cell_number(boxes, cells, role):
    return number(cell_text(boxes, cells, role), role)


def row_evidence(boxes, cells):
    return {
        role: [{"text": boxes[i].text, "polygon": boxes[i].polygon, "ocr_score": boxes[i].score} for i in ids]
        for role, ids in cells.items()
    }


def parse_grid(boxes, width, header, h):
    physical = [[i for i in row if center(boxes[i])[1] > header.bottom] for row in reading_rows(boxes)]
    body, closed = [], False
    for row in physical:
        if not row:
            continue
        text = plain(text_of(boxes, row))
        if CONTINUED.match(text) or re.match(r"^(?:page|trang)\s+\d", text):
            break
        if STOP.match(text):
            closed = True
            break
        if not METADATA.match(text):
            body.append(row)
    # Anchor on a whole amount cell. For staggered baselines, associate
    # neighboring quantity and description cells more loosely than initial
    # OCR line clustering, while limiting ownership to one logical row.
    anchors = []
    for row in body:
        cells = group_cells(boxes, row, header, width)
        if cell_number(boxes, cells, "amount") is not None:
            anchors.append(median(center(boxes[i])[1] for i in cells["amount"]))
    owned = [[] for _ in anchors]
    orphan_descriptions = []
    for row in body:
        row_y = median(center(boxes[i])[1] for i in row)
        if anchors:
            nearest = min(range(len(anchors)), key=lambda i: abs(anchors[i] - row_y))
            if abs(anchors[nearest] - row_y) <= 0.82 * h:
                owned[nearest].extend(row)
                continue
        cells = group_cells(boxes, row, header, width)
        if set(cells) == {"description"}:
            orphan_descriptions.append((row_y, cells["description"]))

    items = []
    for i, ids in enumerate(owned):
        cells = group_cells(boxes, ids, header, width)
        name = cell_text(boxes, cells, "description")
        amount = cell_number(boxes, cells, "amount")
        quantity = cell_number(boxes, cells, "quantity")
        price = cell_number(boxes, cells, "unit_price")
        ordinal = cell_text(boxes, cells, "ordinal")
        if not re.search(r"[^\W\d_]", name) or amount is None or not (
            quantity is not None or price is not None or ordinal.isdecimal()
        ):
            continue
        # A continuation belongs to the preceding row only when it remains
        # closer to that row than the next monetary row.
        next_y = anchors[i + 1] if i + 1 < len(anchors) else float("inf")
        for y, words in orphan_descriptions:
            if anchors[i] < y <= min(anchors[i] + 2.7 * h, (anchors[i] + next_y) / 2):
                name += " " + text_of(boxes, words)
                cells["description"].extend(words)
        items.append({
            "description": name, "unit": cell_text(boxes, cells, "unit") or None, "quantity": quantity,
            "unit_price": price, "amount": amount, "vat_rate": cell_number(boxes, cells, "vat_rate"),
            "vat_amount": cell_number(boxes, cells, "vat_amount"), "evidence": row_evidence(boxes, cells),
        })
    rejected = len(anchors) - len(items)
    return items, closed, rejected


def bill_items(boxes):
    """Use classified bill context and rightmost price candidates before totals."""
    candidates = []
    h = height(boxes)
    for row in reading_rows(boxes):
        text = text_of(boxes, row)
        normalized = plain(text)
        if STOP.match(normalized):
            break
        if METADATA.match(normalized):
            continue
        # Require printed money formatting or an explicitly spaced amount
        # cell. Do not turn transaction IDs or plain model numbers into bills.
        if not re.search(r"\s(?:\d{1,3}(?:[.,]\d{3})+|\d+[.,]\d{2})\s*$", text):
            if len(row) < 2 or not re.fullmatch(r"\d{1,9}", boxes[row[-1]].text):
                continue
            if boxes[row[-1]].word[0] - boxes[row[-2]].word[2] < 1.4 * h:
                continue
        for item in baseline._extract_receipt_line_items(text):
            candidates.append({**item, "vat_rate": None, "vat_amount": None,
                               "evidence": row_evidence(boxes, {"receipt_row": row})})
    return candidates


def findings_for_items(items):
    findings = []
    for item in items:
        for role, parts in item.get("evidence", {}).items():
            scores = [part["ocr_score"] for part in parts if part.get("ocr_score") is not None]
            if scores and min(scores) < 0.85:
                findings.append({"code": "LOW_OCR_CONFIDENCE", "page": item.get("page"),
                                 "line_no": item.get("line_no"), "field": role,
                                 "min_word_score": min(scores), "possible_cause": "ocr_recognition"})
        for role in ("quantity", "unit_price", "amount"):
            evidence = item.get("evidence", {}).get(role, [])
            if item.get(role) is None and evidence:
                findings.append({"code": "CELL_PARSE_UNCERTAIN", "page": item.get("page"),
                                 "line_no": item.get("line_no"), "field": role})
        count, price, amount = (item.get(field) for field in ("quantity", "unit_price", "amount"))
        if None not in (count, price, amount) and abs(Decimal(str(count)) * Decimal(str(price)) - Decimal(str(amount))) >= 2:
            findings.append({
                "code": "LINE_ARITHMETIC_MISMATCH", "page": item.get("page"),
                "line_no": item.get("line_no"), "possible_cause": "ocr_character_or_cell_assignment",
                "reread_roles": ["quantity", "unit_price", "amount"],
            })
        rate, tax = item.get("vat_rate"), item.get("vat_amount")
        if None not in (amount, rate, tax) and abs(amount * rate / 100 - tax) >= 2:
            findings.append({"code": "LINE_VAT_MISMATCH", "page": item.get("page"),
                             "line_no": item.get("line_no"), "possible_cause": "ocr_character_or_cell_assignment"})
    return findings


def parse_document_pages(pages, doc_type):
    table_rows, scan_pages, findings = [], [], []
    carried = None
    for page_number, source, size, boxes in pages:
        h, width = height(boxes), size[0]
        header = find_header(boxes, width, h)
        continuation = False
        inferred = None
        if header is None and carried:
            next_header = Header(0, carried.centers, ())
            inferred = parse_grid(boxes, width, next_header, h)
            if inferred[0]:
                header, continuation = next_header, True
        if header:
            items, closed, rejected = inferred if continuation else parse_grid(boxes, width, header, h)
            carried = header if items and not closed else None
            if rejected:
                findings.append({"code": "UNRESOLVED_ANCHOR", "page": page_number, "count": rejected})
        else:
            carried = None
            items = bill_items(boxes) if doc_type == "bill" else []
        for item in items:
            item["page"] = page_number
            item["line_no"] = len(table_rows) + 1
            table_rows.append(item)
        scan_pages.append({
            "page": page_number, "source": source, "size": size,
            "coordinate_space": "processed raster pixels" if source == "ocr" else "PDF points",
            "boxes": row_evidence(boxes, {"words": range(len(boxes))})["words"],
            "table_found": bool(header or items),
            "continued_columns": continuation, "header_columns": header.centers if header else {},
            "header_evidence": row_evidence(boxes, {"header": header.indices})["header"] if header else [],
            "line_numbers": [r["line_no"] for r in items],
        })
    if not table_rows and doc_type in {"bill", "einvoice"}:
        findings.append({"code": "TABLE_NO_CONFIRMED_ROWS", "possible_cause": "missing_table_or_layout_assignment"})
    return table_rows, scan_pages, findings + findings_for_items(table_rows)


def prepared_image(image):
    from PIL import ImageOps
    if image.width * image.height > 30_000_000:
        raise ValueError("Experimental OCR page exceeds pixel limit")
    gray = ImageOps.exif_transpose(image).convert("L")
    return baseline._deskew_small_angle(ImageOps.autocontrast(gray, cutoff=1)).convert("RGB")


def tesseract_page(image):
    prepared = prepared_image(image)
    ocr = baseline.pytesseract
    result = ocr.image_to_data(prepared, lang="vie+eng", config="--psm 11", timeout=35, output_type=ocr.Output.DICT)
    boxes = []
    for i, raw in enumerate(result["text"]):
        text = raw.strip()
        if text:
            x, y, w, h, conf = (result[key][i] for key in ("left", "top", "width", "height", "conf"))
            score = float(conf)
            boxes.append(rectangle(text, x, y, x + w, y + h, score / 100 if score >= 0 else None))
    return prepared.size, boxes


def reread_numeric_cell(prepared, evidence, role):
    from PIL import ImageOps
    from math import ceil, floor

    polygons = [point for part in evidence for point in part["polygon"]]
    if not polygons:
        return None
    xs, ys = zip(*polygons)
    crop = prepared.crop((max(0, floor(min(xs) - 1)), max(0, floor(min(ys) - 1)),
                          ceil(max(xs) + 1), ceil(max(ys) + 1)))
    crop = ImageOps.expand(crop.resize((crop.width * 2, crop.height * 2)), border=12, fill="white")
    ocr = baseline.pytesseract
    try:
        raw = ocr.image_to_string(
            crop, lang="vie+eng", config="--psm 7 -c tessedit_char_whitelist=0123456789.,-",
            timeout=5,
        ).strip()
    except (RuntimeError, ocr.TesseractError):
        return {"status": "reread_failed"}
    return {"text": raw, "value": number(raw, role), "region": crop.size}


def attach_reread_evidence(data, ext, findings, items, diagnostics):
    """Record bounded OCR alternatives for review without overwriting values."""
    import pymupdf as fitz
    from PIL import Image

    raster_pages = {p["page"] for p in diagnostics if p["source"] == "ocr"}
    rows = {r["line_no"]: r for r in items}
    selected = [f for f in findings if f["code"] == "LINE_ARITHMETIC_MISMATCH"
                and f["page"] in raster_pages and rows.get(f["line_no"], {}).get("evidence")][:2]
    if not selected:
        return

    def inspect(number, image):
        prepared = prepared_image(image)
        for finding in (f for f in selected if f["page"] == number):
            item = rows[finding["line_no"]]
            finding["reread"] = {
                role: reread_numeric_cell(prepared, item["evidence"].get(role, []), role)
                for role in finding["reread_roles"]
            }

    if ext == "pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            for number in sorted({f["page"] for f in selected}):
                pixmap = pdf[number - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                    inspect(number, image)
    else:
        with Image.open(BytesIO(data)) as image:
            inspect(1, image)


def extract_v3(data, ext, max_pages):
    import pymupdf as fitz
    from PIL import Image

    raw, method = baseline.text_from_file(data, ext)
    # Preserve the production field extractor exactly, independent of table
    # findings and the extra OCR passes used for cell coordinates.
    fields = baseline.extract_fields(raw, ext)
    original_items = baseline.extract_line_items(data, ext, raw)
    pages = []
    def add_raster(number, image):
        size, boxes = tesseract_page(image)
        pages.append((number, "ocr", size, boxes))

    if ext == "pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            count = len(pdf)
            for i in range(min(count, max_pages)):
                page = pdf[i]
                words = page.get_text("words", sort=True)
                if sum(c.isalnum() for w in words for c in w[4]) >= 25:
                    boxes = [rectangle(text, x0, y0, x1, y1) for x0, y0, x1, y1, text, *_ in words]
                    pages.append((i + 1, "pdf-text", (page.rect.width, page.rect.height), boxes))
                else:
                    if page.rect.width * page.rect.height * 4 > 30_000_000:
                        raise ValueError("Experimental PDF raster page exceeds pixel limit")
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    with Image.open(BytesIO(pix.tobytes("png"))) as image:
                        add_raster(i + 1, image)
    else:
        count = 1
        with Image.open(BytesIO(data)) as image:
            add_raster(1, image)

    items, diagnostics, findings = parse_document_pages(pages, fields["document_type"])
    choice = "coordinate-table"
    # If the candidate has less structural coverage, retain the old result.
    # In either case validate the actual values, without filling from totals.
    if fields["document_type"] == "unknown" or len(items) < len(original_items):
        choice = "unchanged-baseline"
        items = original_items
        findings += findings_for_items(items) + [{"code": "BASELINE_TABLE_RETAINED"}]
    attach_reread_evidence(data, ext, findings, items, diagnostics)
    return fields, items, {
        "source": method, "raw_text": raw, "total_pages": count, "pages_processed": len(pages),
        "truncated": count > len(pages), "pages": diagnostics, "table_choice": choice,
        "findings": findings, "requires_review": any(f["code"] != "BASELINE_TABLE_RETAINED" for f in findings),
        "vat_rates_seen": sorted({r["vat_rate"] for r in items if r.get("vat_rate") is not None}),
    }
