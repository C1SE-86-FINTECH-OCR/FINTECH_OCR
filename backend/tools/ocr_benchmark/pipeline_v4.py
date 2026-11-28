"""Opt-in offline OCR/context experiment; never imported by the upload service.

Values come from recognized text/boxes only. No dataset/label reads, vendor
templates, numeric reconciliation, network calls or database dependencies.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from difflib import SequenceMatcher
import re
from statistics import median

from app import extraction as old
from .layout import rectangle
from .table_v3 import Header, number, row_evidence, findings_for_items


def plain(s):
    return " ".join(old._plain(s).split())


META = re.compile(
    r"^(?:so\s*(?:hd|hb|hoa don|bill|tham chieu)|hoa don so|h\s*:|"
    r"invoice\s*(?:no|number)|receipt\s*(?:no|number)|bill\s*(?:no|number)|"
    r"ma so thue|mst\b|tax\s*(?:code|id)|ngay\b|date\b|thoi gian|time\b|"
    r"dia chi|address|dien thoai|dt\s*[:.]|sdt|phone|tel\b|hotline|"
    r"tai khoan|account|thu ngan|cashier|khach hang|customer|nguoi mua|nguoi ban|"
    r"so gd|so giao dich|transaction|reference|order\s*(?:id|no)|website|"
    r"http|www\.|powered|password|wifi|cam on|thank|ky ten|da ky|chu ky|"
    r"gio phuc vu|gio mo cua|service hours|gia dang ky|gia ban|"
    r"bill khong|hoa don ban|phieu ban|phieu thanh|receipt$|page\b|trang\s+\d)"
)
SUMMARY = re.compile(
    r"^(?:cong tien hang|tong(?:\s+so|\s+cong|\s+tien|\s+thanh toan)|"
    r"tam tinh|sub\s*total|grand total|total\b|amount due|thanh tien\s*[:\d]|"
    r"tien (?:khach|mat|thua|thue)|cash\b|change\b|payment\b|vat\b|"
    r"thue (?:gtgt|vat)|now\b|delivery commission)"
)
ADJUST = re.compile(r"^(?:km\b|khuyen mai|giam gia|chiet khau|phu thu|phu phi|discount|surcharge)")
HEADINGS = {
    'description': r'ten hang(?: hoa)?|hang hoa(?: dich vu)?|mat hang|dien giai|mo ta|description|item(?: name)?|product',
    'quantity': r'so luong|sl|qty|quantity',
    'unit_price': r'don gia|dngia|don ?gia|bon gia|unit price|price',
    'amount': r'thanh tien|t\s*tien|line total|amount|net amount',
    'unit': r'don vi tinh|dvt|unit|uom',
    'ordinal': r'stt|#',
    'vat_rate': r'thue suat(?: gtgt)?|vat rate|tax rate',
    'vat_amount': r'tien thue|vat amount|tax amount',
}


def semantic(s):
    """Tolerate label noise, never rewrite a recognized business value/name."""
    p = plain(s).replace('_', ' ')
    p = re.sub(r'^[^a-z0-9]+', '', p).strip()
    labels = ('tong tien hang sau khi giam gia', 'tong tien thanh toan',
              'tong tien hang', 'cong tien hang', 'tong cong', 'tong tien',
              'thanh tien', 'tam tinh', 'giam gia', 'chiet khau', 'phu thu')
    # Scanner borders/noisy isolated prefixes can precede a summary label.
    words = p.split()
    for start in range(min(3, len(words))):
        for label in labels:
            n = len(label.split())
            phrase = ' '.join(words[start:start+n])
            # The semantic final word is required, otherwise "tong tien phai"
            # can look deceptively close to "tong tien hang" and invent a
            # subtotal. Tolerance belongs to OCR label noise, not role changes.
            final_matches = len(words[start:start+n]) == n and words[start+n-1].strip(':.,;') == label.split()[-1]
            if len(words[start:start+n]) == n and final_matches and SequenceMatcher(None, phrase, label).ratio() >= .86:
                return label + ' ' + ' '.join(words[start+n:])
        tail = ' '.join(words[start:])
        if META.match(tail) or SUMMARY.match(tail) or ADJUST.match(tail):
            return tail
    return p


@dataclass
class Line:
    ids: list
    boxes: list

    @property
    def text(self):
        return ' '.join(self.boxes[i].text for i in self.ids)

    @property
    def y(self):
        return median((self.boxes[i].word[1] + self.boxes[i].word[3]) / 2 for i in self.ids)


def lines_of(boxes):
    """Group by local baseline, preserving x order and small capture skew."""
    groups = []
    for i in sorted(range(len(boxes)), key=lambda i: sum(boxes[i].word[1:4:2]) / 2):
        x0, y0, x1, y1, _ = boxes[i].word
        y = (y0 + y1) / 2
        candidates = []
        for group in groups[-4:]:
            heights = [boxes[j].word[3] - boxes[j].word[1] for j in group]
            cy = median((boxes[j].word[1] + boxes[j].word[3]) / 2 for j in group)
            if abs(cy - y) <= max(3, .65 * min(y1 - y0, median(heights))):
                candidates.append((abs(cy - y), group))
        if candidates:
            min(candidates, key=lambda v: v[0])[1].append(i)
        else:
            groups.append([i])
    return [Line(sorted(g, key=lambda i: boxes[i].word[0]), boxes) for g in groups]


def money_tokens(line):
    """Join OCR fragments of one number, never adjacent quantity/price cells."""
    result = []
    ids = line.ids
    i = 0
    while i < len(ids):
        token = line.boxes[ids[i]].text.strip().strip('*₫đ').rstrip('.')
        chosen = [ids[i]]
        if re.fullmatch(r'[+-]?\d[\d.,]*%?', token):
            j = i + 1
            while j < len(ids):
                nxt = line.boxes[ids[j]].text.strip().strip('*₫đ')
                gap = line.boxes[ids[j]].word[0] - line.boxes[chosen[-1]].word[2]
                h = line.boxes[ids[j]].word[3] - line.boxes[ids[j]].word[1]
                if gap < .7 * h and (token.endswith(('.', ',')) and nxt.isdigit() or
                                      nxt.startswith(('.', ',')) and re.fullmatch(r'[.,]\d+', nxt)):
                    token += nxt
                    chosen.append(ids[j]); j += 1
                else:
                    break
            value = number(token, 'vat_rate' if token.endswith('%') else 'amount')
            if value is not None:
                result.append({'ids': chosen, 'text': token, 'value': value,
                               'x': median((line.boxes[k].word[0] + line.boxes[k].word[2]) / 2 for k in chosen),
                               'formatted': bool(re.search(r'[.,]\d{3}', token)), 'percent': token.endswith('%')})
            i = j
        else:
            # Some OCR adapters expose a whole text line as one box. Keep that
            # original box as evidence, without inventing word coordinates.
            if re.search(r'\s', token):
                match = re.search(r'(?<![\w/])([+-]?\d[\d.,]*)\s*$', token)
                value = number(match[1], 'amount') if match else None
                if value is not None:
                    result.append({'ids': [ids[i]], 'text': match[1], 'value': value,
                                   'x': line.boxes[ids[i]].word[2],
                                   'formatted': bool(re.search(r'[.,]\d{3}', match[1]))})
            i += 1
    return result


def classify_context(lines, size):
    for line in lines:
        text = semantic(line.text)
        if line.y > .65 * size[1]:
            continue
        # Footer requests/promotions are not the document's legal heading.
        if re.search(r'\b(?:xuat|yeu cau|lien he|cung cap|request|will be issued)\b', text):
            continue
        if re.search(r'^(?:hoa don (?:gia tri gia tang|dien tu)|vat invoice|tax invoice)', text):
            return 'einvoice'
    if any(re.search(r'\b(?:hoa don ban hang|hoa don ban le|phieu (?:ban hang|thanh toan|thu)|receipt|bill)\b', semantic(l.text))
           for l in lines):
        return 'bill'
    text = ' '.join(semantic(l.text) for l in lines)
    if (re.search(r'tong cong|tong tien|thanh tien', text) and
        re.search(r'tien (?:mat|khach|thua)|cash|payment', text) and
        any(find_header(l.boxes, size[0]) is not None for l in lines[:1])):
        return 'bill'
    return 'unknown'


def date_value(text):
    p = plain(text)
    # Whitespace between digits in the same printed date is an OCR token split.
    p = re.sub(r'(\d)/\s*(\d)\s+(\d)/(\d{4})', r'\1/\2\3/\4', p)
    patterns = ((r'\b(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(20\d{2}|19\d{2})\b', False),
                (r'\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b', True),
                (r'\b(?:ngay|date)\s*(\d{1,2})\s*thang\s*(\d{1,2})\s*(?:nam|nm)\s*(\d{4})\b', False))
    for pattern, iso in patterns:
        match = re.search(pattern, p)
        if match:
            a, b, c = map(int, match.groups())
            try:
                return date(a, b, c) if iso else date(c, b, a)
            except ValueError:
                continue
    return None


def field_context(lines, size, ext):
    raw = '\n'.join(line.text for line in lines)
    fields = old.extract_fields(raw, ext)
    fields['document_type'] = classify_context(lines, size)
    evidence, findings, candidates, adjustments = {}, [], {}, []
    h = median(b.word[3] - b.word[1] for line in lines for b in [line.boxes[i] for i in line.ids]) if lines else 12

    def add(key, value, line, priority):
        if value is not None:
            candidates.setdefault(key, []).append((priority, value, line))

    # Name region ends at invoice/table heading; not at a fixed pixel/template.
    boundaries = [l.y for l in lines if re.search(r'^(?:hoa don|phieu |receipt\b|tax invoice|vat invoice|so\s*(?:hd|hoa don)|h\s*:|ngay ban)', semantic(l.text))]
    cutoff = min(boundaries) if boundaries else size[1] * .35
    for line in lines:
        ids = list(line.ids)
        while ids and (not re.search(r'\w',line.boxes[ids[0]].text) or
                       len(plain(line.boxes[ids[0]].text))<3 and (line.boxes[ids[0]].score or 0)<.65):
            ids.pop(0)
        name = ' '.join(line.boxes[i].text for i in ids)
        # Logos can share a baseline with the legal entity heading.
        company_start = re.search(r'\b(?:chi nhanh|cong ty|company)\b',plain(name))
        if company_start:
            name=name[company_start.start():]
        name = re.split(r'\s+TP[.,]\s*', name, maxsplit=1, flags=re.I)[0]
        p = semantic(name)
        if line.y >= cutoff or META.match(p) or SUMMARY.match(p) or ADJUST.match(p) or re.search(r'\d{5,}|@|www\.|http|\b(?:dia chi|address|duong|street|hotline|tel|to \d+|khu |phuong|quan |huyen|tinh |tp[.,]|the va[o0]|ve xe|ticket)', p):
            continue
        letters = re.sub(r'[^a-z]', '', p)
        scores = [line.boxes[i].score for i in line.ids if line.boxes[i].score is not None]
        conf = sum(scores) / len(scores) if scores else 1
        if len(letters) < 5 or conf < .55:
            continue
        company = bool(re.search(r'\b(?:cong ty|company|chi nhanh|cua hang|sieu thi|minimart|nha hang|khach san|restaurant|hotel)\b', p))
        priority = 30 if company else 10
        priority += min(8, len(letters) / 6) + conf * 3 - line.y / max(size[1], 1)
        add('seller_name', name, line, priority)

    buyer_y = next((l.y for l in lines if re.search(r'^(?:nguoi mua|don vi mua|buyer|khach hang)\b', plain(l.text))), float('inf'))
    header_words = {}
    for line in lines:
        key = id(line.boxes)
        if key not in header_words:
            header = find_header(line.boxes, size[0])
            header_words[key] = set(header.indices) if header else set()
    for index, line in enumerate(lines):
        p = semantic(line.text)
        if header_words[id(line.boxes)].intersection(line.ids):
            continue
        if re.search(r'^(?:ky|da ky|chu ky|ngay chuyen doi|signature|signed)\b', p):
            continue
        neighbor = lines[index + 1] if index + 1 < len(lines) and lines[index + 1].y - line.y < 2.8 * h else None
        dates = date_value(line.text)
        if dates and not re.search(r'(?:han su dung|expiry|show time|suat chieu|khuyen mai)', p):
            add('invoice_date', dates, line, 30 if re.search(r'\b(?:ngay|date|thoi gian)\b', p) else 10)
        if not dates and neighbor and re.search(r'^(?:ngay|date)\s*[:.]?$', p):
            add('invoice_date', date_value(neighbor.text), neighbor, 30)
        label = re.search(r'^(?:so\s*(?:hoa don|(?:hd|hb)(?=\s|[:.]))|hoa don so|invoice\s*(?:no\.?|number)|receipt\s*(?:no\.?|number)|bill\s*(?:no\.?|number)|h\s*:|so(?=\s|:))\s*[:.#-]?\s*', plain(line.text).lstrip())
        if label:
            value = line.text[label.end():].strip()
            match = re.match(r'([a-zA-Z0-9][a-zA-Z0-9/-]{3,31})\b', value)
            if match and any(c.isdigit() for c in match[1]) and date_value(match[1]) is None:
                add('invoice_number', match[1], line, 30)
        party = re.match(r'^(?:don vi ban hang|ten don vi ban hang|nguoi ban|seller|don vi mua hang|ten don vi mua hang|buyer|khach hang)\s*[:.-]\s*(.+)', line.text, re.I)
        # Accent-insensitive labels, retain the original value spelling.
        pm = re.match(r'^(don vi ban hang|ten don vi ban hang|nguoi ban|seller|don vi mua hang|ten don vi mua hang|buyer|khach hang)\s*[:.-]\s*', p)
        if pm:
            value = line.text[pm.end():].strip()
            if re.search(r'[^\W\d_]', value) and not META.match(plain(value)):
                add('buyer_name' if pm[1] in ('don vi mua hang','ten don vi mua hang','buyer','khach hang') else 'seller_name', value, line, 50)
        tax = re.search(r'\b(?:ma so thue|mst|tax\s*(?:code|id))\s*[:.-]?\s*(\d{10}(?:-?\d{3})?)\b', p)
        if tax:
            key = 'buyer_tax_code' if line.y >= buyer_y and buyer_y != float('inf') else 'seller_tax_code'
            add(key, tax[1], line, 30)
        elif re.search(r'^(?:ma so thue|mst|tax code)\s*[:.]?$', p) and neighbor:
            tx = re.fullmatch(r'\d{10}(?:-?\d{3})?', neighbor.text.strip())
            if tx:
                add('buyer_tax_code' if line.y >= buyer_y else 'seller_tax_code', tx[0], neighbor, 30)

        # A label may sit just above/below a right-aligned amount.
        money = money_tokens(line)
        nearby = None
        if not money:
            for pos in (index + 1, index - 1):
                if 0 <= pos < len(lines):
                    other = lines[pos]
                    values = money_tokens(other)
                    if abs(other.y - line.y) <= 1.9 * h and values and not re.search(r'[^\W\d_]', other.text):
                        nearby = (values, other)
                        break
        amounts, amount_line = (money, line) if money else nearby or ([], line)
        value = amounts[-1]['value'] if amounts else None
        if ADJUST.match(p):
            adjustments.append({'label': line.text, 'amount': value, 'evidence': row_evidence(amount_line.boxes, {'source': amount_line.ids})})
            continue
        if re.search(r'\b(?:khach (?:dua|tra)|tien (?:mat|thua)|cash|change|now|commission|da tra|con lai)\b', p):
            continue
        if re.search(r'^(?:cong tien hang|tong tien hang(?! sau)|tien truoc thue|subtotal|tam tinh)', p):
            add('subtotal', value, amount_line, 30)
        elif re.search(r'^(?:tien thue(?: gtgt)?|thue gtgt|vat amount|tax amount)', p):
            add('vat_amount', value, amount_line, 30)
        elif re.search(r'^(?:tong tien (?:phai )?thanh toan|tong thanh toan|tong cong thanh toan|thanh tien\b|grand total|amount due|total payment|total amount)', p):
            # A column header has no amount on the same/adjacent numeric-only line.
            add('total_amount', value, amount_line, 50)
        elif re.search(r'^(?:tong cong|tong tien hang sau khi giam gia|total\b|tong tien\b)', p) and not re.search(r'giam|discount', p.replace('sau khi giam gia','')):
            add('total_amount', value, amount_line, 30 if 'tong cong' in p else 20)
    # VAT rates must be printed; a gross price does not establish a tax amount.
    for line in lines:
        p = plain(line.text)
        if re.search(r'vat|thue', p):
            for m in re.finditer(r'\b(\d{1,2}(?:[.,]\d+)?)\s*%', p):
                add('vat_rate', Decimal(m[1].replace(',', '.')), line, 20)
    for key, choices in candidates.items():
        highest = max(c[0] for c in choices)
        winners = [c for c in choices if c[0] == highest]
        values = {str(v) for _, v, _ in winners}
        if len(values) != 1:
            fields[key] = None
            findings.append({'code': 'CONFLICTING_FIELD_CANDIDATES', 'field': key, 'values': sorted(values)})
            continue
        _, value, line = winners[0]
        fields[key] = value
        evidence[key] = row_evidence(line.boxes, {'source': line.ids})['source']
    if 'seller_name' not in candidates:
        fields['seller_name'] = None
    fields['confidence_score'] = None  # OCR word confidence is not field accuracy.
    return fields, evidence, findings, adjustments


def consensus_fields(fields, passes):
    """Select only values actually read in >=2 passes; keep conflict evidence.

    These correlated OCR passes are not independent human verification and
    do not turn a value into a verified field or calibrated probability.
    """
    changes, warnings = {}, []
    def identity(value):
        if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):
            return ('number',Decimal(str(value)))
        return ('text',str(value))
    for key in ('seller_name','seller_tax_code','invoice_number','invoice_symbol',
                'invoice_date','buyer_name','buyer_tax_code','subtotal',
                'vat_rate','vat_amount','total_amount'):
        votes = {}
        for variant, values, evidence in passes:
            value=values.get(key)
            if value is not None:
                votes.setdefault(identity(value),[]).append((variant,value,evidence.get(key,[])))
        if not votes:
            continue
        ranked=sorted(votes.values(),key=len,reverse=True)
        if len(votes)>1:
            warnings.append({'code':'OCR_FIELD_CONFLICT','field':key,'recognized_values':sorted(str(v[0][1]) for v in votes.values())})
        if len(ranked[0])>=2 and (len(ranked)==1 or len(ranked[0])>len(ranked[1])):
            winner=ranked[0]
            if identity(fields.get(key))!=identity(winner[0][1]):
                fields[key]=winner[0][1]
                changes[key]={'value':winner[0][1],'supporting_passes':[v for v,_,_ in winner],
                              'evidence':winner[0][2],'human_verified':False}
    return changes,warnings


def find_header(boxes, width):
    rows = lines_of(boxes)
    h = median(b.word[3] - b.word[1] for b in boxes) if boxes else 12
    spans = []
    for row in rows:
        for start in range(len(row.ids)):
            for end in range(start + 1, min(start + 5, len(row.ids)) + 1):
                ids = row.ids[start:end]
                label = plain(' '.join(boxes[i].text for i in ids)).strip(' :|')
                label = label.replace('.', ' ').strip()
                for role, pattern in HEADINGS.items():
                    if re.fullmatch(pattern, label):
                        spans.append((role, ids, row.y))
    headers = []
    for _, _, y in spans:
        band = [s for s in spans if abs(s[2] - y) < 2.5 * h]
        roles = {}
        for role, ids, _ in sorted(band, key=lambda s: -len(s[1])):
            roles.setdefault(role, ids)
        if 'amount' not in roles or not ({'quantity', 'unit_price'} & roles.keys()):
            continue
        positions = {k: median((boxes[i].word[0] + boxes[i].word[2]) / 2 for i in ids) / width for k, ids in roles.items()}
        if abs(positions['amount'] - positions.get('unit_price', positions.get('quantity', 0))) * width < h:
            continue
        used = sorted({i for ids in roles.values() for i in ids})
        headers.append((len(roles), -y, Header(max(boxes[i].word[3] for i in used), positions, tuple(used))))
    return max(headers, key=lambda v: v[:2])[2] if headers else None


def parse_table(boxes, size, header=None):
    width, _ = size
    rows = lines_of(boxes)
    h = median(b.word[3] - b.word[1] for b in boxes) if boxes else 12
    body, adjustments = [], []
    for row in rows:
        if header and row.y < header.bottom:
            continue
        p = semantic(row.text)
        if SUMMARY.match(p):
            break
        if ADJUST.match(p):
            adjustments.append(row.text)
            continue
        if META.match(p) or date_value(row.text) is not None:
            continue
        body.append(row)
    anchors = []
    descriptions = []
    for row in body:
        values = money_tokens(row)
        if header:
            ac = header.centers['amount'] * width
            others = [v * width for k, v in header.centers.items() if k != 'amount']
            radius = min([abs(ac - x) / 2 for x in others] or [width * .2])
            amounts = [v for v in values if not v.get('percent') and abs(v['x'] - ac) <= max(radius, h)]
        else:
            amounts = [v for v in values if not v.get('percent') and v['x'] > .5 * width and
                       (v['formatted'] or v['value'] == 0 and len(values) >= 2)]
        anchor = max(amounts, key=lambda v: v['x']) if amounts else None
        if anchor:
            roles = {'amount': anchor}
            used = set(anchor['ids'])
            if header:
                for role in ('quantity', 'unit_price', 'vat_rate', 'vat_amount'):
                    if role not in header.centers:
                        continue
                    cx = header.centers[role] * width
                    peers = [v * width for k, v in header.centers.items() if k != role]
                    radius = min([abs(cx - x) / 2 for x in peers] or [width * .1])
                    valid = [v for v in values if not used.intersection(v['ids']) and abs(v['x'] - cx) <= max(radius, h)]
                    if valid:
                        selected = min(valid, key=lambda v: abs(v['x'] - cx))
                        roles[role] = selected; used.update(selected['ids'])
            else:
                before = [v for v in values if v['x'] < anchor['x'] and v['formatted']]
                if before:
                    price = max(before, key=lambda v: v['x'])
                    roles['unit_price'] = price; used.update(price['ids'])
                q = [v for v in values if not used.intersection(v['ids']) and not v['formatted'] and not v.get('percent') and v['value'] < 10000 and
                     v['x'] > width * .3 and v['x'] < anchor['x'] and
                     all(boxes[v['ids'][0]].word[0]-boxes[j].word[2] >= 1.2*h
                         for j in row.ids if boxes[j].word[2] <= boxes[v['ids'][0]].word[0] and
                         re.search(r'[^\W\d_]', boxes[j].text))]
                if q:
                    roles['quantity'] = max(q, key=lambda v: v['x']); used.update(roles['quantity']['ids'])
            anchors.append((row, roles, used))
        else:
            used = set()
        name_ids = [i for i in row.ids if i not in used]
        if header:
            numeric = [v * width for k, v in header.centers.items() if k in ('quantity','unit_price','amount')]
            desc_center = header.centers.get('description')
            if desc_center is not None and (anchor or any(v['formatted'] for v in values)):
                to_right = [x for x in numeric if x > desc_center * width]
                bound = (desc_center * width + min(to_right)) / 2 if to_right else width
                name_ids = [i for i in name_ids if boxes[i].word[0] < bound and not
                            (header.centers.get('ordinal') is not None and boxes[i].word[2] < (desc_center * width + header.centers['ordinal'] * width) / 2)]
        # Strip a stand-alone product barcode, not embedded model digits.
        name_ids = [i for i in name_ids if not re.fullmatch(r'\d{8,14}', boxes[i].text) and
                    (re.search(r'\w', boxes[i].text) or boxes[i].text == '-') and
                    not (len(plain(boxes[i].text)) == 1 and (boxes[i].score or 1) < .7)]
        name = ' '.join(boxes[i].text for i in name_ids).strip(' |')
        if len(re.sub(r'[^a-z]', '', plain(name))) >= 4 and not META.match(semantic(name)) and not SUMMARY.match(semantic(name)):
            if not all(re.fullmatch(r'(?:cai|cha|goi|pcs|hop|unit|vnd)', plain(boxes[i].text)) for i in name_ids):
                descriptions.append((row.y, name_ids))
    owned = [[] for _ in anchors]
    for y, ids in descriptions:
        options = [(abs(y - row.y) * (.9 if y <= row.y else 1), i)
                   for i, (row, _, _) in enumerate(anchors) if -2.7 * h <= y - row.y <= 1.7 * h]
        if options:
            owned[min(options)[1]].append((y, ids))
    items = []
    for index, (row, roles, _) in enumerate(anchors):
        if header is None and any(abs(y-row.y) <= .65*h for y,_ in owned[index]):
            # An inline name is stronger evidence than a preceding orphan
            # model/annotation. Do not silently merge a separate product.
            owned[index] = [(y,ids) for y,ids in owned[index] if y >= row.y-.65*h]
        name_ids = [i for _, ids in sorted(owned[index]) for i in ids]
        name = ' '.join(boxes[i].text for i in name_ids).strip(' |')
        if not name or META.match(plain(name)) or ADJUST.match(plain(name)):
            continue
        item = {'description': name, 'unit': None, 'quantity': None, 'unit_price': None,
                'amount': roles['amount']['value'], 'vat_rate': None, 'vat_amount': None}
        for role in ('quantity','unit_price','vat_rate','vat_amount'):
            if role in roles:
                item[role] = number(roles[role]['text'], role)
        evidence = {k: v['ids'] for k, v in roles.items()}; evidence['description'] = name_ids
        if header and 'unit' in header.centers:
            x = header.centers['unit'] * width
            unit_ids = [i for i in row.ids if abs((boxes[i].word[0]+boxes[i].word[2])/2-x) < max(1.5*h,width*.03) and
                        re.fullmatch(r'[^\W\d_]{1,10}', boxes[i].text)]
            if unit_ids:
                item['unit'] = ' '.join(boxes[i].text for i in unit_ids); evidence['unit'] = unit_ids
        item['evidence'] = row_evidence(boxes, evidence)
        items.append(item)
    return items, adjustments


def prepare(image):
    from PIL import Image, ImageOps, ImageChops, ImageFilter
    im = ImageOps.exif_transpose(image).convert('L')
    if im.width * im.height > 30_000_000:
        raise ValueError('Experimental OCR page exceeds 30 MP')
    info = {'exif_transpose': True, 'orientation_rotation': 0, 'noise_filter': False}
    try:
        osd = old.pytesseract.image_to_osd(im, output_type=old.pytesseract.Output.DICT, timeout=8)
        if osd.get('orientation_conf', 0) >= 8 and osd.get('rotate') in (90,180,270):
            im = im.rotate(-osd['rotate'], expand=True, fillcolor=255)
            info['orientation_rotation'] = osd['rotate']
    except old.pytesseract.TesseractError:
        info['orientation_uncertain'] = True
    except RuntimeError:
        info['orientation_uncertain'] = True
    gray = ImageOps.autocontrast(im, cutoff=.5)
    proxy = gray.copy(); proxy.thumbnail((800,800))
    filtered = proxy.filter(ImageFilter.MedianFilter(3))
    noise = sum(ImageChops.difference(proxy,filtered).histogram()[180:]) / (proxy.width*proxy.height)
    if .002 < noise < .02:
        gray = Image.blend(gray,gray.filter(ImageFilter.MedianFilter(3)),.15)
        info['noise_filter'] = True
    gray = old._deskew_small_angle(gray)
    scale = min(2.5, max(1.,1400/max(gray.width,1)), (12_000_000/(gray.width*gray.height))**.5)
    if abs(scale-1) > .05:
        gray = gray.resize((round(gray.width*scale),round(gray.height*scale)),Image.Resampling.LANCZOS)
    info.update(scale=scale, size=gray.size, coordinate_space='processed raster pixels',
                deskew='bounded projection correction; source bytes unchanged')
    return gray, info


def recognize(image):
    from PIL import ImageOps, ImageChops, ImageFilter, ImageStat
    prepared, info = prepare(image)
    options = []
    variants = [('gray',6,prepared),('gray',11,prepared)]
    # Flatten uneven lighting using a smooth background estimate. This is an
    # alternative recognition pass, not a destructive rewrite of the source.
    background = prepared.filter(ImageFilter.GaussianBlur(max(5,min(prepared.size)/40)))
    if ImageStat.Stat(background).stddev[0] > 18:
        local = ImageOps.autocontrast(ImageChops.subtract(prepared,background,offset=180),cutoff=.5)
        variants.append(('illumination-normalized',6,local))
    failures = []
    for variant, psm, raster in variants:
        try:
            data = old.pytesseract.image_to_data(raster,lang='vie+eng',config=f'--psm {psm}',
                                               output_type=old.pytesseract.Output.DICT,timeout=40)
        except (old.pytesseract.TesseractError, RuntimeError) as exc:
            failures.append({'variant':variant,'psm':psm,'error':type(exc).__name__})
            continue
        boxes = []
        for i,t in enumerate(data['text']):
            if not t.strip():
                continue
            x,y,w,h = (data[k][i] for k in ('left','top','width','height'))
            confidence = float(data['conf'][i])
            boxes.append(rectangle(t.strip(),x,y,x+w,y+h,confidence/100 if confidence>=0 else None))
        quality = sum(len(re.sub(r'[^\w]','',b.text))*(b.score or 0)**2 for b in boxes) / max(1,len(boxes))**.5
        quality -= .5*sum(not re.search(r'\w',b.text) for b in boxes)
        options.append((quality,psm,boxes,variant))
    if not options:
        raise RuntimeError('All bounded OCR attempts failed')
    quality, psm, boxes, variant = max(options,key=lambda o:o[0])
    info.update(selected_psm=psm,selected_variant=variant,
                selection_rule='confidence-squared characters / sqrt(tokens), punctuation penalty; no label access',
                failed_attempts=failures,
                alternatives=[{'psm':p,'variant':v,'quality':s,'boxes':row_evidence(b,{'all':range(len(b))})['all']} for s,p,b,v in options])
    return prepared.size, boxes, info


def extract_v4(data, ext, max_pages=12):
    """Same fields/items/layout tuple as other OFFLINE benchmark adapters."""
    from PIL import Image
    import pymupdf
    if ext == 'xml':
        raw,method=old.text_from_file(data,ext)
        return old.extract_fields(raw,ext),old.extract_line_items(data,ext,raw),{'raw_text':raw,'source':method,'pages':[]}
    pages=[]
    if ext == 'pdf':
        with pymupdf.open(stream=data,filetype='pdf') as pdf:
            total=len(pdf)
            for n in range(min(total,max_pages)):
                page=pdf[n]; words=page.get_text('words',sort=True)
                if sum(c.isalnum() for w in words for c in w[4])>40:
                    boxes=[rectangle(t,x0,y0,x1,y1) for x0,y0,x1,y1,t,*_ in words]
                    pages.append((n+1,'pdf-text',(page.rect.width,page.rect.height),boxes,{}))
                else:
                    if page.rect.width*page.rect.height*4>30_000_000:
                        raise ValueError('PDF raster exceeds pixel cap')
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
                    with Image.open(BytesIO(pix.tobytes('png'))) as image:
                        size,boxes,info=recognize(image)
                    pages.append((n+1,'ocr',size,boxes,info))
    else:
        total=1
        with Image.open(BytesIO(data)) as image:
            size,boxes,info=recognize(image)
        pages.append((1,'ocr',size,boxes,info))
    all_lines=[line for _,_,_,boxes,_ in pages for line in lines_of(boxes)]
    fields,evidence,findings,adjustments=field_context(all_lines,pages[0][2],ext)
    passes=[]
    first=pages[0]
    for alternative in first[4].get('alternatives',[]):
        from .layout import TextBox
        bs=[TextBox(b['text'],tuple(tuple(p) for p in b['polygon']),b['ocr_score']) for b in alternative['boxes']]
        values,ev,_,_=field_context(lines_of(bs),first[2],ext)
        variant=f"{alternative['variant']}/psm{alternative['psm']}"
        passes.append((variant,values,ev))
    consensus,conflicts=consensus_fields(fields,passes)
    findings+=conflicts
    items=[];diagnostics=[];carried=None
    for n,source,size,boxes,info in pages:
        header=find_header(boxes,size[0]);continued=False
        if header is None and carried:
            candidate=Header(0,carried.centers,())
            rows,_=parse_table(boxes,size,candidate)
            if rows:header=candidate;continued=True
        rows,notes=parse_table(boxes,size,header)
        carried=header if rows and header else None
        for row in rows:
            row.update(page=n,line_no=len(items)+1);items.append(row)
        diagnostics.append({'page':n,'source':source,'size':size,'boxes':row_evidence(boxes,{'all':range(len(boxes))})['all'],
                            'header_columns':header.centers if header else {},'continued_columns':continued,
                            'preprocessing':info,'adjustment_notes':notes,'line_numbers':[r['line_no'] for r in rows]})
    findings+=findings_for_items(items)
    for k in ('seller_name','invoice_date','total_amount'):
        if fields.get(k) is None:findings.append({'code':'MISSING_FIELD','field':k})
    if not items:findings.append({'code':'NO_CONFIRMED_ITEMS'})
    return fields,items,{'source':'context-v4','raw_text':'\n'.join(l.text for l in all_lines),
                        'total_pages':total,'pages_processed':len(pages),'truncated':total>max_pages,
                        'pages':diagnostics,'field_evidence':evidence,'financial_adjustments':adjustments,
                        'ocr_consensus_changes':consensus,
                        'findings':findings,'requires_review':bool(findings),
                        'confidence_semantics':'OCR engine word scores only; not calibrated field accuracy'}
