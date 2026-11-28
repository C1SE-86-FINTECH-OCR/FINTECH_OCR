"""V8 Final refinements with source evidence and bounded, recoverable stages.

The original V8/current engines remain available. No database, labels, network
or acceptance decisions are used here. Optional failures retain observed data.
"""
from copy import deepcopy
from math import ceil, floor, isfinite
from statistics import median
from time import perf_counter
import unicodedata

from . import hybrid_v8 as baseline, hybrid_v6 as v6, pipeline_v5 as v5
from . import refine_v8 as refine
from .document_fields_v8_final import financial_observations
from .profiling import capture_v4_rasters
from .review_v8_final import review_summary, selected_field_evidence
from .table_state_v8_final import continuation_header, next_table_state
from .table_v6 import arithmetic_checks
from .table_v3 import findings_for_items


def _crop_bounds(raster, parts):
    points = [point for part in parts for point in part.get('polygon', [])]
    if not points or not all(len(point) == 2 and all(isfinite(float(v)) for v in point) for point in points):
        return None
    x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
    y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
    pad = max(3, (y1 - y0) * .3)
    bounds = (max(0, floor(x0-pad)), max(0, floor(y0-pad)),
              min(raster.width, ceil(x1+pad)), min(raster.height, ceil(y1+pad)))
    return bounds if bounds[2] > bounds[0] and bounds[3] > bounds[1] else None


def _seller_readbacks(raster, candidates, page, findings):
    reads = []
    seller = candidates.get('seller_name', [])
    if raster is None or not seller:
        return reads
    chosen = max(seller, key=lambda c: (c['priority'], c['score']))
    bbox = _crop_bounds(raster, chosen['evidence'])
    if bbox is None:
        findings.append({'code':'V8_FINAL_CROP_NOT_AVAILABLE','field':'seller_name','page':page})
        return reads
    for lang in ('vie', 'vie+eng'):
        try:
            read = v5.ocr_region(raster, bbox, 'final-seller-'+lang, lang, 7, line_height=True)
            reads.append(read)
            literal = ' '.join(line.text for line in read.lines).strip()
            label = refine.party_label(literal)
            if label:
                if label[0] != 'seller_name':
                    continue
                literal = label[2]
            if literal and not refine.NOTICE.search(refine.v4.plain(literal)) and not refine.TITLE.fullmatch(refine.v4.plain(literal)):
                value = refine.candidate(read, read.lines[0], literal,
                                         list(range(len(read.boxes))), chosen['priority'])
                value['observed_literal'] = literal
                value['label_evidence'] = deepcopy(chosen.get('label_evidence', []))
                candidates.setdefault('seller_name', []).append(value)
        except (RuntimeError, ValueError, v5.old.pytesseract.TesseractError) as exc:
            findings.append({'code':'V8_FINAL_SELLER_REREAD_FAILED','page':page,
                             'error_type':type(exc).__name__})
    return reads


def _table_header_readback(raster, reads, page, findings):
    """One bounded, polarity-aware read of an observed incomplete header."""
    if raster is None:
        return []
    headers = [(read, header) for read in reads if (header := refine.grid.header_for(read))]
    if not headers or any('quantity' in header.centers for _read, header in headers):
        return []
    read, header = max(headers, key=lambda pair: len(pair[1].centers))
    if not {'description', 'unit', 'unit_price', 'amount'}.issubset(header.centers) or not header.indices:
        return []
    from PIL import ImageOps, ImageStat
    boxes = [read.boxes[i] for i in header.indices]
    h = median(box.word[3] - box.word[1] for box in boxes)
    if h <= 0:
        return []
    left = max(0, floor(min(box.word[0] for box in boxes) - h))
    right = min(raster.width, ceil(max(box.word[2] for box in boxes) + h))
    top = max(0, floor(min(box.word[1] for box in boxes) - 1.5 * h))
    bottom = min(raster.height, ceil(header.bottom + 1.5 * h))
    if right <= left or bottom <= top or (right - left) * (bottom - top) > 2_000_000:
        return []
    crop = raster.crop((left, top, right, bottom)).convert('L')
    inverted = ImageStat.Stat(crop).median[0] < 128
    if inverted:
        crop = ImageOps.invert(crop)
    try:
        observed = v5.ocr_region(crop, (0, 0, crop.width, crop.height),
                                 'header-final-columns', 'vie+eng', 6)
        mapped = [v5.rectangle(box.text, box.word[0] + left, box.word[1] + top,
                               box.word[2] + left, box.word[3] + top, box.score)
                  for box in observed.boxes]
        result = v5.Read(observed.tag, mapped, observed.groups, raster.size,
                         {**observed.transform, 'bbox': (left, top, right, bottom),
                          'inverted': inverted, 'coordinate_space': 'document pixels'})
        recovered = refine.grid.header_for(result)
        shared = set(header.centers).intersection(recovered.centers) if recovered else set()
        if (not recovered or 'quantity' not in recovered.centers
                or not {'description', 'unit_price', 'amount'}.issubset(shared)
                or any(abs(header.centers[key] - recovered.centers[key]) * raster.width > 3 * h
                       for key in shared)):
            findings.append({'code': 'V8_FINAL_HEADER_COLUMNS_UNRESOLVED', 'page': page,
                             'requires_review': True})
            return []  # An incompatible read must not drive column assignment.
        return [result]
    except (RuntimeError, ValueError, v5.old.pytesseract.TesseractError) as exc:
        findings.append({'code': 'V8_FINAL_HEADER_READ_FAILED', 'page': page,
                         'error_type': type(exc).__name__, 'requires_review': True})
        return []


def _cell_readbacks(raster, rows, reads, page, findings):
    recorded = []
    if raster is None:
        return recorded
    budget = 6
    page_tokens = {(box.text, box.polygon) for read in reads
                   if tuple(read.size) == raster.size and
                   read.transform.get('coordinate_space') == 'V4 processed raster pixels'
                   for box in read.boxes}
    vietnamese = any(refine.marks(read.text) for read in reads)
    for line_number, row in enumerate(rows, 1):
        for key in ('description', 'unit'):
            value = row.get(key)
            parts = row.get('evidence', {}).get(key, [])
            ambiguous = key == 'unit' and value and len([
                unit for unit in refine.UNITS if refine.v4.plain(unit) == refine.v4.plain(value)]) > 1
            low_score = any(part.get('ocr_score') is not None and part['ocr_score'] < .85 for part in parts)
            needs_name = key == 'description' and value and (low_score or (vietnamese and not refine.marks(value)))
            if budget <= 0 or not (ambiguous or needs_name):
                continue
            # A V8 row may retain evidence from a warped paper view. Only
            # crop if these exact tokens occur in this page's raster frame.
            in_frame = parts and all((part['text'], tuple(map(tuple, part['polygon']))) in page_tokens
                                     for part in parts)
            bbox = _crop_bounds(raster, parts) if in_frame else None
            if bbox is None:
                findings.append({'code':'V8_FINAL_CROP_NOT_AVAILABLE','line':line_number,'field':key,'page':page})
                continue
            variants = []
            for psm in (7, 13):
                if budget <= 0:
                    break
                budget -= 1
                try:
                    tag = f'final-cell-{key}/page{page}/line{line_number}/psm{psm}'
                    read = v5.ocr_region(raster, bbox, tag, 'vie', psm, line_height=True)
                    read.transform['coordinate_space'] = 'V4 processed raster pixels'
                    recorded.append(read)
                    text = ' '.join(line.text for line in read.lines).strip()
                    if read.lines and text:
                        variants.append((text, v5.line_conf(read.lines[0]), read))
                        if key == 'description' and len(read.lines) == 1:
                            row.setdefault('_cell_candidates', {}).setdefault(key, []).append({
                                'value': text, 'parts': refine.row_evidence(read.boxes,
                                    {'value': list(read.lines[0].ids)})['value'], 'read': read.tag})
                except (RuntimeError, ValueError, v5.old.pytesseract.TesseractError) as exc:
                    findings.append({'code':'V8_FINAL_CELL_REREAD_FAILED','page':page,
                                     'line':line_number,'field':key,'error_type':type(exc).__name__})
            exact = lambda text: unicodedata.normalize('NFC', text).casefold()
            same_identity = [variant for variant in variants
                             if refine.v4.plain(variant[0]) == refine.v4.plain(value)]
            agreement = (len(same_identity) >= 2 and len({exact(v[0]) for v in same_identity}) == 1
                         and min(v[1] for v in same_identity) >= .8
                         and len(same_identity) == len(variants))
            # More accents alone never establishes a new spelling. Two local
            # source observations must agree; the result still needs review.
            if agreement:
                chosen = max(same_identity, key=lambda variant: variant[1])
                row[key] = refine.canonical_unit(chosen[0]) if key == 'unit' else chosen[0]
                row['evidence'][key] = refine.row_evidence(
                    chosen[2].boxes, {'value': list(range(len(chosen[2].boxes)))})['value']
            else:
                findings.append({'code':'V8_FINAL_CELL_VARIANTS_UNRESOLVED','page':page,
                                 'line':line_number,'field':key,'retained':value,
                                 'alternatives':[variant[0] for variant in variants]})
    return recorded


def _local_table_candidate(local_read, ordinary_rows, inherited):
    """Prefer an observed cell-aware table only if it preserves row coverage.

    The full-page Paddle read remains the source for document-level fields.
    The usual independent Tesseract merge still decides any corrections.
    """
    from .layout import TextBox
    from .paddle_local import _parts_strong
    from .table_v6 import arithmetic_checks
    raw = (local_read.refined or {}).get('table_boxes', [])
    if not raw:
        return None, [], []
    boxes = [TextBox(p['text'], tuple(map(tuple, p['polygon'])), p['score']) for p in raw]
    table_read = v5.Read('paddle-local-table', boxes, [line.ids for line in refine.v4.lines_of(boxes)],
                         local_read.size, dict(local_read.transform),
                         {k:v for k,v in (local_read.refined or {}).items()
                          if k in ('description_band', 'description_crop', 'description_crop_error')})
    header = refine.grid.header_for(table_read)
    continuation = (local_read.refined or {}).get('table_region_kind') == 'continuation'
    if continuation:
        # Re-check the actual final-stage continuation state. Never recover a
        # whole new table using inherited labels alone, or trust a conflicting
        # fresh header detected inside the cropped body.
        if (header is not None or not inherited or not ordinary_rows
                or not {'description','amount'}.issubset(inherited.centers)):
            return None, [], []
    elif not header or not {'description','amount'}.issubset(header.centers):
        return None, [], []
    rows, warnings = refine.recover_rows([table_read], [], inherited)
    if continuation and len(rows) != len(ordinary_rows):
        return None, rows, warnings
    if not rows or len(rows) < len(ordinary_rows) or arithmetic_checks({}, rows):
        return None, rows, warnings
    # Require source-backed names and amounts for every proposed row, and
    # never prefer a candidate which loses populated cells from a known row.
    keys = ('description','unit','quantity','unit_price','amount')
    if not all(r.get(k) is not None and _parts_strong(r.get('evidence', {}).get(k, []), .85)
               for r in rows for k in ('description','amount')):
        return None, rows, warnings
    def y(row):
        pts = [p for part in row.get('evidence', {}).get('amount', []) for p in part.get('polygon', [])]
        return (min(p[1] for p in pts)+max(p[1] for p in pts))/2 if pts else None
    from statistics import median
    h = median(b.word[3]-b.word[1] for b in boxes)
    links = []
    for old in ordinary_rows:
        yy = y(old)
        matches = [i for i,r in enumerate(rows) if yy is not None and y(r) is not None
                   and abs(y(r)-yy) <= max(3,.6*h)]
        if len(matches)!=1 or matches[0] in links:
            return None, rows, warnings
        new = rows[matches[0]]
        if any(old.get(k) is not None and new.get(k) is None for k in keys):
            return None, rows, warnings
        links.append(matches[0])
    return table_read, rows, warnings


def _refine_page(page, old, layout, raster, carried, document_number, local_read=None, local_status=None):
    findings = []
    reads = refine.page_reads(layout, page)
    size = tuple(page['size'])
    if any(read.size != size for read in reads):
        findings.append({'code': 'V8_FINAL_READ_FRAME_MISMATCH'})
        reads = [read for read in reads if read.size == size]
    if raster is not None and raster.size != size:
        findings.append({'code': 'V8_FINAL_RASTER_FRAME_MISMATCH'})
        raster = None
    if not any(read.boxes for read in reads):
        findings.append({'code': 'V8_FINAL_NO_USABLE_PAGE_READS', 'requires_review': True})
        if local_read is not None and raster is not None:
            try:
                from .paddle_local import merge_rows
                candidates = refine.field_candidates([local_read])
                for values in candidates.values():
                    for value in values:
                        value['page'] = page['page']
                        value['read'] = f"page-{page['page']}/paddle-local"
                proposed, notes = refine.recover_rows([local_read], [], None)
                rows, warnings = merge_rows(old, proposed, [], local_read, local_status)
                for row in rows:
                    row['page'] = page['page']
                    row['cell_observations'] = row.pop('_cell_candidates', row.get('cell_observations', {}))
                    row.pop('_y', None)
                    row.pop('_read', None)
                details = {'page': page['page'], 'status': 'refined', 'field_candidates': {},
                           'local_ai_evidence': {'read': v6.serialized(local_read),
                           'field_candidates': candidates, 'rows': proposed, 'parser_findings': notes}}
                findings += warnings + [{'code': 'LOCAL_AI_PRIMARY_TEXT_UNAVAILABLE', 'requires_review': True}]
                return rows, {}, details, findings, None, financial_observations([local_read], page['page'])
            except Exception as exc:
                findings.append({'code': 'LOCAL_AI_COMPARISON_FAILED', 'error_type': type(exc).__name__,
                                 'requires_review': True})
        return old, {}, {'page': page['page'], 'status': 'v8_baseline_retained'}, findings, None, []
    inherited, warnings = continuation_header(carried, reads, page['page'])
    findings += warnings
    if any(note['code'] == 'V8_FINAL_CONTINUATION_IDENTIFIER_CONFLICT' for note in warnings):
        return old, {}, {'page': page['page'], 'status': 'v8_baseline_retained'}, findings, None, []
    header_reads = _table_header_readback(raster, reads, page['page'], findings)
    reads = [*reads, *header_reads]
    candidates = refine.field_candidates(reads)
    crop_reads = _seller_readbacks(raster, candidates, page['page'], findings)
    for values in candidates.values():
        for value in values:
            value['page'] = page['page']
            value['read'] = f"page-{page['page']}/{value['read']}"
    rows, warnings = refine.recover_rows(reads, old, inherited)
    findings += warnings
    cell_reads = _cell_readbacks(raster, rows, reads, page['page'], findings)
    local_evidence = None
    if local_read is not None and raster is not None:
        # Keep the ordinary Final result intact if independent recognition or
        # its parser fails; do not let a new header change the primary table.
        try:
            from .paddle_local import merge_rows
            local_candidates = refine.field_candidates([local_read])
            for values in local_candidates.values():
                for value in values:
                    value['page'] = page['page']
                    value['read'] = f"page-{page['page']}/paddle-local"
            local_rows, local_warnings = refine.recover_rows([local_read], [], inherited)
            staged = deepcopy(local_status)
            chosen, chosen_rows = local_read, local_rows
            table_evidence = None
            if (local_read.refined or {}).get('table_boxes'):
                try:
                    table_read, table_rows, table_warnings = _local_table_candidate(local_read, local_rows, inherited)
                    table_evidence = {'rows': table_rows, 'parser_findings': table_warnings,
                                      'selected': table_read is not None}
                    if table_read is not None:
                        chosen, chosen_rows = table_read, table_rows
                        table_evidence['read'] = v6.serialized(table_read)
                    for page_status in staged['pages']:
                        if page_status['page'] == page['page'] and 'table_ai' in page_status:
                            page_status['table_ai']['status'] = 'selected' if table_read else 'baseline_retained'
                except Exception as exc:
                    table_evidence = {'selected': False, 'error_type': type(exc).__name__}
                    for page_status in staged['pages']:
                        if page_status['page'] == page['page'] and 'table_ai' in page_status:
                            page_status['table_ai'].update(status='comparison_failed', reason=type(exc).__name__)
            compared, merge_warnings = merge_rows(rows, chosen_rows, [*reads, *cell_reads], chosen, staged, raster=raster)
            # Keep both readings and observed values in private extraction evidence.
            local_evidence = {'read': v6.serialized(local_read), 'field_candidates': local_candidates,
                              'rows': local_rows, 'parser_findings': local_warnings}
            if table_evidence is not None:
                local_evidence['table_ai'] = table_evidence
            rows = compared
            local_status.update(staged)
            findings += merge_warnings
        except Exception as exc:
            findings.append({'code': 'LOCAL_AI_COMPARISON_FAILED', 'error_type': type(exc).__name__,
                             'requires_review': True})
    next_state = next_table_state(reads, rows, page['page'], document_number,
                                  refine.table_header(reads, inherited))
    adjustments = financial_observations(reads, page['page'])
    for row in rows:
        row['page'] = page['page']
        row['cell_observations'] = row.pop('_cell_candidates', row.get('cell_observations', {}))
        row.pop('_y', None)
        row.pop('_read', None)
    details = {'page':page['page'], 'status':'refined', 'field_candidates':candidates,
               'inherited_columns':dict(inherited.centers) if inherited else None,
               'header_reads':[v6.serialized(read) for read in header_reads],
               'seller_reads':[v6.serialized(read) for read in crop_reads],
               'cell_reads':[v6.serialized(read) for read in cell_reads]}
    if local_evidence is not None:
        details['local_ai_evidence'] = local_evidence
    return rows, candidates, details, findings, next_state, adjustments


def _refine_document(fields, items, layout, frozen, rasters, start, local_ai=None):
    output, page_evidence, findings, adjustments = [], [], [], []
    document_candidates = {}
    pages = layout.get('pages', [])
    # Raster captures have no page ID of their own. Never index into a
    # shifted sequence when page metadata is absent, duplicated or reordered.
    if not pages or [p['page'] for p in pages] != list(range(1, len(pages) + 1)):
        raise ValueError('Final needs ordered page metadata')
    raster_count_matches = len(rasters) == sum(p['source'] == 'ocr' for p in pages)
    if not raster_count_matches:
        findings.append({'code': 'V8_FINAL_RASTER_SEQUENCE_UNCONFIRMED', 'requires_review': True})
    local_reads, local_status, local_candidates = {}, None, {}
    verification_frames = {}
    if local_ai is not None:
        from .paddle_local import recognize_document
        local_reads, local_status = recognize_document(pages, rasters, local_ai, layout, fields.get('invoice_number'))
        if local_status['status'] in ('partial', 'failed'):
            findings.append({'code': 'LOCAL_AI_UNAVAILABLE', 'requires_review': True,
                             'reason': local_status.get('reason', local_status['status'])})
    implicit_page = 1 if len(pages) == 1 and layout.get('total_pages', 1) == 1 else None
    cursor, carried, handled = 0, None, set()
    for page in pages:
        page_number = page['page']
        handled.add(page_number)
        old = deepcopy([row for row in items if row.get('page', implicit_page) == page_number])
        raster = None
        if page['source'] == 'ocr':
            if raster_count_matches:
                raster = rasters[cursor]
            cursor += 1
        if raster is not None and page_number in local_reads and raster.size == tuple(page['size']):
            verification_frames[page_number] = (raster, page, local_reads[page_number])
        page_local_status = deepcopy(local_status)
        try:
            rows, candidates, details, warnings, carried, observed = _refine_page(
                page, old, layout, raster, carried, fields.get('invoice_number'),
                local_reads.get(page_number), page_local_status)
        except Exception as exc:
            # Refinement is optional. Do not throw away valid V8 observations
            # and invoke the lower-quality current OCR merely for a crop/parser
            # failure. The unchanged baseline remains explicit in evidence.
            if local_status is not None and page_number in local_reads:
                for page_status in local_status['pages']:
                    if page_status['page'] == page_number:
                        page_status['status'] = 'comparison_failed'
            output += old
            carried = None
            findings.append({'code':'V8_FINAL_PAGE_BASELINE_RETAINED','page':page_number,
                             'error_type':type(exc).__name__, 'requires_review':True})
            page_evidence.append({'page':page_number,'status':'v8_baseline_retained',
                                  'error_type':type(exc).__name__})
            continue
        local_evidence = details.get('local_ai_evidence')
        if local_evidence:
            local_status.update(page_local_status)
            for key, values in local_evidence['field_candidates'].items():
                local_candidates.setdefault(key, []).extend(values)
        if local_status is not None and page_number in local_reads:
            for page_status in local_status['pages']:
                if page_status['page'] == page_number:
                    page_status['status'] = 'compared' if local_evidence else 'comparison_failed'
        output += rows
        adjustments += observed
        findings += [{**finding, 'page':finding.get('page', page_number)} for finding in warnings]
        page_evidence.append(details)
        for key, values in candidates.items():
            document_candidates.setdefault(key, []).extend(values)
    if local_status is not None and local_reads:
        compared = sum(page['status'] == 'compared' for page in local_status['pages'])
        if compared != len([page for page in pages if page['source'] == 'ocr']):
            local_status['status'] = 'partial' if compared else 'failed'
    if all(page['status'] == 'v8_baseline_retained' for page in page_evidence):
        if local_status is not None and local_reads:
            local_status.update(status='failed', fields_filled=0, fields_corrected=0,
                                cells_filled=0, cells_corrected=0, rows_recovered=0)
        return frozen['fields'], frozen['items'], {
            **frozen['layout'], 'v8_baseline': frozen, 'final_pages': page_evidence,
            'final_refinement_status': 'v8_baseline_retained', 'requires_review': True,
            'findings': [*frozen['layout'].get('findings', []), *findings],
            **({'local_ai': local_status} if local_status is not None else {}),
        }
    missing_pages = [deepcopy(row) for row in items if row.get('page', implicit_page) not in handled]
    if missing_pages:
        # Adding unlocated rows to reparsed rows risks counting the same
        # product twice. Keep the complete V8 table in its original order.
        output = deepcopy(items)
        if local_status is not None:
            local_status.update(cells_filled=0, cells_corrected=0, rows_recovered=0)
            findings = [note for note in findings if note.get('code') not in
                        ('LOCAL_AI_TABLE_RECOVERED', 'LOCAL_AI_ROW_RECOVERED', 'LOCAL_AI_CELL_ADOPTED')]
        findings.append({'code':'V8_FINAL_UNLINKED_PAGE_ROWS_RETAINED','count':len(missing_pages),
                         'retained_table':'hybrid_v8', 'requires_review':True})
    for n, row in enumerate(output, 1):
        row['line_no'] = n
    fields, warnings = refine.select_fields(fields, document_candidates)
    findings += warnings
    if local_status is not None and local_candidates:
        from .paddle_local import merge_fields
        try:
            staged = deepcopy(local_status)
            amended, local_findings = merge_fields(fields, document_candidates, local_candidates, staged,
                                                   frames=verification_frames, layout=layout)
            # Retain an existing financially consistent result rather than
            # introducing a new failed rule from a proposed correction.
            from app.invoice_financials import observe, arithmetic_rules
            from app import extraction
            financial = observe(layout.get('raw_text', ''), extraction._decimal_money)
            before_failures = {code for code, passed, _ in arithmetic_rules(fields, output, financial) if not passed}
            after_failures = {code for code, passed, _ in arithmetic_rules(amended, output, financial) if not passed}
            if after_failures - before_failures:
                local_status['conflicts'] += 1
                findings.append({'code': 'LOCAL_AI_FIELD_ARITHMETIC_RETAINED', 'requires_review': True})
            else:
                fields = amended
                local_status.update(staged)
                findings += local_findings
            # The final evidence includes both source reads, even if no value is adopted.
            for key, values in local_candidates.items():
                document_candidates.setdefault(key, []).extend(values)
        except Exception as exc:
            local_status['status'] = 'partial'
            findings.append({'code': 'LOCAL_AI_FIELD_COMPARISON_FAILED', 'error_type': type(exc).__name__,
                             'requires_review': True})
    findings += arithmetic_checks(fields, output) + findings_for_items(output)
    for index, observation in enumerate(adjustments):
        findings.append({'code': 'V8_FINAL_FINANCIAL_OBSERVATION', 'field': observation['role'],
                         'page': observation['page'], 'observed_amounts': observation['observed_amounts'],
                         'observed_rates': observation['observed_rates'],
                         'evidence_index': index, 'requires_review': True})
    findings += review_summary(fields, output, document_candidates, findings, layout)
    findings.append({'code':'EXPERIMENTAL_UNVERIFIED','reason':'Implementation is not independent NFR acceptance'})
    return fields, output, {**layout, 'source':'hybrid-v8-final', 'v8_baseline':frozen,
                           'final_pages':page_evidence, 'findings':findings, 'requires_review':True,
                           'final_refinement_status':('completed_with_retained_pages'
                               if any(p['status'] == 'v8_baseline_retained' for p in page_evidence)
                               else 'completed'),
                           'final_field_evidence':selected_field_evidence(fields, document_candidates),
                           'final_financial_observations':adjustments,
                           **({'local_ai': local_status} if local_status is not None else {}),
                           'elapsed_s':perf_counter()-start}


def extract_hybrid(data, ext, max_pages=12, *, local_ai=None):
    start = perf_counter()
    with capture_v4_rasters() as rasters:
        try:
            fields, items, layout = baseline.extract_hybrid(data, ext, max_pages)
            if ext == 'xml':
                return fields, items, layout
            frozen = deepcopy({'fields':fields, 'items':items, 'layout':layout})
            try:
                return _refine_document(fields, items, layout, frozen, rasters, start, local_ai=local_ai)
            except Exception as exc:
                # Baseline failures above still propagate to the existing
                # runtime fallback. Only optional Final-stage failures recover
                # here, with original values and a visible failure finding.
                fields, items = deepcopy(frozen['fields']), deepcopy(frozen['items'])
                return fields, items, {**deepcopy(frozen['layout']), 'source':'hybrid-v8-final',
                    'v8_baseline':frozen, 'requires_review':True,
                    'final_pages':[], 'final_refinement_status':'v8_baseline_retained',
                    'findings':[*deepcopy(frozen['layout'].get('findings', [])),
                                {'code':'V8_FINAL_REFINEMENT_BASELINE_RETAINED',
                                 'error_type':type(exc).__name__, 'requires_review':True},
                                {'code':'EXPERIMENTAL_UNVERIFIED'}],
                    'elapsed_s':perf_counter()-start}
        finally:
            for raster in rasters:
                raster.close()
