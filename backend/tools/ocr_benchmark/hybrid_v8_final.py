"""V8 Final refinements with source evidence and bounded, recoverable stages.

The original V8/current engines remain available. No database, labels, network
or acceptance decisions are used here. Optional failures retain observed data.
"""
from copy import deepcopy
from math import ceil, floor, isfinite
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


def _cell_readbacks(raster, rows, reads, page, findings):
    recorded = []
    if raster is None:
        return recorded
    budget = 6
    page_tokens = {(box.text, box.polygon) for read in reads for box in read.boxes}
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
                    recorded.append(read)
                    text = ' '.join(line.text for line in read.lines).strip()
                    if read.lines and text:
                        variants.append((text, v5.line_conf(read.lines[0]), read))
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


def _refine_page(page, old, layout, raster, carried, document_number):
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
        findings.append({'code': 'V8_FINAL_NO_USABLE_PAGE_READS'})
        return old, {}, {'page': page['page'], 'status': 'v8_baseline_retained'}, findings, None, []
    inherited, warnings = continuation_header(carried, reads, page['page'])
    findings += warnings
    if any(note['code'] == 'V8_FINAL_CONTINUATION_IDENTIFIER_CONFLICT' for note in warnings):
        return old, {}, {'page': page['page'], 'status': 'v8_baseline_retained'}, findings, None, []
    candidates = refine.field_candidates(reads)
    crop_reads = _seller_readbacks(raster, candidates, page['page'], findings)
    for values in candidates.values():
        for value in values:
            value['page'] = page['page']
            value['read'] = f"page-{page['page']}/{value['read']}"
    rows, warnings = refine.recover_rows(reads, old, inherited)
    findings += warnings
    cell_reads = _cell_readbacks(raster, rows, reads, page['page'], findings)
    next_state = next_table_state(reads, rows, page['page'], document_number, inherited)
    adjustments = financial_observations(reads, page['page'])
    for row in rows:
        row['page'] = page['page']
        row['cell_observations'] = row.pop('_cell_candidates', row.get('cell_observations', {}))
        row.pop('_y', None)
        row.pop('_read', None)
    details = {'page':page['page'], 'status':'refined', 'field_candidates':candidates,
               'inherited_columns':dict(inherited.centers) if inherited else None,
               'seller_reads':[v6.serialized(read) for read in crop_reads],
               'cell_reads':[v6.serialized(read) for read in cell_reads]}
    return rows, candidates, details, findings, next_state, adjustments


def _refine_document(fields, items, layout, frozen, rasters, start):
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
        try:
            rows, candidates, details, warnings, carried, observed = _refine_page(
                page, old, layout, raster, carried, fields.get('invoice_number'))
        except Exception as exc:
            # Refinement is optional. Do not throw away valid V8 observations
            # and invoke the lower-quality current OCR merely for a crop/parser
            # failure. The unchanged baseline remains explicit in evidence.
            output += old
            carried = None
            findings.append({'code':'V8_FINAL_PAGE_BASELINE_RETAINED','page':page_number,
                             'error_type':type(exc).__name__, 'requires_review':True})
            page_evidence.append({'page':page_number,'status':'v8_baseline_retained',
                                  'error_type':type(exc).__name__})
            continue
        output += rows
        adjustments += observed
        findings += [{**finding, 'page':finding.get('page', page_number)} for finding in warnings]
        page_evidence.append(details)
        for key, values in candidates.items():
            document_candidates.setdefault(key, []).extend(values)
    if all(page['status'] == 'v8_baseline_retained' for page in page_evidence):
        return frozen['fields'], frozen['items'], {
            **frozen['layout'], 'v8_baseline': frozen, 'final_pages': page_evidence,
            'final_refinement_status': 'v8_baseline_retained', 'requires_review': True,
            'findings': [*frozen['layout'].get('findings', []), *findings],
        }
    missing_pages = [deepcopy(row) for row in items if row.get('page', implicit_page) not in handled]
    if missing_pages:
        # Adding unlocated rows to reparsed rows risks counting the same
        # product twice. Keep the complete V8 table in its original order.
        output = deepcopy(items)
        findings.append({'code':'V8_FINAL_UNLINKED_PAGE_ROWS_RETAINED','count':len(missing_pages),
                         'retained_table':'hybrid_v8', 'requires_review':True})
    for n, row in enumerate(output, 1):
        row['line_no'] = n
    fields, warnings = refine.select_fields(fields, document_candidates)
    findings += warnings
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
                           'elapsed_s':perf_counter()-start}


def extract_hybrid(data, ext, max_pages=12):
    start = perf_counter()
    with capture_v4_rasters() as rasters:
        try:
            fields, items, layout = baseline.extract_hybrid(data, ext, max_pages)
            if ext == 'xml':
                return fields, items, layout
            frozen = deepcopy({'fields':fields, 'items':items, 'layout':layout})
            try:
                return _refine_document(fields, items, layout, frozen, rasters, start)
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
