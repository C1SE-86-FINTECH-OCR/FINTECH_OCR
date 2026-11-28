from dataclasses import asdict, dataclass
from io import BytesIO
from statistics import median



@dataclass(frozen=True)
class TextBox:
    text: str
    polygon: tuple[tuple[float, float], ...]
    score: float | None = None

    @property
    def word(self):
        xs, ys = zip(*self.polygon)
        return min(xs), min(ys), max(xs), max(ys), self.text


def rectangle(text, x0, y0, x1, y1, score=None):
    return TextBox(text, ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), score)


def reading_rows(boxes):
    lines = []
    for index in sorted(range(len(boxes)), key=lambda i: boxes[i].word[1]):
        _, top, _, bottom, _ = boxes[index].word
        center = (top + bottom) / 2
        if lines:
            recent = [boxes[i].word for i in lines[-1]]
            limit = max(2, min(bottom - top, median(w[3] - w[1] for w in recent)) * 0.45)
            if abs(center - median((w[1] + w[3]) / 2 for w in recent)) <= limit:
                lines[-1].append(index)
                continue
        lines.append([index])
    return [sorted(row, key=lambda i: boxes[i].word[0]) for row in lines]


def tesseract_boxes(image):
    from app import extraction as parser
    ocr = parser.pytesseract
    data = ocr.image_to_data(image, lang="vie+eng", config="--psm 11",
                             output_type=ocr.Output.DICT, timeout=35)
    boxes = []
    for i, value in enumerate(data["text"]):
        text = value.strip()
        if text:
            x, y, width, height, conf = (data[key][i] for key in ("left", "top", "width", "height", "conf"))
            score = float(conf)
            boxes.append(rectangle(text, x, y, x + width, y + height, score / 100 if score >= 0 else None))
    return boxes


def paddle_result_boxes(payload):
    core = payload.get("res", payload)
    result = []
    for text, polygon, score in zip(core["rec_texts"], core["rec_polys"], core["rec_scores"], strict=True):
        if text.strip():
            result.append(TextBox(text.strip(), tuple((float(x), float(y)) for x, y in polygon), float(score)))
    return result


def paddle_reader(det, rec, device, threads):
    # A local directory is mandatory for both active models. Disabled
    # submodules must not ask PaddleX to fetch their weights.
    import paddle
    from paddleocr import PaddleOCR
    import numpy as np

    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det", text_detection_model_dir=str(det),
        text_recognition_model_name="latin_PP-OCRv5_mobile_rec", text_recognition_model_dir=str(rec),
        use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
        # Paddle 3.3.0 CPU on Windows hits an unsupported PIR attribute in
        # the oneDNN detector path with the upstream PP-OCRv5 mobile weights.
        device=device, cpu_threads=threads, enable_mkldnn=False, text_recognition_batch_size=1,
    )

    def recognize(image):
        predictions = list(ocr.predict(np.asarray(image)[:, :, ::-1].copy()))
        if len(predictions) != 1:
            raise ValueError("Expected one PaddleOCR result for one page")
        return paddle_result_boxes(predictions[0].json)

    return recognize, paddle.__version__


def page_result(number, size, source, boxes):
    from app import extraction as parser
    rows = reading_rows(boxes)
    text = "\n".join(" ".join(boxes[i].text for i in row) for row in rows)
    words = [box.word for box in boxes]
    items = parser._extract_spatial_table_items(words)
    table_method = "aligned-columns"
    if not items:
        items = parser._extract_staggered_table_items(words)
        table_method = "staggered-columns"
    if not items:
        items = parser._extract_ocr_line_items(text)
        table_method = "text-fallback" if items else None
    return {
        "page": number, "size": size, "source": source,
        "coordinate_space": "rendered OCR input pixels" if source == "ocr" else "PyMuPDF page points",
        "text_boxes": [asdict(box) for box in boxes], "reading_rows": rows,
        "table_method": table_method, "items": items,
    }, text


def extract_with_layout(data, ext, recognize, max_pages):
    from app import extraction as parser
    import fitz
    from PIL import Image, ImageOps

    def raster(number, image):
        if image.width * image.height > 30_000_000:
            raise ValueError("Raster page exceeds 30 megapixels")
        image = ImageOps.exif_transpose(image).convert("RGB")
        # Both engines receive exactly the same raster pixels.
        return page_result(number, image.size, "ocr", recognize(image))

    if ext == "pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            page_count = len(pdf)
            pages = []
            for index in range(min(page_count, max_pages)):
                page = pdf[index]
                words = page.get_text("words", sort=True)
                if sum(c.isalnum() for word in words for c in word[4]) > 40:
                    boxes = [rectangle(text, x0, y0, x1, y1) for x0, y0, x1, y1, text, *_ in words]
                    pages.append(page_result(index + 1, (page.rect.width, page.rect.height), "pdf-text", boxes))
                else:
                    if page.rect.width * page.rect.height * 4 > 30_000_000:
                        raise ValueError("PDF page exceeds the raster size limit at scale 2")
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                        pages.append(raster(index + 1, image))
    else:
        page_count = 1
        with Image.open(BytesIO(data)) as image:
            pages = [raster(1, image)]

    fields = parser.extract_fields("\n".join(text for _, text in pages), ext)
    items = []
    for page, _ in pages:
        for item in page["items"]:
            item["line_no"] = len(items) + 1
            items.append(item)
    return fields, items, {
        "total_pages": page_count, "pages_processed": len(pages),
        "truncated": page_count > len(pages), "pages": [page for page, _ in pages],
    }
