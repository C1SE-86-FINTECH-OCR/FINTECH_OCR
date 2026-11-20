import React,{createContext,useContext,useRef,useState,useEffect,useCallback} from 'react';
import {Routes,Route,NavLink,Navigate,useNavigate,useParams,useLocation,useSearchParams} from 'react-router-dom';
import {Home,FileUp,ClipboardCheck,CalendarDays,MessageSquare,ChartNoAxesCombined,Users,LogOut,Bell,UserCircle,Search,ArrowRight,Plus,FileText,CheckCircle2,XCircle,Clock3,RefreshCw,Download,ShieldCheck,Menu,X,Eye,EyeOff,Save,Send,ChevronLeft,ExternalLink,BarChart3,Trophy,Activity,AlertTriangle,Filter,Settings,Camera,ChevronDown,LockKeyhole,FileCode2,Pencil,UserRoundX,UserRoundCheck,Trash2} from 'lucide-react';
import {api,authStore,money,datefmt,roleName,approvalName,documentTypeName,ROOT} from './api';
import SpendingChart from './SpendingChart';
import QuickInvoiceSearch from './QuickInvoiceSearch';
import WorkspaceSearchPage from './WorkspaceSearchPage';
import EmployeeProfilePage from './EmployeeProfilePage';
import InvoiceDetailPage from './InvoiceDetailPage';
import UploadPage from './UploadPage';
import EmployeeSchedulePage from './SchedulePage';
import { getQuickDateRange } from './reportDateRanges';
import './profile.css';
import { formatNotificationTimestamp, markAllNotificationsReadAfterSuccess, markNotificationReadAfterSuccess, notificationTypeLabel, openNotificationAfterAccessCheck, unreadNotificationCount } from './notificationState';

function useLoad(path){
 const [data,setData]=useState(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[version,setVersion]=useState(0);
 const reload=useCallback(()=>setVersion(v=>v+1),[]);
 useEffect(()=>{let current=true;setBusy(true);setError('');api(path).then(value=>{if(current)setData(value)}).catch(e=>{if(current)setError(e.message)}).finally(()=>{if(current)setBusy(false)});return ()=>{current=false}},[path,version]);
 return {data,busy,error,reload,setData,setError};
}
const NotificationContext=createContext(null);
function Notice({message,onDismiss}){return message?<div className="toast" role="alert">{message}<button onClick={onDismiss} aria-label="Đóng"><X size={16}/></button></div>:null}
function Empty({label='Chưa có dữ liệu'}){return <div className="empty"><FileText size={30}/><span>{label}</span></div>}
function Loading(){return <div className="loading"><RefreshCw size={18} className="spin"/> Đang tải dữ liệu...</div>}
function Title({eyebrow,title,description,action}){return <header className="pagehead"><div><small className="eyebrow">{eyebrow||"FINTECH OCR / KHÔNG GIAN LÀM VIỆC"}</small><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action&&<div className="page-action">{action}</div>}</header>}
function Pill({children,type='default'}){return <span className={`pill pill-${type}`}>{children}</span>}
const stateType=s=>({approved:'green',valid:'green',verified:'green',pending:'orange',needs_review:'orange',draft:'gray',rejected:'red',error:'red',mismatch:'red',not_found:'red',completed:'green',in_progress:'orange'})[s]||'gray';
function Status({value}){return <Pill type={stateType(value)}>{approvalName(value)||value}</Pill>}
function Login({onLogin}){const[email,setEmail]=useState('employee@fintech.local'),[password,setPassword]=useState('Password@123'),[error,setError]=useState(''),[loading,setLoading]=useState(false);
async function submit(e){e.preventDefault();setLoading(true);setError('');try{let res=await api('/auth/login',{method:'POST',body:{email,password}});authStore.set(res.access_token);onLogin(res.user)}catch(e){setError(e.message)}finally{setLoading(false)}}
return <div className="login-wrap"><div className="login-aside"><div className="brand brand-light"><span className="brand-symbol">◈</span><span>FINTECH<strong>OCR / KHÔNG GIAN LÀM VIỆC</strong></span></div><div><p className="overline">KHÔNG GIAN QUẢN LÝ CHI TIÊU NỘI BỘ</p><h1>Từ hóa đơn giấy<br/>đến<em>dữ liệu chuẩn xác.</em></h1><p>Số hóa. Kiểm tra. Phê duyệt.<br/>Mọi công cụ cần thiết cho nhóm, trong một không gian làm việc.</p></div><div className="login-chips"><span>OCR có AI hỗ trợ</span><span>Quy trình phê duyệt</span><span>Phân tích tài chính</span></div></div><div className="login-pane"><div className="login-box"><div className="logo-circle">◈</div><small className="eyebrow">CHÀO MỪNG BẠN TRỞ LẠI</small><h2>Đăng nhập</h2><p>Truy cập không gian làm việc FINTECH OCR</p><form onSubmit={submit} className="stack"><label>Địa chỉ email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Mật khẩu<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<p className="error">{error}</p>}<button className="btn btn-primary full" disabled={loading}>{loading?"Đang đăng nhập...":"Đăng nhập vào hệ thống"} <ArrowRight size={17}/></button></form><div className="demo-account"><strong>TÀI KHOẢN DÙNG THỬ</strong>{['employee','accountant','admin'].map(role=><button key={role} onClick={()=>{setEmail(role+'@fintech.local');setPassword('Password@123')}}>{roleName(role)}<span>Dùng tài khoản này ↗</span></button>)}<small>Mật khẩu: Password@123 · Chỉ dùng để phát triển</small></div></div></div></div>}
const common=[['/',"Tổng quan",Home],['/invoices',"Danh sách hóa đơn",FileText],['/upload',"Tải hóa đơn lên",FileUp],['/schedule',"Lịch công tác",CalendarDays],['/ranking',"Xếp hạng",Trophy],['/chat',"Trò chuyện với AI",MessageSquare],['/notifications',"Thông báo",Bell],['/profile',"Hồ sơ cá nhân",UserCircle]];
function navItems(role){if(role==='employee')return common;if(role==='accountant')return [['/',"Tổng quan",Home],['/approvals',"Hàng đợi phê duyệt",ClipboardCheck],['/invoices',"Tất cả hóa đơn",FileText],['/schedule',"Lịch công tác",CalendarDays],['/ranking',"Xếp hạng",Trophy],['/chat',"Trò chuyện với AI",MessageSquare],['/reports',"Báo cáo",ChartNoAxesCombined],['/notifications',"Thông báo",Bell],['/profile',"Hồ sơ cá nhân",UserCircle]];return [['/',"Tổng quan",Home],['/approvals',"Hàng đợi phê duyệt",ClipboardCheck],['/invoices',"Tất cả hóa đơn",FileText],['/schedule',"Lịch công tác",CalendarDays],['/ranking',"Xếp hạng",Trophy],['/chat',"Trò chuyện với AI",MessageSquare],['/reports',"Báo cáo",ChartNoAxesCombined],['/users',"Quản lý người dùng",Users],['/audit',"Nhật ký kiểm toán",ShieldCheck],['/notifications',"Thông báo",Bell],['/profile',"Hồ sơ cá nhân",UserCircle]]}

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
function initials(name=''){return name.split(/\s+/).filter(Boolean).slice(-2).map(part=>part[0]).join('').toUpperCase()||'U'}
function ProfileAvatar({user,className=''}){const[src,setSrc]=useState('');useEffect(()=>{let active=true,objectUrl='';if(!user.avatar_url){setSrc('');return}const version=encodeURIComponent(user.avatar_url);api('/profile/avatar?version='+version,{raw:true,headers:{'Cache-Control':'no-cache'}}).then(r=>r.blob()).then(blob=>{objectUrl=URL.createObjectURL(blob);if(active)setSrc(objectUrl);else URL.revokeObjectURL(objectUrl)}).catch(()=>{if(active)setSrc('')});return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl)}},[user.avatar_url,user.id]);return <span className={'profile-photo '+className}>{src?<img src={src} alt=""/>:initials(user.full_name)}</span>}
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
        <NavLink to="/" aria-label="Trang chủ FINTECH OCR" className="brand"><span className="brand-symbol">{'\u25c8'}</span><span>FINTECH<strong>OCR / KHÔNG GIAN LÀM VIỆC</strong></span></NavLink>
        <span className="role-tag">{roleName(user.role)}</span>
        <nav className="nav">{navItems(user.role).map(([to,label,Icon])=><NavLink key={to} to={to} end={to==='/'} className={({isActive})=>'nav-item '+(isActive?'active':'')}>
          <Icon size={18}/><span>{label}</span>{label==="Thông báo"&&unread>0&&<b className="nav-count">{unread}</b>}
        </NavLink>)}</nav>
        <div className="sidebar-bottom"><div className="system"><span className="system-dot"/>Tất cả hệ thống đang hoạt động<small>Hóa đơn của bạn được sắp xếp gọn gàng.<br/>Công việc hằng ngày trở nên đơn giản hơn.</small></div><button className="nav-item logout" onClick={onLogout}><LogOut size={18}/>Đăng xuất</button></div>
      </aside>
      <div className="mobile-backdrop" style={{display:menu?'block':'none'}} onClick={()=>setMenu(false)}/>
      <div className="workspace"><div className="topbar">
        <button className="iconbtn menu-btn" onClick={()=>setMenu(!menu)}><Menu size={22}/></button>
        <div className="today"><CalendarDays size={16}/>{new Date().toLocaleDateString('vi-VN',{month:'long',day:'numeric',year:'numeric'})}</div>
        <div className="top-right"><QuickInvoiceSearch/>
          <div className="notif-dropdown-container" ref={notifDropdownRef}>
            <button
              className={`iconbtn bell ${notifDropdownOpen ? 'active' : ''}`}
              aria-label={unread>0?`Thông báo, ${unread} chưa đọc`:'Thông báo'}
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
              <ProfileAvatar user={user}/>
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
                  <span>Hồ sơ cá nhân</span>
                </button>
                <button
                  className="user-dropdown-item"
                  role="menuitem"
                  type="button"
                  onClick={()=>{setUserDropdownOpen(false);n('/notifications');}}
                >
                  <Bell size={18}/>
                  <span>Thông báo</span>
                </button>
                <button
                  className="user-dropdown-item logout"
                  role="menuitem"
                  type="button"
                  onClick={()=>{setUserDropdownOpen(false);onLogout();}}
                >
                  <LogOut size={18}/>
                  <span>Đăng xuất</span>
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
    ["Danh sách hóa đơn", summary.total_invoices, FileText, ''],
    ["Đã phê duyệt", summary.approved, CheckCircle2, 'approved'],
    ["Chờ phê duyệt", summary.pending, Clock3, 'pending'],
    ["Đã từ chối", summary.rejected, XCircle, 'rejected'],
  ];

  return <>
    <Title
      title={'Chào mừng trở lại, ' + user.full_name.split(' ').slice(-2).join(' ')}
      description={employee ? "Quản lý chi phí và các chuyến công tác sắp tới tại một nơi." : "Tổng quan nhanh về không gian tài chính của bạn."}
      action={<button className="btn btn-primary" onClick={() => navigate(employee ? '/upload' : '/approvals')}><Plus size={16}/>{employee ? "Tải hóa đơn lên" : "Xem hóa đơn đang chờ phê duyệt"}</button>}
    />
    {busy ? <Loading/> : error ? <p className="error">{error}</p> : <>
      <div className="kpi-grid">
        {stats.map(([name, value, Icon, status]) => <NavLink className="kpi kpi-link" key={name} to={status ? `/invoices?status=${status}` : "/invoices"}>
          <div className="kpi-label">{name}<Icon size={20}/></div>
          <strong>{value ?? '—'}</strong>
          <small>{name === "Đã phê duyệt" ? "Đã xử lý thành công" : name === "Chờ phê duyệt" ? "Chờ xem xét" : "Trong hệ thống"}</small>
        </NavLink>)}
      </div>
      <div className="dashboard-grid">
        <SpendingChart summary={summary}/>
        <section className="panel">
          <div className="panel-heading"><h3>Hóa đơn gần đây</h3><button className="textbtn" onClick={() => navigate('/invoices')}>Xem tất cả<ArrowRight size={14}/></button></div>
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
          <div className="panel-heading"><h3>Lịch công tác của tôi</h3><button className="textbtn" onClick={() => navigate('/schedule')}>Xem lịch<ArrowRight size={14}/></button></div>
          <div className="trip-list">
            {(sched.data || []).slice(0, 3).map(item => <div className="trip" key={item.id}>
              <div className="trip-time">{new Date(item.starts_at).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}</div>
              <div><strong>{item.title}</strong><small>{item.destination} · {item.employee_name}</small></div>
              <Status value={item.status}/>
            </div>)}
            {!sched.data?.length && <Empty label="Chưa có lịch công tác"/>}
          </div>
        </section>
        <section className="panel black-panel"><MessageSquare size={21}/><h3>Trao đổi về hóa đơn</h3><p>Theo dõi phê duyệt, tìm chứng từ hoặc xem thông tin chi tiêu.</p><button onClick={() => navigate('/chat')} className="black-input">Nhập câu hỏi...<ArrowRight size={18}/></button></section>
      </div>
    </>}
  </>;
}
function InvoicesPage(){const[params,setParams]=useSearchParams();const search=params.get('search')||'';const setSearch=value=>setParams(current=>{const next=new URLSearchParams(current);if(value)next.set('search',value);else next.delete('search');return next},{replace:true});const status=params.get('status')||'';const setStatus=value=>setParams(current=>{const next=new URLSearchParams(current);if(value)next.set('status',value);else next.delete('status');return next});const {data,busy,reload,error}=useLoad('/invoices?'+new URLSearchParams({...search?{search:search.trim()}:{},...status?{approval_status:status}:{}}));const n=useNavigate();let rows=(data||[]).filter(i=>(!status||i.approval_status===status));return <><Title title="Hóa đơn" description="Tìm kiếm, lọc và xem dữ liệu hóa đơn."/><div className="panel"><div className="filters"><label className="searchbox"><Search size={17}/><input placeholder="Tìm số hóa đơn hoặc nhà cung cấp..." value={search} onChange={e=>setSearch(e.target.value)}/></label><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">Tất cả trạng thái</option>{['draft','pending','approved','rejected'].map(s=><option key={s} value={s}>{approvalName(s)}</option>)}</select><button className="btn btn-muted" onClick={reload}><RefreshCw size={16}/></button></div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll"><table><thead><tr><th>Hóa đơn</th><th>Nhà cung cấp</th><th>Ngày</th><th>Số tiền</th><th>Kiểm tra dữ liệu</th><th>Phê duyệt</th><th>Tra cứu thuế</th><th></th></tr></thead><tbody>{rows.map(i=><tr key={i.id}><td><strong>{i.invoice_number||'#'+i.id}</strong><small>{documentTypeName(i.document_type)}</small></td><td>{i.seller_name||'Chưa trích xuất'}</td><td>{datefmt(i.invoice_date)}</td><td className="money">{money(i.total_amount)}</td><td><Status value={i.validation_status}/></td><td><Status value={i.approval_status}/></td><td><Status value={i.lookup_status}/></td><td><button className="btn btn-small btn-muted" onClick={()=>n('/invoices/'+i.id)}>Chi tiết<ArrowRight size={14}/></button></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có hóa đơn phù hợp"/>}</div>}</div></>}
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
  return <section className="panel risk-panel" aria-label="Đánh giá rủi ro">
    <div className="panel-heading risk-heading">
      <div className="risk-heading-main">
        <div className="risk-heading-icon"><ShieldCheck size={20}/></div>
        <div><h3>Đánh giá rủi ro</h3><p>Cảnh báo kiểm tra trùng lặp và dữ liệu bất thường, không phải kết luận gian lận.</p></div>
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
function ApprovalsPage(){const{data,busy,error}=useLoad('/invoices');const[filter,setFilter]=useState('pending');const n=useNavigate();const rows=(data||[]).filter(x=>!filter||x.approval_status===filter);return <><Title title="Hàng đợi phê duyệt" description="Xem chi tiết hóa đơn, ghi nhận kết quả tra cứu thuế và xử lý phê duyệt."/><section className="panel"><div className="tabs">{[['pending',"Chờ xử lý"],['approved',"Đã phê duyệt"],['rejected',"Đã từ chối"],['',"Tất cả"]].map(([v,name])=><button className={filter===v?'selected':''} key={name} onClick={()=>setFilter(v)}>{name} <b>{(data||[]).filter(i=>!v||i.approval_status===v).length}</b></button>)}</div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="approval-cards">{rows.map(i=><div className="approval-card" key={i.id}><div><small>{approvalName(i.document_type)}· HÓA ĐƠN #{i.id}</small><h3>{i.seller_name||i.filename}</h3><p>{i.invoice_number||"Hóa đơn mới"} · {datefmt(i.invoice_date)}</p></div><div className="approval-right"><strong>{money(i.total_amount)}</strong><Status value={i.approval_status}/><button className="btn btn-primary btn-small" onClick={()=>n('/invoices/'+i.id)}>Xem chi tiết<ArrowRight size={15}/></button></div></div>)}{!rows.length&&<Empty label="Hàng đợi đang trống"/>}</div>}</section></>}
function SchedulePage({user}){return <EmployeeSchedulePage user={user}/>}
function RankingPage(){const[params,setParams]=useSearchParams();const location=useLocation();const period=['all','month','quarter','year'].includes(params.get('period'))?params.get('period'):'all';const setPeriod=value=>setParams({period:value});const{data,busy,error}=useLoad('/ranking?period='+period);useEffect(()=>{if(!busy&&location.hash){document.getElementById(location.hash.slice(1))?.scrollIntoView({block:'center',behavior:'smooth'})}},[busy,data,location.hash]);return <><Title title="Xếp hạng công tác" description="Xếp hạng theo số chuyến công tác đã hoàn thành; không tính chuyến dự kiến hoặc đã hủy."/><section className="panel"><div className="filters"><h3>Bảng xếp hạng nhân viên</h3><select value={period} onChange={e=>setPeriod(e.target.value)}><option value="all">Toàn thời gian</option><option value="month">Tháng này</option><option value="quarter">Quý này</option><option value="year">Năm nay</option></select></div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="ranking">{(data||[]).map((r,i)=><div className="rankrow" id={'ranking-'+r.user_id} key={r.user_id}><span className="rank">#{i+1}</span><span className="avatar">{r.full_name.slice(-2).toUpperCase()}</span><strong>{r.full_name}</strong><span className="rank-score">{r.completed} chuyến hoàn thành</span></div>)}{!data?.length&&<Empty label="Chưa có chuyến công tác hoàn thành trong kỳ"/>}</div>}</section></>}
function ChatPage(){const[question,setQuestion]=useState(''),[messages,setMessages]=useState([{role:'assistant',content:'Xin chào! Tôi đang dùng chế độ truy vấn dữ liệu demo, chưa kết nối LLM. Bạn có thể hỏi: Tổng tiền hóa đơn là bao nhiêu?'}]),[sending,setSending]=useState(false);async function submit(e){e.preventDefault();if(!question.trim())return;const q=question;setQuestion('');setMessages(x=>[...x,{role:'user',content:q}]);setSending(true);try{let r=await api('/chatbot/ask',{method:'POST',body:{question:q}});setMessages(x=>[...x,{role:'assistant',content:r.answer}])}catch(e){setMessages(x=>[...x,{role:'assistant',content:e.message}])}finally{setSending(false)}}return <><Title title="Trò chuyện với AI" description="Đặt câu hỏi về dữ liệu hóa đơn trong phạm vi quyền truy cập của bạn."/><section className="panel chat-panel"><div className="chat-heading"><span className="chat-bot">◈</span><div><strong>Trợ lý dữ liệu FINTECH</strong><small>Bản thử nghiệm truy vấn dữ liệu theo quyền · chưa tích hợp LLM</small></div></div><div className="chat-messages">{messages.map((m,i)=><div className={'chat-message '+m.role} key={i}>{m.content}</div>)}{sending&&<Loading/>}</div><form className="chat-form" onSubmit={submit}><input placeholder="Hỏi về hóa đơn..." value={question} onChange={e=>setQuestion(e.target.value)}/><button className="btn btn-primary"><Send size={17}/></button></form></section></>}
function ReportsPage(){
 const navigate=useNavigate();
 const blank={approval_status:'',validation_status:'',document_type:'',search:'',invoice_date_from:'',invoice_date_to:'',seller_name:'',lookup_status:''};
 const [filters,setFilters]=useState(blank),[applied,setApplied]=useState(blank),[summary,setSummary]=useState(null),[pageData,setPageData]=useState(null),[suppliers,setSuppliers]=useState([]),[history,setHistory]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[page,setPage]=useState(0),[pageSize,setPageSize]=useState(10),[sortBy,setSortBy]=useState('date'),[sortOrder,setSortOrder]=useState('desc');
 function change(key,value){setFilters(current=>({...current,[key]:value}))}
 function paramsFor(f=applied){const p=new URLSearchParams();Object.entries(f).forEach(([k,v])=>{if(v)p.set(k,v)});return p.toString()}
 const query=paramsFor();
 async function loadHistory(){setHistory(await api('/reports/history'))}
 async function load(){setBusy(true);setError('');try{const [s,rows]=await Promise.all([api('/reports/summary'+(query?'?'+query:'')),api('/reports/invoices?'+(query?query+'&':'')+new URLSearchParams({limit:pageSize,offset:page*pageSize,sort_by:sortBy,sort_order:sortOrder}).toString())]);setSummary(s);setPageData(rows)}catch(e){setError(e.message)}finally{setBusy(false)}}
 useEffect(()=>{api('/reports/suppliers').then(setSuppliers).catch(e=>setError(e.message));loadHistory().catch(e=>setError(e.message))},[]);
 useEffect(()=>{load()},[applied,page,pageSize,sortBy,sortOrder]);
 function apply(){setPage(0);setApplied({...filters})}
 function reset(){setFilters(blank);setPage(0);setApplied(blank)}
  function quickRange(which){const range=getQuickDateRange(which);change('invoice_date_from',range.from);change('invoice_date_to',range.to)}
 async function saveBlob(response,filename){const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 async function exportNow(){setBusy(true);setError('');try{if(!summary?.invoice_count){setError('Không có hóa đơn phù hợp để xuất.');return}const exportParams=new URLSearchParams(query);exportParams.set('sort_by',sortBy);exportParams.set('sort_order',sortOrder);const response=await api('/reports/export?'+exportParams.toString(),{raw:true});const disposition=response.headers.get('content-disposition')||'',filename=disposition.match(/filename="?([^";]+)"?/i)?.[1]||'bao_cao_hoa_don.xlsx';await saveBlob(response,filename);await loadHistory()}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function download(id){try{const response=await api(`/reports/history/${id}/download`,{raw:true});const row=history.find(x=>x.id===id);await saveBlob(response,row?.filename||'bao_cao.xlsx')}catch(e){setError(e.message)}}
 const items=pageData?.items||[];const total=pageData?.total||0;const stats=[['Tổng số hóa đơn',summary?.invoice_count??'—'],['Tổng tiền trước thuế',summary?.subtotal==null?'—':money(summary.subtotal)],['Tổng tiền thuế VAT',summary?.vat_amount==null?'—':money(summary.vat_amount)],['Tổng tiền thanh toán',summary?.total_amount==null?'—':money(summary.total_amount)]];
 const filterText=f=>Object.entries(f||{}).filter(([,v])=>v).map(([k,v])=>{const label={search:'Từ khóa',invoice_date_from:'Từ ngày',invoice_date_to:'Đến ngày',seller_name:'Nhà cung cấp',approval_status:'Phê duyệt',validation_status:'Kiểm tra',lookup_status:'Tra cứu',document_type:'Loại chứng từ'}[k]||k;const value=k==='document_type'?documentTypeName(v):['approval_status','validation_status','lookup_status'].includes(k)?approvalName(v):v;return `${label}: ${value}`}).join(' · ')||'Không lọc';
 return <><Title title="Báo cáo" description="Lọc, đối chiếu và xuất dữ liệu hóa đơn theo phạm vi được cấp quyền."/>
 <section className="panel report-panel-wide"><div className="panel-heading"><h3>Bộ lọc báo cáo</h3></div><div className="report-filters">
 <label>Tìm số hóa đơn hoặc nhà cung cấp<input value={filters.search} onChange={e=>change('search',e.target.value)} placeholder="Nhập từ khóa"/></label><label>Từ ngày<input type="date" value={filters.invoice_date_from} onChange={e=>change('invoice_date_from',e.target.value)}/></label><label>Đến ngày<input type="date" value={filters.invoice_date_to} onChange={e=>change('invoice_date_to',e.target.value)}/></label>
 <label>Nhà cung cấp<select value={filters.seller_name} onChange={e=>change('seller_name',e.target.value)}><option value="">Tất cả nhà cung cấp</option>{suppliers.map(x=><option key={x} value={x}>{x}</option>)}</select></label><label>Trạng thái phê duyệt<select value={filters.approval_status} onChange={e=>change('approval_status',e.target.value)}><option value="">Tất cả</option>{['draft','pending','approved','rejected'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label>
 <label>Trạng thái kiểm tra<select value={filters.validation_status} onChange={e=>change('validation_status',e.target.value)}><option value="">Tất cả</option>{['valid','needs_review','error'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label><label>Trạng thái tra cứu<select value={filters.lookup_status} onChange={e=>change('lookup_status',e.target.value)}><option value="">Tất cả</option>{['not_checked','verified','mismatch','not_found','not_applicable'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label><label>Loại chứng từ<select value={filters.document_type} onChange={e=>change('document_type',e.target.value)}><option value="">Tất cả</option>{['einvoice','bill','unknown'].map(x=><option key={x} value={x}>{documentTypeName(x)}</option>)}</select></label></div>
 <div className="quick-ranges">{[['today','Hôm nay'],['month','Tháng này'],['prev','Tháng trước'],['year','Năm nay']].map(([v,t])=><button key={v} className="btn btn-small btn-muted" onClick={()=>quickRange(v)}>{t}</button>)}</div><div className="report-actions"><button className="btn btn-secondary" disabled={busy} onClick={apply}><Filter size={16}/>Áp dụng bộ lọc</button><button className="btn btn-muted" onClick={reset}>Đặt lại bộ lọc</button></div></section>
 {busy&&!summary?<Loading/>:error?<p className="error" role="alert">{error}</p>:<><div className="report-kpis">{stats.map(([title,value])=><section className="kpi" key={title}><small>{title}</small><strong>{value}</strong></section>)}</div>
 <section className="panel report-panel-wide"><div className="panel-heading"><h3>Xem trước hóa đơn</h3><span>{total} hóa đơn phù hợp</span></div>{busy?<Loading/>:items.length===0?<Empty label="Không tìm thấy hóa đơn phù hợp"/>:<><div className="table-scroll"><table className="report-table"><thead><tr><th>STT</th><th>Số hóa đơn</th><th><button className="sort-button" onClick={()=>{setSortBy('date');setSortOrder(sortOrder==='desc'?'asc':'desc')}}>Ngày lập hóa đơn ↕</button></th><th>Nhà cung cấp</th><th>Mã số thuế</th><th>Tiền trước thuế</th><th>Thuế VAT</th><th><button className="sort-button" onClick={()=>{setSortBy('total');setSortOrder(sortOrder==='desc'?'asc':'desc')}}>Tổng thanh toán ↕</button></th><th>Trạng thái phê duyệt</th><th></th></tr></thead><tbody>{items.map((i,n)=><tr key={i.id}><td>{page*pageSize+n+1}</td><td><button className="textbtn" onClick={()=>navigate('/invoices/'+i.id)}>{i.invoice_number||'#'+i.id}</button></td><td>{datefmt(i.invoice_date)}</td><td>{i.seller_name||'Chưa trích xuất'}</td><td>{i.seller_tax_code||'—'}</td><td>{i.subtotal==null?'—':money(i.subtotal)}</td><td>{i.vat_amount==null?'—':money(i.vat_amount)}</td><td>{i.total_amount==null?'—':money(i.total_amount)}</td><td><Status value={i.approval_status}/></td><td><button className="btn btn-small btn-muted" onClick={()=>navigate('/invoices/'+i.id)}><Eye size={14}/>Chi tiết</button></td></tr>)}</tbody></table></div><div className="report-pagination"><span>Hiển thị {total? page*pageSize+1:0}–{Math.min((page+1)*pageSize,total)} / {total}</span><select value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(0)}}><option value={10}>10 dòng</option><option value={20}>20 dòng</option><option value={50}>50 dòng</option></select><button className="btn btn-small btn-muted" disabled={!page} onClick={()=>setPage(page-1)}>Trước</button><button className="btn btn-small btn-muted" disabled={(page+1)*pageSize>=total} onClick={()=>setPage(page+1)}>Sau</button><button className="btn btn-primary" disabled={busy||!total} onClick={exportNow}><Download size={16}/>Xuất Excel (.xlsx)</button></div></>}</section>
 <section className="panel report-panel-wide"><div className="panel-heading"><h3>Lịch sử xuất báo cáo</h3><span>{history.length} lần xuất gần đây</span></div>{history.length===0?<Empty label="Chưa có lịch sử xuất báo cáo"/>:<div className="table-scroll"><table><thead><tr><th>Thời gian xuất</th><th>Người xuất</th><th>Điều kiện lọc</th><th>Số hóa đơn</th><th>Tổng giá trị</th><th>Trạng thái</th><th>Tải xuống</th></tr></thead><tbody>{history.map(h=><tr key={h.id}><td>{h.created_at?new Date(h.created_at).toLocaleString('vi-VN'):'—'}</td><td>{h.exported_by}</td><td>{filterText(h.filters)}</td><td>{h.row_count??'—'}</td><td>{h.total_amount==null?'—':money(h.total_amount)}</td><td><Status value={h.status}/></td><td><button className="textbtn" onClick={()=>download(h.id)}><Download size={15}/> Tải xuống</button></td></tr>)}</tbody></table></div>}</section></>}
 <small className="report-note">Giá trị VAT chỉ được cộng từ dữ liệu VAT đã lưu; dữ liệu thiếu được hiển thị là chưa có.</small><Notice message={error} onDismiss={()=>setError('')}/></>}
function UsersPage(){
 const {data,busy,error,reload}=useLoad('/users');
 const [form,setForm]=useState({full_name:'',email:'',password:'',role:'employee',status:'active'}),[editing,setEditing]=useState(null),[search,setSearch]=useState(''),[role,setRole]=useState(''),[status,setStatus]=useState(''),[saving,setSaving]=useState(false),[message,setMessage]=useState(''),[confirm,setConfirm]=useState(null);
 const rows=(data||[]).filter(u=>(u.full_name+' '+u.email).toLowerCase().includes(search.toLowerCase())&&(!role||u.role===role)&&(!status||u.status===status));
 function edit(u){if(saving)return;setConfirm(u?{user:u,action:'toggle'}:null);setEditing(u);setForm(u?{full_name:u.full_name,email:u.email,role:u.role,status:u.status}:{full_name:'',email:'',password:'',role:'employee',status:'active'})}
 async function save(e){e.preventDefault();setSaving(true);try{await api(editing?'/users/'+editing.id:'/users',{method:editing?'PATCH':'POST',body:{...form,full_name:form.full_name.trim(),email:form.email.trim()}});setForm(null);reload();setMessage('Đã lưu người dùng')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
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
     setConfirm(null);if(editing?.id===user.id)setForm(current=>current?{...current,status:deactivate?'disabled':'active'}:current);reload();setMessage(deactivate?'Đã vô hiệu hóa tài khoản':'Đã kích hoạt lại tài khoản');
   }catch(e){setMessage(e.message)}finally{setSaving(false)}
 }
 async function perform(){if(saving||!confirm)return;if(confirm.action==='toggle'){await toggleAccount(confirm.user);return}setSaving(true);try{await api('/users/'+confirm.user.id,confirm.action==='delete'?{method:'DELETE'}:{method:'PATCH',body:{status:confirm.user.status==='active'?'disabled':'active'}});setConfirm(null);reload();setMessage('Đã cập nhật tài khoản')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
 const active=(data||[]).filter(u=>u.status==='active').length;
 const permissions={employee:'Tải hóa đơn cá nhân, xem lịch công tác và trò chuyện với AI. Không có quyền phê duyệt hoặc quản lý người dùng.',accountant:'Kiểm tra hóa đơn, phê duyệt chi phí, quản lý lịch công tác và xem báo cáo.',admin:'Quản lý người dùng, phân quyền, hóa đơn và lịch sử kiểm toán.'};
 const actionLabel=confirm?.action==='delete'?'Xóa tài khoản':confirm?.user.status==='active'?'Vô hiệu hóa tài khoản':'Kích hoạt lại tài khoản';
 return <div className="users-page"><Title title="Quản lý người dùng" description="Quản lý quyền truy cập, vai trò và trạng thái tài khoản. Lịch sử tài khoản được lưu giữ."/>
 <div className={'users-layout '+(!form?'form-closed':'')}><div className="users-main"><section className="panel users-table-panel"><div className="panel-heading"><h3>Danh sách người dùng <span className="users-count">{data?.length||0}</span></h3><small>{active} đang hoạt động · {(data?.length||0)-active} đã vô hiệu hóa</small></div><div className="filters users-filters"><label className="searchbox"><Search size={15}/><input aria-label="Tìm người dùng" placeholder="Tìm theo tên hoặc email" value={search} onChange={e=>setSearch(e.target.value)}/></label><select aria-label="Lọc vai trò" value={role} onChange={e=>setRole(e.target.value)}><option value="">Tất cả vai trò</option>{['employee','accountant','admin'].map(r=><option key={r} value={r}>{roleName(r)}</option>)}</select><button className="btn btn-primary" onClick={()=>edit(null)}><Plus size={15}/> Thêm người dùng</button></div>
 {busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll users-scroll" tabIndex={0} role="region" aria-label="Danh sách người dùng"><table><thead><tr><th>Họ tên</th><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th>Thao tác</th></tr></thead><tbody>{rows.map(u=><tr key={u.id} className={confirm?.user.id===u.id?'user-selected':''} onClick={()=>edit(u)}><td><div className="user-identity"><span className={`avatar user-avatar avatar-tone-${u.id%5}`}>{u.full_name.split(/\s+/).filter(Boolean).slice(-2).map(x=>x[0]).join('').toUpperCase()}</span><button className="user-select-button" aria-pressed={confirm?.user.id===u.id} disabled={saving} onClick={e=>{e.stopPropagation();edit(u)}}>{u.full_name}</button></div></td><td>{u.email}</td><td><Pill>{roleName(u.role)}</Pill></td><td><Pill type={u.status==='active'?'green':'gray'}>{u.status==='active'?'Đang hoạt động':'Đã vô hiệu hóa'}</Pill></td><td className="user-last-login">{u.last_login_at?new Date(u.last_login_at).toLocaleString('vi-VN',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'Chưa đăng nhập'}</td><td><div className="user-actions" onClick={e=>e.stopPropagation()}><button className="iconbtn" title="Sửa người dùng" aria-label={'Sửa '+u.full_name} disabled={saving} onClick={()=>edit(u)}><Pencil size={15}/></button><button className="iconbtn" title={u.status==='active'?'Vô hiệu hóa':'Kích hoạt lại'} aria-label={(u.status==='active'?'Vô hiệu hóa ':'Kích hoạt lại ')+u.full_name} disabled={saving} onClick={()=>edit(u)}>{u.status==='active'?<UserRoundX size={15}/>:<UserRoundCheck size={15}/>}</button><button className="iconbtn danger-action" title="Xóa người dùng" aria-label={'Xóa '+u.full_name} disabled={saving} onClick={()=>setConfirm({user:u,action:'delete'})}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có người dùng phù hợp"/>}</div>}<footer className="users-table-footer"><span>Hiển thị {rows.length} / {data?.length||0} người dùng</span><span><Pencil size={12}/> Sửa <UserRoundX size={13}/> Vô hiệu hóa / Kích hoạt lại</span></footer></section>
 {confirm&&<section className="panel user-confirm" aria-labelledby="confirm-title"><div className="panel-heading"><h3 id="confirm-title"><UserRoundX size={18}/> {actionLabel}?</h3><button className="iconbtn" disabled={saving} aria-label="Hủy thao tác" onClick={()=>setConfirm(null)}><X size={16}/></button></div><strong>{confirm.user.full_name} · {confirm.user.email}</strong><p>{confirm.action==='delete'?'Thao tác xóa không thể hoàn tác. Tài khoản đã có lịch sử liên quan cần được vô hiệu hóa.':confirm.user.status==='active'?'Người dùng sẽ không thể đăng nhập; lịch sử tài khoản vẫn được giữ lại.':'Cho phép người dùng đăng nhập trở lại.'}</p><div className="user-confirm-actions"><button disabled={saving} className="btn btn-muted" onClick={()=>setConfirm(null)}>Hủy</button><button disabled={saving} className="btn btn-primary" onClick={perform}>{saving?'Đang xử lý...':actionLabel}</button></div></section>}
 </div>
 {form&&<aside className="panel user-editor" aria-labelledby="user-form-title"><div className="panel-heading"><h3 id="user-form-title">Thêm / Sửa người dùng</h3><button className="iconbtn" disabled={saving} aria-label="Đóng biểu mẫu" onClick={()=>setForm(null)}><X size={16}/></button></div><p>{editing?'Cập nhật thông tin thành viên.':'Tạo tài khoản thành viên mới.'}</p><form className="stack" onSubmit={save}><label>Họ và tên<input required minLength={2} maxLength={150} value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><label>Email<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>{!editing&&<label>Mật khẩu tạm thời<input type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/><small>Tối thiểu 8 ký tự.</small></label>}<label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{['employee','accountant','admin'].map(r=><option key={r} value={r}>{roleName(r)}</option>)}</select></label><div className="user-permissions"><strong><ShieldCheck size={13}/> {roleName(form.role)} — quyền truy cập</strong><p>{permissions[form.role]}</p></div><label className="user-active-toggle"><span>Đang hoạt động<small>Cho phép người dùng đăng nhập</small></span><input type="checkbox" role="switch" aria-label="Trạng thái kích hoạt tài khoản" disabled={saving} checked={form.status==='active'} onChange={e=>setForm({...form,status:e.target.checked?'active':'disabled'})}/></label><div className="user-editor-actions"><button type="button" disabled={saving} className="btn btn-muted" onClick={()=>setForm(null)}>Hủy</button><button disabled={saving} className="btn btn-primary">{saving?'Đang lưu...':editing?'Lưu thay đổi':'Tạo người dùng'}</button></div></form></aside>}
 </div>
 <Notice message={message} onDismiss={()=>setMessage('')}/></div>;
}
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
const passwordRules=value=>value.length>=8&&/[A-Z]/.test(value)&&/[a-z]/.test(value)&&/\d/.test(value)&&/[^A-Za-z0-9]/.test(value);
function ProfilePage({user,onRefresh}){
 const navigate=useNavigate();const {data:profile,reload:reloadProfile}=useLoad('/profile');const {data:invoices,busy,error,reload}=useLoad('/invoices?limit=250');
 const [modal,setModal]=useState(''),[message,setMessage]=useState(''),[saving,setSaving]=useState(false);const [form,setForm]=useState({full_name:user.full_name,phone:'',team:''}),[photo,setPhoto]=useState(null),[photoPreview,setPhotoPreview]=useState('');const [password,setPassword]=useState({current_password:'',new_password:'',confirm_password:''}),[visible,setVisible]=useState({});const current=profile||user;
 useEffect(()=>{if(profile)setForm({full_name:profile.full_name||'',phone:profile.phone||'',team:profile.team||''})},[profile]);
 function profileErrorMessage(error){const detail=error?.message||'';if(detail==="Mật khẩu hiện tại không đúng")return 'Mật khẩu hiện tại không đúng';if(/^(HTTP \d+|String should|Value error|Input should|Field required)/i.test(detail))return 'Không thể lưu thông tin. Vui lòng kiểm tra dữ liệu và thử lại.';return detail||'Đã xảy ra lỗi. Vui lòng thử lại.'}
 function openEdit(){setForm({full_name:current.full_name||'',phone:current.phone||'',team:current.team||''});setPhoto(null);setPhotoPreview('');setModal('edit')}
 function choosePhoto(file){if(!file)return;if(!['image/jpeg','image/png'].includes(file.type)){setMessage('Vui lòng chọn ảnh JPG hoặc PNG');return}if(file.size>5*1024*1024){setMessage('Dung lượng ảnh không được vượt quá 5 MB');return}setPhoto(file);setPhotoPreview(URL.createObjectURL(file))}
 async function saveProfile(e){e.preventDefault();if(form.full_name.trim().length<2){setMessage('Họ và tên phải có ít nhất 2 ký tự');return}if(form.phone&&!/^[+()\-\d .]{7,30}$/.test(form.phone.trim())){setMessage('Vui lòng nhập số điện thoại hợp lệ');return}setSaving(true);setMessage('');try{if(photo){const body=new FormData();body.append('file',photo);await api('/profile/avatar',{method:'POST',body})}await api('/profile',{method:'PATCH',body:{full_name:form.full_name.trim(),phone:form.phone.trim()||null,team:form.team.trim()||null}});await Promise.all([onRefresh(),reloadProfile()]);setModal('');setMessage('Đã cập nhật hồ sơ thành công')}catch(e){setMessage(profileErrorMessage(e))}finally{setSaving(false)}}
 async function changePassword(e){e.preventDefault();setMessage('');if(password.new_password!==password.confirm_password){setMessage('Mật khẩu mới và xác nhận mật khẩu không khớp');return}if(!passwordRules(password.new_password)){setMessage('Mật khẩu cần có ít nhất 8 ký tự, gồm chữ hoa, chữ thường, chữ số và ký tự đặc biệt');return}setSaving(true);try{await api('/profile/password',{method:'PUT',body:{current_password:password.current_password,new_password:password.new_password}});setPassword({current_password:'',new_password:'',confirm_password:''});setModal('');setMessage('Đã đổi mật khẩu thành công')}catch(e){setMessage(profileErrorMessage(e))}finally{setSaving(false)}}
 function pwField(key,label){return <label className="password-field">{label}<span><input required minLength={key==='new_password'||key==='confirm_password'?8:undefined} type={visible[key]?'text':'password'} value={password[key]} onChange={e=>setPassword({...password,[key]:e.target.value})}/><button type="button" aria-label={visible[key]?'Ẩn mật khẩu':'Hiện mật khẩu'} onClick={()=>setVisible({...visible,[key]:!visible[key]})}>{visible[key]?<EyeOff size={19}/>:<Eye size={19}/>}</button></span></label>}
 return <><Title title="Hồ sơ cá nhân" description="Quản lý thông tin cá nhân và theo dõi các hóa đơn của bạn."/><div className="profile-overview"><section className="panel profile-identity"><ProfileAvatar user={current}/><button type="button" className="textbtn profile-photo-trigger" onClick={openEdit}><Camera size={15}/> Đổi ảnh đại diện</button><h2>{current.full_name}</h2><Pill><LockKeyhole size={13}/>{roleName(current.role)}</Pill><label className="profile-readonly-label">Địa chỉ email <LockKeyhole size={14}/></label><div className="profile-readonly">{current.email}</div></section><section className="panel profile-information"><div className="profile-section-heading"><h3>Thông tin cá nhân</h3>{current.employee_code&&<span>Mã nhân viên - {current.employee_code}</span>}</div><div className="profile-field"><label>Họ và tên</label><div>{current.full_name}</div></div><div className="profile-field-pair"><div className="profile-field"><label>Số điện thoại</label><div>{current.phone||'Chưa cập nhật'}</div></div><div className="profile-field"><label>Phòng ban</label><div>{current.team||'Chưa cập nhật'}</div></div></div><div className="profile-actions"><button className="btn btn-outline" onClick={openEdit}>Chỉnh sửa hồ sơ</button><button className="textbtn change-password-link" onClick={()=>{setPassword({current_password:'',new_password:'',confirm_password:''});setModal('password')}}><LockKeyhole size={17}/> Đổi mật khẩu</button><span className="readonly-badge"><LockKeyhole size={15}/> Chỉ xem</span></div></section></div><section className="panel receipts-panel"><div className="receipts-heading"><h3>{user.role==='employee'?'Hóa đơn đã gửi':'Hóa đơn trong hệ thống'}</h3><span>{Array.isArray(invoices)?invoices.length:0}</span></div>{busy?<Loading/>:error?<div className="profile-invoice-state"><p className="error">{error}</p><button className="btn btn-outline" onClick={reload}>Thử lại</button></div>:!invoices?.length?<Empty label="Chưa có hóa đơn"/>:<div className="receipt-grid">{invoices.map(item=><button className="receipt-card" key={item.id} onClick={()=>navigate('/invoices/'+item.id)}><span className="receipt-thumb"><InvoiceThumbnail invoice={item}/><span className="receipt-preview-action" aria-hidden="true"><Eye size={18}/><small>Xem chi tiết</small></span></span><span className="receipt-meta"><span>{datefmt(item.invoice_date||item.created_at)}</span><Status value={item.approval_status}/></span><strong>{item.seller_name||item.filename}</strong></button>)}</div>}</section>{modal&&<div className="modal-backdrop" onMouseDown={e=>e.target===e.currentTarget&&setModal('')}><section className="profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title"><header><h2 id="profile-modal-title">{modal==='edit'?'Chỉnh sửa hồ sơ':'Đổi mật khẩu'}</h2><button className="iconbtn" aria-label="Đóng hộp thoại" onClick={()=>setModal('')}><X size={22}/></button></header>{modal==='edit'?<form onSubmit={saveProfile}><p className="modal-description">Cập nhật thông tin cá nhân. Vai trò và địa chỉ email không thể thay đổi.</p><div className="modal-avatar-row"><span className="profile-photo">{photoPreview?<img src={photoPreview} alt="Ảnh đại diện xem trước"/>:<ProfileAvatar user={current}/>}</span><div><label className="btn btn-outline photo-select">Đổi ảnh đại diện<input type="file" accept="image/jpeg,image/png" onChange={e=>choosePhoto(e.target.files?.[0])}/></label><small>Ảnh JPG hoặc PNG · Tối đa 5 MB</small></div></div><label className="modal-field">Họ và tên<input required minLength="2" maxLength="150" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><div className="modal-field-pair"><label className="modal-field">Số điện thoại<input type="tel" maxLength="30" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label><label className="modal-field">Phòng ban<input maxLength="120" value={form.team} onChange={e=>setForm({...form,team:e.target.value})}/></label></div><label className="modal-field readonly-input">Địa chỉ email <LockKeyhole size={14}/><input value={current.email} disabled/></label><label className="modal-field readonly-input">Vai trò <LockKeyhole size={14}/><input value={roleName(current.role)} disabled/></label><footer><button type="button" className="btn btn-outline" onClick={()=>setModal('')}>Hủy</button><button className="btn btn-primary" disabled={saving}>{saving?'Đang lưu...':'Lưu thay đổi'}</button></footer></form>:<form onSubmit={changePassword}><p className="modal-description">Hãy sử dụng mật khẩu riêng, an toàn và chưa dùng cho tài khoản khác.</p>{pwField('current_password','Mật khẩu hiện tại')}{pwField('new_password','Mật khẩu mới')}{pwField('confirm_password','Xác nhận mật khẩu mới')}<small className="password-hint">Mật khẩu cần có ít nhất 8 ký tự, gồm chữ hoa, chữ thường, chữ số và ký tự đặc biệt.</small><footer><button type="button" className="btn btn-outline" onClick={()=>setModal('')}>Hủy</button><button className="btn btn-primary" disabled={saving}>{saving?'Đang lưu...':'Đổi mật khẩu'}</button></footer></form>}</section></div>}<Notice message={message} onDismiss={()=>setMessage('')}/></>}
function InvoiceThumbnail({invoice}){const[src,setSrc]=useState(''),[kind,setKind]=useState('loading');useEffect(()=>{let active=true,objectUrl='';setSrc('');setKind('loading');api(`/invoices/${invoice.id}/thumbnail`,{raw:true}).then(async response=>{const type=response.headers.get('content-type')||'';if(type.includes('application/json')){const result=await response.json();if(active)setKind(result.kind==='xml'?'xml':'default');return}if(!type.startsWith('image/'))throw new Error('Không thể tải ảnh xem trước');const blob=await response.blob();objectUrl=URL.createObjectURL(blob);if(active){setSrc(objectUrl);setKind('image')}else URL.revokeObjectURL(objectUrl)}).catch(()=>{if(active)setKind('default')});return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl)}},[invoice.id]);if(kind==='loading')return <span className="receipt-thumb-loading" role="status" aria-label="Đang tải ảnh xem trước"><RefreshCw size={20} className="spin"/></span>;if(kind==='image')return <img src={src} alt={`Hóa đơn ${invoice.filename||invoice.id}`}/>;if(kind==='xml')return <span className="receipt-document receipt-xml"><FileCode2 size={38}/><small>Tệp XML</small></span>;return <span className="receipt-document"><FileText size={34}/><small>{invoice.filename?.split('.').pop()?.toUpperCase()||'TỆP'}</small></span>}

function auditActionLabel(action){return ({'invoice.uploaded':'Tải hóa đơn lên','invoice.submitted':'Gửi hóa đơn phê duyệt','invoice.approved':'Phê duyệt hóa đơn','invoice.rejected':'Từ chối hóa đơn','schedule.created':'Tạo lịch công tác','schedule.updated':'Cập nhật lịch công tác','user.created':'Tạo người dùng','user.updated':'Cập nhật người dùng'})[action]||action}
function auditEntityLabel(entity){return ({invoice:'Hóa đơn',schedule:'Lịch công tác',user:'Tài khoản'})[entity]||entity}
function AuditPage(){const{data}=useLoad('/audit-logs');return <><Title title="Nhật ký kiểm toán" description="Theo dõi hoạt động bảo mật và quy trình trong hệ thống."/><section className="panel"><div className="table-scroll"><table><thead><tr><th>Sự kiện</th><th>Loại</th><th>Đối tượng</th><th>Mã người thực hiện</th><th>Thời gian</th></tr></thead><tbody>{(data||[]).map(a=><tr key={a.id}><td><strong>{auditActionLabel(a.action)}</strong></td><td>{auditEntityLabel(a.entity_type)}</td><td>#{a.entity_id||'—'}</td><td>{a.actor_id||'—'}</td><td>{datefmt(a.created_at)}</td></tr>)}</tbody></table>{!data?.length&&<Empty/>}</div></section></>}
export default function App(){
  const[user,setUser]=useState(null),[loading,setLoading]=useState(!!authStore.get());
  const refresh=useCallback(async()=>{let u=await api('/auth/me');setUser(u)},[]);
  useEffect(()=>{if(authStore.get())refresh().catch(()=>{authStore.set(null);setUser(null)}).finally(()=>setLoading(false))},[refresh]);
  async function logout(){
    if(typeof window!=='undefined'&&window.confirm&&!window.confirm('Bạn có chắc muốn đăng xuất?')){
      return;
    }
    try{await api('/auth/logout',{method:'POST'})}catch{}
    authStore.set(null);
    setUser(null);
  }
  if(loading)return <Loading/>;
  if(!user)return <Login onLogin={setUser}/>;
  return <Shell user={user} onLogout={logout}>
    <Routes>
      <Route path="/people/:id" element={<EmployeeProfilePage/>}/>
      <Route path="/search" element={<WorkspaceSearchPage/>}/>
      <Route path="/" element={<HomePage user={user}/>}/>
      <Route path="/invoices" element={<InvoicesPage/>}/>
      <Route path="/invoices/:id" element={<DetailPage user={user}/>}/>
      <Route path="/upload" element={user.role==='employee'?<UploadPage/>:<Navigate to="/invoices"/>}/>
      <Route path="/approvals" element={user.role!=='employee'?<ApprovalsPage/>:<Navigate to="/"/>}/>
      <Route path="/schedule" element={<SchedulePage user={user}/>}/>
      <Route path="/ranking" element={<RankingPage/>}/>
      <Route path="/chat" element={<ChatPage/>}/>
      <Route path="/reports" element={user.role!=='employee'?<ReportsPage/>:<Navigate to="/"/>}/>
      <Route path="/users" element={user.role==='admin'?<UsersPage/>:<Navigate to="/"/>}/>
      <Route path="/audit" element={user.role==='admin'?<AuditPage/>:<Navigate to="/"/>}/>
      <Route path="/notifications" element={<NotificationsPage/>}/>
      <Route path="/profile" element={<ProfilePage user={user} onRefresh={refresh}/>}/>
      <Route path="*" element={<Navigate to="/"/>}/>
    </Routes>
  </Shell>;
}
