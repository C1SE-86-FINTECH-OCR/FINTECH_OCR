"""Opt-in region OCR experiment. No labels, vendor templates, DB or network.

V4 remains immutable. Crops, OCR alternatives, coordinate transforms and rejected
candidates are evidence, not verified values. Arithmetic never fills a cell.
"""
from collections import Counter, deque
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from io import BytesIO
import math
import re
from statistics import median

from PIL import Image, ImageOps, ImageFilter

from app import extraction as old
from . import pipeline_v4 as v4
from .layout import TextBox, rectangle
from .table_v3 import Header, number, findings_for_items, row_evidence


ADDRESS = re.compile(r'^(?:\d+(?:\s+\d+)?\s|dia\s|address|street|to\s+\d|khu\b|cho\b|phuong\b|quan\b|huyen\b|tp[.,\s]|p\.|q\.)')
LEGAL = re.compile(r'\b(?:cong ty|company|chi nhanh|doanh nghiep|ho kinh doanh|cua hang|sieu thi|minimart|nha hang|khach san)\b')
TYPE = re.compile(r'hoa don|invoice|receipt|phieu (?:thu|ban|thanh)|\bbill\b|ve xe|the va[o0]|ticket')
NONPRODUCT = re.compile(r'\b(?:gio phuc vu|gio mo cua|service hours|thu ngan|cashier|gia dang ky|registered price|tien (?:khach|mat|thua)|tong (?:cong|tien|so)|tam tinh|sub\s*total|grand total|delivery commission|now\b|so (?:hd|hoa don|tham chieu)|password|wifi|khuyen mai|km\b)')
UNIT = re.compile(r'^(?:cai|cha|goi|g[o0]t|pcs|hop|con|kg|g|ml|l|set|box|pc|chiec)$')


def identity(value):
    return Decimal(str(value)) if isinstance(value,(int,float,Decimal)) else str(value)


def area(quad):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(quad,quad[1:]+quad[:1])))/2


def paper_view(image):
    """Find one large low-saturation paper component, with conservative fallback.

    Connected components run on <=230k pixels. QUAD maps the visible paper to a
    rectangle; the original is retained and no text/content is synthesized.
    """
    image=ImageOps.exif_transpose(image).convert('RGB')
    if image.width*image.height>30_000_000:
        raise ValueError('Page exceeds 30 MP')
    proxy=image.copy();proxy.thumbnail((360,640))
    hsv=proxy.convert('HSV');pix=hsv.tobytes();w,h=proxy.size
    central=[pix[(y*w+x)*3+1] for y in range(h//6,h*5//6) for x in range(w//4,w*3//4)
             if pix[(y*w+x)*3+2]>140]
    saturation=min(90,max(25,median(central)+12)) if central else 45
    mask=Image.frombytes('L',(w,h),bytes(255 if pix[i+1]<saturation and pix[i+2]>80 else 0 for i in range(0,len(pix),3)))
    mask=mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    bits=bytearray(mask.tobytes());components=[]
    for seed in range(len(bits)):
        if not bits[seed]:continue
        bits[seed]=0;todo=deque([seed]);points=[]
        while todo:
            n=todo.popleft();x=n%w;y=n//w;points.append((x,y))
            for other in (n-1 if x else -1,n+1 if x+1<w else -1,n-w if y else -1,n+w if y+1<h else -1):
                if other>=0 and bits[other]:bits[other]=0;todo.append(other)
        if len(points)>.12*w*h:components.append(points)
    info={'method':'original','source_size':image.size,'coordinate_space':'document pixels'}
    if not components:return image,info
    pts=max(components,key=len)
    # Convex hull reduction keeps the actual paper corners. Diagonal extrema
    # can cut the right/bottom edge off a long or irregular component.
    ordered=sorted(set(pts))
    cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def half(points):
        hull=[]
        for point in points:
            while len(hull)>1 and cross(hull[-2],hull[-1],point)<=0:hull.pop()
            hull.append(point)
        return hull
    hull=half(ordered)[:-1]+half(list(reversed(ordered)))[:-1]
    if len(hull)<4:return image,info
    while len(hull)>4:
        k=min(range(len(hull)),key=lambda i:abs(cross(hull[i-1],hull[i],hull[(i+1)%len(hull)])))
        hull.pop(k)
    tl=min(range(4),key=lambda i:sum(hull[i]));q=hull[tl:]+hull[:tl]
    if q[1][0]<q[-1][0]:q=[q[0],q[-1],q[-2],q[1]]
    if len(set(q))<4 or not .18*w*h<area(q)<.94*w*h:return image,info
    cx=sum(x for x,_ in q)/4;cy=sum(y for _,y in q)/4
    q=[(min(image.width-1,max(0,(cx+(x-cx)*1.035)*image.width/w)),
        min(image.height-1,max(0,(cy+(y-cy)*1.035)*image.height/h))) for x,y in q]
    qp=[(x*w/image.width,y*h/image.height) for x,y in q]
    inside=sum(all(cross(a,b,pt)>=-1 for a,b in zip(qp,qp[1:]+qp[:1])) or
               all(cross(a,b,pt)<=1 for a,b in zip(qp,qp[1:]+qp[:1])) for pt in pts)
    if inside/len(pts)<.995:
        # A component with an irregular boundary is safe to crop only as a box.
        x0=max(0,(min(x for x,y in pts)-4)*image.width/w);x1=min(image.width,(max(x for x,y in pts)+4)*image.width/w)
        y0=max(0,(min(y for x,y in pts)-4)*image.height/h);y1=min(image.height,(max(y for x,y in pts)+4)*image.height/h)
        return image.crop((x0,y0,x1,y1)),{**info,'method':'paper-component-bbox','source_bbox':(x0,y0,x1,y1),'mask_threshold':saturation}
    width=round(max(math.dist(q[0],q[1]),math.dist(q[3],q[2])))
    height=round(max(math.dist(q[0],q[3]),math.dist(q[1],q[2])))
    if min(width,height)<80 or width*height>16_000_000:return image,info
    doc=image.transform((width,height),Image.Transform.QUAD,(*q[0],*q[3],*q[2],*q[1]),Image.Resampling.BICUBIC)
    info.update(method='paper-component-quad',source_quad=q,document_size=doc.size,mask_threshold=saturation,
                component_coverage=inside/len(pts))
    return doc,info


@dataclass
class Read:
    tag: str
    boxes: list
    groups: list
    size: tuple
    transform: dict
    refined: dict | None = None

    @property
    def lines(self):
        return [v4.Line(ids,self.boxes) for ids in self.groups]

    @property
    def text(self):
        return '\n'.join(l.text for l in self.lines)


def ocr_region(doc,bbox,tag,lang='vie+eng',psm=6,line_height=None):
    crop=ImageOps.autocontrast(doc.crop(bbox).convert('L'),cutoff=.25)
    original_size=crop.size
    requested=max(.25,min(4.,48/crop.height)) if line_height else max(1.,1400/max(1,crop.width))
    scale=min(4.,requested,(12_000_000/(crop.width*crop.height))**.5)
    if abs(scale-1)>.05:
        crop=crop.resize((max(1,round(crop.width*scale)),max(1,round(crop.height*scale))),Image.Resampling.LANCZOS)
    sx=crop.width/original_size[0];sy=crop.height/original_size[1]
    data=old.pytesseract.image_to_data(crop,lang=lang,config=f'--psm {psm} -c preserve_interword_spaces=1',
                                     output_type=old.pytesseract.Output.DICT,timeout=25)
    boxes=[];groups={}
    for i,text in enumerate(data['text']):
        if not text.strip():continue
        x,y,w,h=(data[k][i] for k in ('left','top','width','height'))
        conf=float(data['conf'][i]);index=len(boxes)
        # Boxes are mapped into the document view, not fabricated word positions.
        boxes.append(rectangle(text.strip(),bbox[0]+x/sx,bbox[1]+y/sy,
                               bbox[0]+(x+w)/sx,bbox[1]+(y+h)/sy,conf/100 if conf>=0 else None))
        key=tuple(data.get(k,[0]*len(data['text']))[i] for k in ('block_num','par_num','line_num'))
        groups.setdefault(key,[]).append(index)
    ordered=sorted(groups.values(),key=lambda ids:median(boxes[i].word[1] for i in ids))
    return Read(tag,boxes,ordered,doc.size,{'bbox':bbox,'scale':(sx,sy),'lang':lang,'psm':psm,
                                         'coordinate_space':'document pixels'})


def clean_ids(line):
    ids=list(line.ids)
    while ids and (not re.search(r'\w',line.boxes[ids[0]].text) or
                   len(v4.plain(line.boxes[ids[0]].text))<=2 and (line.boxes[ids[0]].score or 0)<.65):ids.pop(0)
    while ids and not re.search(r'\w',line.boxes[ids[-1]].text):ids.pop()
    return ids


def line_conf(line):
    scores=[line.boxes[i].score for i in line.ids if line.boxes[i].score is not None and re.search(r'\w',line.boxes[i].text)]
    return sum(scores)/len(scores) if scores else 0


def column_header(read):
    """Use OCR line membership for labels split by spaces/punctuation."""
    names={'description':{'tenhang','tenhanghoa','hanghoa','mathang','description','item','product'},
           'quantity':{'sl','soluong','qty','quantity'},'unit_price':{'dongia','unitprice','dngia','bongia'},
           'amount':{'thanhtien','ttien','amount','linetotal'},'unit':{'dvt','donvitinh','unit','uom'},
           'ordinal':{'stt'},'vat_rate':{'thuesuat','vatrate'},'vat_amount':{'tienthue','vatamount'}}
    spans=[]
    for line in read.lines:
        for i in range(len(line.ids)):
            for j in range(i+1,min(len(line.ids),i+4)+1):
                ids=line.ids[i:j];text=''.join(re.sub(r'[^a-z]','',v4.plain(read.boxes[k].text)) for k in ids)
                for role,aliases in names.items():
                    if text in aliases:spans.append((role,ids,line.y))
    h=median(b.word[3]-b.word[1] for b in read.boxes) if read.boxes else 12
    candidates=[]
    for _,_,y in spans:
        role_ids={};used=set()
        for role,ids,_ in sorted([s for s in spans if abs(s[2]-y)<2*h],key=lambda s:-len(s[1])):
            if role not in role_ids and not used.intersection(ids):role_ids[role]=ids;used.update(ids)
        if 'amount' not in role_ids or not {'quantity','unit_price'}.intersection(role_ids):continue
        centers={k:median((read.boxes[i].word[0]+read.boxes[i].word[2])/2 for i in ids)/read.size[0] for k,ids in role_ids.items()}
        if len(set(round(x,2) for x in centers.values()))!=len(centers):continue
        candidates.append((len(centers),-y,Header(max(read.boxes[i].word[3] for i in used),centers,tuple(sorted(used)))))
    return max(candidates,key=lambda c:c[:2])[2] if candidates else v4.find_header(logical_boxes(read),read.size[0])


def zones(read):
    """Locate the selling interval from metadata, header and summary anchors."""
    lines=read.lines;h=median(b.word[3]-b.word[1] for b in read.boxes) if read.boxes else 12
    header=column_header(read)
    table_y=header.bottom if header else None
    if table_y is None:
        metadata=[l.y for l in lines if re.search(r'^(?:so\s*(?:hd|hoa don)|h\s*:|thoi gian|date|ngay|#saletype)',v4.semantic(l.text))]
        earliest=min(metadata) if metadata else 0
        candidates=[l.y for l in lines if l.y>earliest and not v4.META.match(v4.semantic(l.text)) and
                    not NONPRODUCT.search(v4.semantic(l.text)) and any(v['formatted'] for v in v4.money_tokens(l)) and
                    re.search(r'[^\W\d_]',l.text)]
        table_y=min(candidates)-2*h if candidates else read.size[1]*.4
        # Last metadata immediately before sales is a safer lower boundary.
        above=[l.y+h for l in lines if l.y<table_y and v4.META.match(v4.semantic(l.text))]
        if above:table_y=max(above)
    summaries=[]
    for l in lines:
        text=v4.semantic(l.text)
        if l.y>table_y+1.5*h and (v4.SUMMARY.match(text) or re.search(r'\b(?:tong cong|tong tien|tam tinh|thanh tien)\b',text)):
            summaries.append(l.y-h)
    footer=min(summaries) if summaries else read.size[1]
    return {'header_end':max(3,table_y),'table_start':max(0,table_y-2*h),
            'footer_start':max(table_y,footer),'h':h,'header_found':header is not None}


def seller_candidates(read):
    candidates=[];lines=read.lines
    boundary=min([l.y for l in lines if TYPE.search(v4.plain(l.text))] or [read.size[1]])
    heights=[median(read.boxes[i].word[3]-read.boxes[i].word[1] for i in l.ids) for l in lines if l.ids]
    typical=median(heights) if heights else 12
    for index,line in enumerate(lines):
        ids=clean_ids(line);text=' '.join(read.boxes[i].text for i in ids);p=v4.plain(text)
        for start in range(len(ids)):
            tail=' '.join(read.boxes[i].text for i in ids[start:start+4])
            if re.match(r'^(?:cong ty|chi nhanh|company|doanh nghiep)\b',v4.plain(tail)):
                ids=ids[start:];text=' '.join(read.boxes[i].text for i in ids);p=v4.plain(text);break
        if line.y>boundary or len(re.sub(r'[^a-z]','',p))<5 or TYPE.search(p) or ADDRESS.match(p) or v4.META.match(p) or NONPRODUCT.search(p):continue
        if any(re.fullmatch(pattern,p.strip(' :|.')) for pattern in v4.HEADINGS.values()):continue
        # A branch/address on the right may share a row with a logo on the left.
        # Split that separate column before rejecting phone/address metadata.
        # A numeric token inside a company name is not an address boundary.
        for stop in range(1,len(ids)):
            tail=' '.join(read.boxes[i].text for i in ids[stop:])
            prev=read.boxes[ids[stop-1]].word;current=read.boxes[ids[stop]].word
            gap=current[0]-prev[2]
            separate=gap>1.5*typical and ADDRESS.match(v4.plain(tail))
            if separate or re.match(r'^(?:tp[.,]|tel\b|hotline\b|dien thoai\b|dia chi\b)',v4.plain(tail)):
                ids=ids[:stop];text=' '.join(read.boxes[i].text for i in ids);p=v4.plain(text);break
        if len(re.sub(r'[^a-z]','',p))<5:continue
        if re.search(r'\d{4,}|@|\b(?:phuong|huyen|hotline|duong|street|tp[.,]|tel|dia chi)\b',p):continue
        conf=line_conf(v4.Line(ids,read.boxes))
        if conf<.6:continue
        font=median(read.boxes[i].word[3]-read.boxes[i].word[1] for i in ids)
        score=conf+min(2,font/max(1,typical))*.25+(.8 if LEGAL.search(p) else 0)
        score-=line.y/max(read.size[1],1)*.15
        # Join a visibly continued legal name, never an address/signature.
        if re.search(r'\b(?:cong ty|chi nhanh|company)\b',p) and index+1<len(lines):
            nxt=lines[index+1];np=v4.plain(nxt.text)
            if nxt.y-line.y<2.2*typical and not ADDRESS.match(np) and not v4.META.match(np) and not TYPE.search(np) and not re.search(r'\d{4,}|tp[.,]|dien thoai|ma so thue',np):
                if re.search(r'(?:co|co phan|trach nhiem|chi nhanh|company|limited)\s*$',p):
                    text+=' '+nxt.text;ids+=nxt.ids
        candidates.append({'value':text,'score':score,'read':read.tag,
                           'evidence':row_evidence(read.boxes,{'seller':ids})['seller']})
    return candidates


def field_candidates(read):
    fields,evidence,findings,adjustments=v4.field_context(read.lines,read.size,'png')
    candidates={}
    for key,value in fields.items():
        ev=evidence.get(key,[])
        if value is not None and ev:
            scores=[p['ocr_score'] for p in ev if p.get('ocr_score') is not None]
            candidates[key]={'value':value,'score':sum(scores)/len(scores) if scores else .5,
                             'evidence':ev,'read':read.tag}
    sellers=seller_candidates(read) if not read.tag.startswith('footer') else []
    if sellers:candidates['seller_name']=max(sellers,key=lambda c:c['score'])
    elif 'seller_name' in candidates:candidates.pop('seller_name')
    # Tax IDs are accepted only with a nearby tax label, never from phone/account.
    explicit_invoice=False
    for line in read.lines:
        p=v4.plain(line.text)
        # Explicit invoice labels can occupy the right-hand column of a date
        # line. Do not require the label to be the beginning of flattened text.
        inv=re.search(r'\b(?:so hoa don|so hd\b|invoice\s*(?:no\.?|number)|receipt\s*(?:no\.?|number)|h\s*:)\s*[:.#-]?\s*([a-z0-9][a-z0-9/-]{3,31})\b',p)
        if inv and any(ch.isdigit() for ch in inv[1]) and v4.date_value(inv[1]) is None:
            explicit_invoice=True
            # IDs have no accent-bearing glyphs; retain original case from OCR.
            original=line.text[inv.start(1):inv.end(1)]
            candidates['invoice_number']={'value':original,'score':line_conf(line),
                                           'evidence':row_evidence(read.boxes,{'invoice':line.ids})['invoice'],'read':read.tag}
        tax=re.search(r'\b(?:mst|ms[t1il]|ma so thue|tax code)\s*[:.;]?\s*(\d{10}(?:-?\d{3})?)\b',p)
        if tax:
            buyer=any(re.search(r'nguoi mua|buyer|don vi mua|khach hang',v4.plain(l.text)) and l.y<line.y for l in read.lines)
            key='buyer_tax_code' if buyer else 'seller_tax_code'
            candidates[key]={'value':tax[1],'score':line_conf(line),'evidence':row_evidence(read.boxes,{'tax':line.ids})['tax'],'read':read.tag}
        # Joined summary labels are common in OCR. A footer value must still
        # be directly printed on the same OCR line; no arithmetic inference.
        if read.tag.startswith('footer'):
            payable=re.search(r'\b(?:thanh\s*tien|tong\s*cong(?:\s*thanh\s*toan)?|grand\s*total|amount\s*due)\b',p)
            if payable and not re.search(r'khach|tien mat|cash|change|now|commission',p):
                nums=[n for n in v4.money_tokens(line) if not n.get('percent')]
                if nums:
                    amount=max(nums,key=lambda n:n['x'])
                    candidates['total_amount']={'value':amount['value'],'score':line_conf(line),
                                                'evidence':row_evidence(read.boxes,{'total':amount['ids']})['total'],'read':read.tag}
    if read.tag.startswith('footer'):
        allowed={'total_amount','subtotal','vat_rate','vat_amount'}
        if explicit_invoice:allowed.add('invoice_number')
        candidates={k:v for k,v in candidates.items() if k in allowed}
    return candidates,findings,adjustments


def choose_fields(base,reads):
    fields=dict(base);all_candidates={};findings=[];evidence={}
    for read in reads:
        cs=read.refined if read.refined is not None else field_candidates(read)[0]
        for k,c in cs.items():all_candidates.setdefault(k,[]).append(c)
    # Keep V4 classification/subtotal/date unless they are missing. The priority
    # fields below require direct regional support before replacement.
    priority={'seller_name','seller_tax_code','buyer_name','buyer_tax_code','invoice_number','total_amount'}
    for key,cs in all_candidates.items():
        if key not in priority and fields.get(key) is not None:continue
        groups={}
        for c in cs:groups.setdefault(identity(c['value']),[]).append(c)
        ranked=sorted(groups.values(),key=lambda g:(len({c['read'] for c in g}),max(c['score'] for c in g)),reverse=True)
        winner=ranked[0];count=len({c['read'] for c in winner});best=max(winner,key=lambda c:c['score'])
        if len(groups)>1:findings.append({'code':'REGION_FIELD_CONFLICT','field':key,'values':[str(g[0]['value']) for g in ranked]})
        # An unlabelled seller uses typography/location, with uncertainty kept.
        enough=count>=2 or fields.get(key) is None and best['score']>=.9
        if key=='seller_name':
            enough=best['score']>=1.15
            if fields.get(key) and v4.plain(str(fields[key]))==v4.plain(str(best['value'])):
                # Preserve the existing spelling unless a regional pass reads
                # the exact same spelling; accent-only differences need review.
                if not any(c['value']==fields[key] for c in cs) and count<2:enough=False
        if enough and (count>1 or fields.get(key) is None or key=='seller_name'):
            fields[key]=best['value'];evidence[key]=best
    return fields,evidence,findings,all_candidates


def logical_boxes(read):
    """Align words from one OCR line for parsing, retaining original evidence."""
    out=list(read.boxes)
    for ids in read.groups:
        y=median((read.boxes[i].word[1]+read.boxes[i].word[3])/2 for i in ids)
        h=median(read.boxes[i].word[3]-read.boxes[i].word[1] for i in ids)
        for i in ids:
            x0,_,x1,_,text=read.boxes[i].word
            out[i]=rectangle(text,x0,y-h/2,x1,y+h/2,read.boxes[i].score)
    return out


def table_rows(read,zone,diagnostics=None):
    # The document's selling region excludes header times, account/invoice IDs
    # and the complete footer, not only perfectly OCR-spelled summary labels.
    allowed=[]
    for ids in read.groups:
        line=v4.Line(ids,read.boxes);p=v4.semantic(line.text)
        if line.y<zone['table_start'] or line.y>=zone['footer_start']:continue
        if NONPRODUCT.search(p) or v4.META.match(p) or v4.ADJUST.match(p):continue
        if re.fullmatch(r'(?:qua tang|gift|complimentary)\W*',v4.plain(line.text)) and not v4.money_tokens(line):continue
        if v4.date_value(line.text) is not None:continue
        # Remove only a printed leading barcode, including fragmented EANs.
        prefix=[]
        for i in ids:
            if read.boxes[i].text.isdigit():prefix.append(i)
            else:break
        if 8<=sum(len(read.boxes[i].text) for i in prefix)<=16:ids=[i for i in ids if i not in prefix]
        allowed+=ids
    logical=logical_boxes(read)
    # Include the column headings for geometric assignment.
    header=column_header(read)
    if header:allowed+=list(header.indices)
    allowed=sorted(set(allowed));selected=[logical[i] for i in allowed]
    # Header geometry remains in document coordinates; indices are irrelevant
    # to the cell parser after the selected view is constructed.
    rows,_=v4.parse_table(selected,read.size,header)
    retained=[]
    for row in rows:
        p=v4.semantic(row['description'])
        if NONPRODUCT.search(p) or v4.META.match(p) or v4.SUMMARY.match(p) or v4.ADJUST.match(p):continue
        words=p.split()
        if words and all(UNIT.fullmatch(w) or len(w)<3 for w in words):continue
        # A model/package number embedded in a description may cross into the
        # amount column. It is not a sales-row anchor when a separate numeric
        # price/amount row immediately follows it. Keep the raw boxes for review.
        parts=row.get('evidence',{}).get('amount',[])
        if header and parts and row.get('quantity') is None and row.get('unit_price') is None:
            bare=all(re.fullmatch(r'\d+',part['text']) for part in parts)
            ay=median(sum(pt[1] for pt in part['polygon'])/len(part['polygon']) for part in parts)
            h=zone['h'];ax=min(pt[0] for part in parts for pt in part['polygon'])
            same=[b for b in logical if abs((b.word[1]+b.word[3])/2-ay)<h and
                  b.word[2]<=ax and re.search(r'[^\W\d_]',b.text)]
            inline=same and ax-max(b.word[2] for b in same)<1.3*h
            following=any(0<line.y-ay<2.7*h and len([v for v in v4.money_tokens(line) if v['formatted']])>=2 and
                          not re.search(r'[^\W\d_]',line.text) for line in read.lines)
            if bare and inline and following:
                if diagnostics is not None:diagnostics.append({'code':'INLINE_MODEL_ANCHOR_UNCERTAIN','row':row,
                    'reason':'unformatted number beside description; separate price/amount row below'})
                continue
        # Restore real source polygons after logical line alignment.
        for parts in row.get('evidence',{}).values():
            for part in parts:
                matches=[i for i in allowed if read.boxes[i].text==part['text'] and logical[i].polygon==tuple(tuple(v) for v in part['polygon'])]
                if matches:part['polygon']=read.boxes[matches[0]].polygon
        # Keep unparsed but visibly printed numeric-cell evidence. A quantity
        # read as "I" or "10)" can then be OCR'd again from its column, rather
        # than guessed from amount / price. Model digits in the name are owned.
        if header:
            amount_parts=row.get('evidence',{}).get('amount',[])
            if amount_parts:
                ay=median(sum(pt[1] for pt in p['polygon'])/len(p['polygon']) for p in amount_parts)
                heights=[max(pt[1] for pt in p['polygon'])-min(pt[1] for pt in p['polygon']) for p in amount_parts]
                h=median(heights)
                owned={(p['text'],tuple(tuple(pt) for pt in p['polygon'])) for p in row.get('evidence',{}).get('description',[])}
                for role in ('quantity','unit_price'):
                    if row.get(role) is not None or role not in header.centers:continue
                    cx=header.centers[role]*read.size[0]
                    peers=[v*read.size[0] for k,v in header.centers.items() if k!=role]
                    radius=min(abs(cx-x) for x in peers)/2 if peers else h
                    ids=[i for i,b in enumerate(read.boxes) if abs((b.word[0]+b.word[2])/2-cx)<=radius and
                         abs((b.word[1]+b.word[3])/2-ay)<=1.2*h and
                         re.fullmatch(r'[0-9OoIl.,()§-]{1,18}',b.text) and
                         (b.text,tuple(b.polygon)) not in owned]
                    if ids:row['evidence'][role]=row_evidence(read.boxes,{role:ids})[role]
        retained.append(row)
    return retained


def table_quality(rows):
    if not rows:return -1
    good=0.;bad=0.
    for row in rows:
        evidence=[p for parts in row.get('evidence',{}).values() for p in parts]
        scores=[p['ocr_score'] for p in evidence if p.get('ocr_score') is not None]
        good+=sum(scores)/len(scores) if scores else .4
        if row.get('quantity') is not None and row.get('unit_price') is not None and row.get('amount') is not None:
            if abs(Decimal(str(row['quantity']))*Decimal(str(row['unit_price']))-Decimal(str(row['amount'])))>=2:bad+=.5
        if NONPRODUCT.search(v4.semantic(row['description'])):bad+=2
    # Coverage is a weak tie-breaker, not an invented expected item count.
    return (good-bad)/len(rows)+min(len(rows),20)*.015


def numeric_reread(doc,parts,role):
    if not parts:return None
    xs=[p[0] for part in parts for p in part['polygon']];ys=[p[1] for part in parts for p in part['polygon']]
    h=max(ys)-min(ys);pad=max(2,h*.3)
    bbox=(max(0,min(xs)-pad),max(0,min(ys)-pad),min(doc.width,max(xs)+pad),min(doc.height,max(ys)+pad))
    crop=ImageOps.autocontrast(doc.crop(bbox).convert('L'))
    scale=min(5,max(.25,40/max(1,h)))
    crop=ImageOps.expand(crop.resize((max(1,round(crop.width*scale)),max(1,round(crop.height*scale))),Image.Resampling.LANCZOS),border=12,fill=255)
    alternatives=[]
    for lang,psm in (('eng',7),('eng',13),('vie+eng',7)):
        try:
            raw=old.pytesseract.image_to_string(crop,lang=lang,config=f'--psm {psm} -c tessedit_char_whitelist=0123456789.,-%',timeout=8).strip()
            normalized=re.sub(r'\s+','',raw)
            value=(normalized if re.fullmatch(r'\d{10}(?:-?\d{3})?',normalized) else None) if role=='tax_id' else number(raw,role)
            alternatives.append({'psm':psm,'lang':lang,'raw':raw,'value':value})
        except (old.pytesseract.TesseractError,RuntimeError):alternatives.append({'psm':psm,'lang':lang,'error':'OCR_ATTEMPT_FAILED'})
    votes=Counter(a['value'] for a in alternatives if a.get('value') is not None)
    ranked=votes.most_common()
    agreed=ranked[0][0] if ranked and ranked[0][1]>=2 and (len(ranked)==1 or ranked[0][1]>ranked[1][1]) else None
    return {'bbox':bbox,'alternatives':alternatives,'agreed':agreed,'coordinate_space':'document pixels'}


def refine_fields(doc,read):
    candidates=field_candidates(read)[0]
    # Recover an unreadable ID only inside a tax-label-anchored region. Do not
    # replace OCR §/I/O with digits in text or scan arbitrary 10-digit strings.
    for line in read.lines:
        if read.tag.startswith('footer'):break
        label=[i for i in line.ids if re.fullmatch(r'ms[t1il][:;.!]?',v4.plain(read.boxes[i].text))]
        if not label:continue
        box=read.boxes[label[0]].word;h=box[3]-box[1]
        following=[i for i in line.ids if read.boxes[i].word[0]>=box[2] and
                   re.fullmatch(r'[0-9OoIl!§.,-]{1,18}',read.boxes[i].text)]
        if not following:
            following=[i for i,b in enumerate(read.boxes) if b.word[0]>box[2] and b.word[0]<box[2]+14*h and
                       abs((b.word[1]+b.word[3])/2-(box[1]+box[3])/2)<1.4*h and
                       re.fullmatch(r'[0-9OoIl!§.,-]{1,18}',b.text)]
        if not following:continue
        parts=row_evidence(read.boxes,{'tax':following})['tax'];check=numeric_reread(doc,parts,'tax_id')
        if check and check['agreed'] is not None:
            buyer=any(re.search(r'nguoi mua|buyer|don vi mua|khach hang',v4.plain(l.text)) and l.y<line.y for l in read.lines)
            key='buyer_tax_code' if buyer else 'seller_tax_code'
            candidates[key]={'value':check['agreed'],'score':line_conf(line),'evidence':parts,'read':read.tag,'reread':check}
    for key,candidate in candidates.items():
        parts=candidate['evidence']
        if key in ('seller_tax_code','buyer_tax_code','total_amount'):
            numeric=[p for p in parts if re.fullmatch(r'\d[\d.,-]*\*?',p['text'].strip())]
            if not numeric:continue
            # Crop only the recognized value, never a neighbouring phone,
            # tax rate or whole labelled line containing several numbers.
            exact=[p for p in numeric if p['text'].strip('*')==str(candidate['value']) or
                   key=='total_amount' and number(p['text'].strip('*'),'amount')==candidate['value']]
            selected=exact or [max(numeric,key=lambda p:max(v[0] for v in p['polygon']))]
            recheck=numeric_reread(doc,selected,'tax_id' if key.endswith('tax_code') else 'amount')
            if recheck:
                candidate['reread']=recheck
                if recheck['agreed'] is not None:candidate['value']=recheck['agreed']
        elif key=='seller_name' and read.tag.startswith('header') and parts:
            xs=[p[0] for part in parts for p in part['polygon']];ys=[p[1] for part in parts for p in part['polygon']]
            h=max(ys)-min(ys);pad=max(2,h*.15)
            box=(max(0,min(xs)-pad),max(0,min(ys)-pad),min(doc.width,max(xs)+pad),min(doc.height,max(ys)+pad))
            try:
                rr=ocr_region(doc,box,read.tag+'/name-line','vie',7,line_height=True)
                text=' '.join(l.text for l in rr.lines).strip();p=v4.plain(text)
                similar=SequenceMatcher(None,v4.plain(str(candidate['value'])),p).ratio()
                confidence=sum((b.score or 0) for b in rr.boxes)/len(rr.boxes) if rr.boxes else 0
                candidate['name_reread']={'raw':text,'transform':rr.transform,
                                          'boxes':row_evidence(rr.boxes,{'all':range(len(rr.boxes))})['all']}
                if similar>=.8 and confidence>=.75 and not ADDRESS.match(p) and not TYPE.search(p):
                    candidate['value']=text
            except (old.pytesseract.TesseractError,RuntimeError):candidate['name_reread_failed']=True
    read.refined=candidates


def improve_cells(doc,rows,limit=30):
    findings=[];used=0
    for row in rows:
        inconsistent=all(row.get(k) is not None for k in ('quantity','unit_price','amount')) and abs(row['quantity']*row['unit_price']-row['amount'])>=2
        for role in ('quantity','unit_price','amount'):
            parts=row.get('evidence',{}).get(role,[])
            scores=[p['ocr_score'] for p in parts if p.get('ocr_score') is not None]
            if used>=limit or not parts or not (inconsistent or row.get(role) is None or scores and min(scores)<.7):continue
            reread=numeric_reread(doc,parts,role);used+=1
            if reread:
                if reread['agreed'] is not None and reread['agreed']<0 and not any(p['text'].lstrip().startswith(('-', '−')) for p in parts):
                    findings.append({'code':'CELL_RECOGNITION_UNCERTAIN','field':role,'evidence':reread,
                                     'reason':'sign flip without a minus in original OCR cell; source value retained'})
                    continue
                if reread['agreed'] is not None and reread['agreed']!=row.get(role):
                    findings.append({'code':'CELL_RECOGNITION_CHANGED','field':role,'before':row.get(role),'after':reread['agreed'],'evidence':reread})
                    row[role]=reread['agreed']
                elif reread['agreed'] is None:findings.append({'code':'CELL_RECOGNITION_UNCERTAIN','field':role,'evidence':reread})
    return findings


def retain_supported_v4_rows(rows,baseline):
    """Conservative evidence fallback, not a merge to satisfy an item total."""
    remaining=list(baseline);out=[];findings=[]
    for row in rows:
        match=[]
        for index,prior in enumerate(remaining):
            if prior.get('page',1)!=row.get('page',1) or NONPRODUCT.search(v4.semantic(prior['description'])):continue
            if any(prior.get(k) is None for k in ('quantity','unit_price','amount')):continue
            if abs(Decimal(str(prior['quantity']))*Decimal(str(prior['unit_price']))-Decimal(str(prior['amount'])))>=2:continue
            similarity=SequenceMatcher(None,v4.plain(prior['description']),v4.plain(row['description'])).ratio()
            money_agrees=prior.get('amount')==row.get('amount') or prior.get('unit_price')==row.get('unit_price')
            if similarity>=.65 and money_agrees:match.append((similarity,index,prior))
        if match:
            _,index,prior=max(match,key=lambda v:v[0]);remaining.pop(index)
            missing=any(row.get(k) is None for k in ('quantity','unit_price','amount'))
            inconsistent=not missing and abs(row['quantity']*row['unit_price']-row['amount'])>=2
            if missing or inconsistent:
                row={**prior,'selection':'v4-supported-row-fallback','coordinate_space':'v4 processed raster pixels'}
                findings.append({'code':'V4_SUPPORTED_ROW_RETAINED','reason':'complete source cells and consistent arithmetic; regional cells uncertain'})
        out.append(row)
    return out,findings


def read_page(image,page_number,baseline_type='unknown'):
    doc,transform=paper_view(image);evidence=[];failures=[]
    def scan(box,tag,lang='vie+eng',psm=6):
        try:
            read=ocr_region(doc,box,tag,lang,psm);evidence.append(read);return read
        except (old.pytesseract.TesseractError,RuntimeError) as exc:
            failures.append({'tag':tag,'error':type(exc).__name__});return None
    full=scan((0,0,doc.width,doc.height),'document')
    if full is None:return None,[],{'page':page_number,'transform':transform,'failures':failures}
    zone=zones(full)
    document_type=v4.classify_context(full.lines,full.size)
    header_box=(0,0,doc.width,min(doc.height,max(1,zone['header_end'])))
    footer_box=(0,max(0,min(doc.height-1,zone['footer_start']-zone['h'])),doc.width,doc.height)
    table_box=(0,max(0,zone['table_start']-zone['h']),doc.width,min(doc.height,max(zone['table_start']+1,zone['footer_start']+zone['h'])))
    headers=[scan(header_box,'header-vieeng','vie+eng',6),scan(header_box,'header-vie','vie',6),scan(header_box,'header-sparse','vie+eng',11)]
    footers=[scan(footer_box,'footer-vieeng','vie+eng',6),scan(footer_box,'footer-vie','vie',6)]
    tables=[full,scan(table_box,'table-block','vie+eng',6),scan(table_box,'table-sparse','vie+eng',11),scan(table_box,'table-vie','vie',6)]
    all_reads=[r for r in [full,*headers,*footers] if r is not None]
    for rd in all_reads:
        if rd.tag.startswith(('header','footer')):refine_fields(doc,rd)
    rejections=[]
    row_sets=[(r,table_rows(r,zone,rejections)) for r in tables if r is not None]
    if document_type=='unknown' and baseline_type=='unknown' and not zone['header_found']:
        row_sets=[]  # no unstructured product rows from an unclassified ticket/advertisement
    def quality(option):
        rd,rows=option;head=column_header(rd)
        return table_quality(rows)+(.15*len(head.centers) if head and rows else 0)
    picked,rows=max(row_sets,key=quality) if row_sets else (None,[])
    findings=improve_cells(doc,rows)
    serialized=[{'tag':r.tag,'size':r.size,'transform':r.transform,'groups':r.groups,
                 'boxes':row_evidence(r.boxes,{'all':range(len(r.boxes))})['all'],'raw_text':r.text,
                 'refined_candidates':r.refined} for r in evidence]
    return all_reads,rows,{'page':page_number,'source':'region-ocr','transform':transform,'zones':zone,
                         'classification_evidence':{'regional':document_type,'baseline':baseline_type},
                         'selected_table_read':picked.tag if picked else None,'findings':findings,
                         'rejected_table_candidates':rejections,
                         'item_count':len(rows),
                         'reads':serialized,'failures':failures}


def extract_v5(data,ext,max_pages=12):
    base_fields,base_items,base_layout=v4.extract_v4(data,ext,max_pages)
    if ext=='xml':return base_fields,base_items,{**base_layout,'source':'xml-unchanged'}
    fields=dict(base_fields);items=[];pages=[];findings=[];candidates={};field_evidence={}
    if ext=='pdf':
        import pymupdf
        with pymupdf.open(stream=data,filetype='pdf') as pdf:
            images=[]
            for n in range(min(len(pdf),max_pages)):
                if sum(c.isalnum() for c in pdf[n].get_text())>40:
                    # Retain the working text-layer path. No raster-only
                    # enhancement may overwrite searchable PDF content.
                    continue
                if pdf[n].rect.width*pdf[n].rect.height*4>30_000_000:raise ValueError('PDF raster exceeds cap')
                pix=pdf[n].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
                images.append((n+1,Image.open(BytesIO(pix.tobytes('png')))))
            for n,image in images:
                reads,rows,page=read_page(image,n,base_fields.get('document_type','unknown'));image.close();pages.append(page)
                if reads:
                    proposed,ev,warn,cs=choose_fields(fields,reads)
                    if n>1:
                        proposed={k:fields[k] if fields.get(k) is not None else v for k,v in proposed.items()}
                    fields=proposed;field_evidence.update(ev);findings+=warn;candidates[str(n)]=cs
                for row in rows:row.update(page=n,line_no=len(items)+1);items.append(row)
    else:
        with Image.open(BytesIO(data)) as image:reads,items,page=read_page(image,1,base_fields.get('document_type','unknown'))
        pages.append(page)
        if reads:fields,field_evidence,findings,candidates=choose_fields(fields,reads)
        for n,row in enumerate(items,1):row.update(page=1,line_no=n)
    enhanced_pages={p['page'] for p in pages if p.get('item_count',0)>0}
    for row in base_items:
        if row.get('page',1) not in enhanced_pages:items.append(row)
    if not items and base_items:
        items=[r for r in base_items if not NONPRODUCT.search(v4.semantic(r['description'])) and not v4.META.match(v4.semantic(r['description']))]
        findings.append({'code':'V4_TABLE_FALLBACK'})
    items,recovery=retain_supported_v4_rows(items,base_items);findings+=recovery
    for index,row in enumerate(items,1):row['line_no']=index
    findings+=findings_for_items(items)
    findings+=[f for p in pages for f in p.get('findings',[])]
    findings.append({'code':'EXPERIMENTAL_UNVERIFIED','reason':'Regional OCR is not tax verification or calibrated field confidence'})
    return fields,items,{'source':'region-context-v5','raw_text':'\n'.join(r['raw_text'] for p in pages for r in p.get('reads',[]) if r['tag']=='document'),
                         'pages':pages,'field_candidates':candidates,'field_evidence':field_evidence,
                         'v4_fallback':{'fields':base_fields,'items':base_items,'layout':base_layout},
                         'findings':findings,'requires_review':True,
                         'total_pages':base_layout.get('total_pages',len(pages)),
                         'truncated':base_layout.get('truncated',False),
                         'confidence_semantics':'Uncalibrated OCR word scores; no human approval'}
