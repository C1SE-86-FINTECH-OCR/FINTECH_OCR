"""Bounded, page-local PDF extraction for the existing local OCR branch."""
from time import monotonic
import re

from . import extraction as parser
from .invoice_financials import PAGE_FINANCIAL_SUMMARY as _PAGE_SUMMARY


# The former document limits are batch limits. Raster memory is still bounded
# to one page; the document also has explicit CPU, text and result-size bounds.
BATCH_PAGES = parser.MAX_OCR_PAGES
BATCH_CHARACTERS = parser.MAX_OCR_TEXT_CHARS
MAX_DOCUMENT_PAGES = 120
MAX_DOCUMENT_CHARACTERS = 600_000
MAX_DOCUMENT_SECONDS = 300
MAX_DOCUMENT_WORDS = 60_000
MAX_DOCUMENT_ITEMS = 10_000

_FINAL_SUMMARY = re.compile(
    r'\b(?:tong\s+tien\s+(?:phai\s+)?thanh\s+toan|tong\s+cong\s+thanh\s+toan|'
    r'tong\s+thanh\s+toan|grand\s+total|amount\s+due|total\s+payment|payable\s+amount)\b')
_PAGE_NUMBER = re.compile(r'^\s*(?:trang|page)\s+\d+\s*(?:(?:/|of|tren)\s*\d+)?\s*$', re.I)


def select_pdf_page_source(page):
    """Choose native words or the existing raster OCR, once per PDF page.

    The thresholds are routing heuristics, not a field-accuracy score. Image
    positions and native word positions are in the unrotated page frame.
    The selection step does not rasterize the page or invoke OCR.
    """
    from math import isfinite
    from unicodedata import category
    import fitz

    frame = page.rect * page.derotation_matrix
    words = [tuple(word[:5]) for word in page.get_text('words', sort=True)
             if len(word) >= 5 and str(word[4]).strip()
             and all(isfinite(float(v)) for v in word[:4])
             and word[2] > word[0] and word[3] > word[1]]
    text = ' '.join(str(word[4]) for word in words)
    nonspace = [char for char in text if not char.isspace()]
    alnum = sum(char.isalnum() for char in nonspace)
    damaged = sum(char == '\ufffd' or category(char) in ('Cc', 'Co', 'Cs')
                  for char in nonspace)
    cid_tokens = len(re.findall(r'\(cid:\d+\)', text, re.I))
    selection = {'source': 'pdf-text', 'reason': 'usable_native_words',
                 'native_alnum': alnum, 'native_word_count': len(words),
                 'damaged_characters': damaged, 'cid_tokens': cid_tokens,
                 'uncovered_image_regions': 0}

    def use_ocr(reason):
        selection.update(source='ocr', reason=reason)
        return words, (float(frame.width), float(frame.height)), selection

    if alnum <= 40:
        return use_ocr('native_text_sparse')
    if (damaged >= 2 and damaged / max(1, len(nonspace)) >= .02
            or cid_tokens >= 2 or alnum / max(1, len(nonspace)) < .5):
        return use_ocr('native_text_damaged')

    # A short native header/footer can coexist with an image containing the
    # actual invoice. Ignore logos and QR-sized images; only substantial
    # regions with weak native coverage trigger the existing full-page OCR.
    # Searchable scans with distributed native words can still stay native.
    try:
        images = page.get_image_info(hashes=False)
    except (RuntimeError, ValueError, TypeError):
        return use_ocr('image_coverage_unknown')
    area = frame.width * frame.height
    for image in images:
        region = fitz.Rect(image['bbox']) & frame
        if (region.is_empty or area <= 0 or region.get_area() < .25 * area
                or region.width < .25 * frame.width
                or region.height < .25 * frame.height):
            continue
        inside = [(word, (word[1] + word[3]) / 2) for word in words
                  if region.x0 <= (word[0] + word[2]) / 2 <= region.x1
                  and region.y0 <= (word[1] + word[3]) / 2 <= region.y1]
        observed = sum(char.isalnum() for word, _ in inside for char in word[4])
        bands = {min(3, int(4 * (y - region.y0) / region.height)) for _, y in inside}
        if observed <= 40 or len(bands) < 2 or bands == {0, 3}:
            selection['uncovered_image_regions'] += 1
    if selection['uncovered_image_regions']:
        return use_ocr('image_region_without_text')
    return words, (float(frame.width), float(frame.height)), selection


def _item_words(words):
    # Filter only parser input; retain the unmodified OCR boxes as evidence.
    retained = []
    for row in parser._spatial_lines(words):
        line = parser._plain(' '.join(str(word[4]) for word in row))
        if not (_PAGE_SUMMARY.search(line) or _PAGE_NUMBER.fullmatch(line)):
            retained.extend(row)
    return retained


def _item_text(text):
    return '\n'.join(line for line in text.splitlines()
                     if not (_PAGE_SUMMARY.search(parser._plain(line))
                             or _PAGE_NUMBER.fullmatch(parser._plain(line))))


def _document_fields(pages, total_pages, findings):
    raw = '\n\f\n'.join(page['raw_text'] for page in pages)
    fields = parser.extract_fields(raw, 'pdf')
    lines_by_page = [(page['page'], parser._lines(parser.current_document_text(page['raw_text']))) for page in pages]
    final_totals = []
    for number, lines in lines_by_page:
        for _, plain in lines:
            match = _FINAL_SUMMARY.search(plain)
            if match and not _PAGE_SUMMARY.search(plain):
                amount = parser._decimal_money(plain[match.end():].strip(' :;='))
                if amount is not None:
                    final_totals.append((number, amount))
    # Reuse the same label/cell linker as Final on already recognized boxes.
    # PDF reading order may put a right-hand zero on its own text line; this
    # consumes existing source evidence only, with no extra OCR pass.
    for page in pages:
        if not page.get('boxes'):
            continue
        try:
            from tools.ocr_benchmark.layout import TextBox
            from tools.ocr_benchmark.pipeline_v5 import Read
            from tools.ocr_benchmark.pipeline_v4 import lines_of
            from tools.ocr_benchmark.document_fields_v8_final import monetary_observations
            from tools.ocr_benchmark.table_v3 import row_evidence
            boxes = [TextBox(box['text'], tuple(map(tuple, box['polygon'])), box.get('ocr_score'))
                     for box in page['boxes'] if box.get('text') and box.get('polygon')]
            if not boxes:
                continue
            size = (max(point[0] for box in boxes for point in box.polygon),
                    max(point[1] for box in boxes for point in box.polygon))
            read = Read('existing-pdf-source', boxes, [line.ids for line in lines_of(boxes)], size, {})
            for observation in monetary_observations(read):
                if observation['key'] != 'total_amount':
                    continue
                final_totals.append((page['page'], observation['value']))
                findings.append({'code': 'PDF_MONETARY_CELL_LINKED', 'field': 'total_amount',
                                 'page': page['page'], 'value': str(observation['value']),
                                 **row_evidence(boxes, {'label': observation['label_ids'], 'value': observation['ids']})})
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            findings.append({'code': 'PDF_FINANCIAL_LAYOUT_UNAVAILABLE', 'page': page['page'],
                             'error_type': type(exc).__name__, 'requires_review': True})
    summary_page = max((number for number, _ in final_totals), default=total_pages)
    eligible, exclusions = [], []
    for number, lines in lines_by_page:
        for original, plain in lines:
            financial = bool(parser._financial_row_kind(original) or re.match(
                r'^\s*(?:tong\s+(?:cong|tien)|total\b|amount\s+due\b|payable\s+amount\b)', plain))
            if _PAGE_SUMMARY.search(plain) or (financial and number != summary_page):
                exclusions.append({'page': number, 'text': original,
                                   'reason': 'page_or_intermediate_summary'})
                continue
            eligible.append((original, plain))
    fields['total_amount'], _ = parser._amount_and_vat(eligible)
    fields['subtotal'], fields['vat_amount'] = parser._financial_amounts(eligible)
    document_totals = {amount for _, amount in final_totals}
    if len(document_totals) == 1:
        supported = next(iter(document_totals))
        if fields['total_amount'] is None:
            fields['total_amount'] = supported
        elif fields['total_amount'] != supported:
            fields['total_amount'] = None
            findings.append({'code': 'PDF_TOTAL_SOURCE_CONFLICT', 'field': 'total_amount',
                             'requires_review': True,
                             'reason': 'Văn bản và ô tổng thanh toán có giá trị khác nhau; giữ bằng chứng, không tự chọn.'})
    if len({amount for _, amount in final_totals}) > 1:
        fields['total_amount'] = None
        findings.append({'code': 'PDF_DOCUMENT_TOTAL_CONFLICT', 'field': 'total_amount',
                         'requires_review': True,
                         'reason': 'Các trang có nhiều tổng thanh toán cuối khác nhau; giữ bằng chứng, không tự chọn một số hoặc cộng chúng lại.'})
    if exclusions:
        findings.append({'code': 'PDF_INTERMEDIATE_TOTALS_EXCLUDED', 'requires_review': True,
                         'reason': 'Giữ tổng tạm/số chuyển trang trong bằng chứng; không cộng hoặc dùng chúng thay tổng cuối hóa đơn.'})
        for field in ('total_amount', 'subtotal', 'vat_amount'):
            if fields[field] is None:
                findings.append({'code': 'PDF_DOCUMENT_SUMMARY_AMBIGUOUS', 'field': field,
                                 'requires_review': True,
                                 'reason': 'Chưa có giá trị tổng cuối hóa đơn đủ rõ; không lấy tổng tạm của trang khác để điền.'})
    return raw, fields, exclusions


def extract_pdf(data, *, include_items=True, page_texts=None):
    """Keep original page numbers and commit each page before reading the next.

    Optional page_texts are OCR text already read by the public legacy helpers;
    the upload path calls this function once with both text and items enabled.
    No cross-page description/cell carry-over is permitted.
    """
    import fitz
    from PIL import Image

    pages, items, batches, findings = [], [], [], []
    started = monotonic()
    characters = words_kept = evidence_characters = 0
    batch = None
    used_ocr = False
    stopped = False

    def note(code, reason, *, incomplete=True, **details):
        finding = {'code': code, 'reason': reason, 'requires_review': True, **details}
        if incomplete:
            finding['incomplete'] = True
            parser._coverage_finding(code, reason, **details)
        findings.append(finding)

    with fitz.open(stream=data, filetype='pdf') as pdf:
        total = len(pdf)
        if not total:
            raise ValueError('PDF không có trang để trích xuất')
        for index in range(min(total, MAX_DOCUMENT_PAGES)):
            if (monotonic() - started >= MAX_DOCUMENT_SECONDS
                    or characters + (3 if pages else 0) >= MAX_DOCUMENT_CHARACTERS):
                stopped = True
                note('PDF_DOCUMENT_BUDGET_REACHED',
                     f'Dừng sau {len(pages)}/{total} trang do giới hạn thời gian hoặc văn bản; giữ dữ liệu đã xử lý, kết quả chưa đầy đủ.',
                     pages_attempted=len(pages), total_pages=total)
                break
            record = {'page': index + 1, 'raw_text': '', 'boxes': [], 'status': 'failed',
                      'source': 'pdf-text', 'line_numbers': []}
            prepared = None
            page_items, boxes = [], []
            try:
                page = pdf[index]
                record['size'] = [float(page.rect.width), float(page.rect.height)]
                native_words, native_size, selection = select_pdf_page_source(page)
                record['source_selection'] = selection
                if selection['source'] == 'pdf-text':
                    record['size'] = list(native_size)
                    text = page.get_text() or ''
                elif page_texts is not None and index < len(page_texts) and page_texts[index].strip():
                    text = page_texts[index]
                    record['source'] = 'pdf-ocr'
                    used_ocr = True
                else:
                    if page.rect.width * page.rect.height * 4 > 30_000_000:
                        raise ValueError('PDF raster exceeds existing 30 MP limit')
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB, alpha=False)
                    with Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples) as image:
                        prepared = parser._prepare_image(image)
                    del pixmap
                    record['size'] = [prepared.width, prepared.height]
                    text = parser._ocr_image(prepared, prepared=True)
                    record['source'] = 'pdf-ocr'
                    used_ocr = True
                text = parser._bounded_ocr_text(text, f'pdf_page_{index + 1}')
                remaining = MAX_DOCUMENT_CHARACTERS - characters - (3 if pages else 0)
                if len(text) > remaining:
                    text = text[:max(0, text.rfind('\n', 0, max(0, remaining) + 1))]
                    stopped = True
                    note('PDF_DOCUMENT_TEXT_LIMIT_REACHED',
                         f'Văn bản đạt giới hạn {MAX_DOCUMENT_CHARACTERS} ký tự trên trang {index + 1}; giữ các dòng hoàn chỉnh đã đọc, kết quả chưa đầy đủ.',
                         page=index + 1, text_limit=MAX_DOCUMENT_CHARACTERS)
                record.update(raw_text=text, status='completed')
                if not any(char.isalnum() for char in text):
                    # A successful OCR call can still return no readable text.
                    # Keep any later table evidence, but do not claim full coverage.
                    record['status'] = 'partial'
                    note('OCR_PAGE_COVERAGE_UNCONFIRMED',
                         f'Chưa đọc được văn bản tại trang {index + 1}; có thể là trang trống hoặc OCR chưa nhận diện được, cần đối chiếu.',
                         page=index + 1)
                if include_items:
                    layout_allowed = monotonic() - started < MAX_DOCUMENT_SECONDS
                    if not layout_allowed:
                        stopped = True
                        record['status'] = 'partial'
                        note('PDF_DOCUMENT_TIME_LIMIT_REACHED',
                             f'Đạt ngân sách thời gian tại trang {index + 1}; giữ văn bản đã đọc và chỉ phân tích dòng hàng từ văn bản này.',
                             page=index + 1, time_budget_seconds=MAX_DOCUMENT_SECONDS)
                    try:
                        if not layout_allowed:
                            pass
                        elif record['source'] == 'pdf-text':
                            boxes = native_words
                            table_words = _item_words(boxes)
                            page_items = (parser._extract_spatial_table_items(table_words)
                                          or parser._extract_staggered_table_items(table_words))
                        else:
                            if prepared is None:
                                if page.rect.width * page.rect.height * 4 > 30_000_000:
                                    raise ValueError('PDF raster exceeds existing 30 MP limit')
                                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB, alpha=False)
                                with Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples) as image:
                                    prepared = parser._prepare_image(image)
                                del pixmap
                                record['size'] = [prepared.width, prepared.height]
                            observed = {}
                            try:
                                page_items = parser._image_spatial_items(prepared, observed, _item_words)
                            finally:
                                boxes = observed.get('words', [])
                    except (ValueError, RuntimeError, OSError, parser.pytesseract.TesseractError) as exc:
                        record['status'] = 'partial'
                        note('PAGE_ITEM_GEOMETRY_FAILED',
                             f'Không đọc đủ vị trí bảng trang {index + 1}; giữ văn bản và dùng parser văn bản của đúng trang này.',
                             page=index + 1, error_type=type(exc).__name__)
                    if not page_items:
                        page_items = parser._extract_ocr_line_items(_item_text(text))
                    if not page_items:
                        page_items = parser.descriptive_adjustment_items(text)
                    if not page_items and any(parser._is_unstructured_item_header(line) for line in text.splitlines()):
                        record['status'] = 'partial'
                        note('PAGE_TABLE_ROWS_UNRESOLVED',
                             f'Trang {index + 1} có tiêu đề bảng nhưng chưa đọc được dòng hàng; không ghép dữ liệu từ trang khác.',
                             page=index + 1)
                    elif (not page_items and pages and pages[-1]['line_numbers'] and text.strip()
                          and not any(_FINAL_SUMMARY.search(parser._plain(line)) for line in text.splitlines())):
                        record['status'] = 'partial'
                        note('PDF_CONTINUATION_ROWS_UNRESOLVED',
                             f'Trang {index + 1} tiếp sau trang có dòng hàng nhưng chưa xác định được bảng tiếp nối; cần đối chiếu trang gốc.',
                             page=index + 1)
            except (ValueError, RuntimeError, OSError, parser.pytesseract.TesseractError) as exc:
                record['status'] = 'partial' if record['raw_text'] else 'failed'
                note('PAGE_OCR_FAILED',
                     f'Không hoàn tất đọc trang {index + 1}; giữ dữ liệu đã đọc và tiếp tục các trang còn lại.',
                     page=index + 1, error_type=type(exc).__name__)
            finally:
                if prepared is not None:
                    prepared.close()

            # Store the page even on failure: later source IDs never shift.
            text_size = len(record['raw_text'])
            batch_cost = text_size + (3 if batch and batch['page_count'] else 0)
            if batch is None or batch['page_count'] >= BATCH_PAGES or batch['characters'] + batch_cost > BATCH_CHARACTERS:
                batch = {'first_page': index + 1, 'last_page': index + 1, 'page_count': 0, 'characters': 0}
                batches.append(batch)
                batch_cost = text_size
            batch.update(last_page=index + 1, page_count=batch['page_count'] + 1,
                         characters=batch['characters'] + batch_cost)
            characters += text_size + (3 if pages else 0)
            capacity = MAX_DOCUMENT_WORDS - words_kept
            if len(boxes) > capacity:
                note('PDF_EVIDENCE_LIMIT_REACHED',
                     'Đạt giới hạn lưu tọa độ OCR; giữ văn bản và các dòng hàng đã nhận diện, bằng chứng vị trí chưa đầy đủ.',
                     page=index + 1, word_limit=MAX_DOCUMENT_WORDS)
            for x0, y0, x1, y1, word in boxes[:capacity]:
                word = str(word)
                if evidence_characters + len(word) > MAX_DOCUMENT_CHARACTERS:
                    note('PDF_EVIDENCE_TEXT_LIMIT_REACHED',
                         'Đạt giới hạn dung lượng văn bản trong tọa độ OCR; dữ liệu đã đọc được giữ lại, bằng chứng vị trí chưa đầy đủ.',
                         page=index + 1, text_limit=MAX_DOCUMENT_CHARACTERS)
                    break
                record['boxes'].append({'text': word, 'polygon': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]})
                evidence_characters += len(word)
            words_kept += len(record['boxes'])
            for item in page_items:
                if len(items) >= MAX_DOCUMENT_ITEMS:
                    stopped = True
                    note('PDF_ITEM_LIMIT_REACHED',
                         'Đạt giới hạn số dòng hàng; giữ các dòng đã đọc, kết quả chưa đầy đủ.',
                         page=index + 1, item_limit=MAX_DOCUMENT_ITEMS)
                    break
                row = {**item, 'line_no': len(items) + 1, 'page': index + 1}
                record['line_numbers'].append(row['line_no'])
                items.append(row)
            pages.append(record)
            if stopped:
                break
        if total > MAX_DOCUMENT_PAGES and not stopped:
            stopped = True
            note('DOCUMENT_PAGE_LIMIT_REACHED',
                 f'Chứng từ có {total} trang; giới hạn an toàn là {MAX_DOCUMENT_PAGES} trang. Giữ dữ liệu đã đọc, kết quả chưa đầy đủ.',
                 total_pages=total, pages_processed=len(pages), page_limit=MAX_DOCUMENT_PAGES)

    if not any(page['status'] != 'failed' for page in pages):
        raise RuntimeError('Không đọc được trang PDF nào trong giới hạn xử lý an toàn')
    raw, fields, exclusions = _document_fields(pages, total, findings)
    evidence = {'pages': pages, 'total_pages': total, 'pages_processed': len(pages),
                'pages_completed': sum(page['status'] == 'completed' for page in pages),
                'batches': batches, 'truncated': stopped, 'findings': findings,
                'financial_exclusions': exclusions, 'recognized_fields': fields,
                'recognized_items': items}
    return raw, fields, items, 'pdf-ocr' if used_ocr else 'pdf-text', evidence
