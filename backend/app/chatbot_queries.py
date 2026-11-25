"""Controlled, parameterized chat intent parsing and database aggregate queries."""
from __future__ import annotations

import calendar
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Invoice, InvoiceFile, Schedule, User

VN_TZ = ZoneInfo('Asia/Ho_Chi_Minh')
_MONTHS = {'thang 1':'01','thang 2':'02','thang 3':'03','thang 4':'04','thang 5':'05','thang 6':'06',
           'thang 7':'07','thang 8':'08','thang 9':'09','thang 10':'10','thang 11':'11','thang 12':'12'}


def normalize(text: str) -> str:
    value=unicodedata.normalize('NFD',(text or '').casefold())
    return ''.join(ch for ch in value if unicodedata.category(ch)!='Mn').replace('đ','d')


def _period(question: str) -> str | None:
    q=normalize(question)
    aliases={
        'today':('hom nay','today'), 'yesterday':('hom qua','yesterday'),
        'this_week':('tuan nay','tuan hien tai','this week'), 'last_week':('tuan truoc','tuan vua roi','last week'),
        'this_month':('thang nay','thang hien tai','this month'), 'last_month':('thang truoc','thang vua roi','last month'),
        'this_quarter':('quy nay','quy hien tai','this quarter'), 'last_quarter':('quy truoc','quy vua roi','last quarter'),
        'this_year':('nam nay','nam hien tai','this year'), 'last_year':('nam truoc','nam vua roi','last year'),
    }
    for period,terms in aliases.items():
        if any(t in q for t in terms): return period
    range_match=re.search(r'(?:tu\s+)?(\d{1,2}/\d{1,2}/\d{4})\s+den\s+(\d{1,2}/\d{1,2}/\d{4})',q)
    if range_match:
        try:
            start=datetime.strptime(range_match.group(1),'%d/%m/%Y').date()
            end=datetime.strptime(range_match.group(2),'%d/%m/%Y').date()
            return f'range:{start.isoformat()}:{end.isoformat()}' if end>=start else None
        except ValueError: return None
    date_match=re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',q)
    if date_match:
        d,m,y=map(int,date_match.groups())
        try: return f'date:{date(y,m,d).isoformat()}'
        except ValueError: return None
    iso_month=re.search(r'\b(20\d{2})-(0[1-9]|1[0-2])\b',q)
    if iso_month: return f'month:{iso_month.group(1)}-{iso_month.group(2)}'
    month_match=re.search(r'\bthang\s+(\d{1,2})(?:\s+nam\s+(\d{4}))?\b',q)
    if month_match:
        month=int(month_match.group(1)); year=int(month_match.group(2) or datetime.now(VN_TZ).year)
        if 1<=month<=12: return f'month:{year:04d}-{month:02d}'
    year_match=re.search(r'\bnam\s+(20\d{2})\b',q)
    if year_match: return f'year:{year_match.group(1)}'
    quarter_match=re.search(r'\bquy\s+([1-4])(?:\s+nam\s+(20\d{2}))?\b',q)
    if quarter_match:
        quarter=int(quarter_match.group(1)); year=int(quarter_match.group(2) or datetime.now(VN_TZ).year)
        return f'quarter:{year}:{quarter}'
    return None


def _date_group(q: str) -> str | None:
    if any(x in q for x in ('theo ngay','tung ngay','moi ngay')): return 'day'
    if any(x in q for x in ('theo thang','tung thang','moi thang')): return 'month'
    if any(x in q for x in ('theo quy','tung quy','moi quy')): return 'quarter'
    if any(x in q for x in ('theo nam','tung nam','moi nam')): return 'year'
    return None


def _single_plan(question: str) -> dict[str, Any]:
    q=normalize(question)
    plan={k:None for k in ('domain','metric','amount_field','status_field','status_filter','group_by','period','scope','format','percentage')}
    plan['format']='table' if any(x in q for x in ('bang','table','dinh dang bang')) else ('list' if any(x in q for x in ('danh sach','liet ke','list')) else None)
    plan['period']=_period(question)
    plan['group_by']=_date_group(q)
    if any(x in q for x in ('cua toi','cua minh','toi gui','toi da gui','toi tai len','do toi','ca nhan','my invoices','my trips','my schedule','my total','my amount','my expenses','my cost')):
        plan['scope']='personal'
    elif any(x in q for x in ('toan he thong','toan cong ty','tat ca nhan vien','toan bo')):
        plan['scope']='organization'
    plan['percentage']=any(x in q for x in ('ty le','phan tram','percentage','%'))
    schedule_terms=('lich cong tac','lich su cong tac','chuyen cong tac','chuyen di','business trip','business trips','trips','lich trinh')
    invoice_terms=('hoa don','chung tu','invoice','chi phi','tong tien','thanh toan','vat','thue gtgt','truoc thue','amount','spending','cost','expense')
    employee_terms=('nhan vien','nhan su','employee','nguoi dung')
    if any(x in q for x in schedule_terms):
        plan['domain']='schedule';plan['metric']='schedule_stats'
        if any(x in q for x in ('theo nhan vien','by employee','per employee')): plan['group_by']='employee'
    elif any(x in q for x in employee_terms) and any(x in q for x in ('bao nhieu','so luong','dem','tong so')) and not any(x in q for x in invoice_terms):
        plan['domain']='employee';plan['metric']='employee_count'
    elif any(x in q for x in (*invoice_terms,'nha cung cap','supplier','vendor')):
        plan['domain']='invoice'
        if 'nha cung cap' in q or 'supplier' in q or 'vendor' in q:
            if any(x in q for x in ('theo nha cung cap','theo supplier','theo vendor','nha cung cap nao','nha cung cap nao')):
                plan['group_by']='supplier'
        if 'nhan vien' in q or 'employee' in q:
            if any(x in q for x in ('theo nhan vien','theo employee','nhan vien nao','nhan su nao')):
                plan['group_by']='employee'
        if any(x in q for x in ('theo trang thai','trang thai nao','phan bo trang thai','statut distribution','status breakdown')):
            plan['metric']='status_distribution';plan['group_by']='status'
            if any(x in q for x in ('kiem tra','ra soat','validation')): plan['status_field']='validation_status'
            elif any(x in q for x in ('tra cuu','lookup','ma so thue')): plan['status_field']='lookup_status'
            else: plan['status_field']='approval_status'
        elif any(x in q for x in ('truoc thue','chua thue','subtotal')):
            plan['metric']='amount';plan['amount_field']='subtotal'
        elif any(x in q for x in ('thue','vat','gtgt')):
            plan['metric']='amount';plan['amount_field']='vat_amount'
        elif any(x in q for x in ('tong tien','tong chi phi','chi phi','thanh toan','amount','spending','cost')):
            plan['metric']='amount';plan['amount_field']='total_amount'
        elif any(x in q for x in ('cho duyet','dang cho','da duyet','phe duyet','tu choi','bi tu choi','ban nhap')):
            plan['metric']='count';plan['status_field']='approval_status'
        elif any(x in q for x in ('kiem tra','ra soat','hop le','needs review')):
            plan['metric']='count';plan['status_field']='validation_status'
        elif any(x in q for x in ('tra cuu','ma so thue','lookup')):
            plan['metric']='count';plan['status_field']='lookup_status'
        elif any(x in q for x in ('trang thai','status')):
            plan['metric']='status_distribution';plan['group_by']=plan['group_by'] or 'status'
        elif any(x in q for x in ('bao nhieu','so luong','so hoa don','how many','number of','dem','tong so','count')):
            plan['metric']='count'
        elif plan['group_by']:
            plan['metric']='summary'
        else:
            plan['metric']='summary'
        status_map={
            'approved':('da duyet','phe duyet','approved'),
            'submitted':('cho duyet','dang cho','dang xu ly','pending'),
            'rejected':('tu choi','bi tu choi','rejected'),
            'draft':('ban nhap','draft'),
            'needs_review':('can kiem tra','can ra soat','needs review'),
            'valid':('hop le','valid'), 'not_checked':('chua tra cuu','not checked'),
        }
        for status,terms in status_map.items():
            if any(term in q for term in terms):
                plan['status_filter']=status
                if plan['metric'] is None: plan['metric']='count'
                break
    # Resolve status-only follow-ups such as “còn bao nhiêu đang chờ?” from prior context.
    status_map={
        'approved':('da duyet','phe duyet','approved'), 'submitted':('cho duyet','dang cho','dang xu ly','pending'),
        'rejected':('tu choi','bi tu choi','rejected'), 'draft':('ban nhap','draft'),
        'needs_review':('can kiem tra','can ra soat','needs review'), 'valid':('hop le','valid'),
        'not_checked':('chua tra cuu','not checked'),
    }
    if plan['status_filter'] is None:
        for status,terms in status_map.items():
            if any(term in q for term in terms):
                plan['status_filter']=status;break
    if plan['domain'] is None and plan['status_filter']:
        plan['domain']='invoice';plan['metric']='count'
    if plan['status_filter'] in ('needs_review','valid'):
        plan['status_field']='validation_status'
    elif plan['status_filter']=='not_checked':
        plan['status_field']='lookup_status'
    elif plan['status_filter']:
        plan['status_field']='approval_status'
    if plan['domain']=='invoice' and plan['status_filter'] is None and any(term in q for term in ('trang thai','theo status','status distribution')):
        plan['metric']='status_distribution';plan['group_by']='status'
    return plan


def parse_plan(question: str, previous_question: str | None = None, role: str = 'employee',
               previous_context: dict[str,Any] | None = None) -> dict[str, Any]:
    current=_single_plan(question)
    previous=previous_context or (_single_plan(previous_question) if previous_question else None)
    q=normalize(question).strip(' ?.!')
    has_context=bool(previous and previous.get('domain') and previous.get('domain')!='unsupported')
    continuation_starters=('trong do','con ','vay ','the con','noi them','noi ro hon','cu the hon','what about','and those')
    short_query=len(q.split())<=8
    is_pure_refinement=short_query and (
        (current['period'] is not None and not any(term in q for term in ('thoi tiet','tin tuc','su kien','lich su','gia dinh','chuyen gi','cong viec','ke chuyen')))
        or (current['format'] is not None and any(term in q for term in ('dinh dang','trinh bay','duoi dang','bang','danh sach','as table','as list','ket qua')))
    )
    contextual=has_context and (
        any(x in q for x in continuation_starters)
        or is_pure_refinement
    )
    if contextual:
        merged=previous.copy()
        for key,value in current.items():
            if value is not None: merged[key]=value
        # A continuation changes only the explicitly requested measure/status/period/format.
        if current['metric'] is None: merged['metric']=previous['metric']
        if current['group_by'] is None: merged['group_by']=previous['group_by']
        if current['amount_field'] is None and current['metric']!='amount': merged['amount_field']=previous['amount_field']
        if current['status_field'] is None and current['status_filter'] is None: merged['status_field']=previous['status_field']
        if current['scope'] is None: merged['scope']=previous['scope']
        if current['format'] is None: merged['format']=previous['format']
        plan=merged
    else:
        plan=current
    if plan['domain'] is None: plan['domain']='unsupported'
    if plan['scope'] is None: plan['scope']='personal' if role=='employee' else 'organization'
    if plan['format'] is None: plan['format']='text'
    plan['contextual']=bool(contextual)
    plan['previous_domain']=previous.get('domain') if contextual and previous else None
    return plan


def classify_chat_question(question: str, role: str = 'employee', previous_context: dict[str,Any] | None = None) -> dict[str,Any]:
    """Route a question without an extra model call or an unnecessary database query."""
    q=normalize(question)
    security_patterns=(
        r'\b(select\s+.+\s+from|drop\s+table|delete\s+from|database\s+dump)\b',
        r'\b(api[_\s-]?key|secret[_\s-]?key|access[_\s-]?token|system[_\s-]?prompt|prompt\s+he\s+thong|khoa\s+bi\s+mat)\b',
        r'\b(mat\s+khau|password)\b',
        r'(show|reveal|give|print|tell|cho|tiet\s+lo|dua|in|gui).{0,35}(api|key|token|password|mat\s+khau|prompt)',
        r'(toan bo|tat ca|moi).{0,45}(noi dung hoa don|anh hoa don|du lieu ca nhan|email|so dien thoai)',
        r'(invoice (number|id)\s*#?\s*\w+).{0,40}(full|raw|ocr|content|image|detail)',
        r'(ignore\s+previous|bo\s+qua\s+(moi\s+)?(chi\s+dan|quy\s+tac|huong\s+dan))',
    )
    if any(re.search(pattern,q) for pattern in security_patterns):
        return {'kind':'security','plan':None}
    plan=parse_plan(question,role=role,previous_context=previous_context)
    if plan['domain']!='unsupported':
        analysis_terms=('phan tich','so sanh','xu huong','ty trong','danh gia','tai sao','vi sao','du bao')
        analysis=bool(plan.get('group_by') or plan.get('percentage') or plan.get('format') in ('table','list')
                      or any(term in q for term in analysis_terms))
        return {'kind':'analysis' if analysis else 'business','plan':plan}
    return {'kind':'ordinary','plan':plan}


def period_bounds(period: str | None, today: date | None = None) -> tuple[date | None,date | None]:
    if not period: return None,None
    today=today or datetime.now(VN_TZ).date()
    if period=='today': return today,today
    if period=='yesterday': return today-timedelta(days=1),today-timedelta(days=1)
    if period in ('this_week','last_week'):
        start=today-timedelta(days=today.weekday())
        if period=='last_week': start-=timedelta(days=7)
        return start,start+timedelta(days=6)
    if period in ('this_month','last_month'):
        first=today.replace(day=1)
        if period=='last_month': first=(first-timedelta(days=1)).replace(day=1)
        last=first.replace(day=calendar.monthrange(first.year,first.month)[1])
        return first,last
    if period in ('this_quarter','last_quarter'):
        quarter=(today.month-1)//3+1
        if period=='last_quarter':
            quarter-=1
            if quarter==0: quarter=4; year=today.year-1
            else: year=today.year
        else: year=today.year
        start_month=(quarter-1)*3+1
        start=date(year,start_month,1)
        end=date(year,start_month+2,calendar.monthrange(year,start_month+2)[1])
        return start,end
    if period in ('this_year','last_year'):
        year=today.year if period=='this_year' else today.year-1
        return date(year,1,1),date(year,12,31)
    if period.startswith('date:'):
        value=date.fromisoformat(period[5:]);return value,value
    if period.startswith('range:'):
        _,start,end=period.split(':');return date.fromisoformat(start),date.fromisoformat(end)
    if period.startswith('month:'):
        year,month=map(int,period[6:].split('-'))
        start=date(year,month,1);return start,date(year,month,calendar.monthrange(year,month)[1])
    if period.startswith('year:'):
        year=int(period[5:]);return date(year,1,1),date(year,12,31)
    if period.startswith('quarter:'):
        _,year,quarter=period.split(':');year=int(year);quarter=int(quarter)
        month=(quarter-1)*3+1;start=date(year,month,1)
        return start,date(year,month+2,calendar.monthrange(year,month+2)[1])
    return None,None


def _bucket(value: date | datetime | None, by: str | None) -> str:
    if value is None: return 'Chưa có ngày'
    d=value.date() if isinstance(value,datetime) else value
    if by=='day': return d.isoformat()
    if by=='month': return d.strftime('%Y-%m')
    if by=='quarter': return f'{d.year}-Q{(d.month-1)//3+1}'
    if by=='year': return str(d.year)
    return ''


def _format_vnd(value: Decimal) -> str:
    from decimal import ROUND_HALF_UP
    rounded=value.quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    return f"{int(rounded):,}".replace(',','.')+' ₫'


def query_aggregates(db: Session, user: Any, plan: dict[str, Any], base_invoice_query):
    """Return privacy-safe aggregates and a backend-only map for display labels."""
    start,end=period_bounds(plan.get('period'))
    facts:dict[str,Any]={'scope':plan['scope'],'period':plan.get('period'),'metric':plan.get('metric')}
    facts['period_start']=start.isoformat() if start else None
    facts['period_end']=end.isoformat() if end else None
    labels:dict[str,str]={}
    domain=plan['domain'];metric=plan.get('metric');group=plan.get('group_by')
    if domain=='unsupported': return {'facts':facts,'labels':labels}
    if domain=='employee' and user.role=='employee':
        return {'facts':facts|{'denied':True},'labels':labels}
    if domain=='employee':
        count=db.scalar(select(func.count(User.id)).where(User.role=='employee',User.status=='active')) or 0
        facts['employee_count']=int(count)
        return {'facts':facts,'labels':labels}
    if domain=='schedule':
        query=select(Schedule)
        if user.role in ('employee', 'accountant') or plan['scope']=='personal': query=query.where(Schedule.assigned_to==user.id)
        if start: query=query.where(Schedule.starts_at>=datetime.combine(start,datetime.min.time(),tzinfo=VN_TZ))
        if end: query=query.where(Schedule.starts_at<datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=VN_TZ))
        schedules=db.scalars(query.order_by(Schedule.starts_at)).all()
        counts=defaultdict(int)
        for item in schedules:
            key=_bucket(item.starts_at,group) if group in ('day','month','quarter','year') else item.status or 'unknown'
            counts[key]+=1
        if group=='employee':
            ids={item.assigned_to for item in schedules}
            users=db.scalars(select(User).where(User.id.in_(ids))).all() if ids else []
            lookup={u.id:u.full_name for u in users};counts.clear()
            for item in schedules: counts[item.assigned_to]+=1
            for n,(uid,count) in enumerate(sorted(counts.items(),key=lambda x:x[1],reverse=True),1):
                token=f'__ROW_{n}__';labels[token]=lookup.get(uid,'Nhân viên')
                facts.setdefault('rows',[]).append({'label':token,'count':count})
        elif group:
            facts['rows']=[{'label':key,'count':count} for key,count in sorted(counts.items())]
        else:
            facts.update({'schedule_count':len(schedules),'schedule_status_counts':dict(counts)})
        return {'facts':facts,'labels':labels}
    if domain!='invoice': return {'facts':facts,'labels':labels}
    query=base_invoice_query.add_columns(InvoiceFile.uploaded_by)
    if plan['scope']=='personal' and user.role!='employee': query=query.where(InvoiceFile.uploaded_by==user.id)
    if start: query=query.where(Invoice.invoice_date>=start)
    if end: query=query.where(Invoice.invoice_date<=end)
    period_scope_query=query
    status_field=plan.get('status_field') or 'approval_status'
    status_filter=plan.get('status_filter')
    if status_filter:
        if status_filter in ('needs_review','valid'): query=query.where(Invoice.validation_status==status_filter)
        elif status_filter=='not_checked': query=query.where(Invoice.lookup_status==status_filter)
        else: query=query.where(getattr(Invoice,'approval_status')==status_filter)
    selected=(Invoice.invoice_date,Invoice.seller_name,Invoice.approval_status,Invoice.validation_status,
              Invoice.lookup_status,Invoice.subtotal,Invoice.vat_amount,Invoice.total_amount,InvoiceFile.uploaded_by)
    rows=db.execute(query.with_only_columns(*selected)).all()
    field=plan.get('amount_field') or 'total_amount'
    if metric=='status_distribution':
        counts=defaultdict(int)
        attr={'approval_status':'approval_status','validation_status':'validation_status','lookup_status':'lookup_status'}.get(status_field,'approval_status')
        for row in rows: counts[getattr(row,attr) or 'unknown']+=1
        denominator=sum(counts.values())
        facts['status_type']=status_field
        facts['rows']=[{'label':k,'count':v,**({'percentage':round(v*100/denominator,1)} if plan.get('percentage') and denominator else {})} for k,v in sorted(counts.items())]
        return {'facts':facts,'labels':labels}
    if metric=='employee_count': return {'facts':facts|{'employee_count':0},'labels':labels}
    if metric=='count' and status_filter:
        facts.update({'invoice_count':len(rows),'status_filter':status_filter})
        if plan.get('percentage'):
            total_count=int(db.scalar(period_scope_query.with_only_columns(func.count(Invoice.id)).order_by(None)) or 0)
            facts.update({'total_count':total_count,'percentage':round(len(rows)*100/total_count,1) if total_count else 0})
        return {'facts':facts,'labels':labels}
    if group in ('supplier','employee','day','month','quarter','year'):
        grouped=defaultdict(lambda:{'count':0,'amount':Decimal('0'),'known_amounts':0})
        employee_names={}
        if group=='employee':
            ids={r.uploaded_by for r in rows}
            users=db.scalars(select(User).where(User.id.in_(ids))).all() if ids else []
            employee_names={u.id:u.full_name for u in users}
        for row in rows:
            if group=='supplier': key=row.seller_name or 'Chưa cập nhật nhà cung cấp'
            elif group=='employee': key=row.uploaded_by
            elif group in ('day','month','quarter','year'): key=_bucket(row.invoice_date,group)
            else: key='unknown'
            grouped[key]['count']+=1
            amount=getattr(row,field)
            if amount is not None: grouped[key]['amount']+=Decimal(str(amount));grouped[key]['known_amounts']+=1
        sorted_groups=sorted(grouped.items(),key=lambda pair:(pair[1]['amount'] if metric=='amount' else pair[1]['count']),reverse=True)
        for n,(key,value) in enumerate(sorted_groups,1):
            token=f'__ROW_{n}__'
            if group=='supplier': labels[token]=str(key)
            elif group=='employee': labels[token]=employee_names.get(key,'Nhân viên')
            else: labels[token]=str(key)
            result={'label':token,'count':value['count']}
            if metric in ('amount','summary'):
                result.update({'known_amounts':value['known_amounts'],'amount':str(value['amount']),
                               'formatted_vnd':_format_vnd(value['amount'])})
            facts.setdefault('rows',[]).append(result)
        facts['group_by']=group;facts['metric']=metric
        facts['truncated']=len(sorted_groups)>30
        facts['rows']=facts.get('rows',[])[:30]
        if plan.get('percentage'):
            denominator=sum((r.get('amount',Decimal('0')) for r in facts['rows']),Decimal('0')) if metric=='amount' else sum(r['count'] for r in facts['rows'])
            for row in facts['rows']:
                value=row.get('amount',Decimal('0')) if metric=='amount' else row['count']
                row['percentage']=round(float(value*100/denominator),1) if denominator else 0
        return {'facts':facts,'labels':labels}
    if metric=='count': facts['invoice_count']=len(rows)
    elif metric=='amount':
        values=[getattr(r,field) for r in rows if getattr(r,field) is not None]
        total=sum((Decimal(str(v)) for v in values),Decimal('0'))
        facts.update({'amount_field':field,'known_amounts':len(values),'missing_amounts':len(rows)-len(values)})
        if values: facts.update({'amount':str(total),'formatted_vnd':_format_vnd(total)})
    else:
        facts['invoice_count']=len(rows)
        totals={}
        for name in ('subtotal','vat_amount','total_amount'):
            vals=[getattr(r,name) for r in rows if getattr(r,name) is not None]
            value=sum((Decimal(str(v)) for v in vals),Decimal('0'))
            if vals: totals[name]={'known_amounts':len(vals),'formatted_vnd':_format_vnd(value)}
        facts['totals']=totals
    return {'facts':facts,'labels':labels}


def apply_display_labels(answer: str, labels: dict[str,str]) -> str:
    for token,label in labels.items(): answer=answer.replace(token,label)
    return answer


def render_fallback(plan: dict[str,Any], facts: dict[str,Any], labels: dict[str,str] | None = None) -> str:
    """Render trustworthy aggregate data locally when Gemini is unavailable or misses format."""
    labels=labels or {}
    if facts.get('denied'):
        return 'Bạn không có quyền xem thống kê nhân viên khác.'
    if plan.get('domain')=='unsupported':
        return 'Bạn có thể hỏi về số lượng, tổng tiền, trạng thái hóa đơn, thống kê theo thời gian/nhà cung cấp/nhân viên hoặc lịch công tác. Bạn muốn xem mục nào?'
    metric=plan.get('metric');rows=facts.get('rows') or []
    title={'invoice':'Hóa đơn','schedule':'Lịch công tác','employee':'Nhân viên'}.get(plan.get('domain'),'Kết quả thống kê')
    period=''
    if facts.get('period_start') and facts.get('period_end'):
        period=f" trong khoảng {facts['period_start']} đến {facts['period_end']}"
    if metric=='employee_count':
        result=f"Có {facts.get('employee_count',0)} nhân viên đang hoạt động{period}."
    elif metric=='count':
        status_labels={'draft':'bản nháp','submitted':'chờ phê duyệt','pending':'chờ phê duyệt',
                       'approved':'đã phê duyệt','rejected':'từ chối','needs_review':'cần kiểm tra',
                       'valid':'hợp lệ','not_checked':'chưa tra cứu'}
        status=f" có trạng thái {status_labels.get(facts['status_filter'],facts['status_filter'])}" if facts.get('status_filter') else ''
        result=f"Có {facts.get('invoice_count',0)} hóa đơn{status}{period} trong {facts.get('scope','phạm vi được cấp quyền')}."
        if 'percentage' in facts:
            result+=f" Tỷ lệ trên tổng {facts.get('total_count',0)} hóa đơn là {facts['percentage']:.1f}%."
    elif metric=='amount':
        if 'formatted_vnd' not in facts:
            result='Chưa có dữ liệu phù hợp để tính khoản tiền được hỏi; hệ thống không tự ước tính.'
        else:
            result=f"Tổng tiền theo dữ liệu hiện có là {facts['formatted_vnd']}{period}."
            if facts.get('missing_amounts'): result+=f" Có {facts['missing_amounts']} hóa đơn chưa có dữ liệu trường tiền này."
    elif rows:
        group=plan.get('group_by') or 'trạng thái'
        headers=['Nhóm', 'Số lượng']
        if any('formatted_vnd' in row for row in rows): headers.append('Tổng tiền (VND)')
        if any('percentage' in row for row in rows): headers.append('Tỷ lệ (%)')
        if plan.get('format')=='table':
            lines=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
            for row in rows:
                key=row.get('label','Chưa cập nhật')
                display=labels.get(key,key)
                if group=='status': display={
                    'draft':'Bản nháp','submitted':'Chờ phê duyệt','pending':'Chờ phê duyệt',
                    'approved':'Đã phê duyệt','rejected':'Từ chối','valid':'Hợp lệ',
                    'needs_review':'Cần kiểm tra','not_checked':'Chưa tra cứu','unknown':'Chưa cập nhật',
                }.get(key,key)
                cells=[display,str(row.get('count',''))]
                if 'formatted_vnd' in row: cells.append(row['formatted_vnd'])
                if 'percentage' in row: cells.append(f"{row['percentage']:.1f}%")
                lines.append('| '+' | '.join(cells)+' |')
            result='\n'.join(lines)
        elif plan.get('format')=='list':
            result='\n'.join(f"- {labels.get(row.get('label',''),row.get('label',''))}: {row.get('count',0)}"+ (f" ({row['formatted_vnd']})" if 'formatted_vnd' in row else '') for row in rows)
        else:
            if group=='status':
                status_labels={'draft':'bản nháp','submitted':'chờ phê duyệt','pending':'chờ phê duyệt',
                               'approved':'đã phê duyệt','rejected':'từ chối','needs_review':'cần kiểm tra',
                               'valid':'hợp lệ','not_checked':'chưa tra cứu','unknown':'chưa cập nhật'}
                detail=', '.join(f"{status_labels.get(row.get('label'),row.get('label'))}: {row.get('count',0)}" for row in rows)
                result=f"Trạng thái hóa đơn{period}: {detail}."
            else:
                result=f"Có {sum(row.get('count',0) for row in rows)} mục thống kê {group}{period}."
    elif metric=='status_distribution':
        result=f"Chưa có hóa đơn để thống kê trạng thái{period}."
    elif metric=='summary':
        count=facts.get('invoice_count')
        result=f"Có {count} hóa đơn{period}." if count is not None else f"Chưa có dữ liệu {title.lower()}{period}."
        totals=facts.get('totals') or {}
        if totals:
            result+=' Tổng tiền thanh toán: '+totals.get('total_amount',{}).get('formatted_vnd','chưa cập nhật')+'.'
        if plan.get('format')=='table':
            lines=['| Chỉ số | Giá trị |','| --- | --- |']
            if count is not None: lines.append(f"| Số hóa đơn | {count} |")
            for key,label in (('subtotal','Trước thuế'),('vat_amount','VAT'),('total_amount','Thanh toán')):
                if key in totals: lines.append(f"| {label} | {totals[key]['formatted_vnd']} |")
            result='\n'.join(lines)
    elif metric=='schedule_stats':
        count=facts.get('schedule_count',0)
        result=f"Có {count} chuyến công tác{period}."
        if facts.get('schedule_status_counts'):
            result+=' Trạng thái: '+', '.join(f"{k}: {v}" for k,v in facts['schedule_status_counts'].items())+'.'
    else:
        result=f"Chưa có dữ liệu phù hợp cho yêu cầu {title.lower()}{period}."
    if plan.get('format')=='table' and not result.lstrip().startswith('|'):
        result='| Chỉ số | Giá trị |\n| --- | --- |\n| Kết quả | '+result+' |'
    return result
