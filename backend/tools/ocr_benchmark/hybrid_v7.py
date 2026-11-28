"""Opt-in V7: frozen V6 plus geometric ownership and targeted recognition.

No dataset/DB/network access. Original evidence and V6 output remain available.
All coordinates refer to the named raster; no confidence is a verification.
"""
from copy import deepcopy
from decimal import Decimal
from statistics import median
from time import perf_counter
import re

from PIL import ImageOps, ImageFilter
from . import hybrid_v6 as v6, pipeline_v4 as v4, pipeline_v5 as v5
from .layout import TextBox, rectangle
from .profiling import capture_v4_rasters
from .table_v3 import findings_for_items
from .table_v6 import arithmetic_checks, header_for
from .table_v7 import parse_rows, reconcile
from .fields_v7 import labelled_context


def restored(data):
    return v5.Read(data['tag'],[TextBox(b['text'],tuple(map(tuple,b['polygon'])),b.get('ocr_score')) for b in data['boxes']],
                   data['groups'],tuple(data['size']),data.get('transform',{}))


def region(raster,bbox,tag,psm=6,lang='vie+eng'):
    """Bounded local contrast + sharpening. Map actual Tesseract boxes back."""
    x0,y0,x1,y1=bbox
    image=ImageOps.autocontrast(raster.crop(bbox).convert('L'),cutoff=.25)
    scale=min(2.,(8_000_000/max(1,image.width*image.height))**.5)
    image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))))
    image=image.filter(ImageFilter.UnsharpMask(radius=1.2,percent=120,threshold=4))
    try:
        data=v5.old.pytesseract.image_to_data(image,lang=lang,config=f'--psm {psm} -c preserve_interword_spaces=1',
                                            output_type=v5.old.pytesseract.Output.DICT,timeout=25)
    finally:image.close()
    boxes=[];groups={}
    for i,text in enumerate(data['text']):
        if not text.strip():continue
        x,y,w,h=(data[k][i]/scale for k in ('left','top','width','height'));index=len(boxes)
        boxes.append(rectangle(text.strip(),x0+x,y0+y,x0+x+w,y0+y+h,max(0,float(data['conf'][i]))/100))
        key=tuple(data[k][i] for k in ('block_num','par_num','line_num'));groups.setdefault(key,[]).append(index)
    return v5.Read(tag,boxes,sorted(groups.values(),key=lambda ids:median(boxes[i].word[1] for i in ids)),raster.size,
                   {'bbox':bbox,'scale':scale,'coordinate_space':'V4 processed raster pixels','sharpen':True,'lang':lang,'psm':psm})


def reread_uncertain_cells(raster,rows,warnings,budget=9):
    findings=[];used=0
    for row in rows:
        for role in ('quantity','unit_price','amount'):
            parts=row.get('evidence',{}).get(role,[])
            conflict=any(f.get('field')==role and abs(f.get('y',-999)-row['_y'])<20 for f in warnings)
            if not parts or used>=budget or not (conflict or row.get(role) is None):continue
            used+=1;check=v5.numeric_reread(raster,parts,role)
            if not check:continue
            before=row.get(role);agreed=check['agreed']
            if agreed is not None and agreed>=0:
                row[role]=agreed
            findings.append({'code':'V7_CELL_READBACK','field':role,'before':before,'after':row.get(role),
                             'evidence':check,'reason':'pixel observations, not arithmetic repair'})
            if len({str(a['value']) for a in check['alternatives'] if a.get('value') is not None})>1:
                findings.append({'code':'V7_CELL_READBACK_CONFLICT','field':role,'y':row['_y'],
                                 'reason':'OCR attempts disagree, including when a majority exists'})
        if row.get('unit') and re.search(r'[0-9]|got|cat',v4.plain(row['unit'])):
            findings.append({'code':'V7_UNIT_UNCERTAIN','value':row['unit'],'line_y':row['_y'],
                             'reason':'literal OCR unit retained; no dictionary substitution'})
    return findings


def scope_findings(fields,items):
    findings=[]
    for n,row in enumerate(items,1):
        for key in ('quantity','unit_price','amount'):
            if row.get(key) is None:findings.append({'code':'V7_CELL_MISSING','line':n,'field':key,
                                                    'reason':'not observed confidently; no arithmetic filling'})
    if items and fields.get('subtotal') is None and fields.get('total_amount') is not None and all(r.get('amount') is not None for r in items):
        summed=sum(Decimal(str(r['amount'])) for r in items)
        if abs(summed-Decimal(str(fields['total_amount'])))>Decimal('2'):
            findings.append({'code':'V7_ITEM_PAYABLE_SCOPE_DIFFERENCE','items_sum':summed,'payable':fields['total_amount'],
                'reason':'tax/discount scope or OCR may differ; not a replacement for ITEM-SUM validation'})
    return findings


def protect_supported_descriptions(rows,baseline):
    """Keep a supported model/package literal when a new read contradicts it.

    This is not a spelling dictionary: both alternatives remain in evidence.
    Promotional/metadata descriptions are never protected as product names.
    """
    from difflib import SequenceMatcher
    findings=[]
    for row in rows:
        for old in baseline:
            if row.get('amount')!=old.get('amount') or row.get('unit_price')!=old.get('unit_price'):continue
            before=old.get('description','');after=row['description']
            if v5.NONPRODUCT.search(v4.semantic(before)) or re.search(r'[-~−]\s*\d[\d.,]*',before):continue
            if SequenceMatcher(None,v4.plain(before),v4.plain(after)).ratio()<.8:continue
            literals=lambda s:re.findall(r'\b\d+[a-z]+\b',v4.plain(s))
            if literals(before)!=literals(after):
                row['description']=before
                row['evidence']['description']=old.get('evidence',{}).get('description',[])
                findings.append({'code':'V7_DESCRIPTION_LITERAL_CONFLICT','retained':before,'alternative':after})
            break
    return findings


def context_fields(fields, reads):
    result=dict(fields);findings=[];evidence={}
    # V6's contextual seller/buyer/tax extraction remains the baseline.
    # New direct invoice/date readings compete only when repeated, not guessed.
    for key in ('invoice_date','invoice_number'):
        candidates=[]
        for read in reads:
            for line in read.lines:
                p=v4.plain(line.text)
                if key=='invoice_date':
                    value=v4.date_value(line.text) if re.search(r'\b(?:ngay|date)\b',p) else None
                else:
                    m=re.search(r'\b(?:so\s*(?:hoa don|hd)?|invoice\s*(?:no|number)|h)\s*[:.]\s*([a-z0-9][a-z0-9/-]{3,31})\b',p)
                    value=line.text[m.start(1):m.end(1)] if m and any(c.isdigit() for c in m[1]) and not v4.date_value(m[1]) else None
                if value is not None:candidates.append((str(value),value,read.tag,v5.line_conf(line),line.text))
        if not candidates:continue
        groups={}
        for c in candidates:groups.setdefault(c[0],[]).append(c)
        ranked=sorted(groups.values(),key=lambda g:(len({c[2] for c in g}),max(c[3] for c in g)),reverse=True)
        winner=max(ranked[0],key=lambda c:c[3])
        # Correlated full-page votes do not override a clear labelled reread.
        focused=[c for c in candidates if c[2].startswith('v7-label') and c[3]>=.85]
        if focused and len({c[0] for c in focused})==1:winner=max(focused,key=lambda c:c[3])
        if len(groups)>1:findings.append({'code':'V7_FIELD_CONFLICT','field':key,'values':list(groups),'selected':winner[0]})
        if len({c[2] for c in groups[winner[0]]})>=2 or winner in focused:
            result[key]=winner[1];evidence[key]={'value':winner[0],'read':winner[2],'raw_line':winner[4]}
    return result,findings,evidence


def extract_hybrid(data,ext,max_pages=12):
    start=perf_counter()
    with capture_v4_rasters() as rasters:
        try:
            fields,items,layout=v6.extract_hybrid(data,ext,max_pages)
            baseline=deepcopy({'fields':fields,'items':items,'layout':layout})
            if ext=='xml':return fields,items,{**layout,'source':'hybrid-v7-xml-existing'}
            findings=[];output=[];diagnostics=[];cursor=0;all_reads=[]
            inherited=None
            for page in layout.get('pages',[]):
                page_no=page['page'];old=[r for r in items if r.get('page',1)==page_no]
                reads=[v6.saved_read(page)]
                reads.extend(v6.saved_read(page,a['boxes'],f'v7-cached-{n}') for n,a in enumerate(page.get('preprocessing',{}).get('alternatives',[])))
                enhanced=next((p for p in layout.get('enhanced_pages',[]) if p['page']==page_no),{})
                reads.extend(restored(r) for r in enhanced.get('reads',[]) if not r['tag'].startswith('cached'))
                zone=v5.zones(reads[0]);zone['footer_start']=max(zone['table_start'],v6.financial_frontier(reads,zone))
                headers=[header_for(r) for r in reads];header=next((h for h in headers if h and 'unit' in h.centers),None) or next((h for h in headers if h),None)
                if header:inherited=header
                # A repeated header is preferred. Carry only geometry to a
                # headerless continuation, never previous-page text or rows.
                if not header and inherited and page_no>1:
                    from .table_v3 import Header
                    header=Header(0,inherited.centers,());zone['table_start']=0
                tables=[];reject=[];failures=[];timings={}
                def collect():
                    tables.clear();reject.clear()
                    for read in reads:
                        if read.tag.startswith(('header','footer','v7-label')):continue
                        rows,r=parse_rows(read,zone,header);tables.append((read,rows));reject.extend(r)
                collect();rows,warnings=reconcile(tables,zone['h']);findings.extend(warnings)
                raster=None
                if page['source']=='ocr':raster=rasters[cursor];cursor+=1
                if raster is not None:
                    if header and (warnings or len(rows)!=len(old) or any(r.get('quantity') is None for r in rows)):
                        tick=perf_counter()
                        try:
                            bbox=(0,max(0,header.bottom-zone['h']),raster.width,min(raster.height,max(header.bottom+1,zone['footer_start'])))
                            reads.append(region(raster,bbox,'v7-table'));collect();rows,warnings=reconcile(tables,zone['h'])
                            findings.extend(warnings)
                        except (RuntimeError,v5.old.pytesseract.TesseractError) as exc:failures.append({'region':'table','error':type(exc).__name__})
                        timings['table_s']=perf_counter()-tick
                    tick=perf_counter()
                    findings.extend(reread_uncertain_cells(raster,rows,warnings))
                    timings['cells_s']=perf_counter()-tick
                    # Re-read only printed date/number lines in the header.
                    tick=perf_counter();targets=[]
                    for line in reads[0].lines:
                        if line.y>=zone['header_end']:continue
                        if not re.search(r'\b(?:ngay|date|so\s*:)\b|\bso\s*:',v4.plain(line.text)):continue
                        if v5.line_conf(line)>.95:continue
                        bbox=(0,max(0,min(raster.height-1,line.y-zone['h'])),raster.width,min(raster.height,line.y+zone['h']))
                        if any(abs(line.y-y)<2*zone['h'] for y in targets):continue
                        targets.append(line.y)
                        try:reads.append(region(raster,bbox,f'v7-label-{len(targets)}',7))
                        except (RuntimeError,v5.old.pytesseract.TesseractError) as exc:failures.append({'region':'label','error':type(exc).__name__})
                        if len(targets)>=3:break
                    timings['labels_s']=perf_counter()-tick
                    if page_no==1 and fields.get('seller_name'):
                        from difflib import SequenceMatcher
                        candidates=[l for l in reads[0].lines if l.y<zone['header_end'] and
                                    SequenceMatcher(None,v4.plain(l.text),v4.plain(fields['seller_name'])).ratio()>.7]
                        if candidates:
                            line=max(candidates,key=lambda l:SequenceMatcher(None,v4.plain(l.text),v4.plain(fields['seller_name'])).ratio())
                            try:
                                parts=[reads[0].boxes[i] for i in line.ids]
                                bbox=(max(0,min(b.word[0] for b in parts)-zone['h']/2),max(0,line.y-zone['h']),
                                      min(raster.width,max(b.word[2] for b in parts)+zone['h']/2),min(raster.height,line.y+zone['h']))
                                focused=region(raster,bbox,'v7-supplier',7,'vie');reads.append(focused)
                                name=' '.join(l.text for l in focused.lines).strip(' |')
                                if focused.boxes and v5.line_conf(v4.Line(list(range(len(focused.boxes))),focused.boxes))>=.85 and not v6.bad_supplier(name) and SequenceMatcher(None,v4.plain(name),v4.plain(fields['seller_name'])).ratio()>=.85:
                                    if name!=fields['seller_name']:findings.append({'code':'V7_SUPPLIER_READBACK','before':fields['seller_name'],'after':name})
                                    fields['seller_name']=name
                            except (RuntimeError,v5.old.pytesseract.TesseractError) as exc:failures.append({'region':'supplier','error':type(exc).__name__})
                # Retain V6 rows if there is no geometric selling-row evidence.
                if not rows:rows=deepcopy(old)
                findings.extend(protect_supported_descriptions(rows,old))
                for row in rows:
                    row.pop('_y',None);row.pop('_read',None);row['page']=page_no
                output.extend(rows);all_reads.extend(reads)
                diagnostics.append({'page':page_no,'zones':zone,'rejected':reject,'failures':failures,
                                    'timings':timings,'reads':[v6.serialized(r) for r in reads]})
            fields,field_warnings,field_evidence=context_fields(fields,all_reads)
            findings.extend(field_warnings)
            fields,context_evidence,context_warnings=labelled_context(fields,all_reads)
            findings.extend(context_warnings)
            for n,row in enumerate(output,1):row['line_no']=n
            findings.extend(findings_for_items(output));findings.extend(arithmetic_checks(fields,output))
            findings.extend(scope_findings(fields,output))
            if fields.get('subtotal') is None:findings.append({'code':'SUBTOTAL_NOT_OBSERVED','reason':'no inferred subtotal; ITEM-SUM business rule unchanged'})
            if not output:findings.append({'code':'TABLE_UNRESOLVED'})
            uncertain_fields=[]
            for key in ('seller_name','invoice_number','invoice_date','total_amount'):
                if fields.get(key) is None:
                    uncertain_fields.append({'field':key,'reason':'not_observed_or_unresolved'})
            for warning in findings:
                if 'CONFLICT' in warning['code'] or 'UNCERTAIN' in warning['code']:
                    uncertain_fields.append({'field':warning.get('field','items'),'reason':warning['code']})
            findings.append({'code':'EXPERIMENTAL_UNVERIFIED','reason':'V7 observations need human review; confidence is uncalibrated'})
            return fields,output,{**layout,'source':'hybrid-v7','v6_fallback':baseline,'v7_pages':diagnostics,
                                  'v7_field_evidence':field_evidence,'findings':[*layout.get('findings',[]),*findings],
                                  'v7_labelled_context':context_evidence,
                                  'uncertain_fields':uncertain_fields,
                                  'requires_review':True,'elapsed_s':perf_counter()-start}
        finally:
            for image in rasters:image.close()
