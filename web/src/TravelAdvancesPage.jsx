import React, {useEffect, useRef, useState} from 'react';
import {Link, useSearchParams} from 'react-router-dom';
import {api} from './api';

const states = {
  draft: 'Nháp', pending: 'Chờ duyệt tạm ứng', approved: 'Đã duyệt', disbursed: 'Đã chi tạm ứng',
  settlement_pending: 'Chờ quyết toán', checking: 'Đang kiểm tra chứng từ',
  refund_due: 'Chờ hoàn tiền', supplement_due: 'Chờ thanh toán bổ sung',
  settled: 'Đã quyết toán', rejected: 'Từ chối', cancelled: 'Đã hủy',
};
const categories = {
  allowance: 'Công tác phí / phụ cấp', lodging: 'Khách sạn / lưu trú', tickets: 'Vé máy bay, tàu, xe',
  transport: 'Taxi và di chuyển', meals: 'Ăn uống theo chính sách', other: 'Chi phí khác',
};
const actions = {
  created: 'Tạo hồ sơ', submit: 'Gửi duyệt', approve: 'Duyệt tạm ứng', reject: 'Từ chối tạm ứng',
  cancel: 'Hủy hồ sơ', disburse: 'Ghi nhận chi tạm ứng', request_settlement: 'Gửi đề nghị quyết toán',
  review: 'Bắt đầu kiểm tra chứng từ', settle: 'Lập quyết toán', expense_added: 'Bổ sung chứng từ',
  expense_reviewed: 'Kiểm tra khoản chi', refund: 'Ghi nhận nhân viên hoàn tiền',
  supplement: 'Ghi nhận công ty thanh toán thêm', payment_evidence: 'Đính kèm chứng từ giao dịch',
};
const moneyFields = {
  requested: 'Đề nghị', approved: 'Được duyệt', disbursed: 'Đã chi tạm ứng', accepted: 'Chi phí hợp lệ',
  refund_due: 'Nhân viên phải hoàn', refunded: 'Nhân viên đã hoàn', refund_remaining: 'Nhân viên còn phải hoàn',
  supplement_due: 'Công ty phải thanh toán thêm', supplemented: 'Công ty đã thanh toán thêm',
  supplement_remaining: 'Công ty còn phải thanh toán',
};
const invoiceStates = {
  draft: 'Nháp', pending: 'Chờ phê duyệt', approved: 'Đã phê duyệt', rejected: 'Từ chối',
  valid: 'Hợp lệ', needs_review: 'Cần kiểm tra', error: 'Lỗi', verified: 'Đã xác minh',
  mismatch: 'Không khớp', not_found: 'Không tìm thấy', not_checked: 'Chưa tra cứu',
  not_applicable: 'Không áp dụng', invalid: 'Không hợp lệ',
};
const expenseStates = {pending: 'Chờ kiểm tra', accepted: 'Đã chấp nhận', excluded: 'Đã loại trừ'};
const base = '/travel-advances';
const cash = new Intl.NumberFormat('vi-VN', {style: 'currency', currency: 'VND', maximumFractionDigits: 2});
const displayMoney = value => value == null ? '—' : cash.format(value);
const displayDate = value => value ? value.split('-').reverse().join('/') : '—';
const localTime = value => new Date(value).toLocaleString('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh'});
const newRequest = () => Array.from(crypto.getRandomValues(new Uint32Array(4)), part => part.toString(16).padStart(8, '0')).join('');

function useResource(path, revision) {
  const [state, setState] = useState({});
  useEffect(() => {
    if (!path) return;
    let active = true;
    api(path).then(data => {
      if (active) setState({path, data});
    }).catch(error => {
      if (active) setState({path, error: error.message});
    });
    return () => { active = false; };
  }, [path, revision]);
  return state.path === path && path ? state : {};
}

function Form({children, label, disabled, onSave, reset = true}) {
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries([...new FormData(form)].filter(([, value]) => value !== ''));
    if (await onSave(data) && reset) form.reset();
  }
  return <form className="filters" onSubmit={submit}>
    <fieldset disabled={disabled} className="filters advance-fields">
      {children}
      <button type="submit" className="btn btn-primary">{label}</button>
    </fieldset>
  </form>;
}

function Amount({name = 'amount', min = '0.01', max, value}) {
  return <label>Số tiền (VND) <input required name={name} type="number" min={min} max={max} step="0.01" defaultValue={value}/></label>;
}

function ExpenseForm({row, busy, mutate}) {
  const [page, setPage] = useState(0);
  const [reload, setReload] = useState(0);
  const invoices = useResource('/invoices?limit=50&offset='+page*50, reload);
  return <details>
    <summary>Bổ sung chứng từ</summary>
    <p><Link to="/upload" target="_blank">Mở trang tải hóa đơn và OCR</Link> · <button type="button" className="btn btn-outline" onClick={()=>{setPage(0);setReload(n=>n+1)}}>Tải lại chứng từ</button></p>
    {invoices.error&&<p role="alert" className="error">{invoices.error}</p>}
    <Form label="Thêm khoản chi" disabled={busy} onSave={body=>mutate(base+'/'+row.id+'/expenses',body)}>
      <label>Chứng từ <select required name="invoice_id" defaultValue="" key={page}>
        <option value="">Chọn chứng từ</option>
        {invoices.data?.map(invoice=><option key={invoice.id} value={invoice.id}>
          #{invoice.id} · {invoice.invoice_number||invoice.filename} · {displayMoney(invoice.total_amount)}
        </option>)}
      </select></label>
      <button type="button" className="btn btn-outline" disabled={page===0} onClick={()=>setPage(n=>n-1)}>Chứng từ mới hơn</button>
      <button type="button" className="btn btn-outline" disabled={invoices.data?.length!==50} onClick={()=>setPage(n=>n+1)}>Chứng từ cũ hơn</button>
      <label>Loại chi phí <select name="category">{Object.entries(categories).map(([key, text])=><option key={key} value={key}>{text}</option>)}</select></label>
      <label>Nội dung <input name="description" required maxLength={2000}/></label>
      <label>Ngày phát sinh <input name="incurred_on" required type="date"/></label>
      <Amount/>
    </Form>
  </details>;
}

function ReceiptAdvice({path}) {
  const [state,setState]=useState({});
  async function load() {
    setState({busy:true});
    try {
      const result=await api(path,{method:'POST'});
      setState({text:result.advice});
    } catch (error) {
      setState({error:error.message});
    }
  }
  return <div>
    <button type="button" className="btn btn-outline" onClick={load} disabled={state.busy}>
      {state.busy?'Đang tham vấn…':'Tham vấn Gemini từ kết quả OCR'}
    </button>
    {state.error&&<p className="error" role="alert">{state.error}</p>}
    {state.text&&<p className="advance-advice"><strong>Gợi ý đối chiếu từ Gemini</strong>{'\n'+state.text}</p>}
  </div>;
}

async function downloadFile(path, filename) {
  const response=await api(path,{raw:true});
  const url=URL.createObjectURL(await response.blob());
  const link=document.createElement('a');
  link.href=url;
  link.download=filename;
  link.click();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function PaymentEvidence({path, payment, accounting, busy, mutate}) {
  const [error,setError]=useState('');
  async function download() {
    setError('');
    try { await downloadFile(path,payment.filename); }
    catch (failure) { setError(failure.message); }
  }
  if(payment.filename)return <>
    <button type="button" className="btn btn-outline" onClick={download}>Tải {payment.filename}</button>
    {error&&<p className="error" role="alert">{error}</p>}
  </>;
  if(!accounting)return null;
  return <Form label="Đính kèm tệp" disabled={busy} onSave={({file})=>{
    const data=new FormData();
    data.append('file',file);
    return mutate(path,data);
  }}>
    <label>Tệp xác nhận <input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg" required/></label>
  </Form>;
}

function AdvanceDetail({row, user, busy, mutate}) {
  const endpoint=base+'/'+row.id;
  const action=(name,data={})=>mutate(endpoint+'/actions',{...data,action:name});
  const employee=user.role==='employee';
  const accounting=user.role==='accountant';
  const paymentKind=row.status==='refund_due'?'refund':row.status==='supplement_due'?'supplement':null;
  const simpleActions=[
    [employee&&row.status==='draft','submit'],
    [employee&&['draft','pending'].includes(row.status),'cancel'],
    [employee&&row.status==='disbursed','request_settlement'],
    [accounting&&row.status==='settlement_pending','review'],
  ];
  return <div className="advance-detail">
    <section className="advance-section">
    <h3>Thông tin tạm ứng</h3>
    <h4>{row.code} · {row.trip_title}</h4>
    <p><strong>{states[row.status]}</strong> · {row.employee_name} {[row.employee_code,row.department].filter(Boolean).join(' · ')}</p>
    <p>{displayDate(row.starts_on)} – {displayDate(row.ends_on)} · {row.reason}</p>
    {row.notes&&<p>{row.notes}</p>}
    <dl className="advance-money">
      {['requested','approved','disbursed'].map(key=><div key={key}><dt>{moneyFields[key]}</dt><dd>{displayMoney(row[key])}</dd></div>)}
    </dl>
    {row.approved_by&&<p>Người duyệt {row.events.find(event=>event.action==='approve')?.actor_name}</p>}
    {row.disbursed_on&&<p>Ngày chi tạm ứng {displayDate(row.disbursed_on)} · Người chi {row.events.find(event=>event.action==='disburse')?.actor_name}</p>}
    <div className="filters">
      {simpleActions.filter(([show])=>show).map(([,name])=><button key={name} type="button" className="btn btn-outline" disabled={busy}
        onClick={()=>{if(!['settle','cancel'].includes(name)||window.confirm(actions[name]+'?'))action(name)}}>{actions[name]}</button>)}
    </div>
    {row.can_approve&&row.status==='pending'&&<>
      <Form label={actions.approve} disabled={busy} onSave={data=>action('approve',data)}>
        <Amount max={row.requested} value={row.requested}/>
        <label>Ghi chú <input name="reason" maxLength={2000}/></label>
      </Form>
      <Form label={actions.reject} disabled={busy} onSave={data=>action('reject',data)}>
        <label>Lý do từ chối <input name="reason" required maxLength={2000}/></label>
      </Form>
    </>}
    {accounting&&row.status==='approved'&&<Form label={actions.disburse} disabled={busy} onSave={data=>action('disburse',data)}>
      <Amount max={row.approved} value={row.approved}/>
      <label>Ngày chi <input required type="date" name="paid_on"/></label>
      <label>Ghi chú <input name="reason" maxLength={2000}/></label>
    </Form>}
    </section>
    <section className="advance-section">
    <h3>Chi phí &amp; chứng từ</h3>
    {employee&&['draft','pending','approved','disbursed','settlement_pending','checking'].includes(row.status)&&
      <ExpenseForm row={row} busy={busy} mutate={mutate}/>}
    {row.expenses.length===0&&<p>Chưa có khoản chi.</p>}
    <ul className="advance-entries">{row.expenses.map(expense=><li key={expense.id}>
      <strong>{categories[expense.category]} · {expense.description}</strong>
      <p>{displayDate(expense.incurred_on)} · {displayMoney(expense.amount)} · {expenseStates[expense.status]} · {displayMoney(expense.accepted)} được chấp nhận</p>
      <p><Link to={'/invoices/'+expense.invoice_id}>Chứng từ #{expense.invoice_id} {expense.invoice.invoice_number}</Link></p>
      <details><summary>Kết quả OCR và đối chiếu</summary><p>OCR {expense.invoice.confidence_score==null?'—':new Intl.NumberFormat('vi-VN',{style:'percent',maximumFractionDigits:1}).format(expense.invoice.confidence_score)} ·
        Kiểm tra {invoiceStates[expense.invoice.validation_status]||'—'} ·
        Xác minh {invoiceStates[expense.invoice.lookup_status]||'—'} ·
        Phê duyệt hóa đơn {invoiceStates[expense.invoice.approval_status]||'—'}</p>
      {expense.risks.map(risk=><p key={risk.code}>{risk.message}</p>)}
      {accounting&&<ReceiptAdvice path={endpoint+'/expenses/'+expense.id+'/ai-review'}/>}
      </details>
      {expense.review_reason&&<p>Đối chiếu quy định nội bộ · {expense.review_reason}</p>}
      {accounting&&row.status==='checking'&&<Form label="Lưu kết quả kiểm tra" disabled={busy} reset={false}
        onSave={body=>mutate(endpoint+'/expenses/'+expense.id,body,'PATCH')}>
        <Amount name="accepted" min="0" max={expense.amount} value={expense.accepted}/>
        <label>Kết quả đối chiếu (nhập 0 để loại trừ) <input name="reason" required maxLength={2000} defaultValue={expense.review_reason||''}/></label>
      </Form>}
    </li>)}</ul>
    </section>
    <section className="advance-section">
    <h3>Kết quả quyết toán</h3>
    <SettlementSummary row={row}/>
    {accounting&&row.status==='checking'&&<button type="button" className="btn btn-primary" disabled={busy}
      onClick={()=>{if(window.confirm(actions.settle+'?'))action('settle')}}>{actions.settle}</button>}
    {accounting&&paymentKind&&<Form label={actions[paymentKind]} disabled={busy}
      onSave={body=>mutate(endpoint+'/payments',{...body,kind:paymentKind})}>
      <Amount max={paymentKind==='refund'?row.refund_remaining:row.supplement_remaining}/>
      <label>Ngày đối soát <input type="date" name="paid_on" required min={row.disbursed_on}/></label>
      <label>Hình thức <input name="method" required maxLength={40}/></label>
      <label>Mã giao dịch / phiếu <input name="reference" required maxLength={120}/></label>
      <label>Thông tin chứng từ xác nhận <input name="evidence" required maxLength={500}/></label>
      <label>Ghi chú <input name="notes" maxLength={2000}/></label>
    </Form>}
    {row.payments.length===0&&<p>Chưa ghi nhận giao dịch.</p>}
    <ul className="advance-entries">{row.payments.map(payment=><li key={payment.id}>
      <strong>{actions[payment.kind]} · {displayMoney(payment.amount)}</strong>
      <p>{displayDate(payment.paid_on)} · {payment.method} · {payment.reference}</p>
      <p>Chứng từ {payment.evidence}{payment.notes?' · '+payment.notes:''}</p>
      <PaymentEvidence path={endpoint+'/payments/'+payment.id+'/evidence'} {...{payment,accounting,busy,mutate}}/>
    </li>)}</ul>
    <details><summary>Lịch sử xử lý</summary>
    <ol className="advance-entries">{row.events.map(event=><li key={event.id}>
      {localTime(event.created_at)} · {event.actor_name} · {actions[event.action]}
      {event.details.to&&' · '+states[event.details.to]}
      {event.details.reason&&' · '+event.details.reason}
    </li>)}</ol>
    </details>
    </section>
  </div>;
}

const roleView = {
  employee: {title:'Tạm ứng của tôi', description:'Theo dõi tạm ứng và chi phí công tác cá nhân'},
  accountant: {title:'Tạm ứng & Quyết toán', description:'Kiểm tra chứng từ và xử lý quyết toán công tác phí'},
  admin: {title:'Quản lý tạm ứng', description:'Theo dõi hoạt động tạm ứng và quyết toán toàn hệ thống'},
};

function SettlementSummary({row}) {
  const finalized=['refund_due','supplement_due','settled'].includes(row.status);
  const refund=row.status==='refund_due'||Number(row.refund_due)>0;
  const supplement=row.status==='supplement_due'||Number(row.supplement_due)>0;
  const keys=refund?['refund_due','refunded','refund_remaining']:supplement?['supplement_due','supplemented','supplement_remaining']:[];
  return <>
    <p className="advance-equation">{displayMoney(row.disbursed)} đã ứng − {displayMoney(row.accepted)} chi phí được chấp nhận = <strong>{displayMoney(row.difference)}</strong></p>
    {!finalized&&<p>Chênh lệch tạm tính theo các khoản đã được kiểm tra.</p>}
    {finalized&&keys.length===0&&<p>Không phát sinh chênh lệch.</p>}
    {keys.length>0&&<dl className="advance-money">{keys.map(key=><div key={key}><dt>{moneyFields[key]}</dt><dd>{displayMoney(row[key])}</dd></div>)}</dl>}
  </>;
}

function AdvanceSummaryCards({role, data}) {
  const total=key=>displayMoney(data?.totals[key]??0);
  const cards=role==='employee'
    ? [['Đã nhận tạm ứng',total('disbursed')],['Chi phí đã duyệt',total('accepted')],['Số tiền còn phải hoàn',total('refund_remaining')]]
    : role==='accountant'
      ? [['Tổng tiền đã chi tạm ứng',total('disbursed')],['Hồ sơ chờ xử lý',data?.pending_work],['Hồ sơ đã quyết toán',data?.settled]]
      : [['Tổng tiền đã tạm ứng',total('disbursed')],['Hồ sơ chưa quyết toán',data?.unsettled],['Hồ sơ đã hoàn tất',data?.settled]];
  return <dl className="advance-cards">{cards.map(([label,value])=><div key={label}>
    <dt>{label}</dt><dd>{data?value:'—'}</dd>
  </div>)}</dl>;
}

function AdvanceFilters({employee, search, setSearch, status, setStatus, period, setPeriod}) {
  return <div className="advance-filters">
    <label>Tìm hồ sơ<input type="search" maxLength={150} value={search} onChange={e=>setSearch(e.target.value)}
      placeholder={employee?'Nhập mã hồ sơ':'Nhập tên nhân viên hoặc mã hồ sơ'}/></label>
    <label>Trạng thái<select value={status} onChange={e=>setStatus(e.target.value)}>
      <option value="">Tất cả trạng thái</option>
      {Object.entries(states).map(([key,label])=><option key={key} value={key}>{label}</option>)}
    </select></label>
    <label>Thời gian<select value={period} onChange={e=>setPeriod(e.target.value)}>
      <option value="month">Tháng này</option><option value="quarter">Quý này</option>
      <option value="year">Năm nay</option><option value="all">Tất cả</option>
    </select></label>
  </div>;
}

function AdvanceList({items, employee, open}) {
  if(!items.length)return <p className="advance-empty">Không có hồ sơ trong phạm vi đã chọn.</p>;
  return <ul className={'advance-list'+(employee?' advance-list-personal':'')}>
    {items.map(row=><li key={row.id}>
      <div className="advance-row-identity"><strong>{employee?row.trip_title:row.employee_name}</strong><small>{row.code}</small></div>
      {!employee&&<span className="advance-row-trip">{row.trip_title}</span>}
      <div className="advance-row-amount"><small>Đã ứng</small><strong>{displayMoney(row.disbursed)}</strong></div>
      <span className="advance-status" data-status={row.status}>{states[row.status]}</span>
      <button type="button" className="btn btn-outline" aria-label={'Chi tiết '+row.code} onClick={()=>open(row.id)}>Chi tiết</button>
    </li>)}
  </ul>;
}

function AdvanceDialog({title, children, close, busy}) {
  const dialog=useRef(null);
  useEffect(()=>{
    const element=dialog.current;
    element.showModal();
    return ()=>element.close();
  },[]);
  return <dialog ref={dialog} className="advance-dialog" aria-labelledby="advance-dialog-title"
    onCancel={event=>{event.preventDefault();if(!busy)close()}}>
    <header><h2 id="advance-dialog-title">{title}</h2>
      <button type="button" className="btn btn-outline" disabled={busy} onClick={close}>Đóng</button>
    </header>
    <div className="advance-dialog-content">{children}</div>
  </dialog>;
}

export default function TravelAdvancesPage({user}) {
  const employee=user.role==='employee';
  const view=roleView[user.role];
  const [params,setParams]=useSearchParams();
  const selected=params.get('id');
  const [period,setPeriod]=useState('month');
  const [status,setStatus]=useState('');
  const [search,setSearch]=useState('');
  const [appliedSearch,setAppliedSearch]=useState('');
  const [groupBy,setGroupBy]=useState('case');
  const [revision,setRevision]=useState(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [exportError,setExportError]=useState('');
  const [creating,setCreating]=useState(false);
  const requestId=useRef(null);
  useEffect(()=>{
    const timer=setTimeout(()=>setAppliedSearch(search.trim()),250);
    return ()=>clearTimeout(timer);
  },[search]);
  const query=new URLSearchParams({period});
  if(status)query.set('status',status);
  if(appliedSearch)query.set('search',appliedSearch);
  const result=useResource(base+'?'+query,revision);
  const detail=useResource(selected?base+'/'+selected:null,revision);
  const trips=useResource(employee&&creating?'/schedules':null,revision);

  function select(id) {
    setError('');
    setParams(previous=>{
      const next=new URLSearchParams(previous);
      if(id)next.set('id',id);
      else next.delete('id');
      return next;
    });
  }

  async function mutate(path, body, method='POST') {
    if(busy)return false;
    setBusy(true);
    setError('');
    try {
      const updated=await api(path,{method,body});
      if(String(updated.id)!==selected)select(updated.id);
      setRevision(n=>n+1);
      return true;
    } catch (failure) {
      setError(failure.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    setExportError('');
    try {
      const reportQuery=new URLSearchParams(query);
      reportQuery.set('group_by',groupBy);
      await downloadFile(base+'/report.xlsx?'+reportQuery,'tam-ung-cong-tac.xlsx');
    } catch (failure) { setExportError(failure.message); }
  }

  return <div className="advance-page">
    <header className="advance-header"><div><h1>{view.title}</h1><p>{view.description}</p></div>
      {employee&&<button type="button" className="btn btn-primary" onClick={()=>{setError('');setCreating(true)}}>+ Đề nghị tạm ứng</button>}
    </header>
    <AdvanceSummaryCards role={user.role} data={result.data}/>
    <section className="panel advance-overview" aria-label="Danh sách hồ sơ">
      <AdvanceFilters {...{employee, search, setSearch, status, setStatus, period, setPeriod}}/>
      {!employee&&<details className="advance-export"><summary>Xuất báo cáo</summary>
        <label>Nhóm báo cáo <select value={groupBy} onChange={e=>setGroupBy(e.target.value)}>
          <option value="case">Theo hồ sơ</option>
          <option value="employee">Theo nhân viên</option>
          <option value="trip">Theo chuyến công tác</option>
        </select></label>
        <button type="button" className="btn btn-outline" onClick={download}>Tải Excel</button>
        {exportError&&<p role="alert" className="error">{exportError}</p>}
      </details>}
      {result.error&&<p role="alert" className="error">{result.error} <button type="button" className="btn btn-outline" onClick={()=>setRevision(n=>n+1)}>Thử lại</button></p>}
      {!result.data&&!result.error&&<p role="status">Đang tải hồ sơ…</p>}
      {result.data&&<AdvanceList items={result.data.items} employee={employee} open={select}/>}
    </section>
    {creating&&<AdvanceDialog title="Đề nghị tạm ứng" busy={busy} close={()=>{setCreating(false);setError('')}}>
      {(trips.error||error)&&<p role="alert" className="error">{trips.error||error}</p>}
      {!trips.data&&!trips.error&&<p role="status">Đang tải chuyến công tác…</p>}
      <Form label="Lưu hồ sơ nháp" disabled={busy||!trips.data} onSave={async body=>{
        const signature=JSON.stringify(body);
        if(requestId.current?.signature!==signature)requestId.current={signature,id:newRequest()};
        if(!await mutate(base,{...body,request_id:requestId.current.id}))return false;
        requestId.current=null;
        setCreating(false);
        return true;
      }}>
        <label>Chuyến công tác <select name="schedule_id" required defaultValue="">
          <option value="">Chọn chuyến công tác</option>
          {trips.data?.filter(trip=>trip.status!=='cancelled').map(trip=><option key={trip.id} value={trip.id}>{trip.title} · {displayDate(trip.start_date)}</option>)}
        </select></label>
        <Amount name="requested"/>
        <label>Lý do đề nghị (tùy chọn) <input name="reason" maxLength={2000}/></label>
        <label>Ghi chú (tùy chọn) <input name="notes" maxLength={2000}/></label>
      </Form>
    </AdvanceDialog>}
    {selected&&!creating&&<AdvanceDialog title="Chi tiết hồ sơ" busy={busy} close={()=>select(null)}>
      {(detail.error||error)&&<p role="alert" className="error">{detail.error||error}</p>}
      {!detail.data&&!detail.error&&<p role="status">Đang tải chi tiết…</p>}
      {detail.data&&<AdvanceDetail key={detail.data.id} row={detail.data} user={user} busy={busy} mutate={mutate}/>}
    </AdvanceDialog>}
  </div>;
}
