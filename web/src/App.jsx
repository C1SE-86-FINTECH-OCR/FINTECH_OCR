import React,{createContext,useContext,useRef,useState,useEffect,useCallback} from 'react';
import {Routes,Route,NavLink,Navigate,useNavigate,useParams,useLocation} from 'react-router-dom';
import {Home,FileUp,ClipboardCheck,CalendarDays,MessageSquare,ChartNoAxesCombined,Users,LogOut,Bell,UserCircle,Search,ArrowRight,Plus,FileText,CheckCircle2,XCircle,Clock3,RefreshCw,Download,ShieldCheck,Menu,X,Eye,Save,Send,ChevronLeft,ExternalLink,BarChart3,Trophy,Activity,AlertTriangle,Filter,Settings,Camera,ChevronDown} from 'lucide-react';
import {api,authStore,money,datefmt,roleName,approvalName,ROOT} from './api';
import SpendingChart from './SpendingChart';
import InvoiceDetailPage from './InvoiceDetailPage';
import UploadPage from './UploadPage';
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

function isSameDay(d1, d2) {
  return d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate();
}

function getNotifConfig(item) {
  const text = ((item.title || '') + ' ' + (item.message || '')).toLowerCase();
  if (text.includes('duyệt') || text.includes('phê duyệt') || text.includes('approved')) {
    return { icon: CheckCircle2, colorClass: 'notif-icon-green', priority: 'Bình thường' };
  }
  if (text.includes('chỉnh sửa') || text.includes('từ chối') || text.includes('rejected') || text.includes('needs')) {
    return { icon: FileText, colorClass: 'notif-icon-red', priority: 'Cao' };
  }
  if (item.type === 'extraction_finished' || text.includes('ocr')) {
    return { icon: Camera, colorClass: 'notif-icon-teal', priority: 'Cao' };
  }
  if (item.type === 'schedule_assigned' || text.includes('lịch') || text.includes('công tác')) {
    return { icon: CalendarDays, colorClass: 'notif-icon-blue', priority: 'Bình thường' };
  }
  return { icon: FileUp, colorClass: 'notif-icon-green', priority: 'Bình thường' };
}

function formatNotifTime(dateString) {
  if (!dateString) return '—';
  const d = new Date(dateString);
  if (Number.isNaN(d.getTime())) return '—';
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const now = new Date();
  if (isSameDay(d, now)) {
    return `${hours}:${minutes}`;
  }
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${d.getDate()} ${months[d.getMonth()]} · ${hours}:${minutes}`;
}

function Shell({user,onLogout,children}) {
  const [menu,setMenu]=useState(false), n=useNavigate(), loc=useLocation();
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [notifDropdownOpen, setNotifDropdownOpen] = useState(false);
  const userDropdownRef = useRef(null);
  const notifDropdownRef = useRef(null);
  const [dismissedIds, setDismissedIds] = useState(() => new Set());
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
    setUserDropdownOpen(false);
    setNotifDropdownOpen(false);
    if(previousPath.current!==loc.pathname){notes.reload();unreadCountState.reload();}
    previousPath.current=loc.pathname;
  },[loc.pathname]);
  useEffect(()=>{
    function handleOutside(e){
      if(userDropdownRef.current&&!userDropdownRef.current.contains(e.target)){
        setUserDropdownOpen(false);
      }
      if(notifDropdownRef.current&&!notifDropdownRef.current.contains(e.target)){
        setNotifDropdownOpen(false);
      }
    }
    function handleKeyDown(e){
      if(e.key==='Escape'){
        setUserDropdownOpen(false);
        setNotifDropdownOpen(false);
      }
    }
    if(userDropdownOpen || notifDropdownOpen){
      document.addEventListener('mousedown',handleOutside);
      document.addEventListener('keydown',handleKeyDown);
      return ()=>{
        document.removeEventListener('mousedown',handleOutside);
        document.removeEventListener('keydown',handleKeyDown);
      };
    }
  },[userDropdownOpen, notifDropdownOpen]);

  const popoverItems = items.filter(i => !dismissedIds.has(i.id));

  return <NotificationContext.Provider value={notificationState}>
    <div className={'app-shell '+(menu?'menu-open':'')}>
      <aside className={'sidebar '+(menu?'open':'')}>
        <div className="brand"><span className="brand-symbol">{'\u25c8'}</span><span>FINTECH<strong>OCR / WORKSPACE</strong></span></div>
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
        <div className="top-right"><span className="topsearch"><Search size={16}/> Search invoices, suppliers...</span>
          <div className="notif-dropdown-container" ref={notifDropdownRef}>
            <button
              className={`iconbtn bell ${notifDropdownOpen ? 'active' : ''}`}
              aria-label={unread>0?`Notifications, ${unread} unread`:'Notifications'}
              onClick={()=>setNotifDropdownOpen(prev=>!prev)}
              type="button"
            >
              <Bell size={19}/>{unread>0&&<i/>}
            </button>
            {notifDropdownOpen && (
              <div className="notif-popover-menu" role="dialog" aria-label="Thông báo">
                <div className="notif-popover-header">
                  <div className="notif-popover-title">
                    <Bell size={17}/>
                    <strong>Thông báo</strong>
                  </div>
                  <div className="notif-popover-header-actions">
                    <button className="notif-popover-link-btn" type="button" onClick={markAllRead}>
                      Đọc tất cả
                    </button>
                    <button className="notif-popover-close-btn" type="button" onClick={()=>setNotifDropdownOpen(false)} aria-label="Đóng">
                      <X size={16}/>
                    </button>
                  </div>
                </div>

                <div className="notif-popover-list">
                  {notes.busy ? (
                    <div className="notif-popover-loading"><RefreshCw size={16} className="spin"/> Đang tải...</div>
                  ) : !popoverItems.length ? (
                    <div className="notif-popover-empty">Không có thông báo nào</div>
                  ) : (
                    popoverItems.slice(0, 8).map(item => {
                      const { icon: Icon, colorClass, priority } = getNotifConfig(item);
                      return (
                        <div key={item.id} className={`notif-popover-card ${!item.is_read ? 'unread' : ''}`}>
                          <div
                            className="notif-popover-card-main"
                            onClick={async () => {
                              setNotifDropdownOpen(false);
                              await openNotificationAfterAccessCheck(item, api, markRead, n);
                            }}
                          >
                            <div className={`notif-popover-icon ${colorClass}`}>
                              <Icon size={16}/>
                            </div>
                            <div className="notif-popover-body">
                              <div className="notif-popover-card-head">
                                <strong className="notif-popover-item-title">{item.title}</strong>
                                {!item.is_read && <span className="notif-popover-unread-dot"/>}
                              </div>
                              <p className="notif-popover-item-desc">{item.message}</p>
                              <div className="notif-popover-item-meta">
                                <span>{formatNotifTime(item.created_at)}</span>
                                <span className="notif-meta-status">{item.is_read ? 'Đã đọc' : 'Chưa đọc'}</span>
                                <span className={`notif-priority-tag ${priority === 'Cao' ? 'high' : 'normal'}`}>{priority}</span>
                              </div>
                            </div>
                          </div>
                          <div className="notif-popover-card-actions">
                            <button
                              className="notif-pill-btn"
                              type="button"
                              onClick={async () => {
                                setNotifDropdownOpen(false);
                                await openNotificationAfterAccessCheck(item, api, markRead, n);
                              }}
                            >
                              Xem chi tiết
                            </button>
                            {!item.is_read && (
                              <button
                                className="notif-pill-btn"
                                type="button"
                                onClick={() => markRead(item.id)}
                              >
                                Đánh dấu đã đọc
                              </button>
                            )}
                            <button
                              className="notif-pill-btn delete"
                              type="button"
                              onClick={() => setDismissedIds(prev => new Set([...prev, item.id]))}
                            >
                              Xóa
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="notif-popover-footer">
                  <div className="notif-popover-footer-top">
                    <button
                      className="notif-popover-link-btn"
                      type="button"
                      onClick={() => {
                        const readIds = popoverItems.filter(i => i.is_read).map(i => i.id);
                        setDismissedIds(prev => new Set([...prev, ...readIds]));
                      }}
                    >
                      Xóa đã đọc
                    </button>
                    <span className="notif-popover-summary-text">
                      Tổng: {popoverItems.length} · {unread} chưa đọc
                    </span>
                  </div>
                  <button
                    className="notif-popover-view-all-btn"
                    type="button"
                    onClick={() => {
                      setNotifDropdownOpen(false);
                      n('/notifications');
                    }}
                  >
                    Xem tất cả
                  </button>
                </div>
              </div>
            )}
          </div>
          <div className="user-dropdown-container" ref={userDropdownRef}>
            <button
              className={`userchip ${userDropdownOpen ? 'active' : ''}`}
              aria-haspopup="true"
              aria-expanded={userDropdownOpen}
              onClick={()=>setUserDropdownOpen(prev=>!prev)}
              type="button"
            >
              <span className="avatar">{user.full_name.split(' ').slice(-2).map(s=>s[0]).join('').toUpperCase()}</span>
              <span className="userchip-name">{user.full_name}</span>
              <ChevronDown size={15} className={`chevron-icon ${userDropdownOpen ? 'open' : ''}`}/>
            </button>
            {userDropdownOpen && (
              <div className="user-dropdown-menu" role="menu">
                <button
                  className="user-dropdown-item"
                  role="menuitem"
                  type="button"
                  onClick={()=>{setUserDropdownOpen(false);n('/profile');}}
                >
                  <UserCircle size={18}/>
                  <span>Profile</span>
                </button>
                <button
                  className="user-dropdown-item"
                  role="menuitem"
                  type="button"
                  onClick={()=>{setUserDropdownOpen(false);n('/notifications');}}
                >
                  <Bell size={18}/>
                  <span>Notifications</span>
                </button>
                <button
                  className="user-dropdown-item logout"
                  role="menuitem"
                  type="button"
                  onClick={()=>{setUserDropdownOpen(false);onLogout();}}
                >
                  <LogOut size={18}/>
                  <span>Log out</span>
                </button>
              </div>
            )}
          </div>
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
    ['My invoices', summary.total_invoices, FileText],
    ['Approved', summary.approved, CheckCircle2],
    ['Awaiting approval', summary.pending, Clock3],
    ['Rejected', summary.rejected, XCircle],
  ];

  return <>
    <Title
      title={'Welcome back, ' + user.full_name.split(' ').slice(-2).join(' ')}
      description={employee ? 'Your expenses and upcoming trips, all in one place.' : 'Here’s your financial workspace at a glance.'}
      action={<button className="btn btn-primary" onClick={() => navigate(employee ? '/upload' : '/approvals')}><Plus size={16}/>{employee ? 'Upload invoice' : 'Review pending invoices'}</button>}
    />
    {busy ? <Loading/> : error ? <p className="error">{error}</p> : <>
      <div className="kpi-grid">
        {stats.map(([name, value, Icon]) => <div className="kpi" key={name}>
          <div className="kpi-label">{name}<Icon size={20}/></div>
          <strong>{value ?? '—'}</strong>
          <small>{name === 'Approved' ? 'Successfully processed' : name === 'Awaiting approval' ? 'Awaiting review' : 'This workspace'}</small>
        </div>)}
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
function InvoicesPage(){const[search,setSearch]=useState(''),[status,setStatus]=useState('');const {data,busy,reload,error}=useLoad('/invoices');const n=useNavigate();let rows=(data||[]).filter(i=>(i.invoice_number+' '+i.seller_name+' '+i.filename).toLowerCase().includes(search.toLowerCase())&&(!status||i.approval_status===status));return <><Title title="Invoices" description="Search, filter and review your invoice data."/><div className="panel"><div className="filters"><label className="searchbox"><Search size={17}/><input placeholder="Search invoice number or supplier..." value={search} onChange={e=>setSearch(e.target.value)}/></label><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{['draft','pending','approved','rejected'].map(s=><option key={s} value={s}>{approvalName(s)}</option>)}</select><button className="btn btn-muted" onClick={reload}><RefreshCw size={16}/></button></div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll"><table><thead><tr><th>Invoice</th><th>Supplier</th><th>Date</th><th>Amount</th><th>Validation</th><th>Approval</th><th>Lookup</th><th></th></tr></thead><tbody>{rows.map(i=><tr key={i.id}><td><strong>{i.invoice_number||'#'+i.id}</strong><small>{i.document_type}</small></td><td>{i.seller_name||'Chưa trích xuất'}</td><td>{datefmt(i.invoice_date)}</td><td className="money">{money(i.total_amount)}</td><td><Status value={i.validation_status}/></td><td><Status value={i.approval_status}/></td><td><Status value={i.lookup_status}/></td><td><button className="btn btn-small btn-muted" onClick={()=>n('/invoices/'+i.id)}>Details <ArrowRight size={14}/></button></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có hóa đơn phù hợp"/>}</div>}</div></>}
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
function UsersPage(){const{data,reload}=useLoad('/users'),[open,setOpen]=useState(false),[form,setForm]=useState({full_name:'',email:'',password:'',role:'employee'}),[message,setMessage]=useState('');async function create(e){e.preventDefault();try{await api('/users',{method:'POST',body:form});reload();setOpen(false);setMessage('Đã tạo người dùng')}catch(e){setMessage(e.message)}}async function toggle(u){try{await api('/users/'+u.id,{method:'PATCH',body:{status:u.status==='active'?'disabled':'active'}});reload()}catch(e){setMessage(e.message)}}return <><Title title="User Management" description="Manage workspace access, roles and account status. All account history is retained." action={<button className="btn btn-primary" onClick={()=>setOpen(!open)}><Plus size={17}/> Add user</button>}/><div className="two-col"><section className="panel"><h3>Workspace users <Pill>{data?.length||0} accounts</Pill></h3><div className="user-list">{(data||[]).map(u=><div className="user-row" key={u.id}><span className="avatar">{u.full_name.slice(-2).toUpperCase()}</span><div><strong>{u.full_name}</strong><small>{u.email}</small></div><Pill>{roleName(u.role)}</Pill><Pill type={u.status==='active'?'green':'red'}>{u.status}</Pill><button title="Activate / deactivate" className="iconbtn" onClick={()=>toggle(u)}><Settings size={16}/></button></div>)}</div></section><section className="panel">{open?<><h3>Add user</h3><form className="stack" onSubmit={create}><label>Full name<input required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><label>Email<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Temporary password<input type="password" required minLength={8} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Role<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{['employee','accountant','admin'].map(x=><option key={x} value={x}>{roleName(x)}</option>)}</select></label><button className="btn btn-primary"><Plus size={16}/> Create user</button></form></>:<div className="center-helper"><Users size={34}/><h3>Accounts and permissions</h3><p>Only administrators can create, edit, activate and deactivate accounts. Click Add user to create an account.</p></div>}</section></div><Notice message={message} onDismiss={()=>setMessage('')}/></>}

function NotificationsPage(){
  const notificationState=useContext(NotificationContext);
  const {items,busy,error,markRead,markAllRead}=notificationState;
  const [message,setMessage]=useState('');
  const [search,setSearch]=useState('');
  const [tab,setTab]=useState('all');
  const [dismissedIds,setDismissedIds]=useState(()=>new Set());
  const navigate=useNavigate();

  const allItems=(items||[]).filter(item=>!dismissedIds.has(item.id));
  const unreadCount=allItems.filter(i=>!i.is_read).length;
  const readCount=allItems.filter(i=>i.is_read).length;

  const filteredItems=allItems.filter(item=>{
    if(tab==='unread'&&item.is_read)return false;
    if(tab==='read'&&!item.is_read)return false;
    if(search.trim()){
      const q=search.toLowerCase();
      const content=`${item.title||''} ${item.message||''}`.toLowerCase();
      if(!content.includes(q))return false;
    }
    return true;
  });

  async function openNotification(item){
    try{
      await openNotificationAfterAccessCheck(item,api,markRead,navigate);
    }catch(actionError){setMessage(actionError.message);}
  }
  async function markAll(){
    try{
      await markAllRead();
      setMessage('Đã đánh dấu tất cả thông báo là đã đọc');
    }catch(actionError){setMessage(actionError.message);}
  }
  async function handleSingleMarkRead(id,e){
    e.stopPropagation();
    try{
      await markRead(id);
    }catch(actionError){setMessage(actionError.message);}
  }
  function handleDismiss(id,e){
    e.stopPropagation();
    setDismissedIds(prev=>new Set([...prev,id]));
  }
  function handleDeleteRead(){
    const readIds=allItems.filter(i=>i.is_read).map(i=>i.id);
    setDismissedIds(prev=>new Set([...prev,...readIds]));
    setMessage('Đã xóa các thông báo đã đọc');
  }

  const today=new Date();
  const todayItems=[];
  const earlierItems=[];
  filteredItems.forEach(item=>{
    const itemDate=item.created_at?new Date(item.created_at):null;
    if(itemDate&&isSameDay(itemDate,today)){
      todayItems.push(item);
    }else{
      earlierItems.push(item);
    }
  });

  function renderNotifItem(item){
    const {icon:Icon,colorClass,priority}=getNotifConfig(item);
    return (
      <div
        key={item.id}
        className={`notif-card-row ${!item.is_read?'unread':''}`}
        onClick={()=>openNotification(item)}
      >
        <div className={`notif-type-icon ${colorClass}`}>
          <Icon size={18}/>
        </div>
        <div className="notif-body">
          <strong className="notif-title">{item.title}</strong>
          <p className="notif-desc">{item.message}</p>
        </div>
        <div className="notif-meta-col" onClick={e=>e.stopPropagation()}>
          <span className="notif-time">{formatNotifTime(item.created_at)}</span>
          <span className={`notif-priority-tag ${priority==='Cao'?'high':'normal'}`}>{priority}</span>
          <span className="notif-dot"/>
          <button
            className="notif-pill-btn"
            type="button"
            onClick={()=>openNotification(item)}
          >
            Xem chi tiết
          </button>
          {!item.is_read&&(
            <button
              className="notif-pill-btn"
              type="button"
              onClick={e=>handleSingleMarkRead(item.id,e)}
            >
              Đánh dấu đã đọc
            </button>
          )}
          <button
            className="notif-pill-btn delete"
            type="button"
            onClick={e=>handleDismiss(item.id,e)}
          >
            Xóa
          </button>
        </div>
      </div>
    );
  }

  return <>
    <Title
      title="Notifications"
      description="Theo dõi hóa đơn, kết quả OCR, yêu cầu chỉnh sửa và lịch công tác của bạn."
    />
    <section className="panel notif-page-panel">
      <div className="notif-toolbar">
        <div className="notif-search-box">
          <Search size={16}/>
          <input
            placeholder="Tìm hóa đơn, người duyệt..."
            value={search}
            onChange={e=>setSearch(e.target.value)}
          />
        </div>
        <div className="notif-tabs">
          <button
            type="button"
            className={`notif-tab ${tab==='all'?'active':''}`}
            onClick={()=>setTab('all')}
          >
            Tất cả
          </button>
          <button
            type="button"
            className={`notif-tab ${tab==='unread'?'active':''}`}
            onClick={()=>setTab('unread')}
          >
            Chưa đọc {unreadCount>0&&<span className="notif-tab-badge">{unreadCount}</span>}
          </button>
          <button
            type="button"
            className={`notif-tab ${tab==='read'?'active':''}`}
            onClick={()=>setTab('read')}
          >
            Đã đọc {readCount>0&&<span className="notif-tab-badge">{readCount}</span>}
          </button>
        </div>
      </div>

      <div className="notif-subactions">
        <button className="notif-text-btn" type="button" onClick={markAll}>
          Đánh dấu đã đọc
        </button>
        <button className="notif-text-btn" type="button" onClick={handleDeleteRead}>
          Xóa đã đọc
        </button>
      </div>

      {busy ? (
        <Loading/>
      ) : error ? (
        <p className="error">{error}</p>
      ) : !filteredItems.length ? (
        <Empty label="Không có thông báo nào"/>
      ) : (
        <div className="notif-sections">
          {todayItems.length > 0 && (
            <div className="notif-group">
              <div className="notif-group-header">
                <strong>Today</strong>
                <span>
                  {today.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
              <div className="notif-items-list">
                {todayItems.map(renderNotifItem)}
              </div>
            </div>
          )}

          {earlierItems.length > 0 && (
            <div className="notif-group">
              <div className="notif-group-header">
                <strong>Earlier</strong>
              </div>
              <div className="notif-items-list">
                {earlierItems.map(renderNotifItem)}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="notif-footer-summary">
        <span>{allItems.length} thông báo · {unreadCount} chưa đọc · {readCount} đã đọc</span>
      </div>
    </section>
    <Notice message={message} onDismiss={()=>setMessage('')}/>
  </>;
}
function ProfilePage({user,onRefresh}){
  const [name,setName]=useState(user.full_name),[current,setCurrent]=useState(''),[next,setNext]=useState(''),[message,setMessage]=useState('');
  const inv=useLoad('/invoices');
  const n=useNavigate();
  const invoices=Array.isArray(inv.data)?inv.data:[];
  return <>
    <Title title="My Profile" description="Manage your personal details and keep track of your submitted receipts."/>
    <div className="two-col">
      <section className="panel">
        <div className="profile-card-left">
          <div className="profile-avatar">{user.full_name.split(' ').slice(-2).map(s=>s[0]).join('').toUpperCase()}</div>
          <button className="textbtn profile-change-photo" type="button" onClick={()=>setMessage('Tính năng đổi ảnh đại diện sắp ra mắt')}>Change photo</button>
          <h3 className="profile-display-name">{name || user.full_name}</h3>
          <Pill type="default">{roleName(user.role)}</Pill>
          <div className="profile-email-box"><ShieldCheck size={14}/><span>{user.email}</span></div>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h3>Personal information</h3>
          <small className="panel-sub-label">Employee ID · {user.id ? `NV-${String(user.id).padStart(4,'0')}` : 'NV-0018'}</small>
        </div>
        <form className="stack margin-top" onSubmit={async e=>{e.preventDefault();try{await api('/profile',{method:'PATCH',body:{full_name:name}});await onRefresh();setMessage('Đã lưu hồ sơ')}catch(e){setMessage(e.message)}}}>
          <label>Full name<input value={name} onChange={e=>setName(e.target.value)} required/></label>
          <label>Email<input value={user.email} disabled/></label>
          <div className="profile-btn-row">
            <button className="btn btn-primary" type="submit"><Save size={16}/> Save changes</button>
          </div>
        </form>
        <div className="password-section">
          <h4>Change password</h4>
          <form className="stack margin-top" onSubmit={async e=>{e.preventDefault();try{await api('/profile/password',{method:'PUT',body:{current_password:current,new_password:next}});setCurrent('');setNext('');setMessage('Đã thay đổi mật khẩu')}catch(e){setMessage(e.message)}}}>
            <label>Current password<input type="password" value={current} onChange={e=>setCurrent(e.target.value)}/></label>
            <label>New password<input type="password" minLength={8} value={next} onChange={e=>setNext(e.target.value)}/></label>
            <button className="btn btn-outline" type="submit"><ShieldCheck size={16}/> Update password</button>
          </form>
        </div>
      </section>
    </div>
    <section className="panel margin-top">
      <div className="panel-heading">
        <div className="heading-with-badge">
          <h3>My submitted receipts</h3>
          <span className="count-badge">{invoices.length}</span>
        </div>
        <small className="panel-sub-label">{new Date().toLocaleDateString('en-US',{month:'long',year:'numeric'})}</small>
      </div>
      {inv.busy ? <Loading/> : inv.error ? <p className="error">{inv.error}</p> : !invoices.length ? <Empty label="Chưa có hóa đơn nào được gửi"/> : (
        <div className="receipts-grid">
          {invoices.slice(0, 8).map(invoice => (
            <button key={invoice.id} className="receipt-card" type="button" onClick={()=>n('/invoices/' + invoice.id)}>
              <div className="receipt-thumb">
                <FileText size={28}/>
                <span className="receipt-number">{invoice.invoice_number || '#' + invoice.id}</span>
              </div>
              <div className="receipt-footer">
                <span className="receipt-date">{datefmt(invoice.invoice_date) || '—'}</span>
                <Status value={invoice.approval_status}/>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
    <Notice message={message} onDismiss={()=>setMessage('')}/>
  </>;
}
function AuditPage(){const{data}=useLoad('/audit-logs');return <><Title title="Audit logs" description="Review security and workflow activity across the workspace."/><section className="panel"><div className="table-scroll"><table><thead><tr><th>Event</th><th>Type</th><th>Entity</th><th>Actor ID</th><th>Time</th></tr></thead><tbody>{(data||[]).map(a=><tr key={a.id}><td><strong>{a.action}</strong></td><td>{a.entity_type}</td><td>#{a.entity_id||'—'}</td><td>{a.actor_id||'—'}</td><td>{datefmt(a.created_at)}</td></tr>)}</tbody></table>{!data?.length&&<Empty/>}</div></section></>}
export default function App(){const[user,setUser]=useState(null),[loading,setLoading]=useState(!!authStore.get());const refresh=useCallback(async()=>{let u=await api('/auth/me');setUser(u)},[]);useEffect(()=>{if(authStore.get())refresh().catch(()=>{authStore.set(null);setUser(null)}).finally(()=>setLoading(false))},[refresh]);async function logout(){
  if(typeof window!=='undefined'&&window.confirm&&!window.confirm('Bạn có chắc muốn đăng xuất?')){
    return;
  }
  try{await api('/auth/logout',{method:'POST'})}catch{}
  authStore.set(null);
  setUser(null);
}if(loading)return <Loading/>;if(!user)return <Login onLogin={setUser}/>;return <Shell user={user} onLogout={logout}><Routes><Route path="/" element={<HomePage user={user}/>}/><Route path="/invoices" element={<InvoicesPage/>}/><Route path="/invoices/:id" element={<DetailPage user={user}/>}/><Route path="/upload" element={user.role==='employee'?<UploadPage/>:<Navigate to="/invoices"/>}/><Route path="/approvals" element={user.role!=='employee'?<ApprovalsPage/>:<Navigate to="/"/>}/><Route path="/schedule" element={<SchedulePage user={user}/>}/><Route path="/ranking" element={<RankingPage/>}/><Route path="/chat" element={<ChatPage/>}/><Route path="/reports" element={user.role!=='employee'?<ReportsPage/>:<Navigate to="/"/>}/><Route path="/users" element={user.role==='admin'?<UsersPage/>:<Navigate to="/"/>}/><Route path="/audit" element={user.role==='admin'?<AuditPage/>:<Navigate to="/"/>}/><Route path="/notifications" element={<NotificationsPage/>}/><Route path="/profile" element={<ProfilePage user={user} onRefresh={refresh}/>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></Shell>}
