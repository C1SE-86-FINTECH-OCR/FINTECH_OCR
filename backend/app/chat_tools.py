"""Scoped deterministic chat tools and persisted, owner-only conversation context."""
import json,re,os
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select,func
from .models import Invoice,InvoiceFile,ExtractionRun,InvoiceCorrection,ChatMessage,InvoiceItem
from . import finance,finance_chat
from .fraud_assessment import load_policy
from .tax_verification import tax_summary

LABELS={'consistent':'Nhất quán','mismatch':'Sai lệch','insufficient_data':'Chưa đủ dữ liệu','unassessed':'Chưa đánh giá','not_applicable':'Không áp dụng','needs_review':'Cần kiểm tra','unavailable':'Chưa khả dụng','exact':'Trùng file chính xác','suspected':'Nghi ngờ trùng','not_detected':'Chưa phát hiện trùng','low':'Thấp','medium':'Trung bình','high':'Cao','found':'Đã tìm thấy doanh nghiệp'}

def previous_context(db,conversation_id):
 messages=db.scalars(select(ChatMessage).where(ChatMessage.conversation_id==conversation_id,ChatMessage.role=='assistant').order_by(ChatMessage.id.desc()).limit(30)).all()
 for message in messages:
  try:
   if message.content.startswith('[CHAT_TOOL]\n'):return json.loads(message.content.split('\n',1)[1]).get('context') or {}
   if message.content.startswith('[FINANCE_ANALYSIS]\n'):
    data=json.loads(message.content.split('\n',1)[1]);return {'finance':(data.get('finance_analysis') or {}).get('filters',{}),'last_kind':'finance'}
   if message.content.startswith('[TAX_VERIFICATION]\n'):
    data=json.loads(message.content.split('\n',1)[1]);return {'tax':data.get('tax_verification',{}),'last_kind':'invoice'}
  except (ValueError,TypeError):continue
 return {}

def route(question,context):
 q=finance.fold(question)
 internal_finance=any(x in q for x in ('hoa don','chi tieu','chi phi','ngan sach','han muc','tong tien','thong ke','vat','kiem tra so lieu'))
 if re.search(r'(api.?key|mat khau|password|token|secret|ignore previous|bo qua.*quy tac)',q):return 'security'
 if any(x in q for x in ('hom nay ngay','bay gio la ngay','thu may hom nay')):return 'date'
 if not internal_finance and any(x in q for x in ('khach san','nha nghi','so dien thoai','thong tin lien he','dia chi o dau','gia phong','moi nhat','tin tuc','thoi tiet')):return 'external'
 if context.get('last_kind')=='external' and not internal_finance and 'mst' not in q and len(q)<180:return 'external'
 if any(x in q for x in ('chi cuc thue','co so du lieu cua thue','co so du lieu cua chi cuc','hoa don hop phap','hoa don dien tu','hoa don gia','tinh hop phap')):return 'authenticity'
 if any(x in q for x in ('danh gia lai','phan loai lai')):return 'reassess' if 'danh gia' in q else 'classify'
 if any(x in q for x in ('rui ro','gian lan','fraud')):return 'risk'
 if any(x in q for x in ('trung lap','bi trung','trung hoa don','trung file')):return 'duplicates'
 if any(x in q for x in ('confidence','do tin cay','chat luong ocr')):return 'confidence'
 if any(x in q for x in ('so hoc','kiem tra so lieu','tinh dung','chinh xac','dung hay sai','sai lech')) or ('kiem tra' in q and any(x in q for x in ('vat','tong tien','thanh tien'))):return 'financial'
 specific_document=('hoa don nay' in q or 'chung tu nay' in q or re.search(r'(?:hoa don|invoice)\s*(?:id\s*|#)\s*\d+',q))
 if (context.get('invoice_id') or context.get('tax')) and context.get('last_kind') in ('invoice','financial','fields','tax','confidence','duplicates','risk') and not finance_chat.chatbot_queries._period(question) and not any(x in q for x in ('chi tieu','chi phi','thong ke','tat ca','nhung hoa don')):specific_document=True
 if specific_document and any(x in q for x in ('tong tien','thanh toan','nguoi ban','nguoi mua','nha cung cap','san pham','hang hoa','ngay lap','mst','ma so thue','ky hieu','so hoa don','vat','truoc thue')):return 'fields'
 if any(x in q for x in ('phan loai','danh muc cua hoa don','thuoc nhom chi phi')):return 'category'
 if any(x in q for x in ('phe duyet','duyet hoa don','smart approval')) and not any(x in q for x in ('chi tieu','chi phi','tong tien','thong ke')):return 'approval'
 if any(x in q for x in ('ma so thue','mst','tra cuu thue','tax verification')):return 'tax'
 if 'hoa don nay' in q or 'chung tu nay' in q or re.search(r'(?:hoa don|invoice)\s*(?:id\s*|#)\d+',q):return 'invoice'
 prior=context.get('finance') if context.get('last_kind') in ('finance','budget') else None
 request=finance_chat.intent(question,prior)
 if request:return 'budget' if request['budget'] else 'finance'
 return None

def invoice_id(question,context):
 match=re.search(r'(?:hoa don|invoice)\s*(?:id\s*|#)\s*(\d+)\b',finance.fold(question))
 return int(match.group(1)) if match else context.get('invoice_id')

def report_answer(kind,report,question=''):
 if kind=='authenticity':
  return 'Chưa xác minh hóa đơn điện tử với cơ quan thuế. Việc tìm thấy MST chỉ xác nhận thông tin đăng ký doanh nghiệp, không chứng minh hóa đơn hợp pháp. Tra cứu chính thức: https://hoadondientu.gdt.gov.vn/ .'
 if kind in ('fields','invoice'):
  fields=report.get('document_fields') or {};items=report.get('document_items') or []
  labels={'seller_name':'Người bán','buyer_name':'Người mua','seller_tax_code':'MST người bán','buyer_tax_code':'MST người mua','invoice_number':'Số hóa đơn','invoice_symbol':'Ký hiệu','invoice_date':'Ngày lập','subtotal':'Trước thuế','vat_amount':'VAT','total_amount':'Tổng thanh toán','currency':'Tiền tệ'}
  if not fields:return 'Chưa có bản chụp trường OCR trong hồ sơ hội thoại này. Không suy ra số tiền hoặc thông tin hóa đơn từ câu trả lời AI cũ.'
  q=finance.fold(question);keys=list(labels)
  if 'tong tien' in q or 'thanh toan' in q:keys=['total_amount','currency']
  elif 'vat' in q:keys=['vat_amount','currency']
  elif 'nguoi mua' in q:keys=['buyer_name','buyer_tax_code']
  elif 'nguoi ban' in q or 'nha cung cap' in q:keys=['seller_name','seller_tax_code']
  elif 'ngay lap' in q:keys=['invoice_date']
  def display(key):
   value=fields.get(key)
   if value is None or value=='':return 'Chưa đủ dữ liệu'
   if key in ('subtotal','vat_amount','total_amount'):return finance_chat.amount(value,fields.get('currency') or 'VND')
   if key=='invoice_date':return finance_chat.day(value)
   return str(value)
  answer='Dữ liệu trích xuất từ chứng từ, chưa phải xác minh độc lập:\n'+'\n'.join(labels[k]+': '+display(k) for k in keys)
  if items and any(x in q for x in ('san pham','hang hoa','dong hang')):answer+='\n'+'\n'.join(f"- {row.get('description') or 'Chưa có tên hàng'}; số lượng {finance_chat.number(row.get('quantity'),3)}; thành tiền {finance_chat.amount(row.get('amount'),fields.get('currency') or 'VND')}" for row in items)
  return answer
 if kind=='tax':return tax_summary(report.get('tax') or {'status':'unavailable'})
 if kind=='category':
  category=report.get('expense_category') or {}
  return 'Danh mục: '+finance.CATEGORIES.get(category.get('category'),'Chưa phân loại')+'. '+str(category.get('reason') or 'Chưa có bằng chứng phân loại.')
 if kind=='approval':
  risk=report.get('risk') or {};budget=report.get('budget') or {}
  return 'Đề xuất hỗ trợ: '+{'priority_review':'ưu tiên kiểm tra rủi ro','additional_review':'cần kiểm tra thêm','consider_approval':'có thể xem xét phê duyệt'}.get(risk.get('recommendation'),'chưa đủ dữ liệu để đề xuất')+'. Ngân sách: '+{'configured':'đã kiểm tra','not_configured':'chưa thiết lập','reviewer_required':'chỉ người có thẩm quyền xem','insufficient_data':'chưa đủ dữ liệu'}.get(budget.get('status'),'chưa khả dụng')+'. Quyết định vẫn thuộc người có thẩm quyền; Chat không tự phê duyệt hay từ chối.'
 value=report.get(kind) or {}
 key='level' if kind=='risk' else 'status'
 answer=LABELS.get(value.get(key),'Chưa đánh giá')+'.'
 if kind=='risk':answer+=' Điểm quy tắc: '+(str(value['score'])+'/100' if value.get('score') is not None else 'chưa xác định')+'. Đây là dấu hiệu cần rà soát, không phải kết luận gian lận.'
 if kind=='financial':
  answer+='\n'+'\n'.join('- '+str(row.get('message') or row.get('rule'))+': '+LABELS.get(row.get('status'),str(row.get('status')))+(f"; chênh lệch {finance_chat.number(row['difference'])}" if row.get('difference') is not None else '') for row in value.get('checks',[]))
 if kind=='duplicates':answer+='\n'+'\n'.join(f"- Hóa đơn #{m['invoice_id']}: "+', '.join(m.get('reasons',[])) for m in value.get('matches',[]) if m.get('invoice_id'))
 if kind=='confidence':answer+=' Điểm OCR nguồn không phải xác suất dữ liệu đúng; chưa có chính sách hiệu chỉnh thì không tạo phần trăm.\n'+'\n'.join(f"- {field}: "+LABELS.get(item.get('status'),'Chưa đánh giá') for field,item in value.get('fields',{}).items())
 return answer

def execute(db,user,question,context,services):
 kind=route(question,context)
 if kind is None:return None
 state=dict(context);state['last_kind']=kind
 result={'kind':kind,'context':state,'finance_analysis':None,'verification_report':None}
 q=finance.fold(question)
 if kind=='security':answer='Không cung cấp khóa, mật khẩu hoặc thông tin xác thực. Chat chỉ truy vấn dữ liệu trong phạm vi quyền của bạn.'
 elif kind=='date':answer='Hôm nay là '+datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%d/%m/%Y')+' (giờ Việt Nam).'
 elif kind=='external':
  state['external_question']=(str(context.get('external_question',''))+'\n'+question)[-1600:]
  result['external_query']=state['external_question'];answer=None
 elif kind in ('reassess','classify') and any(x in q for x in ('tat ca','toan bo','hang loat')):
  answer='Chưa thực hiện cập nhật hàng loạt. Cần phương án sao lưu và xác nhận riêng; bạn có thể yêu cầu một hóa đơn bằng ID.'
 elif kind in ('finance','budget'):
  request=finance_chat.intent(question,context.get('finance') if context.get('last_kind') in ('finance','budget') else None)
  if request['clarify']:answer='Chưa xác định chính xác bộ lọc. Vui lòng nêu thời gian, phòng ban hoặc nhân viên cụ thể; không tự mở rộng phạm vi truy vấn.'
  elif kind=='budget':
   if user.role=='employee':answer='Bạn chưa có quyền xem ngân sách toàn đơn vị. Kế toán hoặc Quản trị viên có thể xem hạn mức; Chat không suy đoán ngân sách cá nhân.'
   else:
    filters=request['filters'];values=[b for b in services['budgets'](db,user) if (not filters['starts'] or b['ends_on']>=str(filters['starts'])) and (not filters['ends'] or b['starts_on']<=str(filters['ends'])) and (not filters['team'] or b['team']==filters['team']) and (not filters['category'] or b['category']==filters['category'])]
    result['finance_analysis']={'rows':[],'budgets':values,'scope':'organization'}
    answer='Chưa thiết lập ngân sách trong phạm vi được hỏi.' if not values else '\n'.join(f"Ngân sách #{b['id']} ({finance_chat.day(b['starts_on'])} — {finance_chat.day(b['ends_on'])}): hạn mức {finance_chat.amount(b['limit'],b['currency'])}, đã duyệt {finance_chat.amount(b['approved'],b['currency'])}, đang chờ {finance_chat.amount(b['pending'],b['currency'])}, còn lại {finance_chat.amount(b['remaining'],b['currency'])}." for b in values)
   state['finance']={k:str(v) if v is not None else '' for k,v in request['filters'].items()}
  else:
   data=services['analysis'](**request['filters'],db=db,user=user)
   if request['export'] and context.get('finance_compare') and not finance_chat.chatbot_queries._period(question):
    request['compare']=True
    if context.get('finance_compare_filters'):
     from datetime import date
     request['compare_filters']={**request['filters'],**context['finance_compare_filters']}
     for key in ('starts','ends'):request['compare_filters'][key]=date.fromisoformat(request['compare_filters'][key])
   if request['compare_filters']:
    from decimal import Decimal
    other=services['analysis'](**request['compare_filters'],db=db,user=user)
    values=[]
    for currency in {r['currency'] for r in data['rows']+other['rows']}:
     totals=lambda source,key:sum((Decimal(r[key]) for r in source['rows'] if r['currency']==currency),Decimal(0))
     a=totals(data,'approved');b=totals(other,'approved');p=totals(data,'pending');old_p=totals(other,'pending')
     incomplete=any(r['missing_amounts'] for r in data['rows']+other['rows'] if r['currency']==currency)
     values.append({'currency':currency,'approved_current':str(a),'approved_previous':str(b),'difference':str(a-b),'change_percent':str((a-b)*100/b) if b and not incomplete else None,'pending_current':str(p),'pending_previous':str(old_p),'pending_difference':str(p-old_p),'incomplete':incomplete})
    data.update(comparison=values,previous_period={k:str(request['compare_filters'][k]) for k in ('starts','ends')})
   state['finance_compare']=request['compare'];state['finance_compare_filters']={k:str(request['compare_filters'][k]) for k in ('starts','ends')} if request['compare_filters'] else None
   if not request['compare']:data.pop('comparison',None);data.pop('previous_period',None)
   if request['chart']:data['chart']=request['chart']
   data['export_requested']=request['export'];result['finance_analysis']=data;state['finance']=data['filters']
   if request['export']:data['export_url']=services['export'](data,db,user)
   answer=finance_chat.explain(data,request)
 elif kind=='risk' and (any(x in q for x in ('nhung hoa don','danh sach','hoa don nao','tat ca')) or not invoice_id(question,context)) and not ('hoa don nay' in q or 'chung tu nay' in q):
  query=select(Invoice).join(InvoiceFile,Invoice.file_id==InvoiceFile.id)
  if user.role=='employee':query=query.where(InvoiceFile.uploaded_by==user.id)
  period=finance_chat.intent('chi tieu '+question,context.get('finance') if context.get('last_kind') in ('finance','budget') else None)
  if period and period['clarify']:
   result['text']='Chưa xác định được đối tượng hoặc thời gian để lọc rủi ro; cần bộ lọc rõ ràng, không tự mở rộng phạm vi.';return result
  filters=period['filters'] if period else {}
  if filters.get('employee_id'):
   if user.role=='employee' and filters['employee_id']!=user.id:
    from fastapi import HTTPException
    raise HTTPException(403,'Không có quyền xem hóa đơn nhân viên khác')
   query=query.where(InvoiceFile.uploaded_by==filters['employee_id'])
  if filters.get('team'):
   from .models import User
   query=query.join(User,User.id==InvoiceFile.uploaded_by).where(User.team==filters['team'])
  if period and period['filters']['starts']:query=query.where(Invoice.invoice_date>=period['filters']['starts'])
  if period and period['filters']['ends']:query=query.where(Invoice.invoice_date<=period['filters']['ends'])
  invoices=db.scalars(query.order_by(Invoice.id.desc()).limit(1001)).all();unknown=0;matches=[]
  current_policy=load_policy()
  ids=[i.id for i in invoices[:1000]]
  latest=select(func.max(ExtractionRun.id)).where(ExtractionRun.invoice_id.in_(ids)).group_by(ExtractionRun.invoice_id)
  runs={run.invoice_id:run for run in db.scalars(select(ExtractionRun).where(ExtractionRun.id.in_(latest))).all()}
  corrections=dict(db.execute(select(InvoiceCorrection.invoice_id,func.max(InvoiceCorrection.id)).where(InvoiceCorrection.invoice_id.in_(ids)).group_by(InvoiceCorrection.invoice_id)).all())
  for invoice in invoices[:1000]:
   run=runs.get(invoice.id);meta=(run.extracted_json or {}).get('_ocr',{}) if run else {}
   history=meta.get('risk_assessments') or [];risk=history[-1] if history else (meta.get('verification_report') or {}).get('risk') or {}
   correction=corrections.get(invoice.id,0)
   if not risk or risk.get('policy')!=current_policy or risk.get('source_correction_id',0)!=correction:unknown+=1;continue
   if risk.get('level')=='insufficient_data':unknown+=1
   if risk.get('level')=='high':matches.append({'invoice_id':invoice.id,'score':risk.get('score'),'level':'high','signals':risk.get('signals',[])})
  result['risk_invoices']=matches
  answer=('Hóa đơn có dấu hiệu rủi ro cao đã ghi nhận:\n'+'\n'.join(f"- Hóa đơn #{r['invoice_id']}: {r['score']}/100; "+'; '.join(s.get('reason','') for s in r['signals']) for r in matches)) if matches else 'Chưa có hồ sơ đánh giá hợp lệ ghi nhận mức rủi ro cao trong phạm vi của bạn.'
  answer+=f'\nĐã xem {min(len(invoices),1000)} bản ghi; {unknown} chưa đủ đánh giá hoặc hồ sơ đã cũ. Không coi nhóm này là rủi ro thấp.'
  if len(invoices)>1000:answer+=' Danh sách giới hạn 1.000 bản ghi mới nhất; chưa kiểm tra toàn bộ.'
 else:
  target=invoice_id(question,context)
  if target:
   invoice=services['allowed'](db,user,target);state['invoice_id']=target
   result['invoice_id']=target
   if kind=='reassess':
    if user.role not in ('accountant','admin'):answer='Chỉ Kế toán hoặc Quản trị viên được ghi nhận đánh giá lại.'
    else:result['verification_report']=services['reassess'](target,db,user);answer='Đã ghi thêm đánh giá cho hóa đơn #'+str(target)+'. Không sửa dữ liệu OCR hoặc quyết định phê duyệt.'
   elif kind=='classify':
    if user.role=='employee' and invoice.approval_status not in ('draft','rejected'):answer='Không được thay đổi danh mục của hóa đơn đã gửi phê duyệt.'
    else:
     items=[{'description':r.description} for r in db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id==target)).all()]
     record=finance.reclassify(db,invoice,items,user.id);db.commit();answer='Danh mục: '+finance.CATEGORIES[record.category]+'. '+record.reason+('. Giữ nguyên phân loại do người dùng chỉnh sửa.' if record.method=='manual' else '. Đã đối chiếu lại bằng quy tắc; không sửa dữ liệu OCR gốc.')
   else:
    result['verification_report']=services['report'](target,db,user)
    if kind in ('invoice','fields'):
     result['verification_report']['document_fields']={k:getattr(invoice,k,None) for k in ('seller_name','buyer_name','seller_tax_code','buyer_tax_code','invoice_number','invoice_symbol','invoice_date','subtotal','vat_amount','total_amount','currency')}
     result['verification_report']['document_items']=[{'description':r.description,'quantity':r.quantity,'amount':r.amount} for r in db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id==target)).all()]
    answer=report_answer(kind,result['verification_report'],question)
  elif context.get('tax'):
   tax=context['tax'];report=tax.get('verification_report') or {};tax_view={k:v for k,v in tax.items() if k not in ('verification_report','document_fields','document_items')};report={**report,'tax':tax_view,'document_fields':tax.get('document_fields',{}),'document_items':tax.get('document_items',[])};result['verification_report']=report
   answer=report_answer(kind,report,question)
  else:answer='Chưa có dữ liệu chứng từ đã kiểm tra trong ngữ cảnh. Hãy chọn hóa đơn bằng ID hoặc đính kèm chứng từ; Chat không dùng câu trả lời AI cũ làm bằng chứng xác minh.'
 result['text']=answer
 return result
