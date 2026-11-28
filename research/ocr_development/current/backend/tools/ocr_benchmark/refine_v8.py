"""Structural V8 refinements. Source OCR observations only, no dataset access."""
from copy import deepcopy
from decimal import Decimal
from statistics import median
import re
import unicodedata
from app.invoice_financials import (party_name_allowed, item_description_boundary, financial_heading, amount_in_words,
                                   reference_line_indices, party_name_literal)

from . import pipeline_v4 as v4, pipeline_v5 as v5, table_v8 as grid
from .table_v3 import row_evidence, number
from .source_links_v8_final import (
    baseline_row_match, following_value, party_label, contextual_party_label, party_name_anchor, token_ids_for_span, wrapped_party_value, split_party_columns,
)
from .document_fields_v8_final import (document_label, identity, observed_value, target_observations,
                                     inline_invoice_date_observations, monetary_observations, MONETARY_FIELDS)
from .table_state_v8_final import headerless_amount_rows, reconcile_page_rows, source_supported_amount_only


NOTICE = re.compile(r'mau gia lap|chung tu mo phong|khong co gia tri|khong phai hoa don|ocr test|synthetic test|test document|not (?:a |an )?invoice|sample (?:only|document)|\bsigned\b|ky dien tu|ky ghi ro')
TITLE = re.compile(r'^(?:hoa don|phieu thanh toan|bill|receipt|vat invoice|value added tax invoice|invoice)\b')
FOOTER = re.compile(r'^(?:cong tien hang|tong (?:tien|cong|thanh toan)|tam tinh|tien truoc thue|subtotal|grand total|total|giam gia|chiet khau|discount|thue suat|tien thue|vat|tien khach|tien tra lai|tien thua|cash|change)\b')
RECEIPT_HEADER = re.compile(r'mat hang|item|ten hang|description')
SALE = re.compile(r'^\s*(\d+(?:[.,]\d+)?)\s+([^\W\d_]+(?:\s+[^\W\d_]+){0,2}?)\s*[x×*]\s*(\d[\d.,]*)\s+(\d[\d.,]*)(?:\s*(?:VND|đ))?\s*$', re.I)
UNITS = ('Cái', 'Hộp', 'Gói', 'Chai', 'Túi', 'Kg', 'Lít', 'Ram', 'Thùng', 'Quyển', 'Cây', 'Cuộn', 'Cuốn', 'Bộ', 'Tờ', 'Tô', 'Sợi', 'Phần', 'Suất', 'Ly', 'pc', 'giờ', 'ngày')


def canonical_unit(value):
    if value is None:
        return None
    value = value.strip(' .,:;')
    exact = [u for u in UNITS if u.casefold() == value.casefold()]
    if exact:
        return exact[0]
    matches = [u for u in UNITS if v4.plain(u) == v4.plain(value)]
    return matches[0] if len(matches) == 1 else value


def marks(value):
    return sum(bool(unicodedata.combining(c)) for c in unicodedata.normalize('NFD', value)) + sum(c in 'đĐ' for c in value)


def page_reads(layout, page):
    from .hybrid_v8 import read_fingerprint
    from .hybrid_v7 import restored
    from .hybrid_v6 import saved_read
    diag = next((p for p in layout.get('v7_pages', []) if p['page'] == page['page']), {})
    reads = [restored(r) for r in diag.get('reads', [])] or [saved_read(page)]
    distinct, seen = [], set()
    for rd in reads:
        signature = read_fingerprint(rd)
        if signature in seen:
            continue
        seen.add(signature)
        rd.transform = {**rd.transform, 'trusted_text_layer': page['source'] == 'pdf-text'}
        distinct.append(rd)
    return distinct


def field_candidates(reads):
    observations = {}
    for original in reads:
        source_lines = original.lines
        related = reference_line_indices([line.text for line in source_lines])
        if related:
            original = v5.Read(original.tag, original.boxes,
                               [line.ids for index, line in enumerate(source_lines) if index not in related],
                               original.size, original.transform)
        original_header = grid.header_for(original)
        date_boundary = original_header.bottom if original_header else original.size[1]
        for line, value, ids, literal in inline_invoice_date_observations(original, date_boundary):
            entry = candidate(original, line, value, ids, 2)
            entry['observed_literal'] = literal
            entry['label_evidence'] = row_evidence(original.boxes, {'label': line.ids})['label']
            observations.setdefault('invoice_date', []).append(entry)
        rd = split_party_columns(original)
        lines = sorted(rd.lines, key=lambda l: (l.y, min(rd.boxes[i].word[0] for i in l.ids)))
        boundary = min((h.bottom for h in [grid.header_for(rd)] if h), default=rd.size[1])
        party_end = min((line.y for line in lines if amount_in_words(line.text) or financial_heading(line.text)
                         or re.match(r'^(?:chu ky|digitally signed|(?:da )?ky dien tu)\b', v4.plain(line.text))
                         or ((spec := document_label(line.text)) and spec[0] in
                             ('subtotal', 'subtotal_net', 'subtotal_gross', 'vat_amount', 'total_amount')
                             and observed_value(*spec) is not None)), default=boundary)
        party_boundary = min(boundary, party_end)
        party_columns = [(line, spec[1]) for line in lines if line.y < party_boundary
                         and (spec := contextual_party_label(rd, line, lines, party_boundary))
                         and spec[0] in ('buyer_name', 'seller_name')]
        for observation in monetary_observations(rd):
            value = candidate(rd, observation['line'], observation['value'], observation['ids'], 3)
            value['observed_literal'] = observation['literal']
            value['label_evidence'] = row_evidence(rd.boxes, {'label': observation['label_ids']})['label']
            observations.setdefault(observation['key'], []).append(value)
        for line in lines:
            plain = v4.plain(line.text)
            if NOTICE.search(plain):
                continue
            labelled = contextual_party_label(rd, line, lines, party_boundary) if line.y < party_boundary else None
            if labelled:
                key, role, tail = labelled
                left = min(rd.boxes[i].word[0] for i in line.ids)
                height = median(rd.boxes[i].word[3] - rd.boxes[i].word[1] for i in line.ids)
                owner = line if role else None
                original_label = party_label(line.text)
                if original_label and original_label[0] == 'party_name':
                    owner = party_name_anchor(rd, line, lines, party_boundary)
                value_line = line
                ids = line.ids
                if tail:
                    start = re.search('[:：]', line.text).end()
                    ids = token_ids_for_span(line, start, len(line.text))
                else:
                    following = following_value(rd, line, lines, party_boundary)
                    if following and not (v4.META.match(v4.plain(following.text))
                                          or FOOTER.match(v4.plain(following.text))):
                        tail, ids, value_line = following.text, following.ids, following
                if key == 'tax_code':
                    # Remove printed whitespace only; never repair digits or
                    # transfer a buyer's tax identifier into the seller role.
                    observed = re.sub(r'\s+', '', tail)
                    if role is None:
                        # Resolve the column before vertical proximity. A
                        # seller label in the left column cannot own the tax
                        # line below a buyer label in the right column.
                        anchors = [(anchor, side, min(rd.boxes[i].word[0] for i in anchor.ids))
                                   for anchor, side in party_columns if anchor.y <= line.y + height / 2]
                        nearby = []
                        for anchor, side, x in anchors:
                            peers = [px for other, other_side, px in anchors
                                     if other_side != side and abs(other.y - anchor.y) < height]
                            low = max(((x + px) / 2 for px in peers if px < x), default=float('-inf'))
                            high = min(((x + px) / 2 for px in peers if px > x), default=float('inf'))
                            if low <= left < high and (peers or abs(x - left) <= 2 * height):
                                nearby.append((anchor, side, x))
                        if nearby:
                            last = max(anchor.y for anchor, _side, _x in nearby)
                            owners = [(anchor, side) for anchor, side, _x in nearby if last - anchor.y < height / 2]
                            if len({side for _anchor, side in owners}) == 1:
                                owner, role = owners[0]
                    if role and re.fullmatch(r'\d{10}(?:-?\d{3})?', observed):
                        key = role + '_tax_code'
                    else:
                        continue
                else:
                    tail = party_name_literal(tail)
                    value_start = value_line.text.rfind(tail) if tail else -1
                    if value_start >= 0:
                        ids = token_ids_for_span(value_line, value_start, value_start + len(tail))
                    observed = tail
                    if (not party_name_allowed(tail)
                            or len(tail.strip()) < 2 or not re.search(r'[^\W\d_]', tail)
                            or NOTICE.search(v4.plain(tail))
                            or TITLE.fullmatch(v4.plain(tail)) or party_label(tail)
                            or document_label(tail)):
                        continue
                    stop = lambda following: bool(NOTICE.search(v4.plain(following.text))
                                                  or TITLE.match(v4.plain(following.text))
                                                  or v4.META.match(v4.plain(following.text))
                                                  or FOOTER.match(v4.plain(following.text))
                                                  or not party_name_allowed(following.text)
                                                  or document_label(following.text)
                                                  or v4.money_tokens(following))
                    extended = wrapped_party_value(rd, value_line, ids, lines, party_boundary, stop)
                    if extended != ids:
                        # For an inline label/value that shares one box, do
                        # not prepend the label again when extending its name.
                        extra = [i for i in extended if i not in ids]
                        tail = tail + ' ' + ' '.join(rd.boxes[i].text for i in extra)
                        observed, ids = tail, extended
                value = candidate(rd, value_line, observed, ids, 3)
                value['observed_literal'] = tail
                value['label_evidence'] = row_evidence(rd.boxes, {'label': line.ids})['label']
                if owner is not None:
                    value['role_evidence'] = row_evidence(rd.boxes, {'role': owner.ids})['role']
                observations.setdefault(key, []).append(value)
            spec = document_label(line.text)
            if spec and spec[0] not in MONETARY_FIELDS and (line.y < boundary or spec[0] == 'vat_rate'):
                key, literal = spec
                ids, value_line = line.ids, line
                if literal:
                    start = line.text.rfind(literal)
                    ids = token_ids_for_span(line, start, start + len(literal)) if start >= 0 else line.ids
                else:
                    following = following_value(rd, line, lines, rd.size[1])
                    if following:
                        literal, ids, value_line = following.text, following.ids, following
                observed = observed_value(key, literal)
                if observed is not None:
                    value = candidate(rd, value_line, observed, ids, 3)
                    value['observed_literal'] = literal
                    value['label_evidence'] = row_evidence(rd.boxes, {'label': line.ids})['label']
                    observations.setdefault(key, []).append(value)
            # Receipt identifiers are accepted as document numbers, not VAT invoice IDs.
            receipt = re.search(r'\b(?:so phieu|so bill|receipt (?:no\.?|number))\s*[:.]\s*([a-z0-9][a-z0-9/-]*)', plain)
            if receipt and receipt.start() == 0 and receipt.end() == len(plain) and not spec and line.y < boundary:
                observations.setdefault('receipt_number', []).append(candidate(rd, line, receipt[1].upper(), line.ids, 2))
            currency = re.search(r'^(?:dong tien thanh toan|currency|loai tien)\s*:\s*([a-z]{3})$', plain)
            if currency and line.y < boundary:
                observations.setdefault('currency', []).append(candidate(rd, line, currency[1].upper(), line.ids, 2))
        # A title or warning is never a seller. Restrict unlabelled candidates
        # to the header before the first title/date/receipt metadata.
        end = min((l.y for l in lines if TITLE.match(v4.plain(l.text)) or re.match(r'^(?:so phieu|ngay|date|receipt no)\b', v4.plain(l.text))), default=0)
        end = min(end, party_boundary)
        for line in lines:
            p = v4.plain(line.text)
            if not line.y < end or not party_name_allowed(line.text) or NOTICE.search(p) or TITLE.match(p) or re.match(r'^(?:dia chi|address|tel|phone|mst|ma so thue)\b', p):
                continue
            if len(re.findall(r'[^\W\d_]', line.text)) < 4 or v4.money_tokens(line):
                continue
            observations.setdefault('seller_name', []).append(candidate(rd, line, line.text, line.ids, 1))
    return observations


def candidate(rd, line, value, ids, priority):
    scores = [rd.boxes[i].score for i in ids if rd.boxes[i].score is not None]
    score = min(scores) if scores else v5.line_conf(line)
    return {'value': value, 'read': rd.tag, 'priority': priority, 'score': score,
            'trusted_text_layer': bool(rd.transform.get('trusted_text_layer')),
            'evidence': row_evidence(rd.boxes, {'value': ids})['value']}


def select_fields(fields, observations):
    result = dict(fields)
    findings = []
    for role in ('seller_name', 'buyer_name'):
        if result.get(role) and (NOTICE.search(v4.plain(result[role])) or not party_name_allowed(result[role])):
            findings.append({'code':'V8_FINAL_REJECTED_PARTY_METADATA','field':role,'original':result[role]})
            result[role] = None
    for key, values in target_observations(result.get('document_type'), observations).items():
        if key in ('seller_name', 'buyer_name'):
            rejected = [c for c in values if not party_name_allowed(c['value'])]
            if rejected:
                findings.append({'code': 'V8_FINAL_REJECTED_PARTY_METADATA', 'field': key,
                                 'reason': 'semantic type does not match a party name'})
            values = [c for c in values if party_name_allowed(c['value'])]
            if not values:
                continue
        qualified = [c for c in values if c['trusted_text_layer'] or c['score'] >= .8]
        if not qualified:
            findings.append({'code':'V8_FINAL_FIELD_LOW_EVIDENCE','field':key,
                             'observed_values':[c['value'] for c in values]})
            continue
        best_priority = max(c['priority'] for c in qualified)
        eligible = [c for c in qualified if c['priority'] == best_priority]
        if key == 'seller_name' and best_priority < 3 and result.get(key):
            # Unlabelled address/tagline candidates must not displace a
            # supported baseline supplier. A real seller label can do so.
            eligible = [c for c in eligible if identity(c['value'], name=True) == identity(result[key], name=True)]
        if not eligible:
            continue
        # Group recognized identities, not invented spellings. Native text and
        # agreeing source reads rank above a mere confidence-score tie-break.
        groups = {}
        for c in eligible:
            groups.setdefault(identity(c['value'], name=key.endswith('_name')), []).append(c)
        if key == 'vat_rate' and len(groups) > 1:
            result[key] = None
            findings.append({'code': 'V8_FINAL_MULTIPLE_VAT_RATE_OBSERVATIONS', 'field': key,
                             'observed_values': [group[0]['value'] for group in groups.values()],
                             'reason': 'multiple rates or conflicting OCR; no single document rate established'})
            continue
        rank = lambda group: (any(c['trusted_text_layer'] for c in group), len({c['read'] for c in group}))
        strongest = max(map(rank, groups.values()))
        leaders = [group for group in groups.values() if rank(group) == strongest]
        target = key
        if len(leaders) > 1:
            previous = result.get(target)
            findings.append({'code':'V8_FINAL_FIELD_UNRESOLVED','field':target,
                             'observed_values':[c['value'] for c in eligible], 'retained':previous,
                             'reason':'equally supported distinct values; no confidence tie-break'})
            continue
        group = leaders[0]
        exact = [c for c in group if str(c['value']) == str(result.get(target))]
        best = max(exact or group, key=lambda c: (c['trusted_text_layer'], c['score']))
        if len({str(c['value']) for c in group}) > 1:
            findings.append({'code':'V8_FINAL_LITERAL_VARIANTS','field':target,
                             'values':[c['value'] for c in group], 'selected':best['value'],
                             'reason':'accent variants are observations, not verified spelling'})
        if len(groups) > 1:
            findings.append({'code': 'V8_FINAL_FIELD_CONFLICT', 'field': target,
                             'values': [c['value'] for c in eligible],
                             'selected': best['value'],
                             'reason': 'conflicting OCR observations; selection is not verification'})
        result[target] = best['value']
    tax_identity = lambda value: re.sub(r'[\s-]', '', str(value or ''))
    if result.get('buyer_tax_code') and tax_identity(result.get('buyer_tax_code')) == tax_identity(result.get('seller_tax_code')):
        def sources(key):
            return {(entry.get('page'), tuple(tuple(point) for point in part.get('polygon', [])))
                    for entry in observations.get(key, [])
                    if entry.get('role_evidence') and tax_identity(entry['value']) == tax_identity(result[key])
                    and (entry['trusted_text_layer'] or entry['score'] >= .8)
                    for part in entry.get('evidence', [])}
        seller_source, buyer_source = sources('seller_tax_code'), sources('buyer_tax_code')
        if not seller_source or not buyer_source or not seller_source.isdisjoint(buyer_source):
            findings.append({'code': 'V8_FINAL_SHARED_PARTY_TAX_SOURCE', 'field': 'buyer_tax_code',
                             'original': result['buyer_tax_code'],
                             'reason': 'No independent buyer-owned tax observation; do not copy the seller identifier'})
            result['buyer_tax_code'] = None
    return result, findings


def safe_zone(read, header):
    zone = v5.zones(read)
    if not header:
        return zone
    carried = re.compile(r'chuyen trang|cong trang|page total|carried forward|carry forward')
    terminal = re.compile(r'^(?:tong (?:cong )?(?:tien )?(?:phai )?thanh toan|grand total|amount due|total payable|'
                          r'so tien (?:viet )?bang chu|amount in words|chu ky|digitally signed)\b')
    def selling_line(line):
        plain = v4.plain(line.text)
        if FOOTER.match(plain) or financial_heading(line.text) or v4.META.match(plain) or NOTICE.search(plain):
            return False
        return bool(re.search(r'[^\W\d_]{2}', line.text) and any(
            not value.get('percent') and min(header.centers, key=lambda key: abs(header.centers[key] * read.size[0] - value['x'])) == 'amount'
            for value in v4.money_tokens(line)))
    footer = [line.y - zone['h'] / 2 for line in read.lines
              if line.y > header.bottom + zone['h'] and (FOOTER.match(v4.plain(line.text)) or financial_heading(line.text))
              and not carried.search(v4.plain(line.text))
              and (terminal.match(v4.plain(line.text)) or not any(other.y > line.y and selling_line(other) for other in read.lines))]
    return {**zone, 'table_start': header.bottom, 'header_end': header.bottom,
            'footer_start': min(footer, default=read.size[1]), 'header_found': True}


def positioned_rows(read, zone, header):
    """Bound descriptions by source columns and structural row barriers."""
    roles = {key: value for key, value in header.centers.items() if key != 'ordinal'}
    if 'description' not in roles:
        return grid.parse_rows(read, zone, header)
    if min(roles, key=roles.get) == 'description':
        rows, notes = grid.parse_rows(read, zone, header)
    else:
        from . import table_v7
        rows, notes = table_v7.parse_rows(read, zone, header)
    width, h = read.size[0], zone['h']
    center = roles['description'] * width
    before = [value * width for value in roles.values() if value * width < center]
    after = [value * width for value in roles.values() if value * width > center]
    left = (max(before) + center) / 2 if before else 0
    if 'ordinal' in header.centers and header.centers['ordinal'] * width < center:
        left = max(left, header.centers['ordinal'] * width + h / 2)
    right = (min(after) + center) / 2 if after else width
    ordered = sorted(rows, key=lambda row: row['_y'])
    output = []
    for n, row in enumerate(ordered):
        y = row['_y']
        previous = ordered[n - 1]['_y'] if n else header.bottom
        following = ordered[n + 1]['_y'] if n + 1 < len(ordered) else zone['footer_start']
        # Header centers bisect a wide description column. Prefer the actual
        # adjacent cell edges of this row instead of cutting a long name at
        # the midpoint between its heading and the next centered heading.
        right_cells = [min(x for x, _y in part['polygon'])
                       for key, parts in row.get('evidence', {}).items()
                       if key in roles and roles[key] * width > center
                       for part in parts if part.get('polygon')]
        left_cells = [max(x for x, _y in part['polygon'])
                      for key, parts in row.get('evidence', {}).items()
                      if key in roles and roles[key] * width < center
                      for part in parts if part.get('polygon')]
        row_left = max(left_cells) + .15 * h if left_cells else left
        row_right = min(right_cells) - .15 * h if right_cells else right
        def name_parts(line):
            plain = v4.plain(line.text)
            if line.y <= header.bottom or line.y >= zone['footer_start'] or item_description_boundary(line.text) or v4.META.match(plain) or NOTICE.search(plain):
                return []
            ids = [i for i in line.ids if row_left <= (read.boxes[i].word[0] + read.boxes[i].word[2]) / 2 < row_right]
            text = ' '.join(read.boxes[i].text for i in ids)
            return ids if not item_description_boundary(text) else []
        inline = [line for line in read.lines if abs(line.y - y) < .65 * h and name_parts(line)]
        start = min((line.y for line in inline), default=previous + .5 * h)
        stop = following - .65 * h if inline else y + .45 * h
        barriers = [line.y for line in read.lines if start < line.y < stop and item_description_boundary(line.text)]
        stop = min(barriers, default=stop)
        ids = [i for line in sorted(read.lines, key=lambda line: line.y) if start <= line.y < stop
               for i in name_parts(line)]
        ids = list(dict.fromkeys(ids))
        numeric = {(part['text'], tuple(map(tuple, part['polygon'])))
                   for key, parts in row.get('evidence', {}).items() if key != 'description'
                   for part in parts if part.get('polygon')}
        ids = [i for i in ids if (read.boxes[i].text, tuple(map(tuple, read.boxes[i].polygon))) not in numeric]
        description = ' '.join(read.boxes[i].text for i in ids).strip(' |')
        if len(description) < 2 or not re.search(r'[^\W\d_]', description):
            notes.append({'code': 'V8_FINAL_DESCRIPTION_COLUMN_UNRESOLVED', 'y': y})
            continue
        row['description'] = description
        row['evidence']['description'] = row_evidence(read.boxes, {'description': ids})['description']
        if grid.decorate(row, read):
            # Keep the actual name observation alongside the numeric candidates.
            # Local AI can corroborate it; do not infer spelling from arithmetic.
            row['_cell_candidates']['description'] = [{'value': row['description'],
                'parts': deepcopy(row['evidence']['description']), 'read': read.tag}]
            output.append(row)
    return output, notes


def receipt_rows(read):
    """A description followed by a printed q/unit × price/amount expression."""
    lines = sorted(read.lines, key=lambda l: l.y)
    header = next((n for n, l in enumerate(lines) if RECEIPT_HEADER.search(v4.plain(l.text)) and re.search(r'thanh tien|amount', v4.plain(l.text))), None)
    if header is None:
        return []
    output, pending = [], []
    for line in lines[header + 1:]:
        p = v4.plain(line.text)
        if FOOTER.match(p) or NOTICE.search(p):
            break
        match = SALE.fullmatch(line.text)
        if match:
            if not pending:
                continue
            name_ids = list(dict.fromkeys(i for l in pending for i in l.ids))
            description = ' '.join(read.boxes[i].text for i in name_ids)
            if not re.search(r'[^\W\d_]{2}', description):
                pending = []
                continue
            evidence = row_evidence(read.boxes, {
                'description': name_ids,
                **{key: token_ids_for_span(line, *match.span(group))
                   for key, group in (('quantity', 1), ('unit', 2), ('unit_price', 3), ('amount', 4))},
            })
            row = {'description': description, 'unit': match[2], 'quantity': Decimal(match[1].replace(',', '.')),
                   'unit_price': number(match[3], 'unit_price'), 'amount': number(match[4], 'amount'), 'evidence': evidence, '_y': line.y}
            grid.decorate(row, read)
            output.append(row)
            pending = []
        elif v4.META.match(p):
            # Do not attach a name carried across an unrelated metadata field.
            pending = []
        elif re.match(r'^\d{8,}$', p):
            # A standalone barcode is not part of the description. It can
            # legitimately sit between a product name and its printed price.
            continue
        else:
            # Retain long/wrapped descriptions including model numbers.
            pending.append(line)
    return output


def table_header(reads, inherited_header=None):
    """Union explicit, aligned labels from reads of the same page, not cells."""
    headers = [header for rd in reads if (header := grid.header_for(rd))]
    header = max(headers, key=lambda value: len(value.centers), default=inherited_header)
    if header is None or not reads:
        return header
    width = reads[0].size[0]
    heights = [box.word[3] - box.word[1] for rd in reads for box in rd.boxes]
    h = median(heights) if heights else 15
    centers = dict(header.centers)
    for observed in [*headers, *([inherited_header] if inherited_header else [])]:
        shared = set(centers).intersection(observed.centers)
        if (len(shared) < 2
                or (observed is not inherited_header and abs(observed.bottom - header.bottom) > 3 * h)
                or any(abs(centers[key] - observed.centers[key]) * width > 3 * h for key in shared)):
            continue
        for key, center in observed.centers.items():
            if key not in centers and all(abs(center - existing) * width > h for existing in centers.values()):
                centers[key] = center
    return grid.Header(header.bottom, centers, header.indices)


def recover_rows(reads, fallback, inherited_header=None):
    if not reads:
        return deepcopy(fallback), [{'code':'V8_FINAL_NO_USABLE_PAGE_READS'}]
    header = table_header(reads, inherited_header)
    tables, rejected = [], []
    for rd in reads:
        if rd.tag.startswith(('header', 'footer', 'v7-label', 'v7-supplier')):
            continue
        if header:
            rows, notes = positioned_rows(rd, safe_zone(rd, header), header)
            rejected.extend(notes)
        else:
            rows = receipt_rows(rd)
            if not rows:
                rows, notes = grid.parse_rows(rd, v5.zones(rd))
                rejected.extend(notes)
            if not rows:
                rows = headerless_amount_rows(rd)
        if rows:
            tables.append((rd, rows))
    if not tables:
        return deepcopy(fallback), rejected
    h = median(b.word[3] - b.word[1] for b in reads[0].boxes) if reads[0].boxes else 15
    rows, findings = reconcile_page_rows(tables, h)
    findings += rejected
    rows = [row for row in rows if row.get('quantity') is not None or row.get('unit_price') is not None
            or source_supported_amount_only(row)
            or baseline_row_match(row, fallback, set()) is not None]
    # Never replace a supported fuller table with a partial reparse.
    if len(rows) < len(fallback):
        return deepcopy(fallback), findings + [{'code':'V8_FINAL_PARTIAL_TABLE_RETAINED_BASELINE',
                                               'candidate_rows':len(rows), 'retained_rows':len(fallback)}]
    used_baseline = set()
    for row in rows:
        row['unit'] = canonical_unit(row.get('unit'))
        match = baseline_row_match(row, fallback, used_baseline)
        if match:
            index, old = match
            used_baseline.add(index)
            for key in ('quantity', 'unit_price', 'unit'):
                source_parts = old.get('evidence', {}).get(key, [])
                if row.get(key) is None and old.get(key) is not None and source_parts:
                    row[key] = old[key]
                    row['evidence'][key] = deepcopy(source_parts)
                    findings.append({'code':'V8_FINAL_RETAINED_BASELINE_OBSERVATION',
                                     'field':key, 'baseline_row':index + 1,
                                     'reason':'matching source description and printed amount'})
        elif any(old.get('amount') == row.get('amount') for old in fallback):
            findings.append({'code':'V8_FINAL_BASELINE_LINK_UNCERTAIN',
                             'description':row['description'], 'amount':row.get('amount'),
                             'reason':'equal amount alone cannot establish row ownership'})
    supported = [r for r in fallback if not re.match(r'^\d+(?:[.,]\d+)?\s+[^\W\d_]+\s*[x×*]\s*\d',r['description'],re.I)]
    # The frozen V7 protection uses fuzzy names and equal amounts/prices.
    # Final must not copy a different model's description through that path;
    # the explicit one-to-one source link below retains only the same identity.
    used_text = set()
    for row in rows:
        match = baseline_row_match(row, supported, used_text)
        if match:
            index, old = match
            used_text.add(index)
            parts = old.get('evidence', {}).get('description')
            if parts and old['description'] != row['description']:
                findings.append({'code':'V8_FINAL_BASELINE_TEXT_RETAINED','alternative':row['description'],'retained':old['description'],
                                 'reason':'More accent marks do not establish correctness of an abbreviation/model'})
                row['description'] = old['description']
                row['evidence']['description'] = deepcopy(parts)
    return rows, findings
