"""Advisory verification; reuses financial rules and never changes source values."""
from datetime import datetime, timezone
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from io import BytesIO
from math import isfinite
from pathlib import Path
from time import monotonic
from functools import lru_cache
import json
from sqlalchemy import select
from .models import Invoice, InvoiceFile, ChatMessage, Conversation
from .invoice_financials import arithmetic_rules

def image_fingerprint(data, ext):
    from PIL import Image, ImageOps
    if ext=='pdf':
        import pymupdf
        with pymupdf.open(stream=data,filetype='pdf') as doc:
            if not len(doc): return None
            if doc[0].rect.width*doc[0].rect.height*.25>30_000_000:return None
            pix=doc[0].get_pixmap(matrix=pymupdf.Matrix(.5,.5),alpha=False)
            image=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
    elif ext in ('jpg','jpeg','png'):
        image=Image.open(BytesIO(data))
    else: return None
    if image.width*image.height>30_000_000: return None
    image=ImageOps.exif_transpose(image).convert('L').resize((9,8))
    pixels=list(image.getdata());bits=[pixels[y*9+x]>pixels[y*9+x+1] for y in range(8) for x in range(8)]
    if not any(bits) or all(bits): return None
    return sum(int(bit)<<i for i,bit in enumerate(bits))

@lru_cache(maxsize=256)
def stored_fingerprint(path, checksum, ext):
    return image_fingerprint(Path(path).read_bytes(),ext)

def duplicate_report(db, invoice, role, metadata):
    from .core import storage_dir
    query=select(Invoice).join(InvoiceFile).where(Invoice.id!=invoice.id).order_by(Invoice.id.desc())
    if role=='employee':query=query.where(InvoiceFile.uploaded_by==invoice.source_file.uploaded_by)
    candidates=db.scalars(query.limit(201)).all();matches=[];started=monotonic();visual_skipped=False
    fingerprint=metadata.get('image_fingerprint')
    def clean(value):return ''.join(str(value or '').casefold().split()).replace('-','')
    def same(key,left,right):
        if key=='total_amount':
            try:return Decimal(str(left)).is_finite() and Decimal(str(left))==Decimal(str(right))
            except (InvalidOperation,ValueError):return False
        return clean(left)==clean(right)
    for other in candidates[:200]:
        reasons=[];exact=bool(invoice.source_file.checksum_sha256) and other.source_file.checksum_sha256==invoice.source_file.checksum_sha256
        if exact:reasons.append('identical_file_sha256')
        keys=('seller_tax_code','invoice_number','invoice_symbol','invoice_date','total_amount')
        if all(getattr(invoice,k,None) is not None and str(getattr(invoice,k)).strip() for k in keys) and all(same(k,getattr(invoice,k),getattr(other,k)) for k in keys):
            reasons.append('matching_invoice_identity_and_total')
        if fingerprint is not None and not exact:
            if monotonic()-started>3:
                visual_skipped=True
                if reasons:matches.append({'invoice_id':other.id,'reasons':reasons,'status':'suspected'})
                continue
            try:
                root=storage_dir().resolve();path=(root/other.source_file.storage_key).resolve()
                if path.is_relative_to(root) and path.is_file() and path.stat().st_size<=20*1024*1024:
                    previous=stored_fingerprint(str(path),other.source_file.checksum_sha256,other.source_file.file_type)
                    if previous is not None and (int(fingerprint)^previous).bit_count()<=6:
                        reasons.append('similar_visual_dhash_advisory')
                else:visual_skipped=True
            except Exception:visual_skipped=True
        if reasons:matches.append({'invoice_id':other.id,'reasons':reasons,'status':'exact' if exact else 'suspected'})
    if role=='employee':
        chats=db.execute(select(ChatMessage.id,ChatMessage.conversation_id,ChatMessage.content)
            .join(Conversation,ChatMessage.conversation_id==Conversation.id)
            .where(Conversation.user_id==invoice.source_file.uploaded_by,ChatMessage.role=='assistant',
                   ChatMessage.content.startswith('[TAX_VERIFICATION]\n'))
            .order_by(ChatMessage.id.desc()).limit(101)).all()
        visual_skipped=visual_skipped or len(chats)>100
        for message_id,conversation_id,content in chats[:100]:
            try:
                prior=json.loads(content.split('\n',1)[1])['tax_verification']
                if prior.get('document_sha256')==invoice.source_file.checksum_sha256:
                    matches.append({'chat_message_id':message_id,'conversation_id':conversation_id,
                                    'reasons':['identical_file_sha256'],'status':'exact'})
            except (ValueError,KeyError,TypeError):continue
    return {'status':'exact' if any(m['status']=='exact' for m in matches) else 'suspected' if matches else 'not_detected',
            'matches':matches,'coverage':'recent_200_accessible_invoices; own_recent_100_tax_chat_messages_for_employee','coverage_incomplete':len(candidates)>200 or visual_skipped,
            'visual_scope':'first_page_only_for_pdf; resized grayscale dHash distance <= 6',
            'semantics':'Image similarity is advisory, not proof of duplicate or fraud.'}

def financial_report(fields,rows,context):
    def state(code,passed):
        if code=='NON-FINANCIAL-ADJUSTMENT':return 'not_applicable'
        if passed:return 'consistent'
        if code in ('ARITH','VAT-ARITH','TAX-BASE','DISCOUNT-ARITH','FINANCIAL-NUMERIC','ROW-NUMERIC'):return 'mismatch'
        return 'insufficient_data'
    positive_messages={'ARITH':'Tổng thanh toán khớp các số liệu đã đọc trong sai số làm tròn cho phép.',
        'VAT-ARITH':'VAT khớp cơ sở tính thuế và các mức thuế suất có bằng chứng.',
        'TAX-BASE':'Cơ sở tính thuế khớp chiết khấu và phụ phí đã xác định.',
        'DISCOUNT-ARITH':'Chiết khấu khớp tỷ lệ và cơ sở tiền hàng đã xác định.',
        'ADJUSTMENT-SCOPE':'Đã xác định phạm vi các khoản điều chỉnh từ bằng chứng.'}
    checks=[{'rule':code,'status':state(code,passed),'message':positive_messages.get(code,message) if passed else message,
             'source_message':message}
            for code,passed,message in arithmetic_rules(fields,rows,context)]
    if checks and all(check['status']=='not_applicable' for check in checks):
        return {'status':'not_applicable','checks':checks}
    # Check a printed line only when no unexplained row adjustments are present.
    adjusted=bool((context or {}).get('adjustment_observed'))
    for index,row in enumerate(rows,1):
        values=[row.get(k) for k in ('quantity','unit_price','amount')]
        status='insufficient_data';difference=None
        if not adjusted and all(v is not None and str(v).strip() for v in values):
            try:
                q,p,a=map(lambda v:Decimal(str(v)),values)
                if all(v.is_finite() for v in (q,p,a)):
                    difference=abs(q*p-a)
                    tolerance=Decimal('1') if fields.get('currency','VND')=='VND' else Decimal('0.01')
                    status='consistent' if difference<=tolerance else 'mismatch'
            except (InvalidOperation,ValueError):pass
        checks.append({'rule':'LINE-MULTIPLICATION','line_no':index,'fields':['quantity','unit_price','amount'],
                       'message':'Đối chiếu số lượng × đơn giá với thành tiền',
                       'status':status,'difference':str(difference) if difference is not None else None,
                       'rounding_tolerance':'1 currency unit; advisory VND rounding' if fields.get('currency','VND')=='VND' else 'Review currency precision'})
    statuses={c['status'] for c in checks}
    return {'status':'mismatch' if 'mismatch' in statuses else 'needs_review' if 'needs_review' in statuses else 'insufficient_data' if 'insufficient_data' in statuses or not checks else 'not_applicable' if statuses=={'not_applicable'} else 'consistent','checks':checks}

def verification_report(db,invoice,rows,metadata,role):
    fields={k:getattr(invoice,k,None) for k in ('subtotal','vat_rate','vat_amount','total_amount','currency')}
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'invoice_authenticity_verified':False,
            'tax':deepcopy(metadata.get('tax_verification')),'confidence':{'status':'unassessed','score':None,'fields':{}}}
    for section,operation in (
        ('duplicates',lambda:duplicate_report(db,invoice,role,metadata)),
        ('financial',lambda:({'status':'not_applicable','checks':[{'rule':'DOCUMENT-TYPE','status':'not_applicable','message':'Chứng từ đăng ký không phải hóa đơn; không áp dụng đối chiếu tiền hàng/VAT.'}]}
            if (metadata.get('tax_verification') or {}).get('document_kind') in ('tax_registration','business_registration')
            else financial_report(fields,rows,metadata.get('financial_context') or {})))):
        try:result[section]=operation()
        except Exception as exc:result[section]={'status':'unavailable','error_type':type(exc).__name__}
    source=metadata.get('evidence')
    evidence=source.get('final_field_evidence',{}) if isinstance(source,dict) else {}
    policy=metadata.get('confidence') or {}
    if not isinstance(policy,dict):policy={}
    approved=bool(policy.get('policy') and policy.get('approval_reference'))
    if approved:
        result['confidence'].update(status=policy.get('status','unassessed'),score=policy.get('score'),policy=policy.get('policy'))
    if not isinstance(evidence,dict):evidence={}
    for key in ('seller_name','seller_tax_code','invoice_number','invoice_date','vat_amount','total_amount'):
        scores=[]
        candidates=evidence.get(key,[])
        if not isinstance(candidates,list):candidates=[]
        for candidate in candidates:
            if not isinstance(candidate,dict) or str(candidate.get('value'))!=str(getattr(invoice,key,None)):continue
            parts=candidate.get('evidence',[])
            if not isinstance(parts,list):continue
            for part in parts:
                if not isinstance(part,dict):continue
                value=part.get('ocr_score')
                if isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value) and 0<=value<=1:scores.append(value)
        result['confidence']['fields'][key]={'score':None,'status':'source_scores_available' if scores else 'unassessed',
            'ocr_word_scores':scores,'semantics':'Word OCR scores, not calibrated field accuracy; no approved low-score threshold.'}
        entries=policy.get('fields') or {}
        entry=entries.get(key,{}) if isinstance(entries,dict) else {}
        if not isinstance(entry,dict):entry={}
        if approved and entry.get('status')=='low':
            result['confidence']['fields'][key]['status']='low'
    try:
        from .fraud_assessment import assess_risk
        result['risk']=assess_risk(db,invoice,result,metadata)
    except Exception as exc:
        result['risk']={'score':None,'level':'insufficient_data','recommendation':'additional_review','error_type':type(exc).__name__,'signals':[]}
    try:
        from .finance import budget_checks,ExpenseAssignment,propose_category
        from types import SimpleNamespace
        viewer=SimpleNamespace(id=invoice.source_file.uploaded_by,role=role)
        with db.begin_nested():
            result['budget']=budget_checks(db,invoice,viewer)
            assignment=db.get(ExpenseAssignment,invoice.id) if invoice.id else None
            result['expense_category']={'category':assignment.category,'reason':assignment.reason,'version':assignment.version} if assignment else propose_category(invoice,rows)
    except Exception as exc:result['budget']={'status':'unavailable','error_type':type(exc).__name__}
    return result
