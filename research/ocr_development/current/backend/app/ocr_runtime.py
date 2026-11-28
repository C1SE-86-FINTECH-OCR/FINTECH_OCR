"""Opt-in bridge to the frozen V6 experiment; default OCR remains unchanged.

No database, dataset, benchmark runner, profiling hooks, or ground truth reads.
V6's existing scoped raster hook serializes hybrid calls with its own RLock.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import logging

from fastapi.encoders import jsonable_encoder
from . import extraction

logger = logging.getLogger(__name__)
FIELD_NAMES = frozenset((
    'invoice_number', 'invoice_symbol', 'invoice_date', 'seller_name',
    'seller_tax_code', 'buyer_name', 'buyer_tax_code', 'subtotal', 'vat_rate',
    'vat_amount', 'total_amount', 'qr_url', 'document_type', 'confidence_score', 'currency',
))
ITEM_NAMES = ('description', 'unit', 'quantity', 'unit_price', 'amount')


@dataclass
class OCRResult:
    fields: dict
    items: list[dict]
    raw_text: str
    method: str
    metadata: dict | None = None


def _run_hybrid(data, ext, max_pages):
    # Lazy import: normal/default/XML uploads do not load experimental modules.
    from tools.ocr_benchmark.hybrid_v6 import extract_hybrid
    return extract_hybrid(data, ext, max_pages)


def _run_hybrid_v7(data, ext, max_pages):
    from tools.ocr_benchmark.hybrid_v7 import extract_hybrid
    return extract_hybrid(data, ext, max_pages)


def _run_hybrid_v8(data, ext, max_pages):
    from tools.ocr_benchmark.hybrid_v8 import extract_hybrid
    return extract_hybrid(data, ext, max_pages)


def _run_hybrid_v8_final(data, ext, max_pages, *, local_ai=None):
    from tools.ocr_benchmark.hybrid_v8_final import extract_hybrid
    from .ocr_preprocessing import hybrid_preprocessing
    with hybrid_preprocessing() as observations:
        fields, items, layout = (extract_hybrid(data, ext, max_pages, local_ai=local_ai)
                                 if local_ai is not None else extract_hybrid(data, ext, max_pages))
    return fields, items, {**layout, 'opencv_preprocessing': observations}


def _storage_decimal(raw, key, *, allow_signed=False):
    """Respect existing Numeric columns without silently rounding OCR values."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        raise ValueError('invalid_numeric_literal')
    try:
        value = Decimal(str(raw))
        limit = Decimal('999999999999999.999') if key == 'quantity' else Decimal('999.99') if key == 'vat_rate' else Decimal('9999999999999999.99')
        quantum = Decimal('.001') if key == 'quantity' else Decimal('.01')
        if not value.is_finite() or value < (-limit if allow_signed else 0) or value > limit:
            raise ValueError('numeric_range_unsupported')
        if value != value.quantize(quantum):
            raise ValueError('numeric_precision_unsupported')
        return value
    except InvalidOperation:
        raise ValueError('invalid_numeric_literal') from None


def _normalise_result_numbers(result):
    """Unknown stays null; retain rejected source literals in private evidence."""
    metadata = dict(result.metadata or {})
    findings = list(metadata.get('findings', []))
    observations = []
    fields, rows = dict(result.fields), [dict(row) for row in result.items]
    targets = [(fields, key, None) for key in ('subtotal', 'vat_rate', 'vat_amount', 'total_amount')]
    targets += [(row, key, n) for n, row in enumerate(rows, 1) for key in ('quantity', 'unit_price', 'amount')]
    for target, key, line in targets:
        raw = target.get(key)
        try:
            target[key] = _storage_decimal(raw, key)
        except ValueError as exc:
            target[key] = None
            observations.append({'field': key, 'line': line, 'literal': str(raw)[:100], 'reason': str(exc)})
            findings.append({'code': 'OCR_NUMERIC_REVIEW_REQUIRED', 'field': key, 'line': line,
                             'requires_review': True,
                             'reason': 'Số nguồn không phù hợp phạm vi/độ chính xác cột hiện có; giữ bằng chứng, không tự làm tròn hoặc thay bằng 0.'})
    if observations:
        metadata['numeric_source_observations'] = [*metadata.get('numeric_source_observations', []), *observations]
        metadata['requires_review'] = True
    text_observations = []
    text_targets = [(fields, key, None, limit) for key, limit in (
        ('invoice_number', 50), ('invoice_symbol', 40), ('seller_name', 255),
        ('buyer_name', 255), ('seller_tax_code', 25), ('buyer_tax_code', 25))]
    text_targets += [(row, 'unit', line, 30) for line, row in enumerate(rows, 1)]
    for target, key, line, limit in text_targets:
        raw = target.get(key)
        if raw is None or (isinstance(raw, str) and len(raw) <= limit):
            continue
        target[key] = None
        literal = str(raw)
        text_observations.append({'field': key, 'line': line, 'literal': literal[:4096],
                                  'literal_truncated': len(literal) > 4096, 'column_limit': limit})
        findings.append({'code': 'OCR_FIELD_REVIEW_REQUIRED', 'field': key, 'line': line,
                         'requires_review': True,
                         'reason': 'Giá trị nguồn không phù hợp kiểu/độ dài cột hiện có; giữ bằng chứng và tệp gốc, không cắt tên hoặc làm hỏng toàn bộ kết quả.'})
    if text_observations:
        metadata['field_source_observations'] = [*metadata.get('field_source_observations', []), *text_observations]
        metadata['requires_review'] = True
    metadata['findings'] = findings
    result.fields, result.items, result.metadata = fields, rows, metadata
    return result


def _mapped_hybrid(fields, items):
    """Persist only supported columns. Keep page/unit/VAT/boxes in evidence."""
    mapped = {k: v for k, v in fields.items() if k in FIELD_NAMES}
    if mapped.get('document_type') not in ('einvoice', 'bill', 'unknown'):
        raise ValueError('Unsupported Hybrid document type')
    if isinstance(mapped.get('invoice_date'), str):
        mapped['invoice_date'] = date.fromisoformat(mapped['invoice_date'])
    # OCR token confidence is not field accuracy or the old completeness ratio.
    mapped['confidence_score'] = None
    if mapped.get('currency') is None:
        mapped.pop('currency',None)  # preserve the model default, not null
    elif not isinstance(mapped['currency'],str) or len(mapped['currency'])!=3 or not all('A'<=c<='Z' for c in mapped['currency']):
        raise ValueError('Unsupported currency code')
    rows = []
    for n, item in enumerate(items, 1):
        if not isinstance(item.get('description'), str) or not item['description'].strip():
            raise ValueError('Hybrid row lacks recognized description')
        row = {key: item.get(key) for key in ITEM_NAMES}
        for key in ('quantity', 'unit_price', 'amount'):
            if row[key] is not None:
                row[key] = _storage_decimal(row[key], key)
        if row['unit'] is not None and (not isinstance(row['unit'], str) or len(row['unit']) > 30):
            raise ValueError('Hybrid unit exceeds existing column')
        rows.append({'line_no': n, **row})
    for key, limit in (('invoice_number',50),('invoice_symbol',40),('seller_name',255),('buyer_name',255),('seller_tax_code',25),('buyer_tax_code',25)):
        if mapped.get(key) is not None and (not isinstance(mapped[key], str) or len(mapped[key]) > limit):
            raise ValueError('Hybrid field exceeds existing column')
    for key in ('subtotal','vat_amount','total_amount','vat_rate'):
        if mapped.get(key) is not None:
            mapped[key] = _storage_decimal(mapped[key], key)
    return mapped, rows


def _hybrid_result(pipeline, fields, items, layout):
    mapped, rows = _mapped_hybrid(fields, items)
    # Validate the entire payload before the upload handler creates any rows.
    # Keep exact Decimal literals in evidence; JSON's default Decimal encoder
    # converts fractional values to binary floats before they reach storage.
    evidence = json.loads(json.dumps(jsonable_encoder({
        **layout, 'recognized_fields': fields, 'recognized_items': items,
    }, custom_encoder={Decimal: str}), allow_nan=False))
    used = pipeline
    metadata = {'requested_pipeline': pipeline, 'fallback': False, 'requires_review': True,
                'confidence_semantics': 'uncalibrated OCR word scores; not field accuracy',
                'findings': evidence.get('findings', []), 'truncated': bool(layout.get('truncated')),
                'evidence': evidence}
    if isinstance(evidence.get('local_ai'), dict):
        metadata['local_ai'] = evidence['local_ai']
    if metadata['truncated']:
        processed, total = layout.get('pages_processed', len(layout.get('pages', []))), layout.get('total_pages')
        metadata['findings'] = [*metadata['findings'], {
            'code': 'EXTRACTION_COVERAGE_INCOMPLETE', 'incomplete': True, 'requires_review': True,
            'reason': f'Chỉ xử lý {processed} trang trong tổng số {total if total is not None else "chưa xác định"} trang; dữ liệu đã đọc được giữ lại, kết quả chưa bao phủ toàn bộ chứng từ.',
        }]
    # A page counted as processed may still have no readable primary OCR.
    # Keep other pages and flag incomplete coverage, including possible blank
    # pages that require human confirmation. Do not re-run OCR or invent text.
    pages_without_text = []
    for page in evidence.get('pages', []):
        has_text = bool(str(page.get('raw_text') or '').strip()) or any(
            isinstance(box.get('text'), str) and any(c.isalnum() for c in box['text'])
            for box in page.get('boxes', []))
        if not has_text or page.get('status') in ('partial', 'failed'):
            pages_without_text.append(page.get('page'))
    if pages_without_text:
        metadata['coverage_incomplete'] = True
        metadata['findings'] = [*metadata['findings'], {
            'code': 'OCR_PAGE_COVERAGE_UNCONFIRMED',
            'pages': pages_without_text, 'incomplete': True, 'requires_review': True,
            'reason': ('Chưa xác nhận đọc đủ văn bản tại trang: '
                       + ', '.join(str(page) for page in pages_without_text)
                       + '. Có thể là trang trống hoặc OCR chưa đọc được; giữ kết quả các trang còn lại.'),
        }]
    if pipeline == 'hybrid_v8_final' and layout.get('final_refinement_status') == 'v8_baseline_retained':
        used = 'hybrid_v8'
        metadata['reason'] = 'v8_baseline_retained'
    metadata['used_pipeline'] = used
    return OCRResult(mapped, rows, layout.get('raw_text', ''), used.replace('_', '-'), metadata)


def _complete_ocr_result(result, pipeline, source_format=None, *, allow_llm=True):
    """Optional LLM and policy stages always preserve usable OCR on failure."""
    from copy import deepcopy
    from .ocr_llm import refine_with_llm, safe_llm_diagnostics
    from .ocr_confidence import assess_confidence
    from .invoice_financials import observe, arithmetic_rules, party_value_kind, party_name_literal

    metadata = {'requested_pipeline': pipeline, 'used_pipeline': 'current', 'fallback': False,
                **deepcopy(result.metadata or {})}
    if source_format is not None:
        metadata['source_format'] = source_format
    findings = list(metadata.get('findings', []))
    for key in ('seller_name', 'buyer_name'):
        if result.fields.get(key) is not None:
            result.fields = {**result.fields, key: party_name_literal(result.fields[key])}
        kind = party_value_kind(result.fields[key]) if result.fields.get(key) else None
        if kind is not None and kind != 'name_candidate':
            metadata.setdefault('rejected_party_observations', {})[key] = result.fields[key]
            result.fields = {**result.fields, key: None}
            findings.append({'code': 'PARTY_VALUE_IS_METADATA', 'field': key, 'value_kind': kind, 'requires_review': True})
    try:
        financial = (deepcopy(metadata['financial_context']) if source_format == 'xml' and metadata.get('financial_context') is not None
                     else observe(result.raw_text, extraction._decimal_money, metadata.get('evidence')))
    except Exception as exc:
        financial = {'observations': [], 'tax_groups': [], 'adjustment_observed': True,
                     'error_type': type(exc).__name__}
        findings.append({'code': 'FINANCIAL_CONTEXT_UNAVAILABLE', 'requires_review': True,
                         'reason': 'Không hoàn tất phân tích phạm vi tài chính; giữ nguyên dữ liệu OCR, cần xem xét.'})
    metadata['financial_context'] = financial
    financial['coverage_incomplete'] = bool(metadata.get('truncated') or metadata.get('coverage_incomplete')
        or any(page.get('status') in ('partial', 'failed') for page in metadata.get('evidence', {}).get('pages', [])))
    _apply_document_semantics(result, metadata, financial, findings, source_format)
    if financial['adjustment_observed'] or len(financial.get('tax_groups', [])) > 1:
        findings.append({'code': 'FINANCIAL_SCOPE_OBSERVATIONS', 'requires_review': True,
                         'reason': 'Chiết khấu/phụ phí/nhóm VAT được giữ theo bằng chứng; không thêm cột hoặc tự suy diễn số tiền.',
                         'observations': financial['observations'], 'tax_groups': financial['tax_groups']})
    group_rates = {group['rate'] for group in financial.get('tax_groups', [])}
    if len(group_rates) > 1:
        result.fields = {**result.fields, 'vat_rate': None}
        findings.append({'code': 'MULTIPLE_PRINTED_VAT_GROUPS', 'field': 'vat_rate',
                         'observed_values': sorted(group_rates), 'requires_review': True})
    preprocessing = metadata.get('preprocessing', metadata.get('evidence', {}).get('opencv_preprocessing', []))
    for observation in preprocessing:
        if observation.get('opencv_status') != 'applied':
            findings.append({'code': 'OPENCV_FALLBACK_TO_PILLOW',
                             'reason': observation.get('opencv_status'), 'requires_review': True})
    rates = extraction._observed_vat_rates(extraction._lines(extraction.current_document_text(result.raw_text)))
    if len(rates) > 1:
        findings.append({'code': 'OCR_MULTIPLE_VAT_RATE_OBSERVATIONS', 'field': 'vat_rate',
                         'observed_values': sorted(rates), 'requires_review': True})
    metadata['findings'] = list(findings)
    llm = {}
    optional_stage = 'llm_refinement'
    try:
        if allow_llm:
            fields, items, llm, warnings = refine_with_llm(
                result.fields, result.items, result.raw_text, metadata, _mapped_hybrid)
        else:
            fields, items, llm, warnings = result.fields, result.items, {
                'status': 'local_only' if source_format == 'xml' else 'disabled_by_policy'}, []
        # Prove optional-stage metadata can be stored before adopting changes.
        optional_stage = 'metadata_serialization'
        llm = json.loads(json.dumps(jsonable_encoder(llm, custom_encoder={Decimal: str}), allow_nan=False))
        warnings = json.loads(json.dumps(jsonable_encoder(warnings, custom_encoder={Decimal: str}), allow_nan=False))
    except Exception as exc:
        fields, items = result.fields, result.items
        llm = {**safe_llm_diagnostics(llm), 'status': 'failed', 'error_type': type(exc).__name__,
               'failure_stage': optional_stage, 'error_kind': 'integration_error'}
        warnings = [{'code': 'LLM_FALLBACK_TO_OCR', 'reason': 'integration_error',
                     **safe_llm_diagnostics(llm), 'requires_review': True}]
    findings.extend(warnings)
    try:
        review = arithmetic_rules(fields, items, financial)
    except Exception:
        review = [('FINANCIAL-CONTEXT', False, 'Không hoàn tất kiểm tra phạm vi tài chính; giữ số nguồn và cần xem xét.')]
    metadata['financial_review'] = [{'rule': code, 'passed': passed, 'message': message}
                                    for code, passed, message in review]
    if review and all(passed for _code, passed, _message in review):
        resolved = [finding for finding in findings if finding.get('code') == 'ITEM_SUBTOTAL_CONFLICT']
        if resolved:
            metadata['unadjusted_financial_findings'] = resolved
            findings = [finding for finding in findings if finding.get('code') != 'ITEM_SUBTOTAL_CONFLICT']
            findings.append({'code': 'FINANCIAL_SCOPE_RECONCILED',
                             'reason': 'Chênh lệch tổng dòng hàng được đối chiếu bằng chiết khấu/phạm vi in trên chứng từ; các số nguồn không thay đổi.'})
    findings.extend({'code': 'FINANCIAL_REVIEW_REQUIRED', 'rule': code, 'reason': message,
                     'requires_review': True} for code, passed, message in review if not passed)
    metadata['llm'] = llm
    metadata['findings'] = list(findings)
    confidence = assess_confidence(fields, items, metadata)
    # Preserve the former completeness measurement as an observation only.
    if result.fields.get('confidence_score') is not None:
        metadata['legacy_completeness_score'] = result.fields['confidence_score']
    fields = {**fields, 'confidence_score': confidence['score']}
    if confidence['requires_review']:
        findings.append({'code': 'CONFIDENCE_REVIEW_REQUIRED', 'reason': confidence['reason']})
    metadata.update(confidence=confidence, findings=findings,
                    confidence_semantics=confidence['semantics'], requires_review=confidence['requires_review']
                    or any(not passed for _code, passed, _message in review)
                    or any(finding.get('requires_review') for finding in findings)
                    or bool(warnings) or bool(metadata.get('requires_review')))
    return OCRResult(fields, items, result.raw_text, result.method, metadata)


def _apply_document_semantics(result, metadata, financial, findings, source_format):
    """An optional refinement must either complete or retain its OCR baseline."""
    from copy import deepcopy
    fields, items = deepcopy(result.fields), deepcopy(result.items)
    previous_findings = list(findings)
    keys = ('document_semantics', 'rejected_reference_fields', 'descriptive_adjustment_items',
            'not_applicable_financial_findings')
    previous = {key: deepcopy(metadata[key]) for key in keys if key in metadata}
    try:
        _refine_document_semantics(result, metadata, financial, findings, source_format)
    except Exception as exc:
        result.fields, result.items = fields, items
        for key in keys:
            metadata.pop(key, None)
        metadata.update(previous)
        financial['document_semantics_error'] = True
        findings[:] = [*previous_findings, {'code': 'DOCUMENT_SEMANTICS_BASELINE_RETAINED',
                       'error_type': type(exc).__name__, 'requires_review': True,
                       'reason': 'Không hoàn tất phân tích quan hệ hóa đơn; đã giữ nguyên kết quả OCR, cần xem xét.'}]
        metadata['requires_review'] = True


def _refine_document_semantics(result, metadata, financial, findings, source_format):
    """Preserve related-document evidence without moving it into current fields."""
    from .invoice_financials import non_financial_adjustment, party_name_literal
    semantics = financial.get('document_semantics', {})
    metadata['document_semantics'] = semantics
    for key in ('seller_name', 'buyer_name'):
        if result.fields.get(key) is not None:
            result.fields = {**result.fields, key: party_name_literal(result.fields[key])}
    if semantics.get('kind', 'regular') == 'regular':
        return
    kind_label = {'adjustment': 'hóa đơn điều chỉnh', 'replacement': 'hóa đơn thay thế'}.get(semantics.get('kind'), 'quan hệ hóa đơn chưa xác định')
    findings.append({'code': 'DOCUMENT_RELATIONSHIP', 'kind': semantics.get('kind'),
                     'requires_review': True,
                     'reason': 'Nội dung nguồn cho thấy ' + kind_label + '; thông tin hóa đơn gốc và mô tả được giữ riêng trong bằng chứng, không coi là trường của hóa đơn hiện tại.'})
    current = extraction.extract_fields(result.raw_text, source_format or 'pdf')
    references = semantics.get('reference_candidates', {})
    for key in ('invoice_number', 'invoice_symbol', 'invoice_date', 'seller_tax_code', 'buyer_tax_code'):
        value = result.fields.get(key)
        reference_values = (semantics.get('old_tax_codes', []) if key.endswith('_tax_code') else references.get(key, []))
        identity = lambda literal: str(literal).casefold().replace(' ', '').replace('-', '') if key.endswith('_tax_code') else str(literal).casefold()
        if (value is not None and any(identity(value) == identity(old) for old in reference_values)
                and (current.get(key) is None or identity(current[key]) != identity(value))):
            metadata.setdefault('rejected_reference_fields', {})[key] = value
            result.fields = {**result.fields, key: current.get(key)}
            findings.append({'code': 'CURRENT_DOCUMENT_REFERENCE_EXCLUDED', 'field': key, 'requires_review': True})
    # A printed zero is evidence, unlike a missing monetary field. This repairs
    # a missing optional baseline result without inventing a zero elsewhere.
    for key in ('subtotal', 'vat_amount', 'total_amount', 'vat_rate'):
        if result.fields.get(key) is None and current.get(key) is not None and current[key] == 0:
            result.fields = {**result.fields, key: current[key]}
            findings.append({'code': 'PRINTED_ZERO_RETAINED', 'field': key})
    if not result.items and semantics.get('kind') == 'adjustment':
        descriptions = [entry for entry in semantics.get('descriptions', []) if entry.get('non_financial_target')]
        result.items = [{'line_no': n, 'description': entry['text'][:2000], 'unit': None, 'quantity': None,
                         'unit_price': None, 'amount': None, 'page': entry['page'], 'source_line': entry['line']}
                        for n, entry in enumerate(descriptions, 1)]
        if result.items:
            metadata['descriptive_adjustment_items'] = result.items
    if non_financial_adjustment(result.fields, result.items, financial):
        not_applicable = [finding for finding in findings
                          if ((result.items and finding.get('code') == 'V8_FINAL_NO_CONFIRMED_ITEMS')
                              or (finding.get('code') == 'V8_FINAL_CELL_NOT_OBSERVED'
                                  and finding.get('field') in ('unit', 'quantity', 'unit_price', 'amount'))
                              or finding.get('code') == 'V8_FINAL_AMOUNT_EVIDENCE_MISSING')]
        if not_applicable:
            metadata['not_applicable_financial_findings'] = not_applicable
            findings[:] = [finding for finding in findings if finding not in not_applicable]
        findings.append({'code': 'NON_FINANCIAL_ADJUSTMENT', 'requires_review': True,
                         'reason': 'Điều chỉnh thông tin phi tài chính; giữ mô tả và các cột không có dữ liệu ở null. Không áp dụng phép tính tiền/VAT khi chứng từ không cung cấp.'})


def _photo_recovery(data, ext, config, baseline, pipeline):
    """A bounded independent local AI path when the ordinary image route is weak.

    No dependency on successful Tesseract captures, no cloud retry. Source boxes
    are saved in their actual recovery frame; never merge across different IDs.
    """
    from io import BytesIO
    from PIL import Image, ImageOps
    from tools.ocr_benchmark import paddle_local as paddle, pipeline_v4 as v4, pipeline_v5 as v5, refine_v8 as refine
    from tools.ocr_benchmark.table_v3 import row_evidence
    from .ocr_preprocessing import normalize_image
    prior = baseline or OCRResult({}, [], '', 'not-processed', {})
    meta = dict(prior.metadata or {})
    prior_ai = meta.get('local_ai') or {}
    core = ('invoice_number', 'invoice_date', 'seller_name', 'total_amount')
    sparse = sum(prior.fields.get(key) is not None for key in core) < 3 or not prior.items
    if not sparse:
        return prior
    diagnostics = []
    best = None
    best_rank = (-1, -1, -1)
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > 30_000_000:
                raise ValueError('Photo pixel limit')
            original = normalize_image(source)
        with original:
            # Original color pixels first. A separate paper crop is a bounded
            # alternative if the full photo is weak, not a destructive change.
            for variant in ('original', 'paper'):
                image = original.copy()
                try:
                    transform = {'method': 'original', 'source_size': original.size}
                    if variant == 'paper':
                        crop, transform = v5.paper_view(image)
                        if crop is not image:
                            image.close()
                            image = crop
                        if transform.get('method') == 'original':
                            continue
                        # Normalize uneven illumination within the detected paper.
                        from PIL import ImageChops, ImageFilter
                        gray = image.convert('L')
                        with gray, gray.filter(ImageFilter.GaussianBlur(max(5, min(gray.size)/35))) as background:
                            enhanced = ImageOps.autocontrast(ImageChops.subtract(gray, background, offset=180), cutoff=.5).convert('RGB')
                        image.close()
                        image = enhanced
                    page = {'page': 1, 'source': 'ocr', 'size': image.size, 'boxes': []}
                    reads, status = paddle.recognize_document([page], [image], config)
                    diagnostics.append({'variant': variant, 'local_ai': status, 'transform': transform})
                    read = reads.get(1)
                    if read is None:
                        logger.warning('Photo AI recovery %s: %s, pages=%s', variant, status.get('reason', status.get('status')),
                                       [(entry.get('status'), entry.get('reason')) for entry in status.get('pages', [])])
                        continue
                    raw = read.text
                    # Do not require the normal Hybrid parser to succeed before
                    # retaining independently recognized text and labelled fields.
                    fields = extraction.extract_fields(raw, ext)
                    fields['confidence_score'] = None
                    try:
                        spatial, _, _, _ = v4.field_context(read.lines, read.size, ext)
                        for key, value in spatial.items():
                            if fields.get(key) is None and value is not None:
                                fields[key] = value
                        fields.update(extraction._printed_sales_bill_fields(extraction._lines(raw)))
                    except Exception as exc:
                        diagnostics[-1]['field_parser_error'] = type(exc).__name__
                    rows = []
                    try:
                        # Prefer actual spatial cells; only use the existing text
                        # parser if no spatial rows could be recovered.
                        rows, _ = refine.recover_rows([read], [], None)
                    except Exception as exc:
                        diagnostics[-1]['table_parser_error'] = type(exc).__name__
                    if not rows:
                        rows = extraction._extract_ocr_line_items(raw)
                    # When enabled, table AI must see the independent Paddle boxes
                    # rather than depending on the absent primary Tesseract read.
                    if config.get('table_enabled') and not rows:
                        try:
                            page['boxes'] = row_evidence(read.boxes, {'all': range(len(read.boxes))})['all']
                            table_layout = {'pages': [page], 'raw_text': raw}
                            table_status = paddle.recognize_tables([page], [image], reads, config, table_layout, paddle.worker_environment(), fields.get('invoice_number'))
                            diagnostics[-1]['table_ai'] = table_status
                            table_read = reads.get(1)
                            if table_read and (table_read.refined or {}).get('table_boxes'):
                                from tools.ocr_benchmark.hybrid_v8_final import _local_table_candidate
                                selected, table_rows, _ = _local_table_candidate(table_read, [], None)
                                if selected is not None:
                                    rows = table_rows
                        except Exception as exc:
                            diagnostics[-1]['table_recovery_error'] = type(exc).__name__
                    # Reject invalid rows independently, not the whole document.
                    clean = []
                    for row in rows:
                        try:
                            _, valid = _mapped_hybrid({'document_type': 'unknown'}, [row])
                            clean.append(valid[0])
                        except (ValueError, TypeError, ArithmeticError):
                            continue
                    for n, row in enumerate(clean, 1):
                        row['line_no'] = n
                    evidence = {'pages': [{**page, 'raw_text': raw,
                                'boxes': row_evidence(read.boxes, {'all': range(len(read.boxes))})['all'],
                                'coordinate_space': 'photo recovery raster pixels', 'preprocessing': transform}],
                                'recognized_fields': fields, 'recognized_items': rows,
                                'raw_text': raw, 'total_pages': 1, 'pages_processed': 1}
                    evidence = json.loads(json.dumps(jsonable_encoder(evidence, custom_encoder={Decimal: str}), allow_nan=False))
                    rank = (sum(fields.get(key) is not None for key in core), int(bool(clean)),
                            sum(row.get(key) is not None for row in clean for key in ITEM_NAMES))
                    if rank > best_rank:
                        best_rank = rank
                        best = (fields, clean, raw, evidence, status)
                    if rank[0] == 4 and rank[1] == 1 and all(row.get(key) is not None for row in clean for key in ITEM_NAMES):
                        break
                except Exception as exc:
                    diagnostics.append({'variant': variant, 'error_type': type(exc).__name__})
                    logger.warning('Photo recovery stage %s failed: %s', variant, type(exc).__name__)
                finally:
                    image.close()
    except Exception as exc:
        diagnostics.append({'error_type': type(exc).__name__})
        logger.warning('Photo recovery unavailable: %s', type(exc).__name__)
    meta['photo_ai_recovery'] = diagnostics
    if best is None:
        meta['local_ai'] = {**prior_ai, 'provider': 'paddleocr-local', 'status': 'failed',
                            'reason': 'photo_recovery_unavailable'}
        meta['findings'] = [*meta.get('findings', []), {'code': 'LOCAL_AI_PHOTO_RECOVERY_FAILED',
                            'attempts': diagnostics, 'requires_review': True}]
        prior.metadata = meta
        return prior
    fields, rows, raw, evidence, status = best
    merged = dict(prior.fields)
    conflicts = [key for key in ('invoice_number', 'invoice_date', 'seller_tax_code')
                 if merged.get(key) is not None and fields.get(key) is not None
                 and str(merged[key]).casefold() != str(fields[key]).casefold()]
    if conflicts:
        meta['findings'] = [*meta.get('findings', []), {'code': 'LOCAL_AI_PHOTO_ID_CONFLICT', 'fields': conflicts, 'requires_review': True}]
        prior.metadata = meta
        return prior
    adopted = []
    for key, value in fields.items():
        if key in FIELD_NAMES and value is not None and not (key == 'document_type' and value == 'unknown') and (merged.get(key) is None or key == 'document_type' and merged.get(key) == 'unknown'):
            merged[key] = value
            adopted.append(key)
    merged.setdefault('document_type', 'unknown')
    if not adopted and (prior.items or not rows):
        prior.metadata = meta
        return prior
    use_rows = not prior.items and bool(rows)
    # Preserve original primary evidence for inspection. Recovery raw text is
    # used as the active source only if the previous result had no core fields.
    use_recovery_source = not any(prior.fields.get(k) is not None for k in core)
    meta['prior_ocr_evidence'] = meta.get('evidence')
    if use_recovery_source:
        meta['evidence'] = evidence
        meta['used_pipeline'] = 'paddle-local-photo'
    else:
        meta['photo_recovery_evidence'] = evidence
    meta.update(requested_pipeline=pipeline, requires_review=True, fallback=True,
                local_ai={**status, 'status': 'partial', 'reason': 'independent_photo_recovery',
                          'fields_filled': len(adopted), 'rows_recovered': len(rows) if use_rows else 0})
    meta['findings'] = [*meta.get('findings', []), {'code': 'LOCAL_AI_PHOTO_RECOVERED',
        'fields': adopted, 'rows': len(rows) if use_rows else 0, 'requires_review': True}]
    return OCRResult(merged, rows if use_rows else prior.items, raw if use_recovery_source or not prior.raw_text.strip() else prior.raw_text,
                     prior.method if not use_recovery_source else 'paddle-local-photo', meta)


def extract_document(data, ext, *, pipeline='current', fallback=True, max_pages=12,
                     legacy_reader=None, development_preview=False, web_approval=None,
                     require_web_consent=False, allow_llm=True, local_ai=None):
    from .ocr_free_tier import document_scope
    # Permission is tied to the upload bytes inside the worker, not to a Web
    # checkbox or a model-supplied claim. Files outside the approved upload
    # scope (or the legacy manifest) stay entirely local.
    with document_scope(data, web_approval=web_approval, require_web_consent=require_web_consent):
        photo_ai = local_ai is not None and ext.lower().lstrip('.') in ('jpg', 'jpeg', 'png')
        try:
            result = _extract_document(data, ext, pipeline=pipeline, fallback=fallback,
                                       max_pages=max_pages, legacy_reader=legacy_reader, local_ai=local_ai)
        except Exception as exc:
            if not photo_ai or not fallback:
                raise
            logger.warning('Primary photo OCR failed: %s', type(exc).__name__)
            result = OCRResult({'document_type': 'unknown'}, [], '', 'not-processed', {
                'requested_pipeline': pipeline, 'used_pipeline': 'none', 'fallback': True,
                'requires_review': True, 'findings': [{'code': 'PRIMARY_PHOTO_OCR_FAILED', 'error_type': type(exc).__name__}]})
        if photo_ai:
            result = _photo_recovery(data, ext, local_ai, result, pipeline)
        result = _normalise_result_numbers(result)
        currency=extraction.currency_observation(result.raw_text)
        result.metadata={**(result.metadata or {}),'currency_observation':currency}
        if currency['state']=='conflicting' or (currency['state']=='observed' and result.fields.get('currency') not in (None,currency['code'])):
            result.metadata['requires_review']=True
            result.metadata['findings']=[*result.metadata.get('findings',[]),{'code':'CURRENCY_EVIDENCE_CONFLICT','requires_review':True}]
        elif currency['state']=='observed' and result.fields.get('currency') is None:
            result.fields['currency']=currency['code']
        if local_ai is not None and not (result.metadata or {}).get('local_ai'):
            # Native XML and an unavailable Final stage are distinct outcomes.
            summary = {'provider': 'paddleocr-local', 'status': 'not_needed' if ext == 'xml' else 'failed',
                       'reason': 'xml_local_parser' if ext == 'xml' else 'hybrid_result_unavailable'}
            result.metadata = {**(result.metadata or {}), 'local_ai': summary}
            if ext != 'xml':
                result.metadata['findings'] = [*result.metadata.get('findings', []),
                    {'code': 'LOCAL_AI_UNAVAILABLE', 'requires_review': True}]
                result.metadata['requires_review'] = True
        if development_preview:
            result.metadata = {**(result.metadata or {}), 'requires_review': True,
                               'findings': [
                                   {'code': 'LOCAL_DEVELOPMENT_PREVIEW_UNVERIFIED',
                                    'reason': 'UNVERIFIED / DEVELOPMENT PREVIEW — không phải nghiệm thu G13 hoặc NFR01.',
                                    'requires_review': True},
                                   *(result.metadata or {}).get('findings', [])]}
        if ext == 'xml':
            from .invoice_financials import observe, xml_adjustments
            try:
                financial = xml_adjustments(observe(result.raw_text, extraction._decimal_money),
                                            extraction._parse_xml(data),
                                            lambda literal: extraction._xml_decimal(literal, 'discount'))
            except Exception as exc:
                financial = {'observations': [], 'tax_groups': [], 'adjustment_observed': True,
                             'error_type': type(exc).__name__}
            result.metadata = {**(result.metadata or {}), 'financial_context': financial}
            # Keep XML parsing deterministic while applying the same numeric,
            # financial-review and approved-confidence rules as other files.
            # Local-only XML cannot invoke an external provider.
            return _complete_ocr_result(result, pipeline, source_format=ext, allow_llm=False)
        return _complete_ocr_result(result, pipeline, source_format=ext,
                                    allow_llm=allow_llm and local_ai is None)


def _extract_document(data, ext, *, pipeline='current', fallback=True, max_pages=12,
                      legacy_reader=None, local_ai=None):
    if pipeline not in ('current','hybrid_v6','hybrid_v7','hybrid_v8','hybrid_v8_final'):
        raise ValueError('Unsupported OCR pipeline')
    reader = legacy_reader or extraction.text_from_file

    def current(metadata=None):
        from .ocr_preprocessing import capture_preprocessing
        pdf_evidence = None
        with capture_preprocessing() as preprocessing, extraction.capture_extraction_coverage() as coverage:
            if ext == 'pdf' and reader is extraction.text_from_file:
                from .ocr_pdf import extract_pdf
                raw, fields, source_rows, method, pdf_evidence = extract_pdf(data)
                rows = [{key: item.get(key) for key in ('line_no', *ITEM_NAMES)} for item in source_rows]
            else:
                raw, method = reader(data, ext)
                fields = extraction.extract_fields(raw, ext)
                rows = extraction.extract_line_items(data, ext, raw)
        if ext != 'xml':
            metadata = {**(metadata or {}), 'preprocessing': preprocessing}
            metadata.setdefault('requested_pipeline', pipeline)
            metadata.setdefault('used_pipeline', 'current')
            metadata.setdefault('fallback', False)
            if pdf_evidence is not None:
                metadata['evidence'] = pdf_evidence
                metadata['findings'] = [*metadata.get('findings', []),
                                        *(finding for finding in pdf_evidence['findings'] if not finding.get('incomplete'))]
                metadata['truncated'] = pdf_evidence['truncated']
                metadata['requires_review'] = bool(pdf_evidence['findings']) or bool(metadata.get('requires_review'))
            metadata['findings'] = [*metadata.get('findings', []), *coverage]
            metadata['coverage_incomplete'] = bool(coverage)
            metadata['truncated'] = bool(metadata.get('truncated')) or any(
                finding['code'] == 'DOCUMENT_PAGE_LIMIT_REACHED' for finding in coverage)
            if coverage:
                metadata['requires_review'] = True
        elif coverage:
            metadata = {**(metadata or {}), 'requested_pipeline': pipeline, 'used_pipeline': 'current',
                        'findings': [*(metadata or {}).get('findings', []), *coverage],
                        'coverage_incomplete': True, 'requires_review': True}
        return OCRResult(fields, rows, raw, method, metadata)

    if pipeline == 'current':
        return current()
    if ext == 'xml':
        return current({'requested_pipeline':pipeline,'used_pipeline':'current',
                        'fallback':False,'reason':'xml_uses_existing_parser',
                        'requires_review':True,'findings':[]})
    try:
        runner = _run_hybrid_v8_final if pipeline == 'hybrid_v8_final' else _run_hybrid_v8 if pipeline == 'hybrid_v8' else _run_hybrid_v7 if pipeline == 'hybrid_v7' else _run_hybrid
        fields, items, layout = (runner(data, ext, max_pages, local_ai=local_ai)
                                 if pipeline == 'hybrid_v8_final' and local_ai is not None
                                 else runner(data, ext, max_pages))
        try:
            return _hybrid_result(pipeline, fields, items, layout)
        except Exception as exc:
            snapshot = layout.get('v8_baseline') if pipeline == 'hybrid_v8_final' else None
            if not snapshot:
                raise
            original = snapshot['layout']
            # Reuse the existing snapshot. The rejected Final evidence may
            # itself be unserializable, so do not copy it into the retry.
            retained = {**original, 'final_refinement_status': 'v8_baseline_retained',
                        'findings': [*original.get('findings', []),
                                     {'code': 'V8_FINAL_OUTPUT_BASELINE_RETAINED',
                                      'error_type': type(exc).__name__, 'requires_review': True}]}
            return _hybrid_result(pipeline, snapshot['fields'], snapshot['items'], retained)
    except Exception as exc:
        if not fallback:
            raise
        logger.exception('Experimental %s failed; reverting to current OCR', pipeline)
        return current({'requested_pipeline':pipeline,'used_pipeline':'current',
                        'fallback':True,'reason':type(exc).__name__,
                        'requires_review':True,'findings':[{'code':'HYBRID_FALLBACK'}]})
