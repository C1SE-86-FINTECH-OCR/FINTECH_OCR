"""V8 row ownership and evidence-constrained cell selection, no templates."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from itertools import product
from difflib import SequenceMatcher
import re
import unicodedata
from statistics import median
from . import pipeline_v4 as v4, pipeline_v5 as v5, table_v7 as v7
from .table_v6 import header_for as old_header
from .table_v3 import row_evidence,CONTINUED,Header

UNITS={'cai':'Cái','chiec':'Cái','hop':'Hộp','goi':'Gói','chai':'Chai','tui':'Túi',
       'kg':'Kg','lit':'Lít','l':'Lít','ram':'Ram','thung':'Thùng','pc':'pc','pcs':'pc','gio':'giờ','ngay':'ngày'}

def unit(value):
    return UNITS.get(v4.plain(str(value)).strip(' .,:;')) if value is not None else None

def cell_identity(key, value):
    """Compare parsed values without changing the printed value or its evidence."""
    if value is None:
        return ('missing', None)
    if key in ('quantity', 'unit_price', 'amount', 'vat_rate', 'vat_amount'):
        try:
            number = Decimal(str(value))
            if number.is_finite():
                return ('number', number)
        except (InvalidOperation, ValueError):
            pass
        return ('literal', str(value))
    if key == 'unit':
        canonical = unit(value)
        if canonical is not None:
            return ('unit', canonical)
    # Preserve accents, punctuation and case (including case-sensitive SKUs).
    return ('text', ' '.join(unicodedata.normalize('NFC', str(value)).split()))


def label_like(text,label):
    words=v4.plain(text).split();n=len(label.split())
    return any(SequenceMatcher(None,' '.join(words[i:i+n]).strip(' :.'),label).ratio()>=.85 for i in range(max(1,len(words)-n+1)))

def header_for(read):
    header=old_header(read)
    if not header:return None
    centers=dict(header.centers);h=median(b.word[3]-b.word[1] for b in read.boxes)
    no=[b for b in read.boxes if v4.plain(b.text).strip(' .:') in ('no','stt','#') and abs(v7.center(b)[1]-header.bottom)<2*h]
    if no and 'description' in centers:
        b=min(no,key=lambda b:b.word[0])
        if v7.center(b)[0]/read.size[0]<centers['description']:centers['ordinal']=v7.center(b)[0]/read.size[0]
    return Header(header.bottom,centers,header.indices)

def confidence(parts):
    scores=[p.get('ocr_score') for p in parts if p.get('ocr_score') is not None]
    return sum(scores)/len(scores) if scores else .5

def decorate(row,read):
    if '_y' not in row:
        parts=row.get('evidence',{}).get('amount',[])
        if not parts:return False
        row['_y']=median(sum(p[1] for p in part['polygon'])/len(part['polygon']) for part in parts)
    row['_read']=read.tag;row['_cell_candidates']={}
    for key in ('quantity','unit_price','amount','unit'):
        if row.get(key) is not None:row['_cell_candidates'][key]=[{'value':row[key],'parts':row.get('evidence',{}).get(key,[]),'read':read.tag}]
    return True

def parse_rows(read,zone,inherited_header=None):
    # Remove only a label-confirmed registered-price line before it can
    # become a selling-row anchor. Source boxes remain unchanged in evidence.
    kept=[line.ids for line in read.lines if not label_like(line.text,'gia dang ky') and not label_like(line.text,'registered price')]
    ids=list(dict.fromkeys(i for group in kept for i in group));mapping={old:new for new,old in enumerate(ids)}
    read=v5.Read(read.tag,[read.boxes[i] for i in ids],[[mapping[i] for i in group] for group in kept],read.size,read.transform)
    local=header_for(read)
    header=inherited_header if inherited_header and (not local or len(inherited_header.centers)>len(local.centers)) else local
    rows,rejected=v7.parse_rows(read,zone,header)
    if not header:
        amount_only=thermal_rows(read)
        if amount_only:rows=amount_only
        return [r for r in rows if decorate(r,read)],rejected
    boxes=read.boxes;h=zone['h'];w=read.size[0]
    numeric_left=min(header.centers[k]*w for k in ('quantity','unit_price','amount') if k in header.centers)
    ordered=sorted(rows,key=lambda r:r['_y']);lines=sorted(read.lines,key=lambda l:l.y)
    def name_ids(line,y):
        p=v4.semantic(line.text)
        if v4.META.match(p) or v4.SUMMARY.match(p) or v7.PROMO.match(p) or v7.REGISTERED.search(p) or v7.SALE.search(p) or label_like(p,'gia ban') or CONTINUED.match(p):return []
        ids=list(line.ids)
        prefix=[]
        for i in ids:
            if boxes[i].text.isdigit():prefix.append(i)
            else:break
        if 8<=sum(len(boxes[i].text) for i in prefix)<=16:ids=[i for i in ids if i not in prefix]
        if abs(line.y-y)<1.1*h:
            ids=[i for i in ids if v7.center(boxes[i])[0]<numeric_left-h/2]
            if 'unit' in header.centers:
                cx=header.centers['unit']*w
                radius=min([abs(cx-v*w)/2 for k,v in header.centers.items() if k!='unit'] or [h])
                ids=[i for i in ids if not(abs(v7.center(boxes[i])[0]-cx)<radius and re.fullmatch(r'[^\W\d_]{1,12}',boxes[i].text))]
        if 'ordinal' in header.centers and 'description' in header.centers:
            boundary=(header.centers['ordinal']+header.centers['description'])*w/2
            ids=[i for i in ids if not (re.fullmatch(r'\d+[.)]?',boxes[i].text) and v7.center(boxes[i])[0]<boundary)]
        ids=[i for i in ids if not re.fullmatch(r'[-~−]\s*\d[\d.,]*',boxes[i].text)]
        return ids if any(re.search(r'[^\W\d_]{3}',boxes[i].text) for i in ids) else []
    for n,row in enumerate(ordered):
        y=row['_y'];previous=ordered[n-1]['_y'] if n else header.bottom
        following=ordered[n+1]['_y'] if n+1<len(ordered) else zone['footer_start']
        inline=[(line,name_ids(line,y)) for line in lines if abs(line.y-y)<.65*h]
        inline=[(line,ids) for line,ids in inline if ids]
        ids=[]
        if inline:
            ids=[i for _,part in inline for i in part]
            # Once a row starts inline, its following description-only lines
            # belong to it, not to the next numeric anchor.
            for line in lines:
                if not y+.65*h<line.y<following-.65*h:continue
                parts=name_ids(line,y)
                if parts and not any(v['formatted'] for v in v4.money_tokens(line)):ids+=parts
        else:
            for line in lines:
                if previous+.35*h<line.y<=y+.45*h:ids+=name_ids(line,y)
        numeric_parts={ (part['text'],tuple(map(tuple,part['polygon']))) for key,parts in row.get('evidence',{}).items()
                        if key in ('quantity','unit_price','amount','vat_rate','vat_amount') for part in parts }
        ids=[i for i in ids if (boxes[i].text,tuple(boxes[i].polygon)) not in numeric_parts]
        if ids:
            ids=list(dict.fromkeys(ids));row['description']=' '.join(boxes[i].text for i in ids).strip(' |')
            row['evidence']['description']=row_evidence(boxes,{'name':ids})['name']
        # Keep the unit selected by the row-owned V7 parser. A second,
        # wider search here could borrow the unit from a neighbouring row.
        adjustments=[]
        for line in lines:
            if y<line.y<following and v7.PROMO.match(v4.semantic(line.text)):
                for amount in v4.money_tokens(line):
                    adjustments.append({'label':line.text,'amount_observed':amount['value'],
                                        'evidence':row_evidence(boxes,{'adjustment':line.ids})['adjustment']})
        if adjustments:row['discount_observations']=adjustments
        decorate(row,read)
    return ordered,rejected

def thermal_rows(read):
    """Headerless amount-only bill rows need aligned, separated source cells."""
    if v4.classify_context(read.lines,read.size) not in ('bill','einvoice'):return []
    boxes=read.boxes;h=median(b.word[3]-b.word[1] for b in boxes) if boxes else 12
    metadata=[l.y for l in read.lines if re.search(r'^(?:ngay|date|so (?:bill|hd|hoa don)|receipt no|invoice no)',v4.plain(l.text))]
    start=max(metadata) if metadata else 0;rows=[];positions=[]
    for line in read.lines:
        p=v4.semantic(line.text)
        if line.y<=start:continue
        if v4.SUMMARY.match(p) or v7.PROMO.match(p):break
        if v4.META.match(p) or v5.TYPE.search(p):continue
        values=v4.money_tokens(line)
        if not values:continue
        amount=max(values,key=lambda v:v['x'])
        if amount['value']<0 or amount['x']<read.size[0]*.5:continue
        ids=[i for i in line.ids if i not in amount['ids']]
        if not ids or not any(re.search(r'[^\W\d_]{3}',boxes[i].text) for i in ids):continue
        gap=min(boxes[i].word[0] for i in amount['ids'])-max(boxes[i].word[2] for i in ids)
        if gap<2*h or len(re.sub(r'\D','',amount['text']))<3:continue
        rows.append({'description':' '.join(boxes[i].text for i in ids),'quantity':None,'unit_price':None,'unit':None,
                     'amount':amount['value'],'vat_rate':None,'vat_amount':None,'_y':line.y,
                     'evidence':row_evidence(boxes,{'description':ids,'amount':amount['ids']})})
        positions.append(amount['x'])
    return rows if len(rows)>=2 and max(positions)-min(positions)<2*h else []

def add_observation(row,key,value,parts,read):
    if value is None:return
    if key!='unit':
        try:value=Decimal(str(value))
        except Exception:return
        if not value.is_finite() or value<0:return
    row.setdefault('_cell_candidates',{}).setdefault(key,[]).append({'value':value,'parts':parts,'read':read})

def select_cells(row,*,allow_arithmetic=True):
    """Rank only finite OCR observations; never derive a missing numeric cell."""
    findings=[];candidates=row.get('_cell_candidates',{})
    for key in ('quantity','unit_price','amount','unit'):
        values=candidates.get(key,[])
        if not values:continue
        if key=='unit':
            known=[v for v in values if unit(v['value'])]
            if known:
                winner=max(known,key=lambda v:confidence(v['parts']))
                row['unit']=unit(winner['value']);row['evidence']['unit']=winner['parts']
                row['unit_observed_literal']=winner['value']
            else:findings.append({'code':'V8_UNIT_UNRESOLVED','value':row.get('unit')})
        elif row.get(key) is None and len({Decimal(str(v['value'])) for v in values})==1:
            winner=max(values,key=lambda v:confidence(v['parts']))
            row[key]=Decimal(str(winner['value']));row['evidence'][key]=winner['parts']
            findings.append({'code':'V8_OBSERVED_MISSING_CELL_RECOVERED','field':key,'after':row[key]})
        if len({cell_identity(key, v['value']) for v in values})>1:findings.append({'code':'V8_OBSERVATION_CONFLICT','field':key})
    numeric=[]
    for key in ('quantity','unit_price','amount'):
        groups={}
        for value in candidates.get(key,[]):groups.setdefault(Decimal(str(value['value'])),[]).append(value)
        isolated=[v for v in candidates.get(key,[]) if v['read'].startswith(('v7-cell/','v8-cell/'))]
        stable={Decimal(str(v['value'])) for v in isolated}
        # Unanimous successful isolated recognitions may constrain one cell.
        # Conflicting crop readings (even a majority) remain alternatives.
        if len(isolated)>=2 and len(stable)==1:
            only=next(iter(stable));groups={only:groups[only]}
        numeric.append(groups)
    if allow_arithmetic and not row.get('discount_observations') and all(numeric):
        consistent=[triple for triple in product(*(list(g)[:6] for g in numeric)) if abs(triple[0]*triple[1]-triple[2])<=Decimal('2')]
        # Multiple arithmetically possible tuples are not enough to choose a
        # digit. A unique observed tuple may resolve contradictory OCR votes.
        if len(consistent)==1:
            triple=consistent[0]
            for key,value,groups in zip(('quantity','unit_price','amount'),triple,numeric):
                best=max(groups[value],key=lambda c:confidence(c['parts']))
                before=row.get(key);row[key]=value;row['evidence'][key]=best['parts']
                if before!=value:findings.append({'code':'V8_OBSERVED_ARITHMETIC_SELECTION','field':key,'before':before,'after':value,
                    'read':best['read'],'reason':'unique consistent tuple of OCR-observed values; no value derived'})
        elif len(consistent)>1:findings.append({'code':'V8_AMBIGUOUS_ARITHMETIC','candidates':len(consistent)})
    return findings

def reconcile(tables,height):
    bands=[]
    for read,rows in tables:
        for row in rows:
            band=next((b for b in bands if abs(b[0]['_y']-row['_y'])<height),None)
            if band is None:bands.append([row])
            else:band.append(row)
    out=[];findings=[]
    for band in sorted(bands,key=lambda b:b[0]['_y']):
        best=max(band,key=lambda r:confidence(r.get('evidence',{}).get('description',[])))
        row=deepcopy(best);row['_cell_candidates']={}
        for other in band:
            for key,values in other.get('_cell_candidates',{}).items():
                row['_cell_candidates'].setdefault(key,[]).extend(deepcopy(values))
        # Retain existing observed values as the initial winner; correction
        # requires positive semantic/cell evidence in select_cells.
        findings.extend(select_cells(row));out.append(row)
    return out,findings
