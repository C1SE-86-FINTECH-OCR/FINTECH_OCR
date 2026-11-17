import React,{createContext,useContext,useRef,useState,useEffect,useCallback} from 'react';
import {Routes,Route,NavLink,Navigate,useNavigate,useParams,useLocation,useSearchParams} from 'react-router-dom';
import {Home,FileUp,ClipboardCheck,CalendarDays,MessageSquare,ChartNoAxesCombined,Users,LogOut,Bell,UserCircle,Search,ArrowRight,Plus,FileText,CheckCircle2,XCircle,Clock3,RefreshCw,Download,ShieldCheck,Menu,X,Eye,Save,Send,ChevronLeft,ExternalLink,BarChart3,Trophy,Activity,AlertTriangle,Filter,Settings,Camera,ChevronDown,Pencil,UserRoundX,UserRoundCheck,Trash2} from 'lucide-react';
import {api,authStore,money,datefmt,roleName,approvalName,ROOT} from './api';
import SpendingChart from './SpendingChart';
import InvoiceDetailPage from './InvoiceDetailPage';
import EmployeeSchedulePage from './SchedulePage';
import { formatNotificationTimestamp, markAllNotificationsReadAfterSuccess, markNotificationReadAfterSuccess, notificationTypeLabel, openNotificationAfterAccessCheck, unreadNotificationCount } from './notificationState';

function useLoad(path,dependencies=[]){const [data,setData]=useState(null),[busy,setBusy]=useState(true),[error,setError]=useState('');const reload=useCallback(()=>{setBusy(true);setError('');api(path).then(setData).catch(e=>setError(e.message)).finally(()=>setBusy(false))},[path]);useEffect(()=>reload(),[reload]);return {data,busy,error,reload,setData,setError}}
const NotificationContext=createContext(null);
function Notice({message,onDismiss}){return message?<div className="toast" role="alert">{message}<button onClick={onDismiss} aria-label="Đóng"><X size={16}/></button></div>:null}
function Empty({label='Chưa có dữ liệu'}){return <div className="empty"><FileText size={30}/><span>{label}</span></div>}
function Loading(){return <div className="loading"><RefreshCw size={18} className="spin"/> Đang tải dữ liệu...</div>}
function Title({eyebrow,title,description,action}){return <header className="pagehead"><div><small className="eyebrow">{eyebrow||'FINTECH OCR / WORKSPACE'}</small><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action&&<div className="page-action">{action}</div>}</header>}
function Pill({children,type='default'}){return <span className={`pill pill-${type}`}>{children}</span>}
const stateType=s=>({approved:'green',valid:'green',verified:'green',pending:'orange',needs_review:'orange',draft:'gray',rejected:'red',error:'red',mismatch:'red',not_found:'red',completed:'green',in_progress:'orange'})[s]||'gray';
function Status({value}){return <Pill type={stateType(value)}>{approvalName(value==='needs_review'?'Cần kiểm tra':value)||value}</Pill>}
function Login({onLogin}){const[email,setEmail]=useState('employee@fintech.local'),[password,setPassword]=useState('Password@123'),[error,setError]=useState(''),[loading,setLoading]=useState(false);
async function submit(e){e.preventDefault();setLoading(true);setError('');try{let res=await api('/auth/login',{method:'POST',body:{email,password}});authStore.set(res.access_token);onLogin(res.user)}catch(e){setError(e.message)}finally{setLoading(false)}}
return <div className="login-wrap"><div className="login-aside"><div className="brand brand-light"><span className="brand-symbol">◈</span><span>FINTECH<strong>OCR / WORKSPACE</strong></span></div><div><p className="overline">INTERNAL EXPENSE WORKSPACE</p><h1>From paper invoices<br/>to <em>clean data.</em></h1><p>Digitize. Verify. Approve.<br/>Everything your team needs, one workspace.</p></div><div className="login-chips"><span>AI-Assisted OCR</span><span>Approval Workflow</span><span>Finance Analytics</span></div></div><div className="login-pane"><div className="login-box"><div className="logo-circle">◈</div><small className="eyebrow">WELCOME BACK</small><h2>Log in</h2><p>Access your FINTECH OCR workspace</p><form onSubmit={submit} className="stack"><label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<p className="error">{error}</p>}<button className="btn btn-primary full" disabled={loading}>{loading?'Signing in...':'Log in to workspace'} <ArrowRight size={17}/></button></form><div className="demo-account"><strong>DEMO ACCOUNTS</strong>{['employee','accountant','admin'].map(role=><button key={role} onClick={()=>{setEmail(role+'@fintech.local');setPassword('Password@123')}}>{roleName(role)}<span>Use account ↗</span></button>)}<small>Password: Password@123 · Chỉ dùng để phát triển</small></div></div></div></div>}
const common=[['/','Home',Home],['/invoices','My invoices',FileText],['/upload','Upload invoices',FileUp],['/schedule','Schedule',CalendarDays],['/ranking','Ranking',Trophy],['/chat','Chat with AI',MessageSquare],['/notifications','Notifications',Bell],['/profile','Profile',UserCircle]];
function navItems(role){if(role==='employee')return common;if(role==='accountant')return [['/','Home',Home],['/approvals','Approval Queue',ClipboardCheck],['/invoices','All invoices',FileText],['/schedule','Schedule',CalendarDays],['/ranking','Ranking',Trophy],['/chat','Chat with AI',MessageSquare],['/reports','Report',ChartNoAxesCombined],['/notifications','Notifications',Bell],['/profile','Profile',UserCircle]];return [['/','Home',Home],['/approvals','Approval Queue',ClipboardCheck],['/invoices','All invoices',FileText],['/schedule','Schedule',CalendarDays],['/ranking','Ranking',Trophy],['/chat','Chat with AI',MessageSquare],['/reports','Report',ChartNoAxesCombined],['/users','User Management',Users],['/audit','Audit Logs',ShieldCheck],['/notifications','Notifications',Bell],['/profile','Profile',UserCircle]]}
function NotificationDropdown({unread,onOpen}) {
  const {items,busy,error,reload,markRead,markAllRead}=useContext(NotificationContext);
  const navigate=useNavigate();
  const popup=useRef(null);
  const [actionError,setActionError]=useState(''),[pending,setPending]=useState(false);
  const close=()=>popup.current?.hidePopover();
  const location=useLocation();
  useEffect(()=>{close();setActionError('')},[location.pathname,location.search,location.hash]);
  async function openItem(item){
    setPending(true);setActionError('');
    try{await openNotificationAfterAccessCheck(item,api,markRead,navigate);close()}
    catch(e){setActionError(e.message)}finally{setPending(false)}
  }
  async function readAll(){
    setPending(true);setActionError('');
    try{await markAllRead()}catch(e){setActionError(e.message)}finally{setPending(false)}
  }
  return <div className="notification-dropdown">
    <button className="iconbtn bell" popoverTarget="notification-dropdown" aria-label={unread>0?`Notifications, ${unread} unread`:'Notifications'}><Bell size={19}/>{unread>0&&<i/>}</button>
    <section ref={popup} id="notification-dropdown" popover="auto" className="notification-popover" aria-labelledby="notification-dropdown-title" onToggle={e=>{if(e.newState==='open'){setActionError('');onOpen()}}}>
      <header className="notification-popover-heading"><h3 id="notification-dropdown-title">Notifications {unread>0&&<span>{unread}</span>}</h3><button className="iconbtn" aria-label="Close notifications" onClick={close}><X size={16}/></button></header>
      <div className="notification-popover-toolbar"><span>Latest updates</span><button className="textbtn" disabled={pending||busy||!unread} onClick={readAll}>Mark all as read</button></div>
      {actionError&&<p className="error notification-popover-error" role="alert">{actionError}</p>}
      <div className="notification-popover-list">{busy?<Loading/>:error?<div className="notification-popover-error"><p className="error" role="alert">{error}</p><button className="btn btn-small btn-muted" onClick={reload}>Try again</button></div>:items.length?items.slice(0,10).map(item=><button className={'notification-preview '+(!item.is_read?'unread':'')} key={item.id} disabled={pending} onClick={()=>openItem(item)}><span className="notification-preview-icon"><Bell size={16}/></span><span className="notification-preview-content"><strong>{item.title}</strong><span>{item.message}</span><small>{notificationTypeLabel(item.type)} · {formatNotificationTimestamp(item.created_at)}</small></span>{!item.is_read&&<span className="notification-preview-dot"/>}</button>):<div className="notification-popover-empty"><Bell size={25}/><strong>No notifications yet</strong><span>Your workspace updates will appear here.</span></div>}</div>
      <footer><button className="textbtn" onClick={()=>{close();navigate('/notifications')}}>View all notifications <ArrowRight size={14}/></button></footer>
    </section>
  </div>;
}
function Shell({user,onLogout,children}) {
  const [menu,setMenu]=useState(false), n=useNavigate(), loc=useLocation();
  const notes=useLoad('/notifications');
  const unreadCountState=useLoad('/notifications/unread-count');
  const previousPath=useRef(loc.pathname);
  const items=Array.isArray(notes.data)?notes.data:[];
  const unread=Number.isInteger(unreadCountState.data?.count)?unreadCountState.data.count:unreadNotificationCount(items);
  async function markRead(id){
    const changed=await markNotificationReadAfterSuccess(items,id,
      notificationId=>api('/notifications/'+notificationId+'/read',{method:'PATCH'}),notes.setData);
    if(changed){unreadCountState.setData(current=>({count:Math.max(0,(current?.count??unreadNotificationCount(items))-1)}));unreadCountState.reload();}
    return changed;
  }
  async function markAllRead(){
    await markAllNotificationsReadAfterSuccess(()=>api('/notifications/read-all',{method:'PATCH'}),notes.setData);
    unreadCountState.setData({count:0});
    unreadCountState.reload();
  }
  const notificationState={
    items,busy:notes.busy,error:notes.error,reload:notes.reload,
    markRead,markAllRead,
  };
  useEffect(()=>{
    setMenu(false);
    if(previousPath.current!==loc.pathname){notes.reload();unreadCountState.reload();}
    previousPath.current=loc.pathname;
  },[loc.pathname]);
  return <NotificationContext.Provider value={notificationState}>
    <div className={'app-shell '+(menu?'menu-open':'')}>
      <aside className={'sidebar '+(menu?'open':'')}>
        <NavLink to="/" aria-label="FINTECH OCR Home" className="brand"><span className="brand-symbol">{'\u25c8'}</span><span>FINTECH<strong>OCR / WORKSPACE</strong></span></NavLink>
        <span className="role-tag">{roleName(user.role)}</span>
        <nav className="nav">{navItems(user.role).map(([to,label,Icon])=><NavLink key={to} to={to} end={to==='/'} className={({isActive})=>'nav-item '+(isActive?'active':'')}>
          <Icon size={18}/><span>{label}</span>{label==='Notifications'&&unread>0&&<b className="nav-count">{unread}</b>}
        </NavLink>)}</nav>
        <div className="sidebar-bottom"><div className="system"><span className="system-dot"/> All systems ready<small>Your invoices, organized.<br/>Your workday, simplified.</small></div><button className="nav-item logout" onClick={onLogout}><LogOut size={18}/> Log out</button></div>
      </aside>
      <div className="mobile-backdrop" style={{display:menu?'block':'none'}} onClick={()=>setMenu(false)}/>
      <div className="workspace"><div className="topbar">
        <button className="iconbtn menu-btn" onClick={()=>setMenu(!menu)}><Menu size={22}/></button>
        <div className="today"><CalendarDays size={16}/>{new Date().toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}</div>
        <div className="top-right"><div className="page-dropdown"><button className="topsearch page-dropdown-trigger" popoverTarget="page-navigation"><Search size={16}/><span>Go to page...</span><ChevronDown size={15}/></button><div id="page-navigation" popover="auto" className="page-dropdown-menu"><small>WORKSPACE PAGES</small>{navItems(user.role).map(([to,label,Icon])=><NavLink key={to} to={to} end={to==='/'} onClick={()=>document.getElementById('page-navigation')?.hidePopover()}><Icon size={16}/>{label}</NavLink>)}</div></div>
          <NotificationDropdown unread={unread} onOpen={()=>{notes.reload();unreadCountState.reload()}}/>
          <button className="userchip" onClick={()=>n('/profile')}><span className="avatar">{user.full_name.split(' ').slice(-2).map(s=>s[0]).join('').toUpperCase()}</span><span className="userchip-name">{user.full_name}</span><ChevronDown size={15}/></button>
        </div>
      </div><main className="content">{children}</main></div>
    </div>
  </NotificationContext.Provider>;
}
function HomePage({ user }) {
  const { data, busy, error } = useLoad('/dashboard/summary');
  const inv = useLoad('/invoices');
  const sched = useLoad('/schedules');
  const navigate = useNavigate();
  const summary = data || {};
  const employee = user.role === 'employee';
  const stats = [
    [employee?'My invoices':'All invoices', summary.total_invoices, FileText, ''],
    ['Approved', summary.approved, CheckCircle2, 'approved'],
    ['Awaiting approval', summary.pending, Clock3, 'pending'],
    ['Rejected', summary.rejected, XCircle, 'rejected'],
  ];

  return <>
    <Title
      title={'Welcome back, ' + user.full_name.split(' ').slice(-2).join(' ')}
      description={employee ? 'Your expenses and upcoming trips, all in one place.' : 'Here’s your financial workspace at a glance.'}
      action={<button className="btn btn-primary" onClick={() => navigate(employee ? '/upload' : '/approvals')}><Plus size={16}/>{employee ? 'Upload invoice' : 'Review pending invoices'}</button>}
    />
    {busy ? <Loading/> : error ? <p className="error">{error}</p> : <>
      <div className="kpi-grid">
        {stats.map(([name, value, Icon, status]) => <NavLink className="kpi kpi-link" key={name} to={status ? `/invoices?status=${status}` : "/invoices"}>
          <div className="kpi-label">{name}<Icon size={20}/></div>
          <strong>{value ?? '—'}</strong>
          <small>{name === 'Approved' ? 'Successfully processed' : name === 'Awaiting approval' ? 'Awaiting review' : 'This workspace'}</small>
        </NavLink>)}
      </div>
      <div className="dashboard-grid">
        <SpendingChart summary={summary}/>
        <section className="panel">
          <div className="panel-heading"><h3>Recent invoices</h3><button className="textbtn" onClick={() => navigate('/invoices')}>View all <ArrowRight size={14}/></button></div>
          <div className="compact-list">
            {(inv.data || []).slice(0, 5).map(invoice => <button className="compact-invoice" key={invoice.id} onClick={() => navigate('/invoices/' + invoice.id)}>
              <div><strong>{invoice.invoice_number || '#' + invoice.id}</strong><span>{invoice.seller_name || invoice.filename}</span></div>
              <div className="compact-right"><b>{money(invoice.total_amount)}</b><Status value={invoice.approval_status}/></div>
            </button>)}
            {!inv.data?.length && <Empty/>}
          </div>
        </section>
      </div>
      <div className="dashboard-grid bottom-grid">
        <section className="panel">
          <div className="panel-heading"><h3>My schedule</h3><button className="textbtn" onClick={() => navigate('/schedule')}>View calendar <ArrowRight size={14}/></button></div>
          <div className="trip-list">
            {(sched.data || []).slice(0, 3).map(item => <div className="trip" key={item.id}>
              <div className="trip-time">{new Date(item.starts_at).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</div>
              <div><strong>{item.title}</strong><small>{item.destination} · {item.employee_name}</small></div>
              <Status value={item.status}/>
            </div>)}
            {!sched.data?.length && <Empty label="Chưa có lịch công tác"/>}
          </div>
        </section>
        <section className="panel black-panel"><MessageSquare size={21}/><h3>Ask about your invoices</h3><p>Track an approval, find a receipt, or understand your spending.</p><button onClick={() => navigate('/chat')} className="black-input">Ask your question... <ArrowRight size={18}/></button></section>
      </div>
    </>}
  </>;
}
function InvoicesPage(){const[search,setSearch]=useState('');const[params,setParams]=useSearchParams();const status=params.get('status')||'';const setStatus=value=>setParams(current=>{const next=new URLSearchParams(current);if(value)next.set('status',value);else next.delete('status');return next});const {data,busy,reload,error}=useLoad('/invoices'+(status?'?approval_status='+encodeURIComponent(status):''));const n=useNavigate();let rows=(data||[]).filter(i=>(i.invoice_number+' '+i.seller_name+' '+i.filename).toLowerCase().includes(search.toLowerCase())&&(!status||i.approval_status===status));return <><Title title="Invoices" description="Search, filter and review your invoice data."/><div className="panel"><div className="filters"><label className="searchbox"><Search size={17}/><input placeholder="Search invoice number or supplier..." value={search} onChange={e=>setSearch(e.target.value)}/></label><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{['draft','pending','approved','rejected'].map(s=><option key={s} value={s}>{approvalName(s)}</option>)}</select><button className="btn btn-muted" onClick={reload}><RefreshCw size={16}/></button></div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll"><table><thead><tr><th>Invoice</th><th>Supplier</th><th>Date</th><th>Amount</th><th>Validation</th><th>Approval</th><th>Lookup</th><th></th></tr></thead><tbody>{rows.map(i=><tr key={i.id}><td><strong>{i.invoice_number||'#'+i.id}</strong><small>{i.document_type}</small></td><td>{i.seller_name||'Chưa trích xuất'}</td><td>{datefmt(i.invoice_date)}</td><td className="money">{money(i.total_amount)}</td><td><Status value={i.validation_status}/></td><td><Status value={i.approval_status}/></td><td><Status value={i.lookup_status}/></td><td><button className="btn btn-small btn-muted" onClick={()=>n('/invoices/'+i.id)}>Details <ArrowRight size={14}/></button></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có hóa đơn phù hợp"/>}</div>}</div></>}
function UploadPage(){const[file,setFile]=useState(null),[busy,setBusy]=useState(false),[done,setDone]=useState(null),[error,setError]=useState('');const n=useNavigate();async function submit(e){e.preventDefault();if(!file)return;setBusy(true);setError('');const form=new FormData();form.append('file',file);try{const res=await api('/invoices/upload',{method:'POST',body:form});setDone(res)}catch(ex){setError(ex.message)}finally{setBusy(false)}}return <><Title title="Upload invoices" description="Add your receipts. Let AI do the paperwork."/><div className="upload-grid"><section className="panel"><h3>Add your invoices</h3><p>PDF, JPG, PNG or XML · Up to 20MB per file</p><form onSubmit={submit}><label className="dropzone"><FileUp size={42}/><strong>{file?file.name:'Choose an invoice file'}</strong><span>Click to choose PDF, JPG, PNG or XML</span><input type="file" accept=".pdf,.jpg,.jpeg,.png,.xml" onChange={e=>setFile(e.target.files[0]||null)}/></label>{error&&<p className="error">{error}</p>}<button disabled={!file||busy} className="btn btn-primary full" type="submit">{busy?'Processing invoice...':'Upload & extract'}<ArrowRight size={16}/></button></form></section><section className="panel help-panel"><ShieldCheck size={28}/><h3>Keep your records in control</h3><p>Each uploaded document is stored with its original file. OCR runs locally when Tesseract is available; you can manually correct any missing fields before submission.</p><div className="help-step"><span>01</span> Upload your receipt</div><div className="help-step"><span>02</span> Review extracted fields</div><div className="help-step"><span>03</span> Submit for approval</div></section></div>{done&&<div className="panel success-card"><CheckCircle2 size={27} color="#2b9162"/><div><h3>Upload complete</h3><p>Created invoice #{done.id}. Status: {done.validation_status}. Please review before submitting.</p></div><button className="btn btn-primary" onClick={()=>n('/invoices/'+done.id)}>Review now <ArrowRight size={16}/></button></div>}</>}

const RISK_LABELS={
  'DUPLICATE-FILE':'Trùng nội dung file',
  'DUPLICATE-INVOICE':'Trùng thông tin hóa đơn',
  'SAME-TAX-CODE':'MST người mua và người bán giống nhau',
  'INCOMPLETE-FINANCIAL':'Thiếu dữ liệu tài chính',
  'INCOMPLETE-FINANCIALS':'Thiếu dữ liệu tài chính',
  'MISSING-SYMBOL':'Thiếu ký hiệu hóa đơn'
};
function RiskAssessmentPanel({invoiceId}){
  const {data,busy,error,reload,setData,setError}=useLoad('/invoices/'+invoiceId+'/risk-assessment');
  const [refreshing,setRefreshing]=useState(false);
  const [refreshResult,setRefreshResult]=useState(null);
  async function checkAgain(){
    if(busy||refreshing)return;
    setRefreshing(true);
    setRefreshResult(null);
    setError('');
    try{
      const next=await api('/invoices/'+invoiceId+'/risk-assessment');
      const currentFlags=Array.isArray(data?.flags)?data.flags:[];
      const nextFlags=Array.isArray(next?.flags)?next.flags:[];
      const signature=rows=>JSON.stringify(rows.map(f=>[f.code,f.severity,f.message,f.matched_count]));
      const unchanged=signature(currentFlags)===signature(nextFlags);
      setData(next);
      const time=new Date().toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
      setRefreshResult({ok:true,text:unchanged
        ?`Đã kiểm tra lại lúc ${time}. Không có thay đổi (${nextFlags.length} cảnh báo).`
        :`Đã cập nhật lúc ${time}. Hiện có ${nextFlags.length} cảnh báo.`});
    }catch(e){
      setRefreshResult({ok:false,text:`Không kiểm tra lại được: ${e.message}`});
    }finally{
      setRefreshing(false);
    }
  }
  const flags=Array.isArray(data?.flags)?data.flags:[];
  return <section className="panel risk-panel" aria-label="Risk Assessment">
    <div className="panel-heading risk-heading">
      <div className="risk-heading-main">
        <div className="risk-heading-icon"><ShieldCheck size={20}/></div>
        <div><h3>Risk Assessment</h3><p>Cảnh báo kiểm tra trùng lặp và dữ liệu bất thường, không phải kết luận gian lận.</p></div>
      </div>
      <div className="risk-heading-actions">
        {!busy&&!error&&<Pill type={flags.length?'orange':'green'}>{flags.length?flags.length+' cảnh báo':'Chưa có cảnh báo'}</Pill>}
        <button className="btn btn-muted btn-small" onClick={checkAgain} disabled={busy||refreshing} title="Gọi lại API để cập nhật cảnh báo rủi ro" aria-busy={refreshing}><RefreshCw size={14} className={busy||refreshing?'spin':''}/> {refreshing?'Đang kiểm tra...':'Kiểm tra lại'}</button>
      </div>
    </div>
    {refreshing&&<div className="risk-refresh-status risk-refresh-pending" role="status" aria-live="polite"><RefreshCw size={15} className="spin"/> Đang tải kết quả mới từ Backend...</div>}
    {!refreshing&&refreshResult&&<div className={'risk-refresh-status '+(refreshResult.ok?'risk-refresh-ok':'risk-refresh-fail')} role={refreshResult.ok?'status':'alert'} aria-live="polite">{refreshResult.ok?<CheckCircle2 size={16}/>:<AlertTriangle size={16}/>}<span>{refreshResult.text}</span></div>}
    {busy?<div className="risk-loading"><RefreshCw size={17} className="spin"/> Đang kiểm tra các dấu hiệu rủi ro...</div>:
     error?<div className="risk-error" role="alert"><AlertTriangle size={18}/><span>Không tải được cảnh báo rủi ro: {error}</span><button className="btn btn-small btn-outline" onClick={reload}>Thử lại</button></div>:
     <>
       {flags.length?<div className="risk-list">{flags.map((flag,index)=>{
         const severity=flag.severity==='error'?'error':flag.severity==='warning'?'warning':'info';
         return <div className={'risk-flag risk-flag-'+severity} key={(flag.code||'flag')+'-'+index}>
           <span className="risk-flag-icon"><AlertTriangle size={17}/></span>
           <div className="risk-flag-body"><div className="risk-flag-title"><strong>{RISK_LABELS[flag.code]||flag.code||'Cảnh báo rủi ro'}</strong><span className="risk-flag-code">{flag.code||'RISK'}</span></div><p>{flag.message||'Cần kiểm tra thông tin hóa đơn.'}</p>{Number.isInteger(flag.matched_count)&&flag.matched_count>0&&<small>{flag.matched_count} bản ghi khớp được phát hiện</small>}</div>
         </div>
       })}</div>:<div className="risk-clear"><CheckCircle2 size={19}/><span>Chưa phát hiện dấu hiệu rủi ro theo các quy tắc hiện tại. Vẫn cần đối chiếu hóa đơn gốc.</span></div>}
       <div className="risk-footer">
         {data?.tax_lookup_performed===false&&<span><Clock3 size={14}/> Chưa ghi nhận tra cứu thuế</span>}
         {data?.tax_lookup_performed===true&&<span><CheckCircle2 size={14}/> Đã ghi nhận thao tác tra cứu thuế</span>}
         {data?.review_note&&<p>{data.review_note}</p>}
         {data?.confidence_note&&<p>{data.confidence_note}</p>}
       </div>
     </>}
  </section>
}

function DetailPage({user}){const {id}=useParams();const {data,reload,busy,error}=useLoad('/invoices/'+id);const[riskVersion,setRiskVersion]=useState(0);return <><InvoiceDetailPage user={user} id={id} data={data} busy={busy} error={error} reload={reload} onChanged={()=>setRiskVersion(v=>v+1)}/>{data&&!busy&&!error&&<RiskAssessmentPanel key={id+'-'+riskVersion} invoiceId={id}/>}</>}
function ApprovalsPage(){const{data,busy,error}=useLoad('/invoices');const[filter,setFilter]=useState('pending');const n=useNavigate();const rows=(data||[]).filter(x=>!filter||x.approval_status===filter);return <><Title title="Approval Queue" description="Review invoice details, record tax lookup results, and keep approvals moving."/><section className="panel"><div className="tabs">{[['pending','Pending'],['approved','Approved'],['rejected','Rejected'],['','All']].map(([v,name])=><button className={filter===v?'selected':''} key={name} onClick={()=>setFilter(v)}>{name} <b>{(data||[]).filter(i=>!v||i.approval_status===v).length}</b></button>)}</div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="approval-cards">{rows.map(i=><div className="approval-card" key={i.id}><div><small>{i.document_type?.toUpperCase()} · INVOICE #{i.id}</small><h3>{i.seller_name||i.filename}</h3><p>{i.invoice_number||'New invoice'} · {datefmt(i.invoice_date)}</p></div><div className="approval-right"><strong>{money(i.total_amount)}</strong><Status value={i.approval_status}/><button className="btn btn-primary btn-small" onClick={()=>n('/invoices/'+i.id)}>Review <ArrowRight size={15}/></button></div></div>)}{!rows.length&&<Empty label="Hàng đợi đang trống"/>}</div>}</section></>}
function SchedulePage({user}){return <EmployeeSchedulePage user={user}/>}
function RankingPage(){const[period,setPeriod]=useState('all');const{data,busy}=useLoad('/ranking?period='+period);return <><Title title="Completed-trip Ranking" description="Rank employees by completed business trips; planned and cancelled trips do not count."/><section className="panel"><div className="filters"><h3>Team leaderboard</h3><select value={period} onChange={e=>setPeriod(e.target.value)}><option value="all">All time</option><option value="month">This month</option><option value="quarter">This quarter</option><option value="year">This year</option></select></div>{busy?<Loading/>:<div className="ranking">{(data||[]).map((r,i)=><div className="rankrow" key={r.user_id}><span className="rank">#{i+1}</span><span className="avatar">{r.full_name.slice(-2).toUpperCase()}</span><strong>{r.full_name}</strong><span className="rank-score">{r.completed} completed</span></div>)}{!data?.length&&<Empty label="Chưa có chuyến công tác hoàn thành trong kỳ"/>}</div>}</section></>}
function ChatPage(){const[question,setQuestion]=useState(''),[messages,setMessages]=useState([{role:'assistant',content:'Xin chào! Tôi đang dùng chế độ truy vấn dữ liệu demo, chưa kết nối LLM. Bạn có thể hỏi: Tổng tiền hóa đơn là bao nhiêu?'}]),[sending,setSending]=useState(false);async function submit(e){e.preventDefault();if(!question.trim())return;const q=question;setQuestion('');setMessages(x=>[...x,{role:'user',content:q}]);setSending(true);try{let r=await api('/chatbot/ask',{method:'POST',body:{question:q}});setMessages(x=>[...x,{role:'assistant',content:r.answer}])}catch(e){setMessages(x=>[...x,{role:'assistant',content:e.message}])}finally{setSending(false)}}return <><Title title="Chat with AI" description="Ask questions about invoice data within your permissions."/><section className="panel chat-panel"><div className="chat-heading"><span className="chat-bot">◈</span><div><strong>FINTECH data assistant</strong><small>Role-scoped database demo · LLM integration pending</small></div></div><div className="chat-messages">{messages.map((m,i)=><div className={'chat-message '+m.role} key={i}>{m.content}</div>)}{sending&&<Loading/>}</div><form className="chat-form" onSubmit={submit}><input placeholder="Ask about your invoices..." value={question} onChange={e=>setQuestion(e.target.value)}/><button className="btn btn-primary"><Send size={17}/></button></form></section></>}
function ReportsPage(){
 const [filters,setFilters]=useState({approval_status:'',validation_status:'',document_type:'',search:'',invoice_date_from:'',invoice_date_to:''});
 const [summary,setSummary]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 function queryString(){const params=new URLSearchParams();for(const [key,value] of Object.entries(filters))if(value)params.set(key,value);return params.toString()}
 async function loadSummary(){setBusy(true);setMessage('');try{setSummary(await api('/reports/summary'+(queryString()?`?${queryString()}`:'')))}catch(e){setMessage(e.message)}finally{setBusy(false)}}
 useEffect(()=>{loadSummary()},[]);
 async function exportNow(){setBusy(true);setMessage('');try{const nextSummary=await api('/reports/summary'+(queryString()?`?${queryString()}`:''));setSummary(nextSummary);if(!nextSummary.invoice_count){setMessage('Không có dữ liệu để xuất.');return}const response=await api('/reports/export'+(queryString()?`?${queryString()}`:''),{raw:true});const blob=await response.blob();const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='fintech_ocr_invoices.xlsx';anchor.click();URL.revokeObjectURL(url);setMessage('Đã tạo file Excel')}catch(e){setMessage(e.message)}finally{setBusy(false)}}
 function change(key,value){setFilters(current=>({...current,[key]:value}))}
 return <><Title title="Reports" description="Review invoice data and export Excel reports for your accounting team."/><section className="panel report-panel report-panel-wide"><div className="report-image"><ChartNoAxesCombined size={52}/></div><h3>Invoice report</h3><p>Count and total are computed from the same permission-scoped invoice set used by the export.</p>
 <div className="report-filters">
  <label>Search invoice / supplier<input value={filters.search} onChange={e=>change('search',e.target.value)} placeholder="Invoice number or supplier"/></label>
  <label>Approval status<select value={filters.approval_status} onChange={e=>change('approval_status',e.target.value)}><option value="">All</option>{['draft','pending','approved','rejected'].map(x=><option key={x} value={x}>{x}</option>)}</select></label>
  <label>Validation status<select value={filters.validation_status} onChange={e=>change('validation_status',e.target.value)}><option value="">All</option>{['valid','needs_review','error'].map(x=><option key={x} value={x}>{x}</option>)}</select></label>
  <label>Document type<select value={filters.document_type} onChange={e=>change('document_type',e.target.value)}><option value="">All</option>{['einvoice','bill','unknown'].map(x=><option key={x} value={x}>{x}</option>)}</select></label>
  <label>Invoice date from<input type="date" value={filters.invoice_date_from} onChange={e=>change('invoice_date_from',e.target.value)}/></label>
  <label>Invoice date to<input type="date" value={filters.invoice_date_to} onChange={e=>change('invoice_date_to',e.target.value)}/></label>
 </div>
 <div className="report-actions"><button className="btn btn-secondary" disabled={busy} onClick={loadSummary}><Filter size={16}/> Apply filters</button><button className="btn btn-primary" disabled={busy} onClick={exportNow}><Download size={17}/> Export Excel (.xlsx)</button></div>
 {summary&&<div className="report-summary" aria-live="polite"><div><small>Invoices in result</small><strong>{summary.invoice_count}</strong></div><div><small>Total amount (VND)</small><strong>{money(summary.total_amount)}</strong></div></div>}
 <small>Workbook contains one row per invoice and a separate line items sheet. The final statutory format under Circular 78 remains subject to Product Owner confirmation.</small></section><Notice message={message} onDismiss={()=>setMessage('')}/></>}
function UsersPage(){
 const {data,busy,error,reload}=useLoad('/users');
 const [form,setForm]=useState({full_name:'',email:'',password:'',role:'employee',status:'active'}),[editing,setEditing]=useState(null),[search,setSearch]=useState(''),[role,setRole]=useState(''),[status,setStatus]=useState(''),[saving,setSaving]=useState(false),[message,setMessage]=useState(''),[confirm,setConfirm]=useState(null);
 const rows=(data||[]).filter(u=>(u.full_name+' '+u.email).toLowerCase().includes(search.toLowerCase())&&(!role||u.role===role)&&(!status||u.status===status));
 function edit(u){setEditing(u);setForm(u?{full_name:u.full_name,email:u.email,role:u.role,status:u.status}:{full_name:'',email:'',password:'',role:'employee',status:'active'})}
 async function save(e){e.preventDefault();setSaving(true);try{await api(editing?'/users/'+editing.id:'/users',{method:editing?'PATCH':'POST',body:{...form,full_name:form.full_name.trim(),email:form.email.trim()}});setForm(null);reload();setMessage('User saved')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
 async function toggleAccount(user){
   if(saving)return;
   const deactivate=user.status==='active';
   const question=deactivate
     ? `B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n v\u00f4 hi\u1ec7u h\u00f3a t\u00e0i kho\u1ea3n "${user.full_name}" (${user.email}) kh\u00f4ng?\nNg\u01b0\u1eddi d\u00f9ng s\u1ebd kh\u00f4ng th\u1ec3 \u0111\u0103ng nh\u1eadp. L\u1ecbch s\u1eed v\u1eabn \u0111\u01b0\u1ee3c gi\u1eef l\u1ea1i.`
     : `B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n k\u00edch ho\u1ea1t l\u1ea1i t\u00e0i kho\u1ea3n "${user.full_name}" (${user.email}) kh\u00f4ng?\nNg\u01b0\u1eddi d\u00f9ng s\u1ebd c\u00f3 th\u1ec3 \u0111\u0103ng nh\u1eadp tr\u1edf l\u1ea1i.`;
   if(!window.confirm(question))return;
   setSaving(true);
   try{
     await api('/users/'+user.id,{method:'PATCH',body:{status:deactivate?'disabled':'active'}});
     setConfirm(null);reload();setMessage(deactivate?'Account deactivated':'Account reactivated');
   }catch(e){setMessage(e.message)}finally{setSaving(false)}
 }
 async function perform(){setSaving(true);try{await api('/users/'+confirm.user.id,confirm.action==='delete'?{method:'DELETE'}:{method:'PATCH',body:{status:confirm.user.status==='active'?'disabled':'active'}});setConfirm(null);reload();setMessage('Account updated')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
 const active=(data||[]).filter(u=>u.status==='active').length;
 const permissions={employee:'Upload own receipts, view schedules and chat with AI. No approval or user access.',accountant:'Review invoices, approve expenses, manage schedules and view reports.',admin:'Manage workspace users, permissions, invoices and audit history.'};
 const actionLabel=confirm?.action==='delete'?'Delete account':confirm?.user.status==='active'?'Deactivate account':'Reactivate account';
 return <div className="users-page"><Title title="User Management" description="Manage workspace access, roles and account status. All account history is retained."/>
 <div className={'users-layout '+(!form?'form-closed':'')}><div className="users-main"><section className="panel users-table-panel"><div className="panel-heading"><h3>Workspace users <span className="users-count">{data?.length||0}</span></h3><small>{active} active · {(data?.length||0)-active} disabled</small></div><div className="filters users-filters"><label className="searchbox"><Search size={15}/><input aria-label="Search users" placeholder="Search by name or email" value={search} onChange={e=>setSearch(e.target.value)}/></label><select aria-label="Filter role" value={role} onChange={e=>setRole(e.target.value)}><option value="">All roles</option>{['employee','accountant','admin'].map(r=><option key={r} value={r}>{roleName(r)}</option>)}</select><button className="btn btn-primary" onClick={()=>edit(null)}><Plus size={15}/> Add user</button></div>
 {busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th>Actions</th></tr></thead><tbody>{rows.map(u=><tr key={u.id}><td><div className="user-identity"><span className={`avatar user-avatar avatar-tone-${u.id%5}`}>{u.full_name.split(/\s+/).filter(Boolean).slice(-2).map(x=>x[0]).join('').toUpperCase()}</span><strong>{u.full_name}</strong></div></td><td>{u.email}</td><td><Pill>{roleName(u.role)}</Pill></td><td><Pill type={u.status==='active'?'green':'gray'}>{u.status==='active'?'Active':'Disabled'}</Pill></td><td className="user-last-login">{u.last_login_at?new Date(u.last_login_at).toLocaleString('en-GB',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'Never'}</td><td><div className="user-actions"><button className="iconbtn" title="Edit user" aria-label={'Edit '+u.full_name} onClick={()=>edit(u)}><Pencil size={15}/></button><button className="iconbtn" title={u.status==='active'?'Deactivate':'Reactivate'} aria-label={(u.status==='active'?'Deactivate ':'Reactivate ')+u.full_name} disabled={saving} onClick={()=>toggleAccount(u)}>{u.status==='active'?<UserRoundX size={15}/>:<UserRoundCheck size={15}/>}</button><button className="iconbtn danger-action" title="Delete user" aria-label={'Delete '+u.full_name} onClick={()=>setConfirm({user:u,action:'delete'})}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table>{!rows.length&&<Empty label="No matching users"/>}</div>}<footer className="users-table-footer"><span>Showing {rows.length} of {data?.length||0} users</span><span><Pencil size={12}/> Edit <UserRoundX size={13}/> Deactivate / Reactivate</span></footer></section>
 {confirm&&<section className="panel user-confirm" aria-labelledby="confirm-title"><div className="panel-heading"><h3 id="confirm-title"><UserRoundX size={18}/> {actionLabel}?</h3><button className="iconbtn" disabled={saving} aria-label="Cancel action" onClick={()=>setConfirm(null)}><X size={16}/></button></div><strong>{confirm.user.full_name} · {confirm.user.email}</strong><p>{confirm.action==='delete'?'Deletion is permanent. Accounts with related history must be deactivated instead.':confirm.user.status==='active'?'Deactivate account: user can no longer log in; history is kept.':'Reactivate account: allow this user to log in again.'}</p><div className="user-confirm-actions"><button disabled={saving} className="btn btn-muted" onClick={()=>setConfirm(null)}>Cancel</button><button disabled={saving} className="btn btn-primary" onClick={perform}>{saving?'Processing...':actionLabel}</button></div></section>}
 </div>
 {form&&<aside className="panel user-editor" aria-labelledby="user-form-title"><div className="panel-heading"><h3 id="user-form-title">Add / Edit user</h3><button className="iconbtn" disabled={saving} aria-label="Close form" onClick={()=>setForm(null)}><X size={16}/></button></div><p>{editing?'Update team member details.':'Create a new team member.'}</p><form className="stack" onSubmit={save}><label>Full name<input required minLength={2} maxLength={150} value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><label>Email<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>{!editing&&<label>Temporary password<input type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/><small>At least 8 characters.</small></label>}<label>Role<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{['employee','accountant','admin'].map(r=><option key={r} value={r}>{roleName(r)}</option>)}</select></label><div className="user-permissions"><strong><ShieldCheck size={13}/> {roleName(form.role)} permissions</strong><p>{permissions[form.role]}</p></div><label className="user-active-toggle"><span>Active<small>Allow this user to log in</small></span><input type="checkbox" role="switch" checked={form.status==='active'} onChange={e=>setForm({...form,status:e.target.checked?'active':'disabled'})}/></label><div className="user-editor-actions"><button type="button" disabled={saving} className="btn btn-muted" onClick={()=>setForm(null)}>Cancel</button><button disabled={saving} className="btn btn-primary">{saving?'Saving...':editing?'Save changes':'Create user'}</button></div></form></aside>}
 </div>
 <Notice message={message} onDismiss={()=>setMessage('')}/></div>;
}
function NotificationsPage(){
  const notificationState=useContext(NotificationContext);
  const {items,busy,error,markRead,markAllRead}=notificationState;
  const [message,setMessage]=useState('');
  const navigate=useNavigate();
  async function openNotification(item){
    try{
      await openNotificationAfterAccessCheck(item,api,markRead,navigate);
    }catch(actionError){setMessage(actionError.message);}
  }
  async function markAll(){try{await markAllRead();setMessage('');}catch(actionError){setMessage(actionError.message);}}
  return <><Title title="Notifications" description="Stay up to date with your receipts, reviews and upcoming schedules." action={<button className="btn btn-muted" onClick={markAll}>Mark all as read</button>}/>
    <section className="panel notif-list">{busy?<Loading/>:error?<p className="error">{error}</p>:(items||[]).map(item=><button className={'notif '+(!item.is_read?'unread':'')} key={item.id} onClick={()=>openNotification(item)}>
      <Bell size={19}/><span><strong>{item.title}</strong><small>{item.message}</small><small className="notif-type">{notificationTypeLabel(item.type)}</small><small>{formatNotificationTimestamp(item.created_at)}</small></span>{!item.is_read&&<span className="unread-dot"/>}
    </button>)}{!busy&&!error&&!items?.length&&<Empty label={String.fromCharCode(75,104,244,110,103,32,99,243,32,116,104,244,110,103,32,98,225,111)}/>}</section><Notice message={message} onDismiss={()=>setMessage('')}/></>;
}
function ProfilePage({user,onRefresh}){const[name,setName]=useState(user.full_name),[current,setCurrent]=useState(''),[next,setNext]=useState(''),[message,setMessage]=useState('');return <><Title title="Profile" description="Manage your personal details and account security."/><div className="two-col"><section className="panel"><h3>Personal information</h3><div className="profile-avatar">{user.full_name.slice(-2).toUpperCase()}</div><p>{user.email}</p><Pill>{roleName(user.role)}</Pill><form className="stack margin-top" onSubmit={async e=>{e.preventDefault();try{await api('/profile',{method:'PATCH',body:{full_name:name}});await onRefresh();setMessage('Đã lưu hồ sơ')}catch(e){setMessage(e.message)}}}><label>Full name<input value={name} onChange={e=>setName(e.target.value)}/></label><label>Email<input value={user.email} disabled/></label><button className="btn btn-primary"><Save size={16}/> Save changes</button></form></section><section className="panel"><h3>Change password</h3><form className="stack margin-top" onSubmit={async e=>{e.preventDefault();try{await api('/profile/password',{method:'PUT',body:{current_password:current,new_password:next}});setCurrent('');setNext('');setMessage('Đã thay đổi mật khẩu')}catch(e){setMessage(e.message)}}}><label>Current password<input type="password" value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>New password<input type="password" minLength={8} value={next} onChange={e=>setNext(e.target.value)}/></label><button className="btn btn-primary"><ShieldCheck size={16}/> Update password</button></form></section></div><Notice message={message} onDismiss={()=>setMessage('')}/></>}
function AuditPage(){const{data}=useLoad('/audit-logs');return <><Title title="Audit logs" description="Review security and workflow activity across the workspace."/><section className="panel"><div className="table-scroll"><table><thead><tr><th>Event</th><th>Type</th><th>Entity</th><th>Actor ID</th><th>Time</th></tr></thead><tbody>{(data||[]).map(a=><tr key={a.id}><td><strong>{a.action}</strong></td><td>{a.entity_type}</td><td>#{a.entity_id||'—'}</td><td>{a.actor_id||'—'}</td><td>{datefmt(a.created_at)}</td></tr>)}</tbody></table>{!data?.length&&<Empty/>}</div></section></>}
export default function App(){const[user,setUser]=useState(null),[loading,setLoading]=useState(!!authStore.get());const refresh=useCallback(async()=>{let u=await api('/auth/me');setUser(u)},[]);useEffect(()=>{if(authStore.get())refresh().catch(()=>{authStore.set(null);setUser(null)}).finally(()=>setLoading(false))},[refresh]);async function logout(){try{await api('/auth/logout',{method:'POST'})}catch{}authStore.set(null);setUser(null)}if(loading)return <Loading/>;if(!user)return <Login onLogin={setUser}/>;return <Shell user={user} onLogout={logout}><Routes><Route path="/" element={<HomePage user={user}/>}/><Route path="/invoices" element={<InvoicesPage/>}/><Route path="/invoices/:id" element={<DetailPage user={user}/>}/><Route path="/upload" element={user.role==='employee'?<UploadPage/>:<Navigate to="/invoices"/>}/><Route path="/approvals" element={user.role!=='employee'?<ApprovalsPage/>:<Navigate to="/"/>}/><Route path="/schedule" element={<SchedulePage user={user}/>}/><Route path="/ranking" element={<RankingPage/>}/><Route path="/chat" element={<ChatPage/>}/><Route path="/reports" element={user.role!=='employee'?<ReportsPage/>:<Navigate to="/"/>}/><Route path="/users" element={user.role==='admin'?<UsersPage/>:<Navigate to="/"/>}/><Route path="/audit" element={user.role==='admin'?<AuditPage/>:<Navigate to="/"/>}/><Route path="/notifications" element={<NotificationsPage/>}/><Route path="/profile" element={<ProfilePage user={user} onRefresh={refresh}/>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></Shell>}
