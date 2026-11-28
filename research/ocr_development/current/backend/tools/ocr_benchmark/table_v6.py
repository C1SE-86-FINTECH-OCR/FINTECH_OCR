"""Row-first experimental grid parsing, using only recognized source boxes."""
from decimal import Decimal
from difflib import SequenceMatcher
import re
from statistics import median

from . import pipeline_v4 as v4, pipeline_v5 as v5
from .table_v3 import Header, number, row_evidence


def header_for(read):
    header = v5.column_header(read)
    if not header:
        return None
    centers = dict(header.centers)
    # OCR confusion of the short *column label*, never a numeric cell value.
    if 'quantity' not in centers:
        candidates = [b for b in read.boxes if re.fullmatch(r's[l1i|][.:]?', v4.plain(b.text))
                      and abs(b.word[3]-header.bottom)<3*median(x.word[3]-x.word[1] for x in read.boxes)]
        if len(candidates)==1:
            centers['quantity']=(candidates[0].word[0]+candidates[0].word[2])/2/read.size[0]
    return Header(header.bottom, centers, header.indices)


def clean_rows(rows,read,zone,rejected):
    output=[]
    for row in rows:
        ev=row.get('evidence',{});amount=ev.get('amount',[]);parts=ev.get('description',[])
        if amount and parts:
            ax=min(p[0] for a in amount for p in a['polygon'])
            ay=median(sum(p[1] for p in a['polygon'])/len(a['polygon']) for a in amount)
            kept=[d for d in parts if not (min(p[0] for p in d['polygon'])>ax and
                  abs(sum(p[1] for p in d['polygon'])/len(d['polygon'])-ay)<zone['h'])]
            if kept and len(kept)<len(parts):
                rejected.append({'code':'TEXT_BEYOND_AMOUNT_COLUMN','parts':[p for p in parts if p not in kept]})
                row['description']=' '.join(p['text'] for p in kept).strip(' |')
                row['evidence']['description']=kept
            label=re.sub(r'[^a-z]','',v4.plain(row['description']))
            summary=any(SequenceMatcher(None,label,s).ratio()>=.82 for s in ('tamtinh','tongcong','tongtien','thanhtien','subtotal','grandtotal'))
            if summary and row.get('quantity') is None and row.get('unit_price') is None and ay>=zone['footer_start']-3*zone['h']:
                rejected.append({'code':'SUMMARY_LABEL_CANDIDATE','row':row,'reason':'near footer; no independent quantity/price cells'})
                continue
        output.append(row)
    return output


def parse_rows(read, zone):
    header=header_for(read)
    if not header:
        rejected=[]
        return clean_rows(v5.table_rows(read,zone),read,zone,rejected),rejected
    boxes=read.boxes;h=zone['h'];width=read.size[0];body=[];rejected=[]
    for line in read.lines:
        p=v4.semantic(line.text)
        if line.y<header.bottom or line.y>=zone['footer_start']:continue
        if v4.META.match(p) or v4.SUMMARY.match(p) or v4.ADJUST.match(p) or v5.NONPRODUCT.search(p):continue
        if v4.date_value(line.text) is not None:continue
        # A standalone SKU/barcode separates products but is not a description.
        ids=[i for i in line.ids if not re.fullmatch(r'\d{8,16}',boxes[i].text)]
        if ids:body.append(v4.Line(ids,boxes))
    anchors=[]
    for line in body:
        values=[v for v in v4.money_tokens(line) if not v.get('percent')]
        roles={};used=set()
        for role in ('amount','unit_price','quantity','vat_rate','vat_amount'):
            if role not in header.centers:continue
            cx=header.centers[role]*width
            radius=min([abs(cx-v*width)/2 for k,v in header.centers.items() if k!=role] or [width*.12])
            eligible=[v for v in values if not used.intersection(v['ids']) and abs(v['x']-cx)<=max(radius,h)]
            if eligible:
                val=min(eligible,key=lambda v:abs(v['x']-cx));roles[role]=val;used.update(val['ids'])
        if 'amount' not in roles:continue
        amount=roles['amount']
        # A full-width description/model can cross numeric columns. A bare
        # integer on that text line is not enough to establish a numeric row.
        text_ids=[i for i in line.ids if i not in used and re.search(r'[^\W\d_]',boxes[i].text)]
        substantial=[i for i in text_ids if not v5.UNIT.fullmatch(v4.plain(boxes[i].text)) and len(v4.plain(boxes[i].text))>3]
        independent_cells=len(roles)>=2
        if not amount['formatted'] and not independent_cells and substantial:
            rejected.append({'code':'MODEL_NOT_AMOUNT','text':line.text,
                             'evidence':row_evidence(boxes,{'source':line.ids})['source']})
            continue
        if not amount['formatted'] and not independent_cells:
            continue
        anchors.append({'line':line,'roles':roles,'used':used,'names':[]})
    for line in body:
        own=next((a for a in anchors if a['line'] is line),None)
        used=own['used'] if own else set()
        ids=[i for i in line.ids if i not in used and re.search(r'\w',boxes[i].text)
             and not (len(v4.plain(boxes[i].text))<=1 and (boxes[i].score or 0)<.7)]
        if own:
            # On a numeric row the name stays before the first numeric column;
            # an above-row description may span the entire page width.
            left=min(header.centers[k]*width for k in ('quantity','unit_price','amount') if k in header.centers)
            ids=[i for i in ids if boxes[i].word[0]<left-h]
        if not any(re.search(r'[^\W\d_]{3}',boxes[i].text) and not v5.UNIT.fullmatch(v4.plain(boxes[i].text)) for i in ids):continue
        options=[(abs(line.y-a['line'].y)*(.9 if line.y<=a['line'].y else 1.15),a)
                 for a in anchors if -3.2*h<=line.y-a['line'].y<=1.3*h]
        if options:
            min(options,key=lambda x:x[0])[1]['names'].append((line.y,ids))
    items=[]
    for anchor in anchors:
        ids=[i for _,part in sorted(anchor['names']) for i in part]
        name=' '.join(boxes[i].text for i in ids).strip(' |')
        if not name:continue
        roles=anchor['roles']
        row={'description':name,'unit':None,'quantity':None,'unit_price':None,
             'amount':roles['amount']['value'],'vat_rate':None,'vat_amount':None}
        for role in ('quantity','unit_price','vat_rate','vat_amount'):
            if role in roles:row[role]=number(roles[role]['text'],role)
        row['evidence']=row_evidence(boxes,{**{k:v['ids'] for k,v in roles.items()},'description':ids})
        if 'unit' in header.centers:
            cx=header.centers['unit']*width
            units=[i for i in anchor['line'].ids if abs((boxes[i].word[0]+boxes[i].word[2])/2-cx)<1.5*h
                   and v5.UNIT.fullmatch(v4.plain(boxes[i].text))]
            if units:
                row['unit']=' '.join(boxes[i].text for i in units)
                row['evidence']['unit']=row_evidence(boxes,{'unit':units})['unit']
        items.append(row)
    return clean_rows(items,read,zone,rejected),rejected


def arithmetic_checks(fields,items):
    """Detect discrepancies only. Never mutate or fill a value."""
    findings=[]
    for n,row in enumerate(items,1):
        if all(row.get(k) is not None for k in ('quantity','unit_price','amount')):
            q,p,a=(Decimal(str(row[k])) for k in ('quantity','unit_price','amount'))
            if abs(q*p-a)>Decimal('2'):
                findings.append({'code':'ROW_ARITHMETIC_CONFLICT','line':n,'difference':q*p-a})
    if fields.get('subtotal') is not None and items and all(r.get('amount') is not None for r in items):
        difference=sum(Decimal(str(r['amount'])) for r in items)-Decimal(str(fields['subtotal']))
        if abs(difference)>Decimal('2'):
            findings.append({'code':'ITEM_SUBTOTAL_CONFLICT','difference':difference,
                             'note':'incomplete rows or different printed scope possible; no correction'})
    return findings
