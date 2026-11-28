"""Bounded local financial intents. No generated SQL or financial egress."""
import re
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,localcontext
from datetime import date
from . import finance,chatbot_queries

def intent(question,previous=None):
 q=finance.fold(question)
 follow=any(word in q for word in ('con thang','con quy','con nam','so sanh','bieu do','excel','ky truoc','danh muc'))
 if not any(word in q for word in ('chi tieu','chi phi','ngan sach','han muc','bieu do','tong tien','tien thue','bao cao tai chinh','hoa don','vat','truoc thue','excel')) and not (previous and follow):return None
 period=chatbot_queries._period(question)
 quarter=re.search(r'\bquy\s+([1-4])(?:\s+nam\s+(20\d{2}))?\b',q)
 if quarter:
  from datetime import datetime
  from zoneinfo import ZoneInfo
  period='quarter:'+str(quarter.group(2) or datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).year)+':'+quarter.group(1)
 starts,ends=chatbot_queries.period_bounds(period)
 group='month'
 for term,key in [('danh muc','category'),('phong ban','team'),('nhan vien','employee'),('doanh nghiep','supplier'),('trang thai','status'),('theo ngay','day'),('theo quy','quarter'),('theo nam','year')]:
  if term in q:group=key;break
 filters={'starts':starts,'ends':ends,'group':group,'team':'','category':'','employee_id':None,'supplier':''}
 if previous:
  for key in filters:
   if key in previous and key not in ('starts','ends','group'):filters[key]=previous[key]
  if not period:
   from datetime import date
   filters['starts']=date.fromisoformat(previous['starts']) if previous.get('starts') else None
   filters['ends']=date.fromisoformat(previous['ends']) if previous.get('ends') else None
  if group=='month' and not any(term in q for term in ('theo thang','theo ngay','theo quy','theo nam','danh muc','phong ban','nhan vien','doanh nghiep','trang thai')):filters['group']=previous.get('group','month')
 if not filters['employee_id']:filters['employee_id']=None
 elif str(filters['employee_id']).isdigit():filters['employee_id']=int(filters['employee_id'])
 # Exact quoted values avoid confusing grouping requests with entity filters.
 for label,key in [('phong ban','team'),('doanh nghiep','supplier'),('nha cung cap','supplier')]:
  match=re.search(label+r'\s*[:=]\s*"([^"\n]{1,120})"',q)
  if match:
   original=re.search(r'[:=]\s*"([^"\n]{1,120})"',question[match.start():])
   filters[key]=original.group(1) if original else match.group(1)
 match=re.search(r'nhan vien\s*(?:id|#|:)\s*(\d+)\b',q)
 if match:filters['employee_id']=int(match.group(1))
 for key,label in finance.CATEGORIES.items():
  if key!='unclassified' and finance.fold(label) in q:filters['category']=key
 # Do not silently broaden a named filter we cannot resolve.
 unclear=any(term in q and 'theo '+term not in q and 'tung '+term not in q and not filters[key] for term,key in [('phong ban','team'),('nhan vien','employee_id'),('doanh nghiep','supplier')])
 if re.search(r'\b(?:thang|quy|nam|ngay)\s+\d',q) and not period:unclear=True
 compare_filters=None
 named_months=re.findall(r'\bthang\s+(\d{1,2})(?:\s+nam\s+(20\d{2}))?\b',q)
 if len(named_months)==2 and ('so sanh' in q or 'voi' in q):
  from datetime import datetime
  from zoneinfo import ZoneInfo
  year=next((y for _,y in named_months if y),str(datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).year))
  if all(1<=int(m)<=12 for m,_ in named_months):
   filters['starts'],filters['ends']=chatbot_queries.period_bounds('month:'+f'{named_months[0][1] or year}-{int(named_months[0][0]):02d}')
   a,b=chatbot_queries.period_bounds('month:'+f'{named_months[1][1] or year}-{int(named_months[1][0]):02d}')
   compare_filters={**filters,'starts':a,'ends':b}
  else:unclear=True
 return {'filters':filters,'compare_filters':compare_filters,'amount_field':'vat' if 'vat' in q or 'tien thue' in q else 'subtotal' if 'truoc thue' in q else None,'budget':'ngan sach' in q or 'han muc' in q,'clarify':unclear,'compare':'so sanh' in q or 'chenh lech' in q,'export':'excel' in q or 'xlsx' in q,'chart':'pie' if 'tron' in q else 'bar' if 'cot' in q else 'line' if 'duong' in q else None}

def number(value,places=2):
 if value is None or value=='':return 'Chưa xác định'
 try:
  value=Decimal(str(value))
  if not value.is_finite():return 'Chưa xác định'
  with localcontext() as ctx:
   ctx.prec=max(32,len(value.as_tuple().digits)+abs(value.as_tuple().exponent)+4)
   rounded=value.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
  text=f'{rounded:,.{places}f}'
  if '.' in text:text=text.rstrip('0').rstrip('.')
  if rounded==0:text=text.lstrip('-')
  return text.translate(str.maketrans({',':'.','.':','}))
 except (InvalidOperation,ValueError,TypeError):return 'Chưa xác định'

def amount(value,currency='VND'):
 return number(value)+(' đ' if currency=='VND' else ' '+str(currency)) if value is not None and value!='' else 'Chưa đủ dữ liệu'

def day(value):
 if not value:return 'không giới hạn'
 try:return date.fromisoformat(str(value)[:10]).strftime('%d/%m/%Y')
 except ValueError:return 'chưa xác định'

def period_text(filters):return day(filters.get('starts'))+' — '+day(filters.get('ends'))

def percent(value):return number(value)+'%' if value is not None else 'Chưa tính được'

def cell(value):return str(value).replace('|','\\|').replace('\n',' ')

def explain(result,request=None):
 request=request or {};rows=result.get('rows',[]);text=[]
 if not rows:text.append('Chưa có khoản chi đủ điều kiện để cộng trong phạm vi này. Điều đó không có nghĩa là không có hóa đơn.')
 for currency in sorted({r['currency'] for r in rows}):
  subset=[r for r in rows if r['currency']==currency]
  field=request.get('amount_field')
  if field:
   label='VAT' if field=='vat' else 'tiền trước thuế'
   missing=sum(r.get('missing_'+field,0) for r in subset);known=sum(r['count'] for r in subset)-missing
   if not known:text.append(f'Chưa đọc được {label} đủ căn cứ ({currency}); không coi ô trống là 0.')
   else:
    value=sum((Decimal(r.get(field+'_known') or r.get(field) or '0') for r in subset),Decimal(0))
    text.append(f'{label.capitalize()} đọc được: **{amount(value,currency)}** trên {known} hóa đơn; {missing} hóa đơn còn thiếu trường này.')
  approved=sum((Decimal(r['approved']) for r in subset),Decimal(0));pending=sum((Decimal(r['pending']) for r in subset),Decimal(0))
  text.append(f'**Đã phê duyệt: {amount(approved,currency)}. Đang chờ: {amount(pending,currency)}.**\nCó {sum(r["count"] for r in subset)} hóa đơn đủ điều kiện trong nhóm tiền tệ này.')
  missing=sum(r['missing_amounts'] for r in subset)
  if missing:text.append(f'{missing} hóa đơn chưa có tổng tiền; các tổng trên chỉ phản ánh phần dữ liệu đã đọc được.')
 if request.get('compare'):
  text.append('**Kỳ A:** '+period_text(result.get('filters',{}))+'.\n**Kỳ B:** '+period_text(result.get('previous_period',{}))+'.')
  for row in result.get('comparison',[]):
   currency=row['currency'];pending_a=row.get('pending_current');pending_b=row.get('pending_previous')
   pending_percent=None
   if pending_a is not None and pending_b is not None and Decimal(pending_b)!=0 and not row.get('incomplete'):pending_percent=(Decimal(pending_a)-Decimal(pending_b))*100/Decimal(pending_b)
   text.append('| Chỉ tiêu | Kỳ A | Kỳ B | Chênh lệch A − B | Thay đổi |\n|---|---:|---:|---:|---:|\n'+
    '| Đã duyệt | '+amount(row['approved_current'],currency)+' | '+amount(row['approved_previous'],currency)+' | '+amount(row['difference'],currency)+' | '+percent(row['change_percent'])+' |\n'+
    '| Đang chờ | '+amount(pending_a,currency)+' | '+amount(pending_b,currency)+' | '+amount(row.get('pending_difference'),currency)+' | '+percent(pending_percent)+' |')
   if row.get('incomplete') or row.get('change_percent') is None:text.append('Chưa tính tỷ lệ khi còn thiếu dữ liệu hoặc số tiền kỳ đối chiếu bằng 0; không tự suy ra nguyên nhân biến động.')
 if result.get('filters',{}).get('group')=='category' and rows:
  table=['| Danh mục | Hóa đơn | Đã duyệt | Đang chờ | VAT |','|---|---:|---:|---:|---:|']
  for row in rows:table.append('| '+cell(finance.CATEGORIES.get(row['label'],row['label']))+' | '+str(row['count'])+' | '+amount(row['approved'],row['currency'])+' | '+amount(row['pending'],row['currency'])+' | '+amount(None if row.get('missing_vat') else row.get('vat'),row['currency'])+' |')
  text.append('\n'.join(table))
 text.append('Phạm vi: '+('hóa đơn của bạn' if result.get('scope')=='own' else 'hóa đơn đơn vị')+'; '+period_text(result.get('filters',{}))+'. Các tiền tệ được cộng riêng.')
 statuses=result.get('invoice_status_counts',{})
 if statuses:text.append('Số bản ghi trước khi loại trùng: '+', '.join(f"{ {'draft':'nháp','pending':'đang chờ','approved':'đã duyệt','rejected':'từ chối'}.get(k,k)}: {v}" for k,v in statuses.items())+'.')
 text.append('Tổng chi tiêu không tính nháp, từ chối, chứng từ phi tài chính và bản trùng có đủ bằng chứng; ưu tiên bản đã duyệt. Không loại chỉ vì ảnh tương tự.')
 if any(row.get('missing_vat',0) for row in rows):text.append('VAT còn thiếu dữ liệu, không được xác nhận là 0.')
 if request.get('export'):text.insert(0,'Đã tạo tệp Excel theo kết quả này. Chọn **Xuất Excel** bên dưới để tải xuống.')
 return '\n\n'.join(text)
