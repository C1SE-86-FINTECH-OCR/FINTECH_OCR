"""Source linkage for the experimental Final parser, without OCR or DB calls.

Never infer missing numeric cells. Character spans identify the actual source
tokens even when an OCR engine merges a quantity, unit or currency into a box.
"""
import re
from decimal import Decimal, InvalidOperation
from statistics import median
from unicodedata import combining, normalize
from app.invoice_financials import SELLER_NAME_LABEL, BUYER_NAME_LABEL


def folded(value):
    text = normalize('NFD', str(value)).casefold().replace('đ', 'd')
    return ' '.join(''.join(c for c in text if not combining(c)).split())


def token_ids_for_span(line, start, end):
    """Offsets refer to Line.text, which joins the original boxes with spaces."""
    cursor = 0
    ids = []
    for index in line.ids:
        text = line.boxes[index].text
        stop = cursor + len(text)
        if cursor < end and stop > start:
            ids.append(index)
        cursor = stop + 1
    return ids


def party_label(text):
    """Accept a complete party label, or a label followed by an explicit colon.

    A company name is never split by matching a loose substring inside it.
    Parentheses are ignored for label recognition, not for the observed value.
    """
    parts = re.split('[:：]', text, maxsplit=1)
    parenthetical = [folded(value) for value in re.findall(r'\(([^)]*)\)', parts[0])]
    hints = {role for value in parenthetical
             for role, pattern in (('seller', SELLER_NAME_LABEL), ('buyer', BUYER_NAME_LABEL))
             if re.fullmatch(pattern, value)}
    if len(hints) > 1:
        return None
    label = folded(re.sub(r'\([^)]*\)', '', parts[0])).strip(' .;')
    seller = SELLER_NAME_LABEL
    buyer = BUYER_NAME_LABEL
    if re.fullmatch(seller, label):
        field, role = 'seller_name', 'seller'
    elif re.fullmatch(buyer, label):
        field, role = 'buyer_name', 'buyer'
    elif label in ('ten don vi', 'ten cong ty', 'company name') and len(hints) == 1:
        role = next(iter(hints))
        field = role + '_name'
    else:
        tax = re.fullmatch(
            r'(?:ma so thue|mst|tax (?:code|id))(?: (?:nguoi |don vi )?(ban|mua))?'
            r'|(?:(seller|supplier|buyer|customer) )tax (?:code|id)', label)
        if not tax:
            return None
        explicit = tax[1] or tax[2]
        role = ('buyer' if explicit in ('mua', 'buyer', 'customer') else
                'seller' if explicit else None)
        field = 'tax_code'
    if hints:
        hint = next(iter(hints))
        if role and role != hint:
            return None
        role = hint
    return field, role, parts[1].strip() if len(parts) == 2 else ''


def following_value(read, line, lines, boundary):
    """Return one unambiguous nearby value line, not the next field or column."""
    h = median(read.boxes[i].word[3] - read.boxes[i].word[1] for i in line.ids)
    left = min(read.boxes[i].word[0] for i in line.ids)
    from .document_fields_v8_final import document_label, observed_value, MONETARY_FIELDS
    spec = document_label(line.text)
    if spec and spec[0] in MONETARY_FIELDS:
        # Financial values are normally right-aligned. The former party-name
        # left-alignment rule excluded that cell, including a literal zero.
        right = max(read.boxes[i].word[2] for i in line.ids)
        choices = []
        for other in lines:
            if other is line or other.y >= boundary or not -.65 * h <= other.y - line.y < 1.8 * h:
                continue
            if observed_value(spec[0], other.text) is None:
                continue
            x0 = min(read.boxes[i].word[0] for i in other.ids)
            if not (x0 >= right - .5 * h or (other.y > line.y + .5 * h and abs(x0 - left) <= 2 * h)):
                continue
            blocked = False
            for peer in lines:
                if peer is line or peer is other:
                    continue
                px = min(read.boxes[i].word[0] for i in peer.ids)
                between_rows = line.y + .5 * h < peer.y <= other.y + .25 * h
                between_columns = (abs(peer.y - other.y) <= .65 * h and right <= px < x0)
                words = folded(peer.text).strip(' ()|')
                currency_only = bool(re.fullmatch(r'vnd|vndong|dong|d|usd|eur', words))
                if ((between_rows and (document_label(peer.text) or party_label(peer.text)
                                       or (re.search(r'[^\W\d_]', peer.text) and not currency_only)))
                        or (between_columns and re.search(r'[^\W\d_]', peer.text) and not currency_only)):
                    blocked = True
                    break
            if not blocked:
                choices.append(other)
        # Equal values in two different cells still do not establish ownership.
        return choices[0] if len(choices) == 1 else None
    own = party_label(line.text)
    # Party headings often have larger padding than individual field labels.
    # Still take only the first aligned value; never jump over another field.
    distance = 6 if own and own[0] in ('seller_name', 'buyer_name') else 2
    below = [other for other in lines if 0 < other.y - line.y < distance * h
             and other.y < boundary
             and abs(min(read.boxes[i].word[0] for i in other.ids) - left) <= 2 * h]
    if not below:
        return None
    nearest = min(other.y for other in below)
    band = [other for other in below if abs(other.y - nearest) < .5 * h]
    # A second field in the same band is a column boundary, not a value to join.
    aligned = [other for other in band
               if abs(min(read.boxes[i].word[0] for i in other.ids) - left) <= 2 * h]
    if len(aligned) != 1 or party_label(aligned[0].text):
        return None
    if own and own[0] in ('seller_name', 'buyer_name'):
        peers = [other for other in lines if abs(other.y - line.y) < h / 2
                 and (label := party_label(other.text)) and label[0] in ('seller_name', 'buyer_name')
                 and label[1] != own[1]]
        edge = max(read.boxes[i].word[2] for i in aligned[0].ids)
        if any(left < min(read.boxes[i].word[0] for i in peer.ids) < edge for peer in peers):
            return None  # An unsplit value spans two party columns.
    return aligned[0]


def split_party_columns(read):
    """Separate side-by-side labelled fields using original token spans.

    A box shared by two fields is not split by guessing coordinates. It stays
    unresolved so metadata/name guards can reject the combined value.
    """
    from .pipeline_v5 import Read
    from .document_fields_v8_final import document_label, observed_value
    from app.extraction import _header_date_literals
    groups = []
    for line in read.lines:
        labels = []
        for colon in re.finditer('[:：]', line.text):
            words = list(re.finditer(r'\S+', line.text[:colon.start()]))[-8:]
            recognized = []
            for word in words:
                literal = line.text[word.start():colon.end()]
                label = folded(re.sub(r'\([^)]*\)', '', literal[:-1])).strip(' .;')
                if party_label(literal) is not None or document_label(literal) is not None or re.fullmatch(
                        r'dia chi|address|dien thoai|phone|tel|email|tai khoan|bank account|'
                        r'so hoa don|invoice number|ngay lap|invoice date', label):
                    recognized.append(word.start())
            if recognized:
                start = min(recognized)
                if not labels or start > labels[-1]:
                    labels.append(start)
        # Also recognize unpunctuated document labels. Work in original word
        # offsets so accents and combining characters cannot move source spans.
        words = list(re.finditer(r'\S+', line.text))
        spans = []
        for n, word in enumerate(words):
            for end in range(n + 1, min(n + 6, len(words)) + 1):
                spec = document_label(line.text[word.start():words[end - 1].end()])
                if not spec or spec[1] or end == len(words):
                    continue
                key = spec[0]
                if key not in ('invoice_number', 'receipt_number', 'invoice_symbol', 'invoice_date'):
                    continue
                spans.append((word.start(), words[end - 1].end(), key))
        distinct = []
        for span in sorted(spans, key=lambda value: (value[0], -value[1])):
            if not distinct or span[0] >= distinct[-1][1]:
                distinct.append(span)
        boundaries = sorted({*labels, *(start for start, _end, _key in distinct)})
        for start, end, key in distinct:
            stop = min((position for position in boundaries if position > start), default=len(line.text))
            literal = line.text[end:stop].strip(' :：|')
            if observed_value(key, literal) is not None:
                labels.append(start)
        labels = sorted(set(labels))
        # A separate printed date cell must not remain in the invoice-number
        # literal merely because OCR dropped its date label.
        labels = sorted({*labels, *(start for start, _end, _value in _header_date_literals(line.text))})
        # Bare, side-by-side role headings have no colons. Accept them only
        # when the WHOLE row consists of complete party labels and separators;
        # a merchant containing a role word must not become a new label.
        bare = []
        for n, word in enumerate(words):
            for end in range(n + 1, min(n + 8, len(words)) + 1):
                spec = party_label(line.text[word.start():words[end - 1].end()])
                if spec and spec[0] in ('seller_name', 'buyer_name') and not spec[2]:
                    bare.append((word.start(), words[end - 1].end(), spec[1]))
        headings = []
        for part in sorted(bare, key=lambda value: (value[0], -value[1])):
            if not headings or part[0] >= headings[-1][1]:
                headings.append(part)
        if len({part[2] for part in headings}) > 1:
            gaps = [line.text[:headings[0][0]], line.text[headings[-1][1]:]]
            gaps += [line.text[a[1]:b[0]] for a, b in zip(headings, headings[1:])]
            if all(not gap.strip(' |/;') for gap in gaps):
                labels = sorted({*labels, *(part[0] for part in headings)})
        if len(labels) < 2:
            groups.append(line.ids)
            continue
        pieces = [token_ids_for_span(line, start, labels[n + 1] if n + 1 < len(labels) else len(line.text))
                  for n, start in enumerate(labels)]
        # Keep any preceding source text separately instead of discarding it.
        prefix = token_ids_for_span(line, 0, labels[0])
        parts = ([prefix] if prefix else []) + pieces
        if any(not part for part in pieces) or sum(map(len, parts)) != len({i for part in parts for i in part}):
            groups.append(line.ids)
        else:
            groups.extend(parts)
    separated = Read(read.tag, read.boxes, groups, read.size, read.transform)
    table_top = min((line.y for line in read.lines
                     if re.search(r'\b(?:ten hang|description|goods|product|dien giai)\b', folded(line.text))
                     and (re.search(r'\b(?:so luong|quantity|qty|don gia|unit price|thanh tien|amount)\b', folded(line.text))
                          or re.fullmatch(r'(?:ten hang(?: hoa)?|description|goods|product|dien giai)', folded(line.text)))), default=read.size[1])
    anchors = [(line, spec[1]) for line in separated.lines
               if line.y < table_top and (spec := party_label(line.text)) and spec[0] in ('seller_name', 'buyer_name')]
    output = []
    for line in separated.lines:
        if line.y >= table_top or party_label(line.text):
            output.append(line.ids)
            continue
        height = max(1, median(read.boxes[i].word[3] - read.boxes[i].word[1] for i in line.ids))
        pairs = [(a, b) for a, side in anchors for b, other in anchors
                 if side != other and abs(a.y - b.y) < height / 2
                 and min(read.boxes[i].word[0] for i in a.ids) < min(read.boxes[i].word[0] for i in b.ids)
                 and 0 < line.y - max(a.y, b.y) < 6 * height]
        if not pairs:
            output.append(line.ids)
            continue
        # A nearby real whitespace gutter, not the middle of a company name,
        # separates values below two side-by-side party labels. Shared boxes
        # remain untouched when no independently visible gutter exists.
        a, b = max(pairs, key=lambda pair: max(pair[0].y, pair[1].y))
        ax = min(read.boxes[i].word[0] for i in a.ids)
        bx = min(read.boxes[i].word[0] for i in b.ids)
        ids = sorted(line.ids, key=lambda i: read.boxes[i].word[0])
        gaps = [(n + 1, (read.boxes[i].word[2] + read.boxes[j].word[0]) / 2)
                for n, (i, j) in enumerate(zip(ids, ids[1:]))
                if read.boxes[j].word[0] - read.boxes[i].word[2] > 2 * height
                and ax + 2 * height < read.boxes[j].word[0] <= bx + 2 * height
                and read.boxes[j].word[0] >= (ax + bx) / 2]
        if gaps:
            cut, _x = min(gaps, key=lambda gap: abs(gap[1] - (ax + bx) / 2))
            output.extend((ids[:cut], ids[cut:]))
        else:
            output.append(line.ids)
    return Read(read.tag, read.boxes, output, read.size, read.transform)


def wrapped_party_value(read, value_line, ids, lines, boundary, stop, limit=3):
    """Extend a name only through nearby description-only source lines.

    The caller provides the field/metadata boundary predicate. No continuation
    is joined across a different column, label, number-only line or table.
    """
    if not ids:
        return []
    selected = list(ids)
    previous = value_line
    left = min(read.boxes[i].word[0] for i in ids)
    h = median(read.boxes[i].word[3] - read.boxes[i].word[1] for i in ids)
    for _ in range(limit - 1):
        below = [line for line in lines if 0 < line.y - previous.y < 1.8 * h
                 and line.y < boundary]
        if not below:
            break
        y = min(line.y for line in below)
        band = [line for line in below if abs(line.y - y) < .4 * h
                and abs(min(read.boxes[i].word[0] for i in line.ids) - left) < 2 * h]
        if len(band) != 1:
            break
        following = band[0]
        text = following.text
        if stop(following) or party_label(text) or re.search('[:：]', text):
            break
        if not re.search(r'[^\W\d_]{2}', text) or re.fullmatch(r'[\d\s.,/+()-]+', text):
            break
        selected.extend(following.ids)
        previous = following
    return list(dict.fromkeys(selected))


def baseline_row_match(row, baseline, used):
    """Match a source row one-to-one by description and printed amount.

    Equal amounts alone cannot link products. When repeated descriptions have
    distinct positions, use a unique nearby source band; otherwise abstain.
    """
    if row.get('amount') is None:
        return None
    def compatible(old):
        if 'page' in row and 'page' in old and row['page'] != old['page']:
            return False
        for key in ('quantity', 'unit_price'):
            if row.get(key) is None or old.get(key) is None:
                continue
            try:
                if Decimal(str(row[key])) != Decimal(str(old[key])):
                    return False
            except (InvalidOperation, ValueError):
                return False
        return True
    matches = [(n, old) for n, old in enumerate(baseline)
               if folded(old.get('description', '')) == folded(row.get('description', ''))
               and old.get('amount') == row.get('amount') and compatible(old)]
    if not matches:
        return None
    def location(item):
        parts = item.get('evidence', {}).get('amount', [])
        polygons = [p['polygon'] for p in parts if p.get('polygon')]
        if not polygons:
            return None
        heights = [max(y for _, y in poly) - min(y for _, y in poly) for poly in polygons]
        return (median(sum(y for _, y in poly) / len(poly) for poly in polygons),
                max(3, median(heights)))
    position = location(row)
    if position is not None:
        local = []
        for n, old in matches:
            previous = location(old)
            if previous is None or abs(position[0] - previous[0]) < max(position[1], previous[1]):
                local.append((n, old))
        matches = local
    # A consumed duplicate must not make another indistinguishable copy
    # look unique. Establish ownership before consulting the consumption set.
    return matches[0] if len(matches) == 1 and matches[0][0] not in used else None
