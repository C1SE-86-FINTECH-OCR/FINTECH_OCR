"""Conservative continuation of observed table columns in Hybrid V8 Final."""
import re
from copy import deepcopy
from statistics import median

from . import pipeline_v4 as context, pipeline_v5 as regions, table_v8 as grid
from .document_fields_v8_final import document_label, observed_value
from .table_v3 import Header, row_evidence
from .source_links_v8_final import split_party_columns


FINAL_TOTAL = re.compile(
    r'^(?:tong(?: tien| cong)? thanh toan|tong tien phai tra|grand total|total payable|'
    r'amount due|tien khach(?: dua| tra)|cash tendered|tien thua|change)\b')


def continuation_header(state, reads, page_number):
    if not state or state['page'] + 1 != page_number or not reads:
        return None, []
    width, height = reads[0].size
    previous_width, previous_height = state['size']
    if (width <= 0 or height <= 0 or previous_width <= 0 or previous_height <= 0
            or abs(width / previous_width - 1) > .10
            or abs((height / width) / (previous_height / previous_width) - 1) > .10):
        return None, [{'code':'V8_FINAL_CONTINUATION_FRAME_CHANGED','page':page_number}]
    for read in reads:
        for line in split_party_columns(read).lines:
            label = document_label(line.text)
            if label and label[0] in ('invoice_number', 'receipt_number'):
                number = observed_value(*label)
                if number and not state.get('document_number'):
                    return None, [{'code': 'V8_FINAL_CONTINUATION_IDENTIFIER_UNESTABLISHED', 'page': page_number}]
                if number and state.get('document_number') and number != state['document_number']:
                    return None, [{'code':'V8_FINAL_CONTINUATION_IDENTIFIER_CONFLICT',
                                   'page':page_number, 'observed':number,
                                   'previous':state['document_number']}]
    return Header(0, dict(state['centers']), ()), []


def next_table_state(reads, rows, page_number, document_number, inherited=None):
    if not reads or not rows:
        return None
    headers = [grid.header_for(read) for read in reads]
    header = max((value for value in headers if value),
                 key=lambda value: len(value.centers), default=inherited)
    if inherited and header and set(header.centers).issubset(inherited.centers) and all(
            abs(header.centers[key] - inherited.centers[key]) * reads[0].size[0]
            <= 2 * median(box.word[3] - box.word[1] for read in reads for box in read.boxes)
            for key in header.centers):
        header = inherited
    if header is None or not {'description', 'amount'}.issubset(header.centers):
        return None
    positions = [point[1] for row in rows for part in row.get('evidence', {}).get('amount', [])
                 for point in part.get('polygon', [])]
    if not positions:
        return None
    last_row = max(positions)
    for read in reads:
        for line in read.lines:
            text = context.plain(line.text)
            carried_total = re.search(r'chuyen trang|cong trang|page total|carried forward|carry forward', text)
            if line.y > last_row and FINAL_TOTAL.match(text) and not carried_total:
                return None
    return {'page':page_number, 'centers':dict(header.centers), 'size':reads[0].size,
            'document_number':document_number}


def source_supported_amount_only(row):
    """Accept a missing quantity/price only with separate name/amount boxes."""
    evidence = row.get('evidence', {})
    names = [part for part in evidence.get('description', []) if part.get('polygon')]
    amounts = [part for part in evidence.get('amount', []) if part.get('polygon')]
    if not names or not amounts or row.get('amount') is None:
        return False
    if not any(re.search(r'[^\W\d_]{2}', part.get('text', '')) for part in names):
        return False
    height = median(max(p[1] for p in part['polygon']) - min(p[1] for p in part['polygon'])
                    for part in amounts)
    name_right = max(p[0] for part in names for p in part['polygon'])
    amount_left = min(p[0] for part in amounts for p in part['polygon'])
    # A model embedded in the name cannot be its separated amount cell.
    return amount_left - name_right > max(3, height)


def reconcile_page_rows(tables, height):
    """Combine cell observations only for an unambiguous row in two reads."""
    ordered = sorted(tables, key=lambda entry: len(entry[1]), reverse=True)
    bands = [[row] for row in ordered[0][1]]
    findings = []
    for read, rows in ordered[1:]:
        nearby = [[index for index, band in enumerate(bands)
                   if abs(band[0]['_y'] - row['_y']) < height] for row in rows]
        claimed = {}
        for indices in nearby:
            for index in indices:
                claimed[index] = claimed.get(index, 0) + 1
        for row, indices in zip(rows, nearby):
            if not indices:
                bands.append([row])
                continue
            if len(indices) == 1:
                index = indices[0]
                anchor = bands[index][0]
                if (claimed[index] == 1
                        and context.plain(anchor['description']) == context.plain(row['description'])):
                    bands[index].append(row)
                    continue
            findings.append({'code': 'V8_FINAL_ROW_LINK_UNCERTAIN', 'read': read.tag,
                             'description': row['description'], 'y': row['_y']})
    result = []
    for band in sorted(bands, key=lambda group: group[0]['_y']):
        winner = max(band, key=lambda row: grid.confidence(row['evidence'].get('description', [])))
        row = deepcopy(winner)
        candidates = {}
        for source in band:
            for key, values in source.get('_cell_candidates', {}).items():
                candidates.setdefault(key, []).extend(deepcopy(values))
        row['_cell_candidates'] = candidates
        # Arithmetic is a review check, not an oracle for selecting a digit
        # among conflicting OCR alternatives. Preserve observed values.
        findings.extend(grid.select_cells(row, allow_arithmetic=False))
        result.append(row)
    return result, findings


def headerless_amount_rows(read):
    """A bill can print only description and amount, including a single item.

    Require an actual monetary token in a separated right-hand box. Quantities
    and unit prices remain absent. No row is copied from the document total.
    """
    if context.classify_context(read.lines, read.size) not in ('bill', 'einvoice'):
        return []
    h = median(box.word[3] - box.word[1] for box in read.boxes) if read.boxes else 12
    metadata = [line.y for line in read.lines if line.y < read.size[1] * .45
                and re.match(r'^(?:ngay|date|so (?:hoa don|hd|bill|phieu)|invoice no|receipt no)\b',
                             context.plain(line.text))]
    start = max(metadata, default=0)
    rows = []
    for line in sorted(read.lines, key=lambda value: value.y):
        if line.y <= start:
            continue
        text = context.semantic(line.text)
        if context.SUMMARY.match(text) or context.ADJUST.match(text):
            break
        if context.META.match(text) or regions.TYPE.fullmatch(text):
            continue
        values = [value for value in context.money_tokens(line) if not value.get('percent')]
        if len(values) != 1:
            continue
        amount = values[0]
        if not amount['formatted'] or amount['value'] < 0 or amount['x'] < read.size[0] * .55:
            continue
        ids = [i for i in line.ids if i not in amount['ids']]
        if not ids:
            continue
        row = {'description':' '.join(read.boxes[i].text for i in ids), 'unit':None,
               'quantity':None, 'unit_price':None, 'amount':amount['value'], '_y':line.y,
               'evidence':row_evidence(read.boxes, {'description':ids,'amount':amount['ids']})}
        if source_supported_amount_only(row) and grid.decorate(row, read):
            rows.append(row)
    return rows
