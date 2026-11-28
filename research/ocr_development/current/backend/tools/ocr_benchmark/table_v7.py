"""Experimental geometric row/cell ownership. No merchant templates or labels.

Unlike nearest-anchor assignment, a product description stays between the
previous selling row and its own numeric row. Registered prices and promotions
are evidence of adjustments, never product names or alternative selling prices.
"""
from collections import Counter
from decimal import Decimal
from statistics import median
from math import isfinite
import re

from . import pipeline_v4 as v4, pipeline_v5 as v5
from .table_v3 import number, row_evidence
from .table_v6 import header_for, parse_rows as legacy_rows

SALE = re.compile(r'gia\s*ban|selling\s*price|sale\s*price')
REGISTERED = re.compile(r'gia\s*dang\s*ky|registered\s*price|list\s*price')
PROMO = re.compile(r'^(?:km\b|khuyen mai|discount|giam gia|chiet khau|phu thu|surcharge)')


def center(box):
    x0,y0,x1,y1,_=box.word
    return (x0+x1)/2,(y0+y1)/2


def owns_cell(y, row_index, anchors, height):
    """A printed cell belongs to the unique closest amount anchor.

    Use a small ambiguity margin instead of borrowing a neighbouring row's
    value. Anchors include rows that may later be rejected by the parser.
    """
    distances = sorted((abs(y - anchor['y']), index)
                       for index, anchor in enumerate(anchors))
    if not distances or distances[0][1] != row_index or distances[0][0] > 1.05 * height:
        return False
    return len(distances) == 1 or distances[1][0] - distances[0][0] > .15 * height


def parse_rows(read, zone, inherited_header=None):
    local = header_for(read)
    # A caller may have recovered more explicit column labels in another
    # read of this same table. Do not discard those labels merely because
    # this local read also has a partial header.
    compatible = local is None or (inherited_header is not None
        and set(local.centers).issubset(inherited_header.centers)
        and all(abs(local.centers[key] - inherited_header.centers[key]) * read.size[0] <= 2 * zone['h']
                for key in local.centers))
    header = inherited_header if inherited_header and compatible else local
    if not header or 'amount' not in header.centers:
        legacy,rejected=legacy_rows(read,zone)
        positioned=[]
        for row in legacy:
            evidence=row.get('evidence',{})
            parts=evidence.get('amount') or evidence.get('description') or []
            try:
                positions=[float(point[1]) for part in parts for point in part.get('polygon',[])]
                if not positions or not all(isfinite(value) for value in positions):
                    raise ValueError('Missing source coordinates')
                positioned.append({**row,'_y':median(positions),'_read':read.tag})
            except (TypeError,ValueError,IndexError):
                rejected.append({'code':'ROW_POSITION_UNAVAILABLE','evidence':evidence})
        return positioned,rejected
    boxes=read.boxes; width=read.size[0]; h=zone['h']; rejected=[]
    lines=sorted(read.lines,key=lambda l:l.y)
    body=[]
    for line in lines:
        p=v4.semantic(line.text)
        if line.y<=header.bottom or line.y>=zone['footer_start']:continue
        if REGISTERED.search(p) or PROMO.match(p):
            rejected.append({'code':'NON_SELLING_ADJUSTMENT','text':line.text,
                             'evidence':row_evidence(boxes,{'source':line.ids})['source']});continue
        if (v4.META.match(p) and not SALE.search(p)) or v4.SUMMARY.match(p) or v4.date_value(line.text):continue
        body.append(line)
    # Assign numbers using column Voronoi intervals, not product model digits.
    def role_of(x):
        roles={k:v*width for k,v in header.centers.items() if k!='ordinal'}
        role=min(roles,key=lambda k:abs(roles[k]-x))
        return role
    anchors=[]
    for line in body:
        for value in v4.money_tokens(line):
            if value.get('percent') or role_of(value['x'])!='amount':continue
            if value['value']<0:
                rejected.append({'code':'NEGATIVE_ADJUSTMENT_NOT_PRODUCT','text':line.text,
                                 'evidence':row_evidence(boxes,{'amount':value['ids']})['amount']})
                continue
            alpha=[i for i in line.ids if re.search(r'[^\W\d_]{3}',boxes[i].text)]
            if not value['formatted'] and alpha:
                # Bare zero is legitimate only with independent numeric cells.
                others=[v for v in v4.money_tokens(line) if v is not value and role_of(v['x']) in ('quantity','unit_price')]
                if not others:continue
            if len(re.sub(r'\D','',value['text']))>=8 and not value['formatted']:continue
            anchors.append({'y':line.y,'amount':value})
    # OCR sometimes splits the amount from price/quantity into a nearby line.
    rows=[];previous=header.bottom
    for row_index, anchor in enumerate(anchors):
        y=anchor['y']; roles={'amount':anchor['amount']};used=set(anchor['amount']['ids'])
        nearby=[l for l in body if abs(l.y-y)<=1.05*h]
        def owns(ids):
            return bool(ids) and owns_cell(median(center(boxes[i])[1] for i in ids),
                                           row_index, anchors, h)
        for role in ('quantity','unit_price','vat_rate','vat_amount'):
            if role not in header.centers:continue
            observed=[v for l in nearby for v in v4.money_tokens(l)
                      if not used.intersection(v['ids']) and role_of(v['x'])==role
                      and (not v.get('percent') or role=='vat_rate')]
            candidates=[v for v in observed if owns(v['ids'])]
            if candidates:
                picked=min(candidates,key=lambda v:abs(center(boxes[v['ids'][0]])[1]-y))
                roles[role]=picked;used.update(picked['ids'])
            elif observed:
                rejected.append({'code':'ROW_CELL_OWNERSHIP_UNRESOLVED', 'field':role,
                                 'y':y, 'requires_review':True})
        names=[]
        for line in body:
            if not previous+0.3*h<line.y<=y+0.45*h:continue
            if SALE.search(v4.plain(line.text)):continue
            ids=[i for i in line.ids if i not in used]
            # Strip a leading EAN (including fragmented EAN), not model digits.
            prefix=[]
            for i in ids:
                if boxes[i].text.isdigit():prefix.append(i)
                else:break
            if 8<=sum(len(boxes[i].text) for i in prefix)<=16:ids=[i for i in ids if i not in prefix]
            selected=[]
            for i in ids:
                token=boxes[i].text.strip()
                if re.fullmatch(r'[-~−]\s*\d[\d.,]*',token):
                    rejected.append({'code':'ADJUSTMENT_BESIDE_DESCRIPTION','text':token});continue
                if abs(line.y-y)<=1.05*h and role_of(center(boxes[i])[0]) in ('quantity','unit_price','amount','unit','vat_rate','vat_amount'):
                    continue
                selected.append(i)
            if any(re.search(r'[^\W\d_]{3}',boxes[i].text) for i in selected):names.extend(selected)
        name=' '.join(boxes[i].text for i in names).strip(' |')
        if not name:continue
        p=v4.semantic(name)
        if v4.META.match(p) or v4.SUMMARY.match(p) or PROMO.match(p):continue
        row={'description':name,'unit':None,'quantity':None,'unit_price':None,'amount':anchor['amount']['value'],
             'vat_rate':None,'vat_amount':None,'_y':y,'_read':read.tag}
        ev={k:v['ids'] for k,v in roles.items()};ev['description']=names
        for role in ('quantity','unit_price','vat_rate','vat_amount'):
            if role in roles:row[role]=number(roles[role]['text'],role)
        # Keep unreadable printed quantity cells for a pixel reread; never
        # substitute I/l/O with digits or derive quantity from price and total.
        if row['quantity'] is None and 'quantity' in header.centers:
            ids=[i for l in nearby for i in l.ids if role_of(center(boxes[i])[0])=='quantity'
                 and i not in used and owns([i])
                 and re.fullmatch(r'[0-9OoIljJ|.,()]{1,8}',boxes[i].text)]
            if ids:ev['quantity']=ids
        if 'unit' in header.centers:
            ids=[i for l in nearby for i in l.ids if role_of(center(boxes[i])[0])=='unit'
                 and i not in used and owns([i])
                 and re.fullmatch(r'[^\W\d_]{1,12}',boxes[i].text)]
            if ids:
                chosen=min(ids,key=lambda i:abs(center(boxes[i])[1]-y))
                row['unit']=boxes[chosen].text;ev['unit']=[chosen]
        row['evidence']=row_evidence(boxes,ev);rows.append(row);previous=y
    return rows,rejected


def reconcile(tables, height):
    """Choose observed cells by spatial correspondence and distinct OCR reads.

    Arithmetic is deliberately excluded from ranking: it may detect an error,
    but cannot supply a missing digit, quantity, price or product.
    """
    bands=[];findings=[]
    for read,rows in tables:
        for row in rows:
            y=row['_y']; band=next((b for b in bands if abs(b[0]['_y']-y)<height),None)
            if band is None:bands.append([row])
            else:band.append(row)
    output=[]
    for band in sorted(bands,key=lambda b:b[0]['_y']):
        def score(row):
            parts=row['evidence'].get('description',[])
            return sum(p.get('ocr_score') or 0 for p in parts)/max(1,len(parts))
        best=max(band,key=score);result={**best,'evidence':dict(best['evidence'])}
        for role in ('quantity','unit_price','amount','unit','vat_rate','vat_amount'):
            valid=[r for r in band if r.get(role) is not None]
            if not valid:continue
            groups={}
            for r in valid:groups.setdefault(str(r[role]),[]).append(r)
            ranked=sorted(groups.values(),key=lambda g:(len({r['_read'] for r in g}),
                max(sum(p.get('ocr_score') or 0 for p in r['evidence'].get(role,[]))/max(1,len(r['evidence'].get(role,[]))) for r in g)),reverse=True)
            winner=max(ranked[0],key=lambda r:sum(p.get('ocr_score') or 0 for p in r['evidence'].get(role,[])))
            result[role]=winner[role];result['evidence'][role]=winner['evidence'].get(role,[])
            if len(groups)>1:findings.append({'code':'V7_CELL_CONFLICT','field':role,'y':best['_y'],
                                            'values':list(groups),'selected':str(winner[role])})
        output.append(result)
    return output,findings
