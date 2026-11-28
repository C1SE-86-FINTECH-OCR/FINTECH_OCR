"""V4-first OFFLINE experiment. No labels, DB, network or vendor templates.

Routing uses missing/contradictory/low-confidence evidence, not the expected
answer. Prepared rasters and all V4 OCR alternatives are reused per document.
No early-exit is allowed to mark data verified; unresolved conflicts are kept.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import re

from . import pipeline_v4 as v4, pipeline_v5 as v5
from .layout import TextBox
from .profiling import capture_v4_rasters, stage
from .table_v3 import findings_for_items, row_evidence, number
from .table_v6 import parse_rows, arithmetic_checks


def saved_read(page, data=None, tag='cached-selected'):
    data=page['boxes'] if data is None else data
    boxes=[TextBox(b['text'],tuple(tuple(p) for p in b['polygon']),b.get('ocr_score')) for b in data]
    return v5.Read(tag,boxes,[l.ids for l in v4.lines_of(boxes)],tuple(page['size']),
                   {'coordinate_space':'V4 processed raster pixels','reused':True,'lang':'vie+eng'})


def bad_supplier(name):
    if not name:return True
    p=re.sub(r'[_\W]+',' ',v4.plain(str(name))).strip()
    return bool(v5.ADDRESS.match(p) or v5.TYPE.search(p) or v4.META.match(p) or
                re.search(r'ky dien tu|ky ten|ho ten|dien thoai|gio phuc vu|thu ngan',p) or
                re.search(r'(?:cong ty co|cong ty|chi nhanh)\s*$',p))


def confidence(parts):
    values=[p['ocr_score'] for p in parts if p.get('ocr_score') is not None]
    return sum(values)/len(values) if values else None


def routing(fields,items,layout):
    reasons={'header':[],'table':[],'footer':[]}
    raw=v4.plain(layout.get('raw_text',''))
    evidence=layout.get('field_evidence',{})
    if bad_supplier(fields.get('seller_name')):reasons['header'].append('supplier_missing_or_metadata')
    score=confidence(evidence.get('seller_name',[]))
    if score is not None and score<.85:reasons['header'].append('supplier_low_ocr_score')
    if re.search(r'\b(?:mst|ma so thue|tax code)\b',raw) and not fields.get('seller_tax_code'):
        reasons['header'].append('printed_tax_label_unresolved')
    elif fields.get('document_type')=='einvoice' and not fields.get('seller_tax_code'):
        reasons['header'].append('einvoice_tax_unresolved')
    if not fields.get('invoice_number') and re.search(r'\b(?:so hd|so hoa don|invoice no|h\s*:)',raw):
        reasons['header'].append('printed_invoice_label_unresolved')
    conflicts=[f.get('field') for f in layout.get('findings',[]) if 'CONFLICT' in f['code']]
    if any(k in conflicts for k in ('seller_name','seller_tax_code','invoice_number')):
        reasons['header'].append('header_alternatives_conflict')
    if not items and fields.get('document_type') in ('bill','einvoice'):
        reasons['table'].append('classified_invoice_without_rows')
    math=arithmetic_checks(fields,items)
    if math:reasons['table'].append('arithmetic_discrepancy')
    for row in items:
        ev=row.get('evidence',{})
        if any(confidence(parts) is not None and confidence(parts)<.8 for parts in ev.values()):
            reasons['table'].append('low_ocr_score');break
    if any(row.get('quantity') is None or row.get('unit_price') is None for row in items):
        # Missing does NOT mean invalid: it just permits a targeted check when
        # column labels were read. Bill amount-only rows stay legitimate nulls.
        if re.search(r'so luong|don gia|unit price|\bsl\b',raw):reasons['table'].append('printed_columns_unresolved')
    if any(v5.NONPRODUCT.search(v4.semantic(r['description'])) or
           r.get('quantity') is None and r.get('unit_price') is None and
           any(re.fullmatch(r'\d+',p['text']) for p in r.get('evidence',{}).get('amount',[])) for r in items):
        reasons['table'].append('possible_model_or_metadata_anchor')
    if fields.get('total_amount') is None:reasons['footer'].append('total_missing')
    elif not evidence.get('total_amount'):reasons['footer'].append('consensus_total_without_primary_region_evidence')
    score=confidence(evidence.get('total_amount',[]))
    if score is not None and score<.85:reasons['footer'].append('total_low_ocr_score')
    if 'total_amount' in conflicts:reasons['footer'].append('total_alternatives_conflict')
    if math and re.search(r'tong|total|thanh tien',raw):reasons['footer'].append('amount_scope_discrepancy')
    if any(a.get('amount') is not None for a in layout.get('financial_adjustments',[])):
        reasons['footer'].append('adjustments_need_final_total_scope')
    return {k:sorted(set(v)) for k,v in reasons.items()}


def serialized(read):
    return {'tag':read.tag,'size':read.size,'transform':read.transform,'groups':read.groups,
            'raw_text':read.text,'boxes':row_evidence(read.boxes,{'all':range(len(read.boxes))})['all'],
            'refined_candidates':read.refined}


def select_fields(base,reads,findings):
    fields,ev,warn,cs=v5.choose_fields(base,reads)
    findings+=warn
    # Label presence alone must not turn a single corrupted 10-digit reading
    # into a verified identifier. All alternatives remain visible for review.
    for key in ('seller_tax_code','buyer_tax_code'):
        choices=cs.get(key,[]);votes=Counter(str(c['value']) for c in choices)
        if fields.get(key)!=base.get(key) and (not choices or votes[str(fields.get(key))]<2):
            fields[key]=base.get(key);ev.pop(key,None)
            findings.append({'code':'TAX_VALUE_UNCONFIRMED','field':key})
    totals=[c for c in cs.get('total_amount',[]) if c.get('payable_region_confirmed')]
    if totals:
        values={Decimal(str(c['value'])) for c in totals}
        if len(values)==1:
            best=max(totals,key=lambda c:confidence(c['evidence']) or 0)
            fields['total_amount']=best['value'];ev['total_amount']=best
            if best.get('reread_conflict'):
                findings.append({'code':'PAYABLE_READBACK_CONFLICT','value':best['value'],
                                 'reason':'regional labelled amount and isolated segmentation agree; other OCR attempts disagree'})
        else:
            findings.append({'code':'PAYABLE_REGION_CONFLICT','values':sorted(map(str,values))})
    choices=[c for c in cs.get('seller_name',[]) if not bad_supplier(c['value'])]
    regional=[c for c in choices if c['read'].startswith('header')]
    if regional:
        # Prefer actual word evidence from the focused region over a majority
        # of correlated full-page passes. A language model spelling is not used.
        best=max(regional,key=lambda c:(confidence(c['evidence']) or 0,c['score']))
        if (confidence(best['evidence']) or 0)>=.8 and best['score']>=1.15:
            fields['seller_name']=best['value'];ev['seller_name']=best
    if bad_supplier(fields.get('seller_name')):
        if choices:
            best=max(choices,key=lambda c:c['score'])
            fields['seller_name']=best['value'];ev['seller_name']=best
        else:
            fields['seller_name']=base.get('seller_name')
            findings.append({'code':'SUPPLIER_UNRESOLVED','reason':'no reliable name evidence; baseline retained for review'})
    return fields,ev,cs


def row_quality(rows):
    if not rows:return -1
    return v5.table_quality(rows)+.12*sum(r.get('quantity') is not None and r.get('unit_price') is not None for r in rows)/len(rows)


def financial_frontier(reads,zone):
    """Earliest printed summary across existing passes, not just chosen OCR.

    In staggered/large-font footers, the payable label and its digits can have
    different baselines. A later commission line must not define the crop.
    """
    positions=[]
    for read in reads:
        for line in read.lines:
            p=v4.plain(line.text);compact=re.sub(r'[^a-z]','',p)
            labelled=bool(re.match(r'^(?:tong(?:tien|cong)?|tamtinh|thanhtien|subtotal|grandtotal|giamgia|phuthu|tienthue)',compact))
            if line.y>zone['table_start']+2*zone['h'] and labelled:
                if v4.money_tokens(line) or any(abs(other.y-line.y)<1.7*zone['h'] and v4.money_tokens(other) for other in read.lines):
                    positions.append(line.y-zone['h'])
    return min([zone['footer_start'],*positions])


def confirm_payable(raster,read,baseline,cache):
    """A named final-total cell plus pixel rereads, not arithmetic inference."""
    cs=read.refined if read.refined is not None else v5.field_candidates(read)[0]
    for line in read.lines:
        p=v4.plain(line.text)
        if not re.search(r'\b(?:thanh\s*tien|tong\s*(?:cong\s*)?(?:phai\s*)?thanh\s*toan|grand\s*total|amount\s*due)\b',p):continue
        if re.search(r'khach|cash|change|now|commission',p):continue
        values=[v for v in v4.money_tokens(line) if not v.get('percent')]
        if not values:continue
        val=max(values,key=lambda v:v['x'])
        parts=row_evidence(read.boxes,{'value':val['ids']})['value']
        if not val['formatted'] and len(re.sub(r'\D','',val['text']))<3:continue
        if (confidence(parts) or 0)<.8:continue
        if val['value']==baseline:continue
        key=tuple(tuple(tuple(x) for x in p['polygon']) for p in parts)
        if key not in cache:cache[key]=v5.numeric_reread(raster,parts,'amount')
        check=cache[key]
        if check:
            # Isolated-word OCR can append punctuation to a complete grouped
            # integer (e.g. 12,000,). Trim only that grammar-proven separator;
            # never substitute a digit or normalize a malformed numeric group.
            for attempt in check['alternatives']:
                raw=attempt.get('raw','').strip()
                if attempt.get('value') is None and re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+[.,]',raw):
                    attempt['trailing_punctuation_value']=number(raw[:-1],'amount')
            support=[a for a in check['alternatives'] if a.get('value',a.get('trailing_punctuation_value'))==val['value'] or
                     a.get('trailing_punctuation_value')==val['value']]
            if cs.get('total_amount') is not None:cs['total_amount']['payable_reread']=check
        else:support=[]
        # The labelled regional PSM6 read plus an isolated-cell segmentation
        # are two actual observations. Correlated PSM7 language votes do not
        # overrule that semantic source; all disagreement remains reviewable.
        confirmed=check and (check['agreed']==val['value'] or
                            (confidence(parts) or 0)>=.9 and bool(support))
        if confirmed and val['value']>=0:
            cs['total_amount']={'value':val['value'],'score':confidence(parts),'read':read.tag,
                'evidence':parts,'payable_region_confirmed':True,'reread':check,
                'reread_conflict':check['agreed'] not in (None,val['value']),
                'label_evidence':row_evidence(read.boxes,{'label':line.ids})['label']}
    read.refined=cs


def enhance_page(raster,page,fields,baseline_items,route):
    selected=saved_read(page);reads=[];tables=[];findings=[];rejected=[];failures=[]
    cached=[selected]
    for index,alt in enumerate(page.get('preprocessing',{}).get('alternatives',[])):
        cached.append(saved_read(page,alt['boxes'],f'cached-{index}'))
    reads+=cached
    with stage('hybrid.layout_reuse'):
        zone=v5.zones(selected)
        zone['footer_start']=max(zone['table_start'],financial_frontier(cached,zone))
        for read in cached:
            rows,reject=parse_rows(read,zone);tables.append((read,rows));rejected+=reject
    def scan(bbox,tag,lang='vie+eng',psm=6):
        try:
            read=v5.ocr_region(raster,bbox,tag,lang,psm);reads.append(read);return read
        except (v5.old.pytesseract.TesseractError,RuntimeError) as exc:
            failures.append({'tag':tag,'error':type(exc).__name__});return None
    w,h=raster.size
    if route['header']:
        box=(0,0,w,min(h,max(1,zone['header_end'])))
        focused=scan(box,'header-vie','vie')
        if focused:
            # Refine only on printed tax uncertainty. Supplier-only checks do
            # not trigger the V5 suite of per-field numeric/name OCR passes.
            if any('tax' in r for r in route['header']):v5.refine_fields(raster,focused)
            cs=v5.field_candidates(focused)[0]
            if not cs.get('seller_name') or (confidence(cs['seller_name']['evidence']) or 0)<.8:
                scan(box,'header-vieeng','vie+eng')
    if route['footer']:
        box=(0,max(0,min(h-1,zone['footer_start']-zone['h'])),w,h)
        first=scan(box,'footer-vie','vie')
        if first:
            # Obtain a second recognition only when the new total differs or
            # remains missing; a matching clear value does not need re-OCR.
            cs=v5.field_candidates(first)[0];value=cs.get('total_amount',{}).get('value')
            if value is None or value!=fields.get('total_amount'):
                other=scan(box,'footer-vieeng','vie+eng')
                if other:
                    a=v5.field_candidates(other)[0].get('total_amount',{}).get('value')
                    if a is None or a!=value:v5.refine_fields(raster,first)
        checks={}
        for read in [r for r in reads if r.tag.startswith('footer')]:
            confirm_payable(raster,read,fields.get('total_amount'),checks)
    if route['table']:
        box=(0,max(0,zone['table_start']-zone['h']),w,min(h,max(zone['table_start']+1,zone['footer_start']+zone['h'])))
        first=scan(box,'table-block')
        if first:
            rows,reject=parse_rows(first,zone);tables.append((first,rows));rejected+=reject
            if not rows or arithmetic_checks(fields,rows) or any(r.get('quantity') is None for r in rows):
                alternative=scan(box,'table-vie','vie')
                if alternative:
                    rows,reject=parse_rows(alternative,zone);tables.append((alternative,rows));rejected+=reject
    recognized_type=fields.get('document_type','unknown')
    if recognized_type=='unknown' and not zone['header_found']:
        tables=[]
    picked,rows=max(tables,key=lambda t:row_quality(t[1])) if tables else (None,[])
    if rows and route['table']:findings+=v5.improve_cells(raster,rows)
    for r in rows:r['page']=page['page']
    if not rows:rows=list(baseline_items)
    rows,recovery=v5.retain_supported_v4_rows(rows,baseline_items);findings+=recovery
    field_reads=[r for r in reads if not r.tag.startswith('table')]
    proposed,ev,cs=select_fields(fields,field_reads,findings)
    return proposed,rows,{'page':page['page'],'route':route,'zones':zone,'source':'V4 raster reused',
        'coordinate_space':'V4 processed raster pixels','selected_table_read':picked.tag if picked else None,
        'reads':[serialized(r) for r in reads],'field_candidates':cs,'field_evidence':ev,
        'rejected_table_candidates':rejected,'findings':findings,'failures':failures}


def extract_hybrid(data,ext,max_pages=12):
    with capture_v4_rasters() as rasters:
        try:
            with stage('hybrid.baseline'):
                fields,items,layout=v4.extract_v4(data,ext,max_pages)
            baseline=deepcopy({'fields':fields,'items':items,'layout':layout})
            route=routing(fields,items,layout)
            if ext=='xml' or not any(route.values()):
                return fields,items,{**layout,'source':'hybrid-v6-v4-fast-path','routing':route,
                    'v4_fallback':baseline,'enhanced_pages':[],'requires_review':True,
                    'findings':[*layout.get('findings',[]),{'code':'EXPERIMENTAL_UNVERIFIED'}]}
            output=[];pages=[];cursor=0
            for page in layout.get('pages',[]):
                old=[r for r in items if r.get('page',1)==page['page']]
                if page['source']!='ocr':output+=old;continue
                raster=rasters[cursor];cursor+=1
                with stage('hybrid.conditional_enhancement'):
                    proposed,rows,diagnostics=enhance_page(raster,page,fields,old,route)
                if page['page']>1:proposed={k:fields[k] if fields.get(k) is not None else v for k,v in proposed.items()}
                fields=proposed;output+=rows;pages.append(diagnostics)
            for n,row in enumerate(output,1):row['line_no']=n
            findings=[*layout.get('findings',[]),*findings_for_items(output),*arithmetic_checks(fields,output)]
            findings.extend(f for p in pages for f in p['findings'])
            findings.append({'code':'EXPERIMENTAL_UNVERIFIED','reason':'routing/word confidence is not verification'})
            return fields,output,{'source':'hybrid-v6','routing':route,'enhanced_pages':pages,
                'pages':[{**p,'table_found':any(r.get('page',1)==p['page'] for r in output)} for p in layout.get('pages',[])],
                'v4_fallback':baseline,'raw_text':layout.get('raw_text',''),'findings':findings,
                'total_pages':layout.get('total_pages'),'truncated':layout.get('truncated',False),
                'requires_review':True,'confidence_semantics':'uncalibrated word scores; no ground truth access'}
        finally:
            for image in rasters:image.close()
