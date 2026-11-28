"""Explainable advisory risk policy. Scores are not fraud probabilities."""
import json,os
from pathlib import Path
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
from statistics import median
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .models import Invoice,InvoiceFile,InvoiceCorrection

DEFAULT_POLICY={'version':'advisory-risk-v1','weights':{'exact_duplicate':40,'suspected_duplicate':20,
    'tax_mismatch':25,'tax_partial':10,'financial_mismatch':30,'future_date':15,
    'ocr_conflict':15,'low_confidence':10,'spending_outlier':15},
    'medium':25,'high':60,'minimum_history':20,'outlier_multiplier':6}

def load_policy():
    path=os.getenv('INVOICE_RISK_POLICY_PATH')
    if not path:
        from dotenv import dotenv_values
        path=dotenv_values(Path(__file__).resolve().parents[1]/'.env',interpolate=False).get('INVOICE_RISK_POLICY_PATH')
    if path:
        file=Path(path)
        if not file.is_absolute():file=Path(__file__).resolve().parents[1]/file
        if file.stat().st_size>65536:raise ValueError('Risk policy file exceeds size limit')
        policy=json.loads(file.read_text(encoding='utf-8-sig'))
    else:policy=json.loads(json.dumps(DEFAULT_POLICY))
    if (set(policy)!=set(DEFAULT_POLICY) or not isinstance(policy['version'],str) or not policy['version'].strip()
        or set(policy['weights'])!=set(DEFAULT_POLICY['weights'])
        or any(type(v)is not int or not 0<=v<=100 for v in policy['weights'].values())
        or not 0<policy['medium']<policy['high']<=100
        or type(policy['minimum_history'])is not int or not 20<=policy['minimum_history']<=1000
        or not 3<=policy['outlier_multiplier']<=20):
        raise ValueError('Invalid risk policy')
    return policy

def evaluate_risk(report,issued,findings=(),history=None,amount=None,policy=None):
    policy=policy or load_policy();signals=[];missing=[]
    def add(code,reason,action):signals.append({'rule':code,'points':policy['weights'][code],'reason':reason,'action':action})
    duplicates=report.get('duplicates') or {};tax=report.get('tax') or {};financial=report.get('financial') or {};confidence=report.get('confidence') or {}
    if duplicates.get('status')=='exact':add('exact_duplicate','Tệp trùng nội dung đã lưu.','Đối chiếu bản ghi liên quan trước khi quyết định.')
    elif duplicates.get('status')=='suspected':add('suspected_duplicate','Có dấu hiệu trùng hình ảnh hoặc thông tin định danh.','Mở và đối chiếu hai chứng từ gốc.')
    if duplicates.get('coverage_incomplete') or duplicates.get('status') not in ('exact','suspected','not_detected'):missing.append('duplicate_coverage')
    if tax.get('name_comparison')=='mismatch':add('tax_mismatch','Thông tin chứng từ khác dữ liệu đăng ký.','Đối chiếu tên/MST và nguồn tra cứu.')
    elif tax.get('name_comparison') in ('partial_match','needs_review') or (tax.get('name_comparison')=='insufficient_data' and tax.get('observed_name_available')):add('tax_partial','Tên chưa đối chiếu khớp đầy đủ; OCR có thể thiếu hoặc sai ký tự.','Kiểm tra bản gốc, không kết luận sai lệch chắc chắn.')
    if tax.get('status')!='found' or tax.get('name_comparison') not in ('match','mismatch'):missing.append('tax_evidence')
    if financial.get('status')=='mismatch':add('financial_mismatch','Có phép đối chiếu số liệu không nhất quán.','Kiểm tra dòng hàng, VAT và phạm vi chiết khấu.')
    if financial.get('status') not in ('consistent','mismatch','not_applicable'):missing.append('financial_evidence')
    try:
        issued=date.fromisoformat(str(issued)[:10])
        if issued>datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date():add('future_date','Ngày lập nằm trong tương lai theo múi giờ Việt Nam.','Kiểm tra ngày lập và múi giờ.')
    except (ValueError,TypeError):missing.append('invoice_date')
    if any('CONFLICT' in str(f.get('code','')) for f in findings):add('ocr_conflict','Các nguồn OCR có dữ liệu mâu thuẫn.','Đối chiếu bằng chứng và sửa thủ công nếu cần.')
    if confidence.get('status')=='low':add('low_confidence','Confidence thấp theo chính sách đã phê duyệt.','Kiểm tra các trường được đánh dấu.')
    if confidence.get('status') not in ('low','assessed'):missing.append('calibrated_confidence')
    historical={'status':'insufficient_data','sample_count':len(history or [])}
    try:
        values=[Decimal(str(v)) for v in (history or []) if v is not None]
        values=[v for v in values if v.is_finite() and v>0]
        historical['sample_count']=len(values)
        current=Decimal(str(amount))
        if len(values)>=policy['minimum_history'] and current.is_finite():
            center=median(values);mad=median([abs(v-center) for v in values])
            # Zero dispersion is insufficient to infer an anomaly threshold.
            if mad>0:
                historical={'status':'evaluated','sample_count':len(values),'method':'median + multiplier * median absolute deviation'}
                if current>center+Decimal(str(policy['outlier_multiplier']))*mad:add('spending_outlier','Khoản chi cao bất thường so với lịch sử cùng người gửi và loại tiền.','Kiểm tra mục đích chi và chứng từ bổ sung.')
    except (InvalidOperation,ValueError,TypeError):pass
    if historical['status']!='evaluated':missing.append('spending_history')
    points=min(100,sum(s['points'] for s in signals))
    level='high' if points>=policy['high'] else 'medium' if points>=policy['medium'] else 'insufficient_data' if missing else 'low'
    return {'policy':policy,'score':points if signals or not missing else None,'level':level,
        'missing_evidence':missing,'signals':signals,'history':historical,
        'document_tampering':{'status':'not_assessed','reason':'Chưa có phương pháp giám định chỉnh sửa đủ tin cậy; không dùng độ giống ảnh làm bằng chứng chỉnh sửa.'},
        'recommendation':'priority_review' if level=='high' else 'consider_approval' if level=='low' else 'additional_review',
        'fraud_confirmed':False,'semantics':'Configurable heuristic risk points, not fraud probability; human decision required.',
        'generated_at':datetime.now(timezone.utc).isoformat()}

def assess_risk(db,invoice,report,metadata):
    tax=report.get('tax') or {}
    if tax.get('document_kind') in ('tax_registration','business_registration'):
        return {'score':None,'level':'insufficient_data','applicability':'not_applicable','recommendation':'additional_review',
                'signals':[],'reason':'Chứng từ đăng ký không phải hóa đơn; không áp dụng điểm rủi ro hóa đơn.','fraud_confirmed':False}
    query=(select(Invoice.total_amount).join(InvoiceFile).where(Invoice.id!=invoice.id,
        InvoiceFile.uploaded_by==invoice.source_file.uploaded_by,Invoice.currency==getattr(invoice,'currency','VND'),
        Invoice.approval_status=='approved',Invoice.total_amount.is_not(None)).order_by(Invoice.id.desc()).limit(1000))
    history=list(db.scalars(query).all())
    evaluation={**report,'tax':{**tax,'observed_name_available':bool(getattr(invoice,'seller_name',None))}}
    result=evaluate_risk(evaluation,getattr(invoice,'invoice_date',None),metadata.get('findings') or [],history,getattr(invoice,'total_amount',None))
    missing_fields=[key for key in ('seller_name','seller_tax_code','invoice_number','invoice_date','total_amount')
                    if getattr(invoice,key,None) is None or not str(getattr(invoice,key)).strip()]
    result['missing_evidence'].extend('field:'+key for key in missing_fields)
    if missing_fields and result['level']=='low':
        result.update(level='insufficient_data',recommendation='additional_review',score=result['score'] if result['signals'] else None)
    from sqlalchemy import func
    result['source_correction_id']=db.scalar(select(func.max(InvoiceCorrection.id)).where(InvoiceCorrection.invoice_id==invoice.id)) or 0
    return result
