"""Local financial analytics, explainable categories and advisory budgets."""
from datetime import date,datetime,timezone
from decimal import Decimal
import unicodedata
from sqlalchemy import Integer,String,Date,Numeric,JSON,ForeignKey,UniqueConstraint,select,case
from sqlalchemy.orm import mapped_column
from .core import Base
from .models import Invoice,InvoiceFile,InvoiceItem,User,ExtractionRun

CATEGORIES={'food':'Ăn uống','transport':'Vận chuyển','travel':'Công tác','lodging':'Lưu trú',
 'office':'Văn phòng phẩm','equipment':'Thiết bị','services':'Dịch vụ','utilities':'Điện nước','other':'Chi phí khác','unclassified':'Chưa phân loại'}
RULES={'food':['nha hang','quan an','com van phong','thuc an','restaurant','coffee'],
 'transport':['taxi','cuoc xe','van chuyen','grab','ve xe'], 'travel':['cong tac','ve may bay'],
 'lodging':['khach san','luu tru','hotel'],'office':['van phong pham','giay a4','but bi'],
 'equipment':['may tinh','ban phim','o cung','laptop','thiet bi'],
 'services':['dich vu','tu van','bao tri'],'utilities':['tien dien','tien nuoc','cap nuoc']}

class ExpenseAssignment(Base):
 __tablename__='expense_assignments'
 invoice_id=mapped_column(ForeignKey('invoices.id'),primary_key=True)
 category=mapped_column(String(32),nullable=False)
 method=mapped_column(String(20),nullable=False)
 reason=mapped_column(String(1000),nullable=False)
 version=mapped_column(Integer,nullable=False,default=1)

class FinanceHistory(Base):
 __tablename__='finance_history'
 id=mapped_column(Integer,primary_key=True)
 actor_id=mapped_column(ForeignKey('users.id'),nullable=True)
 entity_type=mapped_column(String(30),nullable=False)
 entity_id=mapped_column(Integer,nullable=False)
 payload=mapped_column(JSON,nullable=False)
 created_at=mapped_column(String(40),default=lambda:datetime.now(timezone.utc).isoformat())

class Budget(Base):
 __tablename__='expense_budgets'
 id=mapped_column(Integer,primary_key=True)
 starts_on=mapped_column(Date,nullable=False)
 ends_on=mapped_column(Date,nullable=False)
 team=mapped_column(String(120),nullable=False,default='')
 category=mapped_column(String(32),nullable=False,default='')
 amount=mapped_column(Numeric(18,2),nullable=False)
 currency=mapped_column(String(3),nullable=False,default='VND')
 thresholds=mapped_column(JSON,nullable=False,default=lambda:[80,90,100])
 version=mapped_column(Integer,nullable=False,default=1)
 __table_args__=(UniqueConstraint('starts_on','ends_on','team','category','currency',name='uq_budget_scope'),)

def fold(value):
 text=unicodedata.normalize('NFD',str(value or '').lower().replace('đ','d'))
 return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())

def propose_category(invoice,items):
 text=fold(' '.join(str(row.get('description') or '') for row in items))
 hits={key:[word for word in words if word in text] for key,words in RULES.items()}
 if not any(hits.values()):
  text=fold(getattr(invoice,'seller_name',None))
  hits={key:[word for word in words if word in text] for key,words in RULES.items()}
 active=[key for key in hits if hits[key]]
 category=active[0] if len(active)==1 else 'unclassified'
 reason='Từ khóa trên chứng từ: '+', '.join(hits.get(category,[])) if category!='unclassified' else 'Chưa đủ bằng chứng hoặc có nhiều nhóm chi phí'
 return {'category':category,'reason':reason,'method':'rules'}

def classify(db,invoice,items,actor_id=None):
 prior=db.get(ExpenseAssignment,invoice.id)
 if prior:return prior
 proposal=propose_category(invoice,items);category=proposal['category'];reason=proposal['reason']
 result=ExpenseAssignment(invoice_id=invoice.id,category=category,method='rules',reason=reason,version=1)
 db.add(result);db.add(FinanceHistory(actor_id=actor_id,entity_type='category',entity_id=invoice.id,payload={'new':category,'method':'rules','reason':reason}))
 db.flush();return result

def reclassify(db,invoice,items,actor_id):
 # Explicit single-invoice action; never replace a human category.
 db.scalar(select(Invoice).where(Invoice.id==invoice.id).with_for_update())
 prior=db.scalar(select(ExpenseAssignment).where(ExpenseAssignment.invoice_id==invoice.id).with_for_update().execution_options(populate_existing=True))
 if not prior:return classify(db,invoice,items,actor_id)
 if prior.method=='manual':return prior
 proposal=propose_category(invoice,items)
 if prior.category==proposal['category'] and prior.reason==proposal['reason']:return prior
 old=prior.category;prior.category=proposal['category'];prior.reason=proposal['reason'];prior.version+=1
 db.add(FinanceHistory(actor_id=actor_id,entity_type='category',entity_id=invoice.id,payload={'old':old,'new':prior.category,'method':'rules','reason':prior.reason,'version':prior.version,'explicit_reclassification':True}))
 db.flush();return prior

def expense_rows(db,user,starts=None,ends=None,team=None,category=None,employee_id=None,supplier=None):
 q=(select(Invoice,InvoiceFile,User,ExpenseAssignment).join(InvoiceFile,Invoice.file_id==InvoiceFile.id)
    .join(User,InvoiceFile.uploaded_by==User.id).outerjoin(ExpenseAssignment,ExpenseAssignment.invoice_id==Invoice.id))
 if user.role=='employee':q=q.where(InvoiceFile.uploaded_by==user.id)
 rows=db.execute(q.order_by(case((Invoice.approval_status=='approved',0),else_=1),Invoice.id)).all();seen=set();result=[]
 from .travel import official_invoice_costs
 rows=official_invoice_costs(db,rows)
 rows.sort(key=lambda row:(not getattr(row[0],'_travel_official',False),row[0].approval_status!='approved',row[0].id))
 from sqlalchemy import func
 latest=select(func.max(ExtractionRun.id)).where(ExtractionRun.invoice_id.in_([r[0].id for r in rows])).group_by(ExtractionRun.invoice_id)
 metadata={r.invoice_id:(r.extracted_json or {}).get('_ocr',{}) for r in db.scalars(select(ExtractionRun).where(ExtractionRun.id.in_(latest))).all()}
 for invoice,file,owner,assignment in rows:
  if invoice.approval_status not in ('approved','pending') or invoice.validation_status=='error':continue
  if invoice.document_type not in ('bill','einvoice'):continue
  source=metadata.get(invoice.id) or {}
  if (source.get('financial_context') or {}).get('document_semantics',{}).get('declared_non_financial'):continue
  if (source.get('tax_verification') or {}).get('document_kind') in ('tax_registration','business_registration'):continue
  if invoice.total_amount is not None and Decimal(str(invoice.total_amount))<0:continue
  identity=(invoice.seller_tax_code,invoice.invoice_number,invoice.invoice_symbol,invoice.invoice_date,invoice.total_amount)
  keys=[('hash',file.checksum_sha256)] if file.checksum_sha256 else []
  if all(v is not None and str(v).strip() for v in identity):keys.append(('identity',identity))
  if any(key in seen for key in keys):continue
  seen.update(keys)
  # Choose the canonical expense before applying dimensions; otherwise the
  # same file can consume multiple department/category budgets.
  if starts and (not invoice.invoice_date or invoice.invoice_date<starts):continue
  if ends and (not invoice.invoice_date or invoice.invoice_date>ends):continue
  if team and owner.team!=team:continue
  if category and (assignment.category if assignment else 'unclassified')!=category:continue
  if employee_id and owner.id!=employee_id:continue
  if supplier and fold(supplier) not in fold(invoice.seller_name):continue
  result.append((invoice,file,owner,assignment))
 return result

def budget_usage(db,budget,user):
 rows=expense_rows(db,user,budget.starts_on,budget.ends_on,budget.team or None,budget.category or None)
 approved=pending=Decimal('0');missing=0
 for invoice,*_ in rows:
  if invoice.currency!=budget.currency:continue
  if invoice.total_amount is None:missing+=1;continue
  if invoice.approval_status=='approved':approved+=Decimal(str(invoice.total_amount))
  else:pending+=Decimal(str(invoice.total_amount))
 from .travel import manual_budget_cost
 manual=manual_budget_cost(db,budget,user);approved+=manual
 amount=Decimal(str(budget.amount));percent=approved*100/amount if amount>0 and not missing else None
 return {'id':budget.id,'starts_on':str(budget.starts_on),'ends_on':str(budget.ends_on),'team':budget.team,'category':budget.category,
  'currency':budget.currency,'limit':str(amount),'approved':str(approved),'pending':str(pending),'remaining':str(amount-approved) if not missing else None,
  'utilization_percent':str(percent) if percent is not None else None,'missing_amounts':missing,
  'alerts':[v for v in budget.thresholds if (percent is not None and percent>=Decimal(str(v))) or (amount==0 and approved>0)],
  'projected_over_budget':approved+pending>amount,'thresholds':budget.thresholds,'version':budget.version,'travel_manual_approved':str(manual)}

def invoice_status_counts(db,user,starts=None,ends=None,team=None,category=None,employee_id=None,supplier=None):
 from sqlalchemy import func,or_
 query=select(Invoice.approval_status,func.count()).join(InvoiceFile,Invoice.file_id==InvoiceFile.id).join(User,InvoiceFile.uploaded_by==User.id).outerjoin(ExpenseAssignment,ExpenseAssignment.invoice_id==Invoice.id)
 if user.role=='employee':query=query.where(User.id==user.id)
 if starts:query=query.where(Invoice.invoice_date>=starts)
 if ends:query=query.where(Invoice.invoice_date<=ends)
 if team:query=query.where(User.team==team)
 if employee_id:query=query.where(User.id==employee_id)
 if category:
  query=query.where(or_(ExpenseAssignment.category=='unclassified',ExpenseAssignment.invoice_id.is_(None)) if category=='unclassified' else ExpenseAssignment.category==category)
 if supplier:
  counts={}
  for status,count,name in db.execute(query.add_columns(Invoice.seller_name).group_by(Invoice.approval_status,Invoice.seller_name)).all():
   if fold(supplier) in fold(name):counts[status]=counts.get(status,0)+count
  return counts
 return dict(db.execute(query.group_by(Invoice.approval_status)).all())

def previous_period(starts,ends):
 """Calendar periods stay calendar periods; arbitrary ranges use equal days."""
 from datetime import timedelta
 from calendar import monthrange
 previous_end=starts-timedelta(days=1)
 months=(ends.year-starts.year)*12+ends.month-starts.month+1
 if starts.day==1 and ends.day==monthrange(ends.year,ends.month)[1] and months in (1,3,12):
  index=starts.year*12+starts.month-1-months
  return date(index//12,index%12+1,1),previous_end
 return starts-(ends-starts+timedelta(days=1)),previous_end

def budget_checks(db,invoice,user):
 if not invoice.invoice_date:return {'status':'insufficient_data','budgets':[]}
 assignment=db.get(ExpenseAssignment,invoice.id) if invoice.id else None
 owner=db.get(User,invoice.source_file.uploaded_by)
 budgets=db.scalars(select(Budget).where(Budget.starts_on<=invoice.invoice_date,Budget.ends_on>=invoice.invoice_date,Budget.currency==invoice.currency)).all()
 matching=[b for b in budgets if (not b.team or b.team==(owner.team or '')) and (not b.category or assignment and b.category==assignment.category)]
 if user.role=='employee':return {'status':'reviewer_required' if matching else 'not_configured','budgets':[], 'reason':'Ngân sách đơn vị chỉ hiển thị cho người có thẩm quyền.'}
 return {'status':'configured' if matching else 'not_configured','budgets':[budget_usage(db,b,user) for b in matching]}
