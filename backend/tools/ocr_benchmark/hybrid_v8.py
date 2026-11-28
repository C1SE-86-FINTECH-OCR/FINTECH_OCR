"""V8 experiment. Frozen V6/V7/current remain unmodified and reviewable.

No DB/network/dataset/label access. Arithmetic ranks OCR observations only.
"""
from copy import deepcopy
from decimal import Decimal
from difflib import SequenceMatcher
from io import BytesIO
from statistics import median
from time import perf_counter
import re
from PIL import Image
from . import hybrid_v7 as v7, hybrid_v6 as v6, pipeline_v4 as v4, pipeline_v5 as v5
from . import table_v8 as table
from .fields_v8 import labelled_fields
from .preprocess_v8 import views
from .profiling import capture_v4_rasters
from .table_v6 import arithmetic_checks
from .table_v3 import Header,findings_for_items

def read_fingerprint(read):
    return tuple((b.text,tuple(b.polygon)) for b in read.boxes)

def attach_readbacks(rows,layout,height):
    for finding in layout.get('findings',[]):
        if finding['code']!='V7_CELL_READBACK':continue
        check=finding.get('evidence',{});bbox=check.get('bbox')
        if not bbox:continue
        y=(bbox[1]+bbox[3])/2
        row=min(rows,key=lambda r:abs(r['_y']-y)) if rows else None
        if row is None or abs(row['_y']-y)>height:continue
        key=finding['field'];parts=row.get('evidence',{}).get(key,[])
        for alt in check.get('alternatives',[]):
            table.add_observation(row,key,alt.get('value'),parts,f"v7-cell/{alt.get('lang')}/psm{alt.get('psm')}")

def row_quality(rows):
    return (len(rows),sum(all(r.get(k) is not None for k in ('quantity','unit_price','amount')) and
                         abs(Decimal(str(r['quantity']))*Decimal(str(r['unit_price']))-Decimal(str(r['amount'])))<=2 for r in rows))

def extract_hybrid(data,ext,max_pages=12):
    start=perf_counter()
    with capture_v4_rasters() as rasters:
        try:
            fields,items,layout=v7.extract_hybrid(data,ext,max_pages)
            baseline=deepcopy({'fields':fields,'items':items,'layout':layout})
            if ext=='xml':return fields,items,{**layout,'source':'hybrid-v8-xml-existing'}
            pages=[];output=[];findings=[];all_reads=[];carried=None;cursor=0
            for page in layout.get('pages',[]):
                n=page['page'];old=[r for r in items if r.get('page',1)==n]
                diag=next((p for p in layout.get('v7_pages',[]) if p['page']==n),{})
                reads=[v7.restored(r) for r in diag.get('reads',[])] or [v6.saved_read(page)]
                seen=set();unique=[]
                for rd in reads:
                    fp=read_fingerprint(rd)
                    if fp in seen:continue
                    seen.add(fp);unique.append(rd)
                    rd.transform={**rd.transform,'trusted_text_layer':page['source']=='pdf-text'}
                reads=unique
                headers=[table.header_for(r) for r in reads];header=max((h for h in headers if h),key=lambda h:len(h.centers),default=None)
                zone=v5.zones(reads[0]);zone['footer_start']=max(zone['table_start'],v6.financial_frontier(reads,zone))
                if header:carried=header
                elif carried and n>1:header=Header(0,carried.centers,());zone['table_start']=0
                tables=[];reject=[]
                for rd in reads:
                    if rd.tag.startswith(('header','footer','v7-label','v7-supplier')):continue
                    rows,notes=table.parse_rows(rd,zone,header);tables.append((rd,rows));reject+=notes
                rows,warn=table.reconcile(tables,zone['h']);findings+=warn
                if layout.get('total_pages')==1:attach_readbacks(rows,layout,zone['h'])
                for row in rows:findings+=table.select_cells(row)
                alternative_reads=[];errors=[]
                raster=rasters[cursor] if page['source']=='ocr' else None
                if raster is not None:cursor+=1
                # New preprocessing uses original image pixels, not a warped
                # crop in the previous coordinate space. Views stay separate.
                if ext in ('jpg','jpeg','png') and n==1 and (warn or arithmetic_checks(fields,rows) or any(r.get('quantity') is None or not table.unit(r.get('unit')) for r in rows)):
                    with Image.open(BytesIO(data)) as source:
                        for view,transform in views(source):
                            try:
                                rd=v5.ocr_region(view,(0,0,view.width,view.height),'v8-'+transform['variant'],'vie+eng',6)
                                rd.transform.update({'view':transform,'coordinate_space':'V8 paper view pixels'})
                                alternative_reads.append(rd);all_reads.append(rd)
                                z=v5.zones(rd);z['footer_start']=max(z['table_start'],v6.financial_frontier([rd],z))
                                proposed,rejects=table.parse_rows(rd,z);reject+=rejects
                                # Merge only equal-sized, order-preserving,
                                # semantically corresponding product rows.
                                if len(proposed)==len(rows) and all(SequenceMatcher(None,v4.plain(a['description']),v4.plain(b['description'])).ratio()>=.6 for a,b in zip(rows,proposed)):
                                    for target,candidate in zip(rows,proposed):
                                        for key,cs in candidate.get('_cell_candidates',{}).items():
                                            target.setdefault('_cell_candidates',{}).setdefault(key,[]).extend(cs)
                                        findings+=table.select_cells(target)
                                elif not rows and proposed:rows=proposed
                            except (RuntimeError,v5.old.pytesseract.TesseractError) as exc:errors.append(type(exc).__name__)
                            finally:view.close()
                if not rows:rows=deepcopy(old)
                findings+=v7.protect_supported_descriptions(rows,old)
                for row in rows:
                    for prior in old:
                        if row.get('amount')!=prior.get('amount') or v4.plain(row['description'])!=v4.plain(prior['description']):continue
                        import unicodedata
                        marks=lambda s:sum(bool(unicodedata.combining(c)) for c in unicodedata.normalize('NFD',s))
                        if marks(row['description'])<marks(prior['description']):
                            findings.append({'code':'V8_DESCRIPTION_DIACRITICS_UNCERTAIN','alternative':row['description'],'retained':prior['description']})
                            row['description']=prior['description'];row['evidence']['description']=prior.get('evidence',{}).get('description',[])
                        break
                for row in rows:
                    row['page']=n
                    row['cell_observations']=row.pop('_cell_candidates',{})
                    row.pop('_y',None);row.pop('_read',None)
                output+=rows;all_reads+=reads
                pages.append({'page':n,'source':page['source'],'zones':zone,'rejected':reject,'errors':errors,
                              'alternative_reads':[v6.serialized(r) for r in alternative_reads]})
            fields,field_evidence,field_warnings=labelled_fields(fields,all_reads);findings+=field_warnings
            for n,row in enumerate(output,1):row['line_no']=n
            fields['confidence_score']=None
            findings+=arithmetic_checks(fields,output)+v7.scope_findings(fields,output)+findings_for_items(output)
            if layout.get('truncated'):findings.append({'code':'DOCUMENT_TRUNCATED','reason':'page limit reached'})
            findings.append({'code':'EXPERIMENTAL_UNVERIFIED','reason':'V8 is not calibrated or independently accepted'})
            return fields,output,{**layout,'source':'hybrid-v8','v7_baseline':baseline,'v8_pages':pages,'v8_field_evidence':field_evidence,
                                  'findings':findings,'requires_review':True,'elapsed_s':perf_counter()-start}
        finally:
            for raster in rasters:raster.close()
