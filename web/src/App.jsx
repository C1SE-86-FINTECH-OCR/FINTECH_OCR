import TravelPage, {TravelDashboardNotice} from './TravelPage.jsx';
import {Wallet as TravelWallet} from 'lucide-react';
import {SLABadge, SLAOverview} from './ApprovalSLA.jsx';
import ChatToolResult from './ChatToolResult.jsx';
import {InvoiceVerificationPanel} from './InvoiceVerificationReport.jsx';
import TaxVerificationCard from './TaxVerificationCard.jsx';
import FinancePage,{FinancialAnalysisCard} from './FinancePage.jsx';
import PeriodFilter from './PeriodFilter';
import {currentPeriod, periodQuery, validPeriod} from './periodFilters';
import BrandLogo,{BrandMark} from './BrandLogo.jsx';
import InvoiceDateFilter from './InvoiceDateFilter.jsx';
import {invoiceDateRange,emptyProfileInvoiceRange,profileInvoiceQuery} from './invoiceDateFilter.js';
import React,{createContext,useContext,useRef,useState,useEffect,useCallback,useMemo} from 'react';
import {Routes,Route,NavLink,Navigate,useNavigate,useParams,useLocation,useSearchParams} from 'react-router-dom';
import {Home,FileUp,ClipboardCheck,CalendarDays,MessageSquare,ChartNoAxesCombined,Users,LogOut,Bell,UserCircle,Search,ArrowRight,Plus,FileText,CheckCircle2,XCircle,Clock3,RefreshCw,Download,ShieldCheck,Menu,X,Eye,EyeOff,Save,Send,Square,ChevronLeft,ExternalLink,BarChart3,Trophy,Activity,AlertTriangle,Filter,Settings,Camera,ChevronDown,LockKeyhole,FileCode2,ScanText,Pencil,UserRoundX,UserRoundCheck,Trash2,Sparkles,ThumbsUp,ThumbsDown,Copy,Check,ArrowUp,Lock,Bookmark,Globe} from 'lucide-react';
import {api,authStore,money,datefmt,roleName,approvalName,documentTypeName,ROOT} from './api';
import SpendingChart from './SpendingChart';
import QuickInvoiceSearch from './QuickInvoiceSearch';
import WorkspaceSearchPage from './WorkspaceSearchPage';
import { matchesWorkspaceText } from './workspaceSearch';
import EmployeeProfilePage from './EmployeeProfilePage';
import ChatMarkdown from './ChatMarkdown.js';
import InvoiceDetailPage from './InvoiceDetailPage';
import './invoiceMessages.css';
import UploadPage from './UploadPage';
import EmployeeSchedulePage from './SchedulePage';
import { getQuickDateRange } from './reportDateRanges';
import {reportQueries} from './reportQueries.js';
import './profile.css';
import { formatNotificationTimestamp, markAllNotificationsReadAfterSuccess, markNotificationReadAfterSuccess, notificationTypeLabel, openNotificationAfterAccessCheck, unreadNotificationCount } from './notificationState';
import {
  FileUp as UploadIcon,
  ScanText as ExtractIcon,
  ClipboardCheck as ReviewIcon,
  ArrowRight as FlowArrow
} from 'lucide-react';

function useLoad(path,{allPages=false}={}){
 const [data,setData]=useState(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[version,setVersion]=useState(0);
 const reload=useCallback(()=>setVersion(v=>v+1),[]);
 useEffect(()=>{
   let current=true;
   async function load(){
     setBusy(true);
     setError('');
     try{
       if(!allPages){
         const value=await api(path);
         if(current)setData(value);
         return;
       }
       const items=[];
       const limit=250;
       const separator=path.includes('?')?'&':'?';
       while(current){
         const page=await api(path+separator+'limit='+limit+'&offset='+items.length);
         items.push(...page);
         if(page.length<limit){
           if(current)setData(items);
           return;
         }
       }
     }catch(e){
       if(current)setError(e.message);
     }finally{
       if(current)setBusy(false);
     }
   }
   load();
   return ()=>{current=false};
 },[path,version,allPages]);
 return {data,busy,error,reload,setData,setError};
}
const NotificationContext=createContext(null);
function Notice({message,onDismiss}){return message?<div className="toast" role="alert">{message}<button onClick={onDismiss} aria-label="Đóng"><X size={16}/></button></div>:null}
function Empty({label='Chưa có dữ liệu'}){return <div className="empty"><FileText size={30}/><span>{label}</span></div>}
function Loading(){return <div className="loading"><RefreshCw size={18} className="spin"/> Đang tải dữ liệu...</div>}
function Title({eyebrow,title,description,action}){return <header className="pagehead"><div><small className="eyebrow">{eyebrow||"FINTECH OCR / KHÔNG GIAN LÀM VIỆC"}</small><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action&&<div className="page-action">{action}</div>}</header>}
function Pill({children,type='default'}){return <span className={`pill pill-${type}`}>{children}</span>}
const stateType=s=>({approved:'green',valid:'green',verified:'green',pending:'orange',needs_review:'orange',draft:'gray',rejected:'red',error:'red',mismatch:'red',not_found:'red',completed:'green',in_progress:'orange'})[s]||'gray';
function Status({value}){if(value==='draft')return null;return <Pill type={stateType(value)}>{approvalName(value)||value}</Pill>}
function Login({onLogin}){const[email,setEmail]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(false);
async function submit(e){e.preventDefault();setLoading(true);setError('');try{let res=await api('/auth/login',{method:'POST',body:{email,password}});authStore.set(res.access_token);onLogin(res.user)}catch(e){setError(e.message)}finally{setLoading(false)}}
return <div className="login-wrap"><div className="login-aside"><div className="brand brand-light"><BrandLogo/></div><div><p className="overline">KHÔNG GIAN QUẢN LÝ CHI TIÊU NỘI BỘ</p><h1 style={{fontSize:'clamp(38px, 3.8vw, 62px)',lineHeight:1.15,letterSpacing:'-0.035em',fontWeight:750}}>
  Từ hóa đơn giấy<br/>đến{' '}<em>dữ liệu chuẩn xác.</em>
</h1>
<p>Số hóa hóa đơn. Chuẩn hóa dữ liệu. Tối ưu chi tiêu.<br/>Nền tảng quản lý tài chính thông minh dành cho doanh nghiệp.</p>
<div style={{marginTop:28,padding:'22px 24px',background:'rgba(255,255,255,0.035)',border:'1px solid rgba(174,188,219,0.16)',borderRadius:18}}>
  <div style={{color:'#aebcdb',fontSize:12,fontWeight:600,letterSpacing:'0.08em',marginBottom:24}}>QUY TRÌNH XỬ LÝ THÔNG MINH</div>
  <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:8}}>
    {[[FileUp,'Tải hóa đơn','Tiếp nhận chứng từ'],[ScanText,'AI trích xuất','Số hóa dữ liệu'],[ClipboardCheck,'Kiểm duyệt','Xác thực thông tin']].map(([Icon,label,description],index)=>(
      <React.Fragment key={label}>
        {index>0&&<ArrowRight aria-hidden="true" size={20} style={{color:'#778295',marginTop:19,flexShrink:0}}/>}
        <div style={{flex:1,minWidth:0,textAlign:'center'}}>
          <div style={{width:56,height:56,margin:'0 auto 12px',display:'grid',placeItems:'center',background:'rgba(174,188,219,0.08)',border:'1px solid rgba(174,188,219,0.18)',borderRadius:15,color:'#aebcdb'}}>
            <Icon aria-hidden="true" size={26} strokeWidth={1.6}/>
          </div>
          <div style={{color:'#f1f3f5',fontSize:14,fontWeight:600}}>{label}</div>
          <div style={{color:'#929aa8',fontSize:11,marginTop:6,lineHeight:1.5}}>{description}</div>
        </div>
      </React.Fragment>
    ))}
  </div>
</div></div></div><div className="login-pane"><div className="login-box"><div className="logo-circle fintech-login-mark" aria-label="FINTECH"><BrandMark/></div><small className="eyebrow">CHÀO MỪNG BẠN TRỞ LẠI</small><h2>Đăng nhập</h2><p>Truy cập không gian làm việc FINTECH OCR</p><form onSubmit={submit} className="stack" autoComplete="off"><label>Địa chỉ email<input type="email" name="login-email" autoComplete="off" autoCapitalize="none" spellCheck={false} value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Mật khẩu<input type="password" name="login-password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<p className="error">{error}</p>}<button className="btn btn-primary full" disabled={loading}>{loading?"Đang đăng nhập...":"Đăng nhập vào hệ thống"} <ArrowRight size={17}/></button></form></div></div></div>}
const messageNavItem=['/messages',"Tin nhắn",MessageSquare];
const common=[['/',"Tổng quan",Home],['/invoices',"Danh sách hóa đơn",FileText],['/upload',"Tải hóa đơn lên",FileUp],['/schedule',"Lịch công tác",CalendarDays],['/travel',"Tạm ứng và quyết toán",TravelWallet],['/ranking',"Xếp hạng",Trophy],['/chat',"Trò chuyện với AI",MessageSquare],messageNavItem,['/notifications',"Thông báo",Bell],['/profile',"Hồ sơ cá nhân",UserCircle]];
function navItems(role){if(role==='employee')return common;if(role==='accountant')return [['/',"Tổng quan",Home],['/approvals',"Hàng đợi phê duyệt",ClipboardCheck],['/invoices',"Tất cả hóa đơn",FileText],['/schedule',"Lịch công tác",CalendarDays],['/travel',"Tạm ứng và quyết toán",TravelWallet],['/ranking',"Xếp hạng",Trophy],['/chat',"Trò chuyện với AI",MessageSquare],['/reports',"Báo cáo",ChartNoAxesCombined],messageNavItem,['/notifications',"Thông báo",Bell],['/profile',"Hồ sơ cá nhân",UserCircle]];return [['/',"Tổng quan",Home],['/approvals',"Hàng đợi phê duyệt",ClipboardCheck],['/invoices',"Tất cả hóa đơn",FileText],['/schedule',"Lịch công tác",CalendarDays],['/travel',"Tạm ứng và quyết toán",TravelWallet],['/ranking',"Xếp hạng",Trophy],['/chat',"Trò chuyện với AI",MessageSquare],['/reports',"Báo cáo",ChartNoAxesCombined],['/users',"Quản lý người dùng",Users],['/audit',"Nhật ký hoạt động",ShieldCheck],messageNavItem,['/notifications',"Thông báo",Bell],['/profile',"Hồ sơ cá nhân",UserCircle]]}

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
  const [bellPopup, setBellPopup] = useState(null);
  const bellPopupTimerRef = useRef(null);
  const lastSeenNotifIdRef = useRef(null);
  const initialLoadRef = useRef(true);
  const userDropdownRef = useRef(null);
  const notifDropdownRef = useRef(null);
  const [dismissedIds, setDismissedIds] = useState(() => new Set());
  const notes=useLoad('/notifications');
  const unreadCountState=useLoad('/notifications/unread-count');
  const previousPath=useRef(loc.pathname);
  const items=Array.isArray(notes.data)?notes.data:[];
  const unread=Number.isInteger(unreadCountState.data?.count)?unreadCountState.data.count:unreadNotificationCount(items);

  const triggerBellPopup = useCallback((notif) => {
    if (!notif) return;
    if (bellPopupTimerRef.current) clearTimeout(bellPopupTimerRef.current);
    setBellPopup(notif);
    bellPopupTimerRef.current = setTimeout(() => {
      setBellPopup(null);
    }, 5000); // 5s tự biến mất
  }, []);

  useEffect(() => {
    if (!Array.isArray(items) || items.length === 0) return;
    const latest = items[0];
    if (initialLoadRef.current) {
      initialLoadRef.current = false;
      lastSeenNotifIdRef.current = latest.id;
      if (!latest.is_read) {
        triggerBellPopup(latest);
      }
      return;
    }
    if (lastSeenNotifIdRef.current != null && latest.id > lastSeenNotifIdRef.current) {
      lastSeenNotifIdRef.current = latest.id;
      triggerBellPopup(latest);
    } else if (lastSeenNotifIdRef.current == null) {
      lastSeenNotifIdRef.current = latest.id;
    }
  }, [items, triggerBellPopup]);

  useEffect(() => {
    function handleCustomBell(e) {
      if (e.detail) {
        triggerBellPopup(e.detail);
      }
    }
    window.addEventListener('fintech_bell_notification', handleCustomBell);
    return () => window.removeEventListener('fintech_bell_notification', handleCustomBell);
  }, [triggerBellPopup]);

  useEffect(() => {
    const timer = setInterval(() => {
      notes.reload();
      unreadCountState.reload();
    }, 12000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    return () => {
      if (bellPopupTimerRef.current) clearTimeout(bellPopupTimerRef.current);
    };
  }, []);

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
    markRead,markAllRead,triggerBellPopup,
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
        <NavLink to="/" aria-label="Trang chủ FINTECH OCR" className="brand"><BrandLogo/></NavLink>
        <span className="role-tag">{roleName(user.role)}</span>
        <nav className="nav">{[...navItems(user.role),['/finance','Tài chính và ngân sách',ChartNoAxesCombined]].map(([to,label,Icon])=><NavLink key={to} to={to} end={to==='/'} className={({isActive})=>'nav-item '+(isActive?'active':'')}>
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
              onClick={()=>{
                setBellPopup(null);
                setNotifDropdownOpen(prev=>!prev);
              }}
              type="button"
            >
              <Bell size={19}/>{unread>0&&<i/>}
            </button>
            {bellPopup && !notifDropdownOpen && (
              <div
                className="bell-popup-toast"
                role="status"
                aria-live="polite"
                onClick={async () => {
                  setBellPopup(null);
                  if (bellPopup.id && !bellPopup.is_read) {
                    await openNotificationAfterAccessCheck(bellPopup, api, markRead, n);
                  } else {
                    setNotifDropdownOpen(true);
                  }
                }}
              >
                <div className="bell-popup-icon"><Bell size={16}/></div>
                <div className="bell-popup-body">
                  <div className="bell-popup-title">{bellPopup.title || 'Thông báo mới'}</div>
                  {bellPopup.message && <div className="bell-popup-desc">{bellPopup.message}</div>}
                </div>
                <button
                  type="button"
                  className="bell-popup-close"
                  onClick={(e) => { e.stopPropagation(); setBellPopup(null); }}
                  aria-label="Đóng thông báo"
                >×</button>
              </div>
            )}
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
  const { data, busy, error } = useLoad('/dashboard/summary?counted_only=true');
  const inv = useLoad('/invoices?counted_only=true&limit=5');
  const sched = useLoad('/schedules');
  const navigate = useNavigate();
  const [chatPrompt, setChatPrompt] = useState('');
  const summary = data || {};
  const employee = user.role === 'employee';
  const stats = [
    ["Danh sách hóa đơn", summary.total_invoices, FileText, ''],
    ["Đã phê duyệt", summary.approved, CheckCircle2, 'approved'],
    ["Chờ phê duyệt", summary.pending, Clock3, 'pending'],
    ["Đã từ chối", summary.rejected, XCircle, 'rejected'],
  ];

  function handleChatSubmit(e){
    e.preventDefault();
    const q=chatPrompt.trim();
    if(q){
      navigate('/chat',{state:{initialQuestion:q}});
    }else{
      navigate('/chat');
    }
  }

  return <>
    <TravelDashboardNotice user={user}/>
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
              <div className="compact-right"><b>{money(invoice.total_amount)}</b><Status value={invoice.approval_status}/><SLABadge sla={invoice.approval_sla}/></div>
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
        <section className="panel black-panel">
          <MessageSquare size={21}/>
          <h3>Trao đổi về hóa đơn</h3>
          <p>Theo dõi phê duyệt, tìm chứng từ hoặc xem thông tin chi tiêu.</p>
          <form className="black-input-form" onSubmit={handleChatSubmit}>
            <input
              type="text"
              className="black-input-field"
              placeholder="Nhập câu hỏi..."
              value={chatPrompt}
              onChange={e=>setChatPrompt(e.target.value)}
              aria-label="Nhập câu hỏi cho trợ lý AI"
            />
            <button
              type="submit"
              className="black-input-submit"
              title="Gửi câu hỏi đến Trợ lý AI"
              aria-label="Gửi câu hỏi"
            >
              <ArrowRight size={18}/>
            </button>
          </form>
        </section>
      </div>
    </>}
  </>;
}
const unsubmittedInvoiceLabel='Chưa gửi duyệt';

function UnsubmittedInvoiceNotice({count,active,onToggle}){
  return <button type="button" className="warning-box invoice-unsubmitted-notice" aria-pressed={active} onClick={onToggle}>
    <AlertTriangle size={18} aria-hidden="true"/>
    <span className="invoice-unsubmitted-copy">
      <strong>{active?'Đang xem hóa đơn chưa gửi duyệt':`Có ${count} hóa đơn chưa gửi duyệt`}</strong>
      {active&&<small>Quay lại danh sách hóa đơn</small>}
    </span>
    <ArrowRight size={16} aria-hidden="true"/>
  </button>;
}

function InvoicesPage({user}){
  const {data:unsubmitted,reload:reloadUnsubmitted}=useLoad('/invoices/unsubmitted-count');
  const showUploader=['accountant','admin'].includes(user.role);const[params,setParams]=useSearchParams();const search=params.get('search')||'';const setSearch=value=>setParams(current=>{const next=new URLSearchParams(current);if(value)next.set('search',value);else next.delete('search');return next},{replace:true});const status=['draft','pending','approved','rejected'].includes(params.get('status'))?params.get('status'):'';const draftView=status==='draft';const setStatus=value=>setParams(current=>{const next=new URLSearchParams(current);if(value)next.set('status',value);else next.delete('status');return next});const {data,busy,reload,error}=useLoad('/invoices?'+new URLSearchParams({[draftView?'unsubmitted_only':'counted_only']:'true',...invoiceDateRange(['month','year','quarter'].includes(params.get('period'))?params.get('period'):'',params.get('date_value'),params.get('quarter')||'1'),...search?{search:search.trim()}:{},...status?{approval_status:status}:{}}),{allPages:true});const n=useNavigate();let rows=(data||[]).filter(i=>(draftView||i.approval_status!=='draft')&&(!status||i.approval_status===status));return <><Title title="Hóa đơn" description="Tìm kiếm, lọc và xem dữ liệu hóa đơn."/><div className="panel">
    {(draftView||unsubmitted?.count>0)&&<UnsubmittedInvoiceNotice count={unsubmitted?.count} active={draftView} onToggle={()=>setParams(draftView?{}:{status:'draft'})}/>}
    <div className="filters"><label className="searchbox"><Search size={17}/><input placeholder="Tìm số hóa đơn hoặc nhà cung cấp..." value={search} onChange={e=>setSearch(e.target.value)}/></label><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">Tất cả trạng thái</option>{['draft','pending','approved','rejected'].map(s=><option key={s} value={s}>{s==='draft'?unsubmittedInvoiceLabel:approvalName(s)}</option>)}</select><button className="btn btn-muted" onClick={()=>{reload();reloadUnsubmitted();}}><RefreshCw size={16}/></button></div><InvoiceDateFilter params={params} setParams={setParams}/>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll"><table><thead><tr><th>Hóa đơn</th><th>Nhà cung cấp</th>{showUploader&&<th>Người gửi hóa đơn</th>}<th>Ngày</th><th>Số tiền</th><th>Kiểm tra dữ liệu</th><th>Phê duyệt</th><th>Tra cứu thuế</th><th></th></tr></thead><tbody>{rows.map(i=><tr key={i.id}><td><strong>{i.invoice_number||'#'+i.id}</strong><small>{documentTypeName(i.document_type)}</small></td><td>{i.seller_name||'Chưa trích xuất'}</td>{showUploader&&<td>{i.uploaded_by_name||'Không xác định'}</td>}<td>{datefmt(i.invoice_date)}</td><td className="money">{money(i.total_amount)}</td><td><Status value={i.validation_status}/></td><td>{draftView?<Pill type="gray">{unsubmittedInvoiceLabel}</Pill>:<Status value={i.approval_status}/>}<SLABadge sla={i.approval_sla}/></td><td><Status value={i.lookup_status}/></td><td><div className="invoice-message-actions">
  {showUploader && i.uploaded_by_name && i.uploaded_by!==user.id && (
    <button className="btn btn-small btn-outline" aria-label={'Nhắn tin với '+i.uploaded_by_name} title={'Nhắn tin với '+i.uploaded_by_name} onClick={()=>n('/messages?recipient='+i.uploaded_by)}>
      <MessageSquare size={17}/>
    </button>
  )}
  <button className="btn btn-small btn-muted" onClick={()=>n('/invoices/'+i.id)}>
    Chi tiết<ArrowRight size={14}/>
  </button>
</div></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có hóa đơn phù hợp"/>}</div>}</div></>}
const RISK_LABELS={
  'DUPLICATE-FILE':'Tệp này đã được tải lên trước đây',
  'DUPLICATE-INVOICE':'Phát hiện hóa đơn có thông tin trùng',
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
         const duplicateFile=flag.code==='DUPLICATE-FILE';
         const duplicateInvoice=flag.code==='DUPLICATE-INVOICE';
         const duplicate=duplicateFile||duplicateInvoice;
         return <div className={'risk-flag risk-flag-'+severity} key={(flag.code||'flag')+'-'+index}>
           <span className="risk-flag-icon"><AlertTriangle size={17}/></span>
           <div className="risk-flag-body">
             <div className="risk-flag-title"><strong>{RISK_LABELS[flag.code]||flag.code||'Cảnh báo rủi ro'}</strong>{!duplicate&&<span className="risk-flag-code">{flag.code||'RISK'}</span>}</div>
             <p>{duplicateFile?'Nội dung tệp khớp với dữ liệu đã tải lên.':duplicateInvoice?'Trùng MST người bán, ký hiệu, số hóa đơn và ngày lập.':flag.message||'Cần kiểm tra thông tin hóa đơn.'}</p>
             {duplicate?<details className="risk-flag-details"><summary>Chi tiết</summary>
               <code>{flag.code}</code><p>{flag.message}</p>
               {Number.isInteger(flag.matched_count)&&flag.matched_count>0&&<small>{flag.matched_count} bản ghi khớp do hệ thống trả về</small>}
               <p>API không cung cấp mã bản ghi liên quan.{duplicateInvoice?' Cảnh báo này không xác nhận nội dung tệp khác nhau; cần đối chiếu chứng từ.':''}</p>
             </details>:Number.isInteger(flag.matched_count)&&flag.matched_count>0&&<small>{flag.matched_count} bản ghi khớp được phát hiện</small>}
           </div>
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

function DetailPage({user}){
  const {id}=useParams();
  const {data,reload,busy,error}=useLoad('/invoices/'+id);
  const [riskVersion,setRiskVersion]=useState(0);
  const navigate=useNavigate();
  const canDiscuss=data && !busy && !error && data.approval_status!=='draft' &&
    (user.role==='accountant' || data.uploaded_by===user.id);
  return <>
    <InvoiceDetailPage user={user} id={id} data={data} busy={busy} error={error} reload={reload} onChanged={()=>setRiskVersion(v=>v+1)}/>
    {canDiscuss&&<button className="btn btn-outline" onClick={()=>navigate('/invoices/'+id+'/messages')}>
      <MessageSquare size={16}/> Tin nhắn về hóa đơn
    </button>}
    {data&&!busy&&!error&&<RiskAssessmentPanel key={id+'-'+riskVersion} invoiceId={id}/>}
  </>;
}

function ApprovalsPage({user}){
  const {data,busy,error}=useLoad('/invoices',{allPages:true});
  const [filter,setFilter]=useState('pending');
  const [riskFilter,setRiskFilter]=useState('');
  const [riskSort,setRiskSort]=useState(false);
  const [slaData,setSlaData]=useState(null),[slaFilter,setSlaFilter]=useState(''),[slaSort,setSlaSort]=useState('');
  const {data:riskData}=useLoad('/approvals/risk-summary');
  const riskFor=invoice=>riskData?.invoices?.[invoice.id]||{level:'insufficient_data',score:null};
  const navigate=useNavigate();
  const invoices=data||[];
  const slaFor=invoice=>slaData?.invoices?.[invoice.id]||invoice.approval_sla;
  const rows=invoices.filter(invoice=>(!filter||invoice.approval_status===filter)&&(!riskFilter||riskFor(invoice).level===riskFilter)&&(!slaFilter||(slaFilter==='unknown'?(!slaFor(invoice)||slaFor(invoice).status==='unknown'):slaFor(invoice)?.status===slaFilter)));
  if(slaSort)rows.sort((a,b)=>{const x=slaFor(a),y=slaFor(b);if(!x)return 1;if(!y)return -1;const rank={overdue:0,due_soon:1,in_time:2,approved:3,rejected:4,unknown:5};return (slaSort==='urgent'?rank[x.status]-rank[y.status]:0)||new Date(x.due_at)-new Date(y.due_at);});
  if(riskSort&&!slaSort)rows.sort((a,b)=>({high:3,medium:2,insufficient_data:1,low:0}[riskFor(b).level]??1)-({high:3,medium:2,insufficient_data:1,low:0}[riskFor(a).level]??1)||(riskFor(b).score??-1)-(riskFor(a).score??-1));
  const tabs=[['pending','Chờ xử lý'],['approved','Đã phê duyệt'],['rejected','Đã từ chối'],['','Tất cả']];
  return <>
    <Title title="Hàng đợi phê duyệt" description="Xem chi tiết hóa đơn, ghi nhận kết quả tra cứu thuế và xử lý phê duyệt."/>
    <SLAOverview user={user} onChange={setSlaData} filter={slaFilter} onFilter={setSlaFilter} sort={slaSort} onSort={setSlaSort}/>
    <section className="panel">
      <div className="filters"><select aria-label="Lọc rủi ro" value={riskFilter} onChange={e=>setRiskFilter(e.target.value)}><option value="">Tất cả mức rủi ro</option><option value="high">Cao</option><option value="medium">Trung bình</option><option value="low">Thấp</option><option value="insufficient_data">Chưa đủ dữ liệu</option></select><label><input type="checkbox" checked={riskSort} onChange={e=>setRiskSort(e.target.checked)}/> Ưu tiên rủi ro cao</label></div>
      <div className="tabs">{tabs.map(([value,name])=><button className={filter===value?'selected':''} key={name} onClick={()=>setFilter(value)}>
        {name} <b>{invoices.filter(i=>!value||i.approval_status===value).length}</b>
      </button>)}</div>
      {busy?<Loading/>:error?<p className="error">{error}</p>:<div className="approval-cards">
        {rows.map(invoice=><div className="approval-card" key={invoice.id}>
          <div>
            <p>Đánh giá rủi ro đã lưu: {({high:'Cao',medium:'Trung bình',low:'Thấp',insufficient_data:'Chưa đủ dữ liệu'})[riskFor(invoice).level]||'Chưa đánh giá'} {riskFor(invoice).score==null?"":`${riskFor(invoice).score}/100 điểm quy tắc`}</p>
            <InvoiceVerificationPanel invoiceId={invoice.id}/>
            <small>{documentTypeName(invoice.document_type)} · HÓA ĐƠN #{invoice.id}</small>
            <h3>{invoice.seller_name||invoice.filename}</h3>
            <p>{invoice.invoice_number||'Hóa đơn mới'} · {datefmt(invoice.invoice_date)}</p>
            <p>Người đăng: <strong>{invoice.uploaded_by_name||'Không xác định'}</strong></p>
          </div>
          <div className="approval-right">
            <strong>{money(invoice.total_amount)}</strong>
            <Status value={invoice.approval_status}/>
            <div className="invoice-message-actions">
              {user.role==='accountant'&&invoice.uploaded_by_name&&
                <button className="btn btn-outline btn-small" aria-label={'Nhắn tin với '+invoice.uploaded_by_name} title={'Nhắn tin với '+invoice.uploaded_by_name} onClick={()=>navigate('/messages?recipient='+invoice.uploaded_by)}>
                  <MessageSquare size={17}/>
                </button>}
              <button className="btn btn-primary btn-small" onClick={()=>navigate('/invoices/'+invoice.id)}>
                Xem chi tiết<ArrowRight size={15}/>
              </button>
            </div>
          </div>
        </div>)}
        {!rows.length&&<Empty label="Hàng đợi đang trống"/>}
      </div>}
    </section>
  </>;
}

function InvoiceMessagesRoute({user}){
  const {id}=useParams();
  return <InvoiceMessagesPage key={id} id={id} user={user}/>;
}

function messageInitials(name){
  return name.trim().split(/\s+/).slice(-2).map(word=>word[0]).join('').toUpperCase();
}

function InvoiceMessagesPage({id,user}){
  const direct=!id;
  const [params]=useSearchParams();
  const path=direct?'/messages':'/invoices/'+id+'/messages';
  const {data,busy,error,reload}=useLoad(path);
  const navigate=useNavigate();
  const requestedPeerId=params.get('recipient')||'';
  const [peerId,setPeerId]=useState(requestedPeerId);
  const [peerQuery,setPeerQuery]=useState('');
  const [body,setBody]=useState('');
  const [sending,setSending]=useState(false);
  const [sendError,setSendError]=useState('');
  const messageList=useRef(null);

  useEffect(()=>{
    setPeerId(requestedPeerId);
    setBody('');
    setSendError('');
  },[requestedPeerId]);

  useEffect(()=>{
    if(busy) return;
    const messageRefreshTimer=setTimeout(reload,3000);
    return ()=>clearTimeout(messageRefreshTimer);
  },[busy,reload]);

  const latest=data?.messages.at(-1);
  const latestPeerId=latest?.sender_id===user.id?latest.recipient_id:latest?.sender_id;
  const peer=data?.peers.find(item=>String(item.id)===peerId)||
    data?.peers.find(item=>item.id===latestPeerId)||data?.peers[0];

  useEffect(()=>{
    if(!peerId&&peer) setPeerId(String(peer.id));
  },[peerId,peer?.id]);

  const visiblePeers=direct?(data?.peers??[])
    .filter(item=>matchesWorkspaceText(peerQuery,item.name))
    .map(item=>({item,givenName:item.name.trim().split(/\s+/).at(-1)}))
    .sort((a,b)=>a.givenName.localeCompare(b.givenName,'vi')||a.item.name.localeCompare(b.item.name,'vi'))
    .map(({item})=>item):[];
  const messages=data?.messages.filter(message=>message.sender_id===peer?.id||message.recipient_id===peer?.id)||[];
  const lastMessageId=messages.at(-1)?.id;
  function selectPeer(value){
    setPeerId(String(value));
    setBody('');
    setSendError('');
  }
  useEffect(()=>{
    const list=messageList.current;
    if(list) list.scrollTop=list.scrollHeight;
  },[peer?.id,lastMessageId,error]);

  async function send(event){
    event.preventDefault();
    if(!peer?.active||!body.trim()||sending) return;
    setSending(true);
    setSendError('');
    try{
      await api(path,{method:'POST',body:{body:body.trim(),recipient_id:peer.id}});
      setBody('');
      reload();
    }catch(e){
      setSendError(e.message);
    }finally{
      setSending(false);
    }
  }

  return <>
    <Title title={direct?'Tin nhắn':'Tin nhắn · Hóa đơn #'+id} action={direct?null:
      <button className="btn btn-outline" onClick={()=>navigate('/invoices/'+id)}><ChevronLeft size={16}/> Về hóa đơn</button>
    }/>
    <section className={direct?'panel invoice-message-panel direct-message-panel':'panel invoice-message-panel'} aria-label={direct?'Tin nhắn':'Cuộc trò chuyện về hóa đơn'}>
      {direct&&Boolean(data?.peers.length)&&<aside className="direct-message-peers" aria-label="Người nhận">
        <h2>Người nhận</h2>
        <input className="direct-message-peer-search" type="search" aria-label="Tìm người nhận theo tên"
          placeholder="Tìm theo tên…" value={peerQuery} onChange={event=>setPeerQuery(event.target.value)}/>
        {!visiblePeers.length&&<p className="direct-message-peer-empty" role="status">Không tìm thấy người nhận.</p>}
        <ul>
          {visiblePeers.map(item=><li key={item.id}>
            <button type="button" aria-pressed={item.id===peer?.id} disabled={sending} onClick={()=>{
              if(item.id!==peer?.id) selectPeer(item.id);
            }}>
              <span className="invoice-message-avatar" aria-hidden="true">{messageInitials(item.name)}</span>
              <span className="direct-message-peer-details">
                <strong>{item.name}</strong>
                {item.role&&<small>{roleName(item.role)}</small>}
              </span>
            </button>
          </li>)}
        </ul>
      </aside>}
      <div className="invoice-message-thread">
      <header className="invoice-message-header">
        <div className="invoice-message-person">
          <span className="invoice-message-avatar" aria-hidden="true">
            {peer?messageInitials(peer.name):<MessageSquare size={21}/>}
          </span>
          <div>
            {!direct&&data?.peers.length>1?<select aria-label="Chọn người trao đổi" value={peer?.id} disabled={sending} onChange={event=>selectPeer(event.target.value)}>
              {data.peers.map(item=><option key={item.id} value={item.id}>{item.name}{item.role?' · '+roleName(item.role):''}</option>)}
            </select>:<strong>{peer?.name||'Cuộc trò chuyện'}</strong>}
            {peer?.role&&<small>{roleName(peer.role)}</small>}
          </div>
        </div>
        <button className="btn btn-muted btn-small" onClick={reload} disabled={busy}><RefreshCw size={15}/> Làm mới</button>
      </header>
      {error?<div className="invoice-message-state"><p role="alert" className="error">{error}</p></div>:busy&&!data?<Loading/>:<>
        {messages.length?<ol ref={messageList} className="invoice-message-list" aria-label="Tin nhắn" tabIndex={0}>
          {messages.map(message=><li key={message.id} className={message.sender_id===user.id?'own-message':''}>
            <small>{message.sender_id===user.id?'Bạn':peer.name} · {formatNotificationTimestamp(message.created_at)}</small>
            <p className="invoice-message-bubble">{message.body}</p>
          </li>)}
        </ol>:<div className="invoice-message-empty">
          <span aria-hidden="true"><MessageSquare size={24}/></span>
          <strong>{direct&&!peer?'Chưa có người nhận':'Chưa có tin nhắn'}</strong>
          {peer?.active&&<p>Gửi tin nhắn đầu tiên để bắt đầu trao đổi.</p>}
        </div>}
        {peer&&(peer.active?<form onSubmit={send} className="invoice-message-form">
          <div className="invoice-message-composer">
            <textarea aria-label="Nội dung tin nhắn" placeholder="Nhập tin nhắn…" value={body} onChange={event=>setBody(event.target.value)} rows={direct?2:3} maxLength={2000} required disabled={sending}/>
            <button type="submit" className="btn btn-primary invoice-message-send"
              aria-label={sending?'Đang gửi…':'Gửi tin nhắn'} title={sending?'Đang gửi…':'Gửi tin nhắn'}
              disabled={sending||busy||!body.trim()}><Send size={17} aria-hidden="true"/></button>
          </div>
          {sendError&&<p role="alert" className="error">{sendError}</p>}
        </form>:<p className="invoice-message-state">Người nhận hiện không thể nhận tin nhắn.</p>)}
      </>}
      </div>
    </section>
  </>;
}
function SchedulePage({user}){return <EmployeeSchedulePage user={user}/>}
function RankingPage(){
 const [params,setParams]=useSearchParams();
 const period=params.get('period')||(params.has('year')?'year':'month');
 const current=currentPeriod();
 const selection={...current,...Object.fromEntries(params),period};
 const query=periodQuery(selection);
 query.set('include_totals','true');
 return <>
   <Title title="Xếp hạng công tác" description="Xếp hạng theo số chuyến công tác đã hoàn thành."/>
   <section className="panel">
     <PeriodFilter value={selection} onChange={next=>setParams(next)}/>
     {validPeriod(selection)&&<RankingTable key={query.toString()} query={query.toString()}/>}
   </section>
 </>;
}

function RankingTable({query}){
 const {hash}=useLocation();
 const {data,busy,error}=useLoad('/ranking?'+query);
 useEffect(()=>{
   if(!busy&&hash)document.getElementById(hash.slice(1))?.scrollIntoView({block:'center',behavior:'smooth'});
 },[busy,data,hash]);
 if(busy)return <Loading/>;
 if(error)return <p className="error" role="alert">{error}</p>;
 const totals=(data||[]).reduce((sum,row)=>[sum[0]+row.total,sum[1]+row.completed],[0,0]);
 return <div className="ranking">
   <p>{totals[0]} chuyến công tác · {totals[1]} chuyến hoàn thành</p>
   {data?.map(r=><div className="rankrow" id={'ranking-'+r.user_id} key={r.user_id}>
     <span className="rank">{r.rank ? '#'+r.rank : '—'}</span>
     <span className="avatar">{r.full_name.slice(-2).toUpperCase()}</span>
     <strong>{r.full_name}</strong>
     <span className="rank-score">{r.completed} / {r.total} chuyến hoàn thành</span>
   </div>)}
   {!data?.length&&<Empty label="Không có dữ liệu công tác trong kỳ này"/>}
 </div>;
}
function compressImage(file,maxDimension=1280,quality=0.85){
  return new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=(e)=>{
      const img=new window.Image();
      img.onload=()=>{
        let width=img.width;
        let height=img.height;
        if(width>maxDimension||height>maxDimension){
          if(width>height){
            height=Math.round((height*maxDimension)/width);
            width=maxDimension;
          }else{
            width=Math.round((width*maxDimension)/height);
            height=maxDimension;
          }
        }
        const canvas=document.createElement('canvas');
        canvas.width=width;
        canvas.height=height;
        const ctx=canvas.getContext('2d');
        ctx.drawImage(img,0,0,width,height);
        const dataUrl=canvas.toDataURL('image/jpeg',quality);
        resolve(dataUrl);
      };
      img.onerror=()=>reject(new Error('Không thể tải hình ảnh'));
      img.src=e.target.result;
    };
    reader.onerror=()=>reject(new Error('Không thể đọc tệp hình ảnh'));
    reader.readAsDataURL(file);
  });
}

function ChatPage({user}){
  const location=useLocation();
  const [params,setParams]=useSearchParams();
  const lastSentInitRef=useRef('');
  const [question,setQuestion]=useState('');
  const [attachedImage,setAttachedImage]=useState(null);
  const [messages,setMessages]=useState([]);
  const [sending,setSending]=useState(false);
  const [streamingText,setStreamingText]=useState('');
  const [connection,setConnection]=useState(null);
  const [conversationId,setConversationId]=useState(null);
  const [activeTitle,setActiveTitle]=useState('Cuộc trò chuyện mới');
  const [activeDate,setActiveDate]=useState('');
  const [conversations,setConversations]=useState([]);
  const [hasOlder,setHasOlder]=useState(false);
  const [historyBusy,setHistoryBusy]=useState(false);
  const [historyError,setHistoryError]=useState('');
  const historyRequest=useRef(0);
  const [copiedIdx,setCopiedIdx]=useState(null);
  const [feedback,setFeedback]=useState({});

  const messagesContainerRef=useRef(null);
  const messagesEnd=useRef(null);
  const sendingRef=useRef(false);
  const abortRef=useRef(null);
  const fileInputRef=useRef(null);

  const handleFileChange=async(e)=>{
    const file=e.target.files?.[0];
    if(!file)return;
    try{
      if(file.size>20*1024*1024 || !/\.(pdf|jpe?g|png|xml)$/i.test(file.name))throw new Error('Unsupported file or size');
      const compressed=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>{const ext=file.name.split('.').pop().toLowerCase();const mime=({pdf:'application/pdf',xml:'application/xml',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg'})[ext];resolve(String(reader.result).replace(/^data:[^;]*;/,'data:'+mime+';'));};reader.onerror=reject;reader.readAsDataURL(file);});
      setAttachedImage(compressed);
      void submitWithText('',compressed);
    }catch(err){
      console.error('Lỗi nén ảnh:',err);
      setMessages(current=>[...current,{role:'assistant',content:'Không đọc được tệp. Hãy chọn PDF, JPG, PNG hoặc XML tối đa 20 MB.'}]);
    }finally{
      if(fileInputRef.current)fileInputRef.current.value='';
    }
  };

  const handlePaste=async(e)=>{
    const items=e.clipboardData?.items;
    if(!items)return;
    for(let i=0;i<items.length;i++){
      if(items[i].type&&items[i].type.indexOf('image')!==-1){
        const file=items[i].getAsFile();
        if(file){
          e.preventDefault();
          try{
            const compressed=await compressImage(file);
            setAttachedImage(compressed);
          }catch(err){
            console.error('Lỗi dán ảnh:',err);
          }
          break;
        }
      }
    }
  };

  const formatChatDate=useCallback((isoString)=>{
    if(!isoString)return '';
    try{
      const d=new Date(isoString);
      return d.toLocaleDateString('vi-VN',{day:'2-digit',month:'short',year:'numeric',timeZone:'Asia/Ho_Chi_Minh'})+' · '+d.toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Ho_Chi_Minh'});
    }catch{return '';}
  },[]);

  const fetchConversations=useCallback(async(beforeId)=>{
    const request=++historyRequest.current;
    setHistoryBusy(true);
    setHistoryError('');
    try{
      const list=await api('/chatbot/conversations?limit=30'+(beforeId?'&before_id='+beforeId:''));
      if(request!==historyRequest.current)return;
      setConversations(previous=>beforeId?[...previous,...list]:list);
      setHasOlder(list.length===30);
    }catch(error){
      if(request===historyRequest.current)setHistoryError(error.message);
    }finally{
      if(request===historyRequest.current)setHistoryBusy(false);
    }
  },[]);

  useEffect(()=>{
    let alive=true;
    api('/chatbot/status').then(s=>{if(alive)setConnection(s)}).catch(()=>{if(alive)setConnection({connected:false,state:'unavailable'})});
    fetchConversations();
    return()=>{alive=false};
  },[fetchConversations]);

  useEffect(()=>{
    const el=messagesContainerRef.current;
    if(el){
      el.scrollTo({top:el.scrollHeight,behavior:'smooth'});
    }
  },[messages,sending,streamingText]);

  function stopGenerating(){
    if(abortRef.current){
      abortRef.current.abort();
      abortRef.current=null;
    }
  }

  function resetChat(){
    setConversationId(null);
    setActiveTitle('Cuộc trò chuyện mới');
    setActiveDate('');
    setMessages([]);
    setQuestion('');
    setAttachedImage(null);
  }

  useEffect(()=>{const id=params.get('conversation');if(id && /^[1-9][0-9]*$/.test(id))void selectConversation({id:Number(id)});},[params]);

  async function selectConversation(conv){
    if(sending||conv.id===conversationId||historyBusy)return;
    setHistoryBusy(true);
    setHistoryError('');
    try{
      const detail=await api('/chatbot/conversations/'+conv.id);
      setConversationId(detail.id);
      setActiveTitle(detail.title);
      setActiveDate(formatChatDate(detail.created_at));
      setMessages(detail.messages.map(m=>({role:m.role,content:m.content,image:m.image||null,meta:m.meta||null})));
    }catch(error){setHistoryError(error.message)}
    finally{setHistoryBusy(false)}
  }

  async function renameConv(conv,e){
    e.stopPropagation();
    if(sending||historyBusy)return;
    const title=window.prompt('Tiêu đề cuộc trò chuyện',conv.title)?.trim();
    if(!title||title===conv.title)return;
    try{
      const updated=await api('/chatbot/conversations/'+conv.id,{method:'PATCH',body:{title}});
      setConversations(previous=>previous.map(item=>item.id===conv.id?updated:item));
      if(conversationId===conv.id)setActiveTitle(updated.title);
    }catch(error){setHistoryError(error.message)}
  }

  async function deleteConv(id,e){
    e.stopPropagation();
    if(sending||historyBusy||!window.confirm('Xóa cuộc trò chuyện này?'))return;
    try{
      await api('/chatbot/conversations/'+id,{method:'DELETE'});
      setConversations(prev=>prev.filter(c=>c.id!==id));
      if(conversationId===id)resetChat();
    }catch(error){setHistoryError(error.message)}
  }

  function copyMessage(text,idx){
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(()=>setCopiedIdx(null),2000);
  }

  function toggleFeedback(idx,type){
    setFeedback(prev=>({...prev,[idx]:prev[idx]===type?null:type}));
  }

  async function submitWithText(rawText,selectedAttachment=attachedImage){
    const q=(rawText||'').trim();
    if((!q&&!selectedAttachment)||sendingRef.current)return;
    sendingRef.current=true;
    const currentImg=selectedAttachment;
    setAttachedImage(null);
    setQuestion('');
    setMessages(x=>[...x,{role:'user',content:q,image:currentImg}]);
    setSending(true);
    setStreamingText('');

    if(!activeTitle||activeTitle==='Cuộc trò chuyện mới'){
      setActiveTitle(q?q.slice(0,40):'Phân tích hình ảnh');
      setActiveDate(formatChatDate(new Date().toISOString()));
    }

    const abortController=new AbortController();
    abortRef.current=abortController;
    let accumulatedText='';
    let metaData=null;
    let streamError=null;
    const requestId=Array.from(globalThis.crypto.getRandomValues(new Uint32Array(4)), n=>n.toString(16).padStart(8,'0')).join('');

    try{
      const token=authStore.get();
      const body={question:q,request_id:requestId};
      if(currentImg)body.image_base64=currentImg;
      if(conversationId)body.conversation_id=conversationId;

      const response=await fetch(ROOT+'/chatbot/stream',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          ...(token?{Authorization:`Bearer ${token}`}:{})
        },
        body:JSON.stringify(body),
        signal:abortController.signal
      });

      if(!response.ok){
        let errJson;
        try{errJson=await response.json()}catch{}
        const errMsg=errJson?.detail||`Lỗi kết nối (HTTP ${response.status})`;
        throw Object.assign(new Error(errMsg),{status:response.status});
      }

      const reader=response.body.getReader();
      const decoder=new TextDecoder();
      let buffer='';

      while(true){
        const {done,value}=await reader.read();
        if(done)break;
        buffer+=decoder.decode(value,{stream:true});
        const parts=buffer.split('\n\n');
        buffer=parts.pop();
        for(const part of parts){
          if(!part.trim())continue;
          const lines=part.split('\n');
          let eventType='message';
          let dataStr='';
          for(const line of lines){
            if(line.startsWith('event:'))eventType=line.slice(6).trim();
            else if(line.startsWith('data:'))dataStr=line.slice(5).trim();
          }
          if(!dataStr)continue;
          try{
            const data=JSON.parse(dataStr);
            if(eventType==='meta'){
              if(data.conversation_id)setConversationId(data.conversation_id);
              if(data.model)setConnection(s=>({...s,connected:true,model:data.model,state:'connected'}));
            }else if(eventType==='delta'){
              if(data.text){
                accumulatedText+=data.text;
                setStreamingText(accumulatedText);
              }
            }else if(eventType==='error'){
              streamError=Object.assign(new Error(data.error||'Không thể tạo phản hồi.'),{status:data.status||400});
            }else if(eventType==='done'){
              metaData=data;
              if(typeof data.answer==='string')accumulatedText=data.answer;
              if(data.conversation_id)setConversationId(data.conversation_id);
              if(data.model)setConnection(s=>({...s,connected:true,model:data.model,state:'connected'}));
            }
          }catch(parseErr){}
        }
      }

      if(streamError)throw streamError;
      if(!metaData)throw new Error('Kết nối bị gián đoạn');
      if(accumulatedText){
        setMessages(x=>[...x,{role:'assistant',content:accumulatedText,meta:metaData}]);
        fetchConversations();
      }
    }catch(err){
      if(err.name==='AbortError'){
        if(accumulatedText){
          setMessages(x=>[...x,{role:'assistant',content:accumulatedText+' *(Đã dừng tạo câu trả lời)*',meta:metaData}]);
        }
        fetchConversations();
      }else{
        try{
          if(err.status&&err.status<500&&err.status!==429)throw err;
          const fallbackBody={question:q,request_id:requestId};
          if(currentImg)fallbackBody.image_base64=currentImg;
          if(conversationId)fallbackBody.conversation_id=conversationId;
          const r=await api('/chatbot/ask',{method:'POST',body:fallbackBody});
          if(r.conversation_id)setConversationId(r.conversation_id);
          setMessages(x=>[...x,{role:'assistant',content:r.answer,meta:{...r,total_time_ms:r.total_time_ms,ttft_ms:r.llm_time_ms,db_time_ms:r.db_time_ms,kind:r.kind}}]);
          if(r.gemini_connected===true)setConnection({connected:true,state:'connected',model:r.model});
          fetchConversations();
        }catch(askErr){
          setMessages(x=>[...x,{role:'assistant',content:err.message||'Đã xảy ra lỗi khi tạo phản hồi.'}]);
          setConnection(s=>({...s,connected:false,state:'unavailable'}));
        }
      }
    }finally{
      sendingRef.current=false;
      abortRef.current=null;
      setStreamingText('');
      setSending(false);
    }
  }

  useEffect(()=>{
    const initQ=(location.state?.initialQuestion||params.get('q')||'').trim();
    if(initQ&&lastSentInitRef.current!==initQ){
      lastSentInitRef.current=initQ;
      if(location.state?.initialQuestion){
        window.history.replaceState({},document.title);
      }
      if(params.get('q')){
        setParams(p=>{
          const next=new URLSearchParams(p);
          next.delete('q');
          return next;
        },{replace:true});
      }
      submitWithText(initQ);
    }
  },[location.state,params]);

  function submit(e){
    e.preventDefault();
    submitWithText(question);
  }

  const userInitials=((user?.full_name||'Bạn').trim().split(/\s+/).slice(-2).map(w=>w[0]).join('')||'U').toUpperCase();

  function groupConvs(list){
    const today=[],last7=[],older=[];
    const startOfToday=Date.parse(currentPeriod().date_to+'T00:00:00+07:00');
    const sevenDaysAgo=startOfToday-7*86400000;
    for(const c of list){
      const t=c.created_at?new Date(c.created_at).getTime():0;
      if(t>=startOfToday)today.push(c);
      else if(t>=sevenDaysAgo)last7.push(c);
      else older.push(c);
    }
    return {today,last7,older};
  }

  function extractSources(content){
    if(!content)return [];
    const matches=content.match(/\b(INV-[A-Za-z0-9_-]+)\b/g);
    if(!matches)return [];
    return Array.from(new Set(matches)).slice(0,3);
  }

  const {today,last7,older}=groupConvs(conversations);


  const connectionLabel=!connection?'Đang kiểm tra kết nối Gemini…':connection.connected?`Gemini đã sẵn sàng · ${connection.model}`:connection.state==='not_configured'?'Chưa cấu hình Gemini':'Gemini tạm thời ngoại tuyến (sử dụng chế độ dữ liệu nội bộ)';

  return <>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',gap:20,margin:'12px 0 24px'}}>
      <div>
        <h1 style={{fontSize:27,fontWeight:800,marginBottom:4}}>Trò chuyện với AI</h1>
        <p style={{margin:0,fontSize:13,color:'#777983'}}>Tìm kiếm hóa đơn, phân tích xu hướng hoặc theo dõi chi tiêu của bạn.</p>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:7,fontSize:12,fontWeight:700,color:'#3e8c54',background:'#e8f4eb',padding:'6px 14px',borderRadius:100}}>
        <CheckCircle2 size={15}/> Đã kết nối với hóa đơn của bạn
      </div>
    </div>

    <div className="chat-layout">
      {/* Left Sidebar: Lịch sử trò chuyện */}
      <aside className="chat-sidebar">
        <button type="button" className="chat-new-btn" disabled={sending||historyBusy} onClick={resetChat} title="Tạo cuộc trò chuyện mới">
          <Plus size={16}/> Cuộc trò chuyện mới
        </button>

        {historyError&&<p className="error" role="alert">{historyError} <button type="button" onClick={()=>fetchConversations()}>Thử lại</button></p>}
        {hasOlder&&<button type="button" className="btn btn-outline" disabled={historyBusy||sending} onClick={()=>fetchConversations(conversations.at(-1)?.id)}>Tải thêm</button>}
        <div className="chat-history-scroll">
          {conversations.length===0?(
            <div style={{textAlign:'center',padding:'30px 10px',color:'#9ca3af',fontSize:12}}>
              Chưa có lịch sử trò chuyện
            </div>
          ):(
            <>
              {[[today,'Hôm nay'],[last7,'7 ngày trước'],[older,'Cũ hơn']].map(([group,label])=>group.length>0&&(
                <div key={label}>
                  <div className="chat-history-group-title">{label}</div>
                  {group.map(c=><div key={c.id} className={'chat-history-item '+(conversationId===c.id?'active':'')}>
                    <button type="button" className="chat-history-open" disabled={sending||historyBusy} onClick={()=>selectConversation(c)}>
                      <Bookmark size={15}/>
                      <span className="chat-history-item-body">
                        <span className="chat-history-item-title">{c.title}</span>
                        <span className="chat-history-item-preview">{formatChatDate(c.updated_at)}</span>
                      </span>
                    </button>
                    <button type="button" className="chat-history-del-btn" disabled={sending||historyBusy}
                      onClick={e=>renameConv(c,e)} title="Đổi tên" aria-label="Đổi tên cuộc trò chuyện"><Pencil size={13}/></button>
                    <button type="button" className="chat-history-del-btn" disabled={sending||historyBusy}
                      onClick={e=>deleteConv(c.id,e)} title="Xóa" aria-label="Xóa cuộc trò chuyện"><Trash2 size={13}/></button>
                  </div>)}
                </div>
              ))}
            </>
          )}
        </div>

        <div className="chat-sidebar-security">
          <Lock size={15}/>
          <span>Chỉ hóa đơn và lịch trình trong không gian làm việc của bạn được sử dụng để trả lời.</span>
        </div>
      </aside>

      {/* Right Main Chat Panel */}
      <section className="chat-main-panel">
        <div className="chat-main-header">
          <div className="chat-main-header-left">
            <div className="chat-sparkle-badge">
              <Sparkles size={18}/>
            </div>
            <div>
              <h3 className="chat-main-header-title">{activeTitle}</h3>
            </div>
          </div>
          {activeDate&&<span className="chat-main-header-time">{activeDate}</span>}
        </div>

        <div className="chat-messages-container" ref={messagesContainerRef}>
          {messages.map((m,i)=>{
            if(m.role==='user'){
              return (
                <div className="chat-row-user" key={i}>
                  <div className="chat-bubble-user">
                    {m.image?.startsWith('data:image/')&&(
                      <div className="chat-user-img-box">
                        <img src={m.image} alt="Ảnh đính kèm" onClick={()=>window.open(m.image,'_blank')} title="Nhấn để xem ảnh phóng to"/>
                      </div>
                    )}
                    {m.content&&<div>{m.content}</div>}
                  </div>
                  <div className="chat-avatar-user" title={user?.full_name||'Bạn'}>{userInitials}</div>
                </div>
              );
            }

            const internalSources=extractSources(m.content);
            const webSources=m.meta?.web_sources||[];
            const hasInternalData=(m.meta&&m.meta.kind&&m.meta.kind!=='ordinary'&&(m.meta.db_time_ms>0||m.meta.count_visible_invoices!=null));
            const isVerified=internalSources.length>0||webSources.length>0||hasInternalData;

            return (
              <div className="chat-row-assistant" key={i}>
                <div className="chat-assistant-head">
                  <Sparkles size={16} color="#2563eb"/>
                  <span>Fintech AI</span>
                  {isVerified&&(
                    <span className="chat-source-verified-badge" title="Thông tin có căn cứ xác minh từ hệ thống hoặc nguồn tra cứu">
                      Nguồn đã xác thực
                    </span>
                  )}
                </div>

                <div className="chat-assistant-body">
                  <ChatMarkdown>{m.content}</ChatMarkdown>
                  {m.meta?.tax_verification && <TaxVerificationCard result={m.meta.tax_verification} llmStatus={m.meta.llm_status}/>}
                  {m.meta?.finance_analysis && <FinancialAnalysisCard data={m.meta.finance_analysis}/>}
                  {m.meta && <ChatToolResult meta={m.meta}/>}
                </div>

                {(internalSources.length>0||webSources.length>0)&&(
                  <div className="chat-sources-row">
                    <span className="chat-sources-label">
                      {internalSources.length>0&&webSources.length>0
                        ?'Nguồn tham khảo:'
                        :internalSources.length>0
                        ?'Nguồn nội bộ (Hóa đơn):'
                        :'Nguồn kiểm chứng (Web):'}
                    </span>
                    {internalSources.map(s=>(
                      <NavLink key={s} to="/invoices" className="chat-source-tag" title="Xem hóa đơn nội bộ">
                        <FileText size={12}/> {s} <ExternalLink size={10}/>
                      </NavLink>
                    ))}
                    {webSources.map((ws,wIdx)=>(
                      <a
                        key={wIdx}
                        href={ws.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="chat-source-tag chat-source-tag-web"
                        title={ws.title||ws.url}
                      >
                        <Globe size={12}/> {ws.title?(ws.title.length>32?ws.title.slice(0,32)+'…':ws.title):'Nguồn web'} <ExternalLink size={10}/>
                      </a>
                    ))}
                  </div>
                )}

                <div className="chat-assistant-footer">
                  <div>
                    {m.meta?(
                      <span>
                        ⚡ {Number.isFinite(m.meta.total_time_ms)?`${(m.meta.total_time_ms/1000).toFixed(2)}s`:'Chưa ghi nhận thời gian'}
                        {Number.isFinite(m.meta.ttft_ms)&&` · Phản hồi đầu: ${(m.meta.ttft_ms/1000).toFixed(2)}s`}
                        {m.meta.db_time_ms>0&&` · CSDL: ${m.meta.db_time_ms}ms`}
                        {m.meta.kind&&` · ${m.meta.kind==='ordinary'?'Kiến thức phổ thông':m.meta.kind==='security'?'Từ chối bảo mật':m.meta.kind==='analysis'?'Phân tích':'Nghiệp vụ'}`}
                      </span>
                    ):(
                      <span>Phạm vi: Dữ liệu được cấp quyền</span>
                    )}
                  </div>

                  <div className="chat-action-buttons">
                    <button
                      type="button"
                      className="chat-action-btn"
                      onClick={()=>copyMessage(m.content,i)}
                      title="Sao chép nội dung"
                    >
                      {copiedIdx===i?<><Check size={13} color="#16a34a"/> Đã sao chép</>:<><Copy size={13}/> Sao chép</>}
                    </button>
                    <button
                      type="button"
                      className={'chat-action-btn '+(feedback[i]==='up'?'active':'')}
                      onClick={()=>toggleFeedback(i,'up')}
                      title="Hữu ích"
                    >
                      <ThumbsUp size={13}/>
                    </button>
                    <button
                      type="button"
                      className={'chat-action-btn '+(feedback[i]==='down'?'active':'')}
                      onClick={()=>toggleFeedback(i,'down')}
                      title="Chưa chính xác"
                    >
                      <ThumbsDown size={13}/>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}

          {sending&&(
            streamingText?(
              <div className="chat-row-assistant">
                <div className="chat-assistant-head">
                  <Sparkles size={16} color="#2563eb"/>
                  <span>Fintech AI</span>
                  <span className="chat-source-verified-badge">Nguồn đã xác thực</span>
                </div>
                <div className="chat-assistant-body">
                  <ChatMarkdown>{streamingText}</ChatMarkdown>
                </div>
              </div>
            ):(
              <div className="chat-row-assistant" aria-live="polite">
                <div className="chat-assistant-head">
                  <Sparkles size={16} color="#2563eb"/>
                  <span>Fintech AI</span>
                </div>
                <div style={{display:'flex',alignItems:'center',gap:8,color:'#71717a',fontStyle:'italic',fontSize:13}}>
                  <RefreshCw size={14} className="spin"/> Đang suy nghĩ và phân tích dữ liệu...
                </div>
              </div>
            )
          )}


          <div ref={messagesEnd}/>
        </div>

        <form className="chat-input-area" onSubmit={submit}>
          <div className="chat-input-container">
            {attachedImage&&(
              <div className="chat-img-preview-container">
                <div className="chat-img-preview-card">
                  {!attachedImage.startsWith('data:image/') && <span>Document</span>}<img hidden={!attachedImage.startsWith('data:image/')} src={attachedImage} alt="Xem trước ảnh đính kèm"/>
                  <button
                    type="button"
                    className="chat-img-remove-btn"
                    onClick={()=>setAttachedImage(null)}
                    title="Xóa ảnh"
                  >
                    <X size={12}/>
                  </button>
                </div>
              </div>
            )}

            <div className="chat-input-top-row">
              <Sparkles size={18} className="chat-input-sparkle"/>
              <textarea
                className="chat-input-field"
                aria-label="Nhập câu hỏi cho trợ lý AI"
                rows={1}
                placeholder="Hỏi về hóa đơn, chi tiêu hoặc đính kèm ảnh để phân tích…"
                value={question}
                onChange={e=>setQuestion(e.target.value)}
                onPaste={handlePaste}
                onKeyDown={e=>{
                  if(e.key==='Enter'&&!e.shiftKey){
                    e.preventDefault();
                    if(!sending&&(question.trim()||attachedImage)){
                      submitWithText(question);
                    }
                  }
                }}
                readOnly={sending}
              />
            </div>

            <div className="chat-input-bottom-row">
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="application/pdf,application/xml,text/xml,image/jpeg,image/png,.xml"
                  style={{display:'none'}}
                  onChange={handleFileChange}
                />
                <button
                  type="button"
                  className="chat-attach-btn"
                  onClick={()=>fileInputRef.current?.click()}
                  title="Đính kèm ảnh từ máy tính"
                  disabled={sending}
                >
                  <Plus size={16}/>
                </button>
                <span style={{fontSize:12,color:'#9ca3af'}}>
                  {attachedImage?'1 ảnh đính kèm':'Dán ảnh (Ctrl+V) hoặc nhấn + để tải ảnh'}
                </span>
              </div>

              {sending?(
                <button
                  type="button"
                  className="btn btn-secondary chat-stop-btn"
                  style={{height:32,padding:'0 12px',borderRadius:10,fontSize:12}}
                  onClick={stopGenerating}
                  title="Dừng tạo câu trả lời"
                >
                  <Square size={13} fill="currentColor"/> Dừng
                </button>
              ):(
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={!question.trim()&&!attachedImage}
                  title="Gửi câu hỏi"
                >
                  <ArrowUp size={18}/>
                </button>
              )}
            </div>
          </div>
          <div className="chat-disclaimer">
            AI có thể mắc lỗi. Hãy kiểm tra lại thông tin quan trọng từ hóa đơn gốc.
          </div>
        </form>
      </section>
    </div>
  </>;
}
function ReportsPage(){
 const navigate=useNavigate();
 const blank={approval_status:'',validation_status:'',document_type:'',search:'',invoice_date_from:'',invoice_date_to:'',seller_name:'',lookup_status:''};
 const [filters,setFilters]=useState(blank),[applied,setApplied]=useState(blank),[search,setSearch]=useState('');
 const [result,setResult]=useState(null),[suppliers,setSuppliers]=useState([]),[history,setHistory]=useState([]);
 const [exporting,setExporting]=useState(false),[error,setError]=useState('');
 const [page,setPage]=useState(0),[pageSize,setPageSize]=useState(10),[sortBy,setSortBy]=useState('date'),[sortOrder,setSortOrder]=useState('desc');
 const {summary:summaryPath,preview:previewPath,export:exportPath}=reportQueries(applied,{page,pageSize,sortBy,sortOrder});
 const current=result?.path===previewPath?result:null;
 const summary=current?.summary,pageData=current?.pageData,queryError=current?.error;
 const busy=!current;
 function change(key,value){setFilters(current=>({...current,[key]:value}))}
 async function loadHistory(){setHistory(await api('/reports/history'))}
 useEffect(()=>{api('/reports/suppliers').then(setSuppliers).catch(e=>setError(e.message));loadHistory().catch(e=>setError(e.message))},[]);
 useEffect(()=>{
   let active=true;
   Promise.all([api(summaryPath),api(previewPath)])
     .then(([summary,pageData])=>{if(active)setResult({path:previewPath,summary,pageData})})
     .catch(e=>{if(active)setResult({path:previewPath,error:e.message})});
   return ()=>{active=false};
 },[summaryPath,previewPath,applied]);
 function apply(){setResult(null);setPage(0);setApplied({...filters,search:applied.search})}
 function applySearch(value){setResult(null);setPage(0);setApplied(current=>({...current,search:value.trim()}))}
 function reset(){setFilters(blank);setSearch('');setPage(0);setApplied(blank)}
  function quickRange(which){const range=getQuickDateRange(which);change('invoice_date_from',range.from);change('invoice_date_to',range.to)}
 async function saveBlob(response,filename){const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 async function exportNow(){setExporting(true);setError('');try{if(!summary?.invoice_count){setError('Không có hóa đơn phù hợp để xuất.');return}const response=await api(exportPath,{raw:true});const disposition=response.headers.get('content-disposition')||'',filename=disposition.match(/filename="?([^";]+)"?/i)?.[1]||'bao_cao_hoa_don.xlsx';await saveBlob(response,filename);await loadHistory()}catch(e){setError(e.message)}finally{setExporting(false)}}
 async function download(id){try{const response=await api(`/reports/history/${id}/download`,{raw:true});const row=history.find(x=>x.id===id);await saveBlob(response,row?.filename||'bao_cao.xlsx')}catch(e){setError(e.message)}}
 const items=pageData?.items||[];const total=pageData?.total||0;const stats=[['Tổng số hóa đơn',summary?.invoice_count??'—'],['Tổng tiền trước thuế',summary?.subtotal==null?'—':money(summary.subtotal)],['Tổng tiền thuế VAT',summary?.vat_amount==null?'—':money(summary.vat_amount)],['Tổng tiền thanh toán',summary?.total_amount==null?'—':money(summary.total_amount)]];
 const filterText=f=>Object.entries(f||{}).filter(([,v])=>v).map(([k,v])=>{const label={search:'Từ khóa',invoice_date_from:'Từ ngày',invoice_date_to:'Đến ngày',seller_name:'Nhà cung cấp',approval_status:'Phê duyệt',validation_status:'Kiểm tra',lookup_status:'Tra cứu',document_type:'Loại chứng từ'}[k]||k;const value=k==='document_type'?documentTypeName(v):['approval_status','validation_status','lookup_status'].includes(k)?approvalName(v):v;return `${label}: ${value}`}).join(' · ')||'Không lọc';
 return <><Title title="Báo cáo" description="Lọc, đối chiếu và xuất dữ liệu hóa đơn theo phạm vi được cấp quyền."/>
 <section className="panel report-panel-wide"><div className="panel-heading"><h3>Bộ lọc báo cáo</h3></div><div className="report-filters">
 <label>Từ ngày<input type="date" value={filters.invoice_date_from} onChange={e=>change('invoice_date_from',e.target.value)}/></label><label>Đến ngày<input type="date" value={filters.invoice_date_to} onChange={e=>change('invoice_date_to',e.target.value)}/></label>
 <label>Nhà cung cấp<select value={filters.seller_name} onChange={e=>change('seller_name',e.target.value)}><option value="">Tất cả nhà cung cấp</option>{suppliers.map(x=><option key={x} value={x}>{x}</option>)}</select></label><label>Trạng thái phê duyệt<select value={filters.approval_status} onChange={e=>change('approval_status',e.target.value)}><option value="">Tất cả</option>{['pending','approved','rejected'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label>
 <label>Trạng thái kiểm tra<select value={filters.validation_status} onChange={e=>change('validation_status',e.target.value)}><option value="">Tất cả</option>{['valid','needs_review','error'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label><label>Trạng thái tra cứu<select value={filters.lookup_status} onChange={e=>change('lookup_status',e.target.value)}><option value="">Tất cả</option>{['not_checked','verified','mismatch','not_found','not_applicable'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label><label>Loại chứng từ<select value={filters.document_type} onChange={e=>change('document_type',e.target.value)}><option value="">Tất cả</option>{['einvoice','bill','unknown'].map(x=><option key={x} value={x}>{documentTypeName(x)}</option>)}</select></label></div>
 <div className="quick-ranges">{[['today','Hôm nay'],['month','Tháng này'],['prev','Tháng trước'],['year','Năm nay']].map(([v,t])=><button key={v} className="btn btn-small btn-muted" onClick={()=>quickRange(v)}>{t}</button>)}</div><div className="report-actions"><button className="btn btn-secondary" disabled={busy} onClick={apply}><Filter size={16}/>Áp dụng bộ lọc</button><button className="btn btn-muted" onClick={reset}>Đặt lại bộ lọc</button></div></section>
 <div className="report-kpis" aria-busy={busy}>{stats.map(([title,value])=><section className="kpi" key={title}><small>{title}</small><strong>{value}</strong></section>)}</div>
 <section className="panel report-panel-wide"><div className="panel-heading"><h3>Xem trước hóa đơn</h3><span>{total} hóa đơn phù hợp</span></div>
 <form className="report-search" onSubmit={e=>{e.preventDefault();applySearch(search)}}>
   <input type="search" aria-label="Tìm hóa đơn" placeholder="Số hóa đơn, tên nhà cung cấp hoặc mã số thuế" value={search} onChange={e=>setSearch(e.target.value)}/>
   <button type="submit" className="btn btn-secondary"><Search size={16}/>Tìm kiếm</button>
   {(search||applied.search)&&<button type="button" className="btn btn-muted" onClick={()=>{setSearch('');applySearch('')}}>Xóa tìm kiếm</button>}
 </form>
 {busy?<Loading/>:queryError?<p className="error" role="alert">{queryError}</p>:items.length===0?<Empty label="Không tìm thấy hóa đơn phù hợp"/>:<><div className="table-scroll"><table className="report-table"><thead><tr><th>STT</th><th>Số hóa đơn</th><th><button className="sort-button" onClick={()=>{setSortBy('date');setSortOrder(sortOrder==='desc'?'asc':'desc')}}>Ngày lập hóa đơn ↕</button></th><th>Nhà cung cấp</th><th>Mã số thuế</th><th>Tiền trước thuế</th><th>Thuế VAT</th><th><button className="sort-button" onClick={()=>{setSortBy('total');setSortOrder(sortOrder==='desc'?'asc':'desc')}}>Tổng thanh toán ↕</button></th><th>Trạng thái phê duyệt</th><th></th></tr></thead><tbody>{items.map((i,n)=><tr key={i.id}><td>{page*pageSize+n+1}</td><td><button className="textbtn" onClick={()=>navigate('/invoices/'+i.id)}>{i.invoice_number||'#'+i.id}</button></td><td>{datefmt(i.invoice_date)}</td><td>{i.seller_name||'Chưa trích xuất'}</td><td>{i.seller_tax_code||'—'}</td><td>{i.subtotal==null?'—':money(i.subtotal)}</td><td>{i.vat_amount==null?'—':money(i.vat_amount)}</td><td>{i.total_amount==null?'—':money(i.total_amount)}</td><td><Status value={i.approval_status}/></td><td><button className="btn btn-small btn-muted" onClick={()=>navigate('/invoices/'+i.id)}><Eye size={14}/>Chi tiết</button></td></tr>)}</tbody></table></div><div className="report-pagination"><span>Hiển thị {total? page*pageSize+1:0}–{Math.min((page+1)*pageSize,total)} / {total}</span><select value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(0)}}><option value={10}>10 dòng</option><option value={20}>20 dòng</option><option value={50}>50 dòng</option></select><button className="btn btn-small btn-muted" disabled={!page} onClick={()=>setPage(page-1)}>Trước</button><button className="btn btn-small btn-muted" disabled={(page+1)*pageSize>=total} onClick={()=>setPage(page+1)}>Sau</button><button className="btn btn-primary" disabled={exporting||!total} onClick={exportNow}><Download size={16}/>Xuất Excel (.xlsx)</button></div></>}</section>
 <section className="panel report-panel-wide"><div className="panel-heading"><h3>Lịch sử xuất báo cáo</h3><span>{history.length} lần xuất gần đây</span></div>{history.length===0?<Empty label="Chưa có lịch sử xuất báo cáo"/>:<div className="table-scroll"><table><thead><tr><th>Thời gian xuất</th><th>Người xuất</th><th>Điều kiện lọc</th><th>Số hóa đơn</th><th>Tổng giá trị</th><th>Trạng thái</th><th>Tải xuống</th></tr></thead><tbody>{history.map(h=><tr key={h.id}><td>{h.created_at?new Date(h.created_at).toLocaleString('vi-VN'):'—'}</td><td>{h.exported_by}</td><td>{filterText(h.filters)}</td><td>{h.row_count??'—'}</td><td>{h.total_amount==null?'—':money(h.total_amount)}</td><td><Status value={h.status}/></td><td><button className="textbtn" onClick={()=>download(h.id)}><Download size={15}/> Tải xuống</button></td></tr>)}</tbody></table></div>}</section>
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
 async function perform(){if(saving||!confirm)return;if(confirm.action==='toggle'){await toggleAccount(confirm.user);return}setSaving(true);try{await api('/users/'+confirm.user.id,confirm.action==='delete'?{method:'DELETE'}:{method:'PATCH',body:{status:confirm.user.status==='active'?'disabled':'active'}});setConfirm(null);reload();setMessage(confirm.action==='delete'?'Đã xóa hoàn toàn tài khoản':'Đã cập nhật tài khoản')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
 const active=(data||[]).filter(u=>u.status==='active').length;
 const permissions={employee:'Tải hóa đơn cá nhân, xem và tự điều chỉnh lịch công tác của mình, trò chuyện với AI. Không có quyền phê duyệt hoặc quản lý người dùng.',accountant:'Kiểm tra hóa đơn, phê duyệt chi phí, xem lịch công tác và xem báo cáo.',admin:'Quản lý người dùng, phân quyền, phân và điều chỉnh lịch công tác, hóa đơn và nhật ký hoạt động.'};
 const actionLabel=confirm?.action==='delete'?'Xóa tài khoản':confirm?.user.status==='active'?'Vô hiệu hóa tài khoản':'Kích hoạt lại tài khoản';
 return <div className="users-page"><Title title="Quản lý người dùng" description="Quản lý quyền truy cập, vai trò và trạng thái tài khoản. Lịch sử tài khoản được lưu giữ."/>
 <div className={'users-layout '+(!form?'form-closed':'')}><div className="users-main"><section className="panel users-table-panel"><div className="panel-heading"><h3>Danh sách người dùng <span className="users-count">{data?.length||0}</span></h3><small>{active} đang hoạt động · {(data?.length||0)-active} đã vô hiệu hóa</small></div><div className="filters users-filters"><label className="searchbox"><Search size={15}/><input aria-label="Tìm người dùng" placeholder="Tìm theo tên hoặc email" value={search} onChange={e=>setSearch(e.target.value)}/></label><select aria-label="Lọc vai trò" value={role} onChange={e=>setRole(e.target.value)}><option value="">Tất cả vai trò</option>{['employee','accountant','admin'].map(r=><option key={r} value={r}>{roleName(r)}</option>)}</select><button className="btn btn-primary" onClick={()=>edit(null)}><Plus size={15}/> Thêm người dùng</button></div>
 {busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll users-scroll" tabIndex={0} role="region" aria-label="Danh sách người dùng"><table><thead><tr><th>Họ tên</th><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th>Thao tác</th></tr></thead><tbody>{rows.map(u=><tr key={u.id} className={confirm?.user.id===u.id?'user-selected':''} onClick={()=>edit(u)}><td><div className="user-identity"><span className={`avatar user-avatar avatar-tone-${u.id%5}`}>{u.full_name.split(/\s+/).filter(Boolean).slice(-2).map(x=>x[0]).join('').toUpperCase()}</span><button className="user-select-button" aria-pressed={confirm?.user.id===u.id} disabled={saving} onClick={e=>{e.stopPropagation();edit(u)}}>{u.full_name}</button></div></td><td>{u.email}</td><td><Pill>{roleName(u.role)}</Pill></td><td><Pill type={u.status==='active'?'green':'gray'}>{u.status==='active'?'Đang hoạt động':'Đã vô hiệu hóa'}</Pill></td><td className="user-last-login">{u.last_login_at?new Date(u.last_login_at).toLocaleString('vi-VN',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'Chưa đăng nhập'}</td><td><div className="user-actions" onClick={e=>e.stopPropagation()}><button className="iconbtn" title="Sửa người dùng" aria-label={'Sửa '+u.full_name} disabled={saving} onClick={()=>edit(u)}><Pencil size={15}/></button><button className="iconbtn" title={u.status==='active'?'Vô hiệu hóa':'Kích hoạt lại'} aria-label={(u.status==='active'?'Vô hiệu hóa ':'Kích hoạt lại ')+u.full_name} disabled={saving} onClick={()=>edit(u)}>{u.status==='active'?<UserRoundX size={15}/>:<UserRoundCheck size={15}/>}</button><button className="iconbtn danger-action" title="Xóa người dùng" aria-label={'Xóa '+u.full_name} disabled={saving} onClick={()=>setConfirm({user:u,action:'delete'})}><Trash2 size={14}/></button></div></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có người dùng phù hợp"/>}</div>}<footer className="users-table-footer"><span>Hiển thị {rows.length} / {data?.length||0} người dùng</span><span><Pencil size={12}/> Sửa <UserRoundX size={13}/> Vô hiệu hóa / Kích hoạt lại</span></footer></section>
 {confirm&&<section className="panel user-confirm" aria-labelledby="confirm-title"><div className="panel-heading"><h3 id="confirm-title"><UserRoundX size={18}/> {actionLabel}?</h3><button className="iconbtn" disabled={saving} aria-label="Hủy thao tác" onClick={()=>setConfirm(null)}><X size={16}/></button></div><strong>{confirm.user.full_name} · {confirm.user.email}</strong><p>{confirm.action==='delete'?'Chỉ xóa hoàn toàn tài khoản chưa tải hóa đơn và không có lịch sử xử lý hóa đơn. Tin nhắn, thông báo, báo cáo cá nhân và lịch được giao sẽ bị xóa. Thao tác không thể hoàn tác.':confirm.user.status==='active'?'Người dùng sẽ không thể đăng nhập; lịch sử tài khoản vẫn được giữ lại.':'Cho phép người dùng đăng nhập trở lại.'}</p><div className="user-confirm-actions"><button disabled={saving} className="btn btn-muted" onClick={()=>setConfirm(null)}>Hủy</button><button disabled={saving} className="btn btn-primary" onClick={perform}>{saving?'Đang xử lý...':actionLabel}</button></div></section>}
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
 const {data:profile,reload:reloadProfile}=useLoad('/profile');
 const [modal,setModal]=useState(''),[message,setMessage]=useState(''),[saving,setSaving]=useState(false);const [form,setForm]=useState({full_name:user.full_name,phone:'',team:''}),[photo,setPhoto]=useState(null),[photoPreview,setPhotoPreview]=useState('');const [password,setPassword]=useState({current_password:'',new_password:'',confirm_password:''}),[visible,setVisible]=useState({});const current=profile||user;
 useEffect(()=>{if(profile)setForm({full_name:profile.full_name||'',phone:profile.phone||'',team:profile.team||''})},[profile]);
 function profileErrorMessage(error){const detail=error?.message||'';if(detail==="Mật khẩu hiện tại không đúng")return 'Mật khẩu hiện tại không đúng';if(/^(HTTP \d+|String should|Value error|Input should|Field required)/i.test(detail))return 'Không thể lưu thông tin. Vui lòng kiểm tra dữ liệu và thử lại.';return detail||'Đã xảy ra lỗi. Vui lòng thử lại.'}
 function openEdit(){setForm({full_name:current.full_name||'',phone:current.phone||'',team:current.team||''});setPhoto(null);setPhotoPreview('');setModal('edit')}
 function choosePhoto(file){if(!file)return;if(!['image/jpeg','image/png'].includes(file.type)){setMessage('Vui lòng chọn ảnh JPG hoặc PNG');return}if(file.size>5*1024*1024){setMessage('Dung lượng ảnh không được vượt quá 5 MB');return}setPhoto(file);setPhotoPreview(URL.createObjectURL(file))}
 async function saveProfile(e){e.preventDefault();if(form.full_name.trim().length<2){setMessage('Họ và tên phải có ít nhất 2 ký tự');return}if(form.phone&&!/^[+()\-\d .]{7,30}$/.test(form.phone.trim())){setMessage('Vui lòng nhập số điện thoại hợp lệ');return}setSaving(true);setMessage('');try{if(photo){const body=new FormData();body.append('file',photo);await api('/profile/avatar',{method:'POST',body})}await api('/profile',{method:'PATCH',body:{full_name:form.full_name.trim(),phone:form.phone.trim()||null,team:form.team.trim()||null}});await Promise.all([onRefresh(),reloadProfile()]);setModal('');setMessage('Đã cập nhật hồ sơ thành công')}catch(e){setMessage(profileErrorMessage(e))}finally{setSaving(false)}}
 async function changePassword(e){e.preventDefault();setMessage('');if(password.new_password!==password.confirm_password){setMessage('Mật khẩu mới và xác nhận mật khẩu không khớp');return}if(!passwordRules(password.new_password)){setMessage('Mật khẩu cần có ít nhất 8 ký tự, gồm chữ hoa, chữ thường, chữ số và ký tự đặc biệt');return}setSaving(true);try{await api('/profile/password',{method:'PUT',body:{current_password:password.current_password,new_password:password.new_password}});setPassword({current_password:'',new_password:'',confirm_password:''});setModal('');setMessage('Đã đổi mật khẩu thành công')}catch(e){setMessage(profileErrorMessage(e))}finally{setSaving(false)}}
 function pwField(key,label){return <label className="password-field">{label}<span><input required minLength={key==='new_password'||key==='confirm_password'?8:undefined} type={visible[key]?'text':'password'} value={password[key]} onChange={e=>setPassword({...password,[key]:e.target.value})}/><button type="button" aria-label={visible[key]?'Ẩn mật khẩu':'Hiện mật khẩu'} onClick={()=>setVisible({...visible,[key]:!visible[key]})}>{visible[key]?<EyeOff size={19}/>:<Eye size={19}/>}</button></span></label>}
 return <><Title title="Hồ sơ cá nhân" description="Quản lý thông tin cá nhân và theo dõi các hóa đơn của bạn."/><div className="profile-overview"><section className="panel profile-identity"><ProfileAvatar user={current}/><button type="button" className="textbtn profile-photo-trigger" onClick={openEdit}><Camera size={15}/> Đổi ảnh đại diện</button><h2>{current.full_name}</h2><Pill><LockKeyhole size={13}/>{roleName(current.role)}</Pill><label className="profile-readonly-label">Địa chỉ email <LockKeyhole size={14}/></label><div className="profile-readonly">{current.email}</div></section><section className="panel profile-information"><div className="profile-section-heading"><h3>Thông tin cá nhân</h3>{current.employee_code&&<span>Mã nhân viên - {current.employee_code}</span>}</div><div className="profile-field"><label>Họ và tên</label><div>{current.full_name}</div></div><div className="profile-field-pair"><div className="profile-field"><label>Số điện thoại</label><div>{current.phone||'Chưa cập nhật'}</div></div><div className="profile-field"><label>Phòng ban</label><div>{current.team||'Chưa cập nhật'}</div></div></div><div className="profile-actions"><button className="btn btn-outline" onClick={openEdit}>Chỉnh sửa hồ sơ</button><button className="textbtn change-password-link" onClick={()=>{setPassword({current_password:'',new_password:'',confirm_password:''});setModal('password')}}><LockKeyhole size={17}/> Đổi mật khẩu</button><span className="readonly-badge"><LockKeyhole size={15}/> Chỉ xem</span></div></section></div><ProfileInvoices key={user.id}/>{modal&&<div className="modal-backdrop" onMouseDown={e=>e.target===e.currentTarget&&setModal('')}><section className="profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title"><header><h2 id="profile-modal-title">{modal==='edit'?'Chỉnh sửa hồ sơ':'Đổi mật khẩu'}</h2><button className="iconbtn" aria-label="Đóng hộp thoại" onClick={()=>setModal('')}><X size={22}/></button></header>{modal==='edit'?<form onSubmit={saveProfile}><p className="modal-description">Cập nhật thông tin cá nhân. Vai trò và địa chỉ email không thể thay đổi.</p><div className="modal-avatar-row"><span className="profile-photo">{photoPreview?<img src={photoPreview} alt="Ảnh đại diện xem trước"/>:<ProfileAvatar user={current}/>}</span><div><label className="btn btn-outline photo-select">Đổi ảnh đại diện<input type="file" accept="image/jpeg,image/png" onChange={e=>choosePhoto(e.target.files?.[0])}/></label><small>Ảnh JPG hoặc PNG · Tối đa 5 MB</small></div></div><label className="modal-field">Họ và tên<input required minLength="2" maxLength="150" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><div className="modal-field-pair"><label className="modal-field">Số điện thoại<input type="tel" maxLength="30" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label><label className="modal-field">Phòng ban<input maxLength="120" value={form.team} onChange={e=>setForm({...form,team:e.target.value})}/></label></div><label className="modal-field readonly-input">Địa chỉ email <LockKeyhole size={14}/><input value={current.email} disabled/></label><label className="modal-field readonly-input">Vai trò <LockKeyhole size={14}/><input value={roleName(current.role)} disabled/></label><footer><button type="button" className="btn btn-outline" onClick={()=>setModal('')}>Hủy</button><button className="btn btn-primary" disabled={saving}>{saving?'Đang lưu...':'Lưu thay đổi'}</button></footer></form>:<form onSubmit={changePassword}><p className="modal-description">Hãy sử dụng mật khẩu riêng, an toàn và chưa dùng cho tài khoản khác.</p>{pwField('current_password','Mật khẩu hiện tại')}{pwField('new_password','Mật khẩu mới')}{pwField('confirm_password','Xác nhận mật khẩu mới')}<small className="password-hint">Mật khẩu cần có ít nhất 8 ký tự, gồm chữ hoa, chữ thường, chữ số và ký tự đặc biệt.</small><footer><button type="button" className="btn btn-outline" onClick={()=>setModal('')}>Hủy</button><button className="btn btn-primary" disabled={saving}>{saving?'Đang lưu...':'Đổi mật khẩu'}</button></footer></form>}</section></div>}<Notice message={message} onDismiss={()=>setMessage('')}/></>}
function ProfileInvoices(){
 const navigate=useNavigate();
 const [draft,setDraft]=useState(emptyProfileInvoiceRange);
 const [range,setRange]=useState(emptyProfileInvoiceRange);
 const [page,setPage]=useState(0);
 const [validation,setValidation]=useState('');
 const limit=20;
 const {data,busy,error,reload}=useLoad(profileInvoiceQuery(range,page,limit));
 const pages=Math.ceil((data?.total||0)/limit);
 function apply(e){
   e.preventDefault();
   if(draft.from&&draft.to&&draft.from>draft.to){
     setValidation('Từ ngày không được sau Đến ngày.');
     return;
   }
   setValidation('');
   if(page===0&&range.from===draft.from&&range.to===draft.to)reload();
   setRange(draft);
   setPage(0);
 }
 function clear(){
   setDraft(emptyProfileInvoiceRange);
   setRange(emptyProfileInvoiceRange);
   setPage(0);
   setValidation('');
 }
 function change(field,value){
   setDraft(previous=>({...previous,[field]:value}));
   setValidation('');
 }
 return <section className="panel receipts-panel">
   <div className="receipts-heading">
     <h3>Hóa đơn cá nhân</h3>
     {!busy&&!error&&data&&<span role="status">{data.total} hóa đơn</span>}
   </div>
   <form className="profile-invoice-filter" onSubmit={apply}>
     <label>Từ ngày<input type="date" min="0001-01-01" max="9999-12-31" value={draft.from} onChange={e=>change('from',e.target.value)}/></label>
     <label>Đến ngày<input type="date" min="0001-01-01" max="9999-12-31" value={draft.to} onChange={e=>change('to',e.target.value)}/></label>
     <button type="submit" className="btn btn-primary">Lọc hóa đơn</button>
     <button type="button" className="btn btn-outline" onClick={clear}>Xóa bộ lọc</button>
   </form>
   {validation&&<p className="error" role="alert">{validation}</p>}
   <div aria-busy={busy}>
     {busy?<div role="status"><Loading/></div>:error?
       <div className="profile-invoice-state"><p className="error" role="alert">Không thể tải hóa đơn. Vui lòng thử lại.</p><button type="button" className="btn btn-outline" onClick={reload}>Thử lại</button></div>:
       <>
         {!data?.items.length&&<Empty label={data?.total?'Không có hóa đơn trên trang này':range.from||range.to?'Không có hóa đơn trong khoảng ngày đã chọn':'Chưa có hóa đơn cá nhân'}/>}
         {!!data?.items.length&&<div className="receipt-grid">{data.items.map(item=><button className="receipt-card" key={item.id} onClick={()=>navigate('/invoices/'+item.id)}><span className="receipt-thumb"><InvoiceThumbnail invoice={item}/><span className="receipt-preview-action" aria-hidden="true"><Eye size={18}/><small>Xem chi tiết</small></span></span><span className="receipt-meta"><span>{item.invoice_date?item.invoice_date.split('-').reverse().join('/'):'Chưa có ngày phát hành'}</span><Status value={item.approval_status}/></span><strong>{item.seller_name||item.filename}</strong></button>)}</div>}
         {(pages>1||page>0)&&<nav className="profile-invoice-pagination" aria-label="Phân trang hóa đơn">
           <button type="button" className="btn btn-outline" disabled={page===0} onClick={()=>setPage(page-1)}>Trang trước</button>
           <span>Trang {page+1} / {Math.max(pages,page+1)}</span>
           <button type="button" className="btn btn-outline" disabled={page+1>=pages} onClick={()=>setPage(page+1)}>Trang sau</button>
         </nav>}
       </>
     }
   </div>
 </section>;
}
function InvoiceThumbnail({invoice}){const[src,setSrc]=useState(''),[kind,setKind]=useState('loading');useEffect(()=>{let active=true,objectUrl='';setSrc('');setKind('loading');api(`/invoices/${invoice.id}/thumbnail`,{raw:true}).then(async response=>{const type=response.headers.get('content-type')||'';if(type.includes('application/json')){const result=await response.json();if(active)setKind(result.kind==='xml'?'xml':'default');return}if(!type.startsWith('image/'))throw new Error('Không thể tải ảnh xem trước');const blob=await response.blob();objectUrl=URL.createObjectURL(blob);if(active){setSrc(objectUrl);setKind('image')}else URL.revokeObjectURL(objectUrl)}).catch(()=>{if(active)setKind('default')});return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl)}},[invoice.id]);if(kind==='loading')return <span className="receipt-thumb-loading" role="status" aria-label="Đang tải ảnh xem trước"><RefreshCw size={20} className="spin"/></span>;if(kind==='image')return <img src={src} alt={`Hóa đơn ${invoice.filename||invoice.id}`}/>;if(kind==='xml')return <span className="receipt-document receipt-xml"><FileCode2 size={38}/><small>Tệp XML</small></span>;return <span className="receipt-document"><FileText size={34}/><small>{invoice.filename?.split('.').pop()?.toUpperCase()||'TỆP'}</small></span>}

function auditActionLabel(action){return ({'invoice.uploaded':'Tải hóa đơn lên','invoice.submitted':'Gửi hóa đơn phê duyệt','invoice.approved':'Phê duyệt hóa đơn','invoice.rejected':'Từ chối hóa đơn','schedule.created':'Tạo lịch công tác','schedule.updated':'Cập nhật lịch công tác','user.created':'Tạo người dùng','user.updated':'Cập nhật người dùng'})[action]||action}
function auditEntityLabel(entity){return ({invoice:'Hóa đơn',schedule:'Lịch công tác',user:'Tài khoản'})[entity]||entity}
function AuditPage(){
  const [period, setPeriod] = useState('');
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const thisMonthStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
  const thisYearStr = String(now.getFullYear());
  const [dateVal, setDateVal] = useState(todayStr);

  const queryPath = useMemo(() => {
    if (!period) return '/audit-logs';
    if (period === 'day') return `/audit-logs?day=${dateVal}`;
    if (period === 'month') return `/audit-logs?month=${dateVal.slice(0, 7)}`;
    if (period === 'year') return `/audit-logs?year=${dateVal.slice(0, 4)}`;
    return '/audit-logs';
  }, [period, dateVal]);

  const {data, busy, error, reload} = useLoad(queryPath);

  function selectPeriod(mode) {
    setPeriod(mode);
    if (mode === 'day') setDateVal(todayStr);
    else if (mode === 'month') setDateVal(thisMonthStr);
    else if (mode === 'year') setDateVal(thisYearStr);
    else setDateVal('');
  }

  return <>
    <Title title="Nhật ký hoạt động" description="Theo dõi hoạt động bảo mật và quy trình trong hệ thống."/>
    <section className="panel">
      <div className="panel-heading" style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'12px',marginBottom:'16px'}}>
        <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
          <span style={{fontWeight:600,display:'flex',alignItems:'center',gap:'6px'}}><CalendarDays size={16}/> Lọc thời gian:</span>
          <div className="btn-group" role="group" aria-label="Kiểu lọc thời gian" style={{display:'inline-flex',gap:'4px'}}>
            <button type="button" className={`btn ${period===''?'btn-primary':'btn-outline'}`} onClick={()=>selectPeriod('')}>Tất cả</button>
            <button type="button" className={`btn ${period==='day'?'btn-primary':'btn-outline'}`} onClick={()=>selectPeriod('day')}>Ngày</button>
            <button type="button" className={`btn ${period==='month'?'btn-primary':'btn-outline'}`} onClick={()=>selectPeriod('month')}>Tháng</button>
            <button type="button" className={`btn ${period==='year'?'btn-primary':'btn-outline'}`} onClick={()=>selectPeriod('year')}>Năm</button>
          </div>
          {period==='day'&&<input type="date" className="filter-input" style={{padding:'6px 10px',borderRadius:'8px',border:'1px solid #cbd5e1'}} value={dateVal} onChange={e=>setDateVal(e.target.value)}/>}
          {period==='month'&&<input type="month" className="filter-input" style={{padding:'6px 10px',borderRadius:'8px',border:'1px solid #cbd5e1'}} value={dateVal.slice(0,7)} onChange={e=>setDateVal(e.target.value)}/>}
          {period==='year'&&<select className="filter-input" style={{padding:'6px 10px',borderRadius:'8px',border:'1px solid #cbd5e1'}} value={dateVal.slice(0,4)} onChange={e=>setDateVal(e.target.value)}>
            {Array.from({length:10},(_,i)=>now.getFullYear()+1-i).map(y=><option key={y} value={y}>{y}</option>)}
          </select>}
          {period&&<button type="button" className="btn btn-outline" style={{display:'inline-flex',alignItems:'center',gap:'4px'}} onClick={()=>selectPeriod('')}><X size={14}/> Xóa lọc</button>}
        </div>
        <small style={{color:'#64748b'}}>Hiển thị {data?.length||0} bản ghi</small>
      </div>
      {busy?<Loading/>:error?<div className="profile-invoice-state"><p className="error">{error}</p><button className="btn btn-outline" onClick={reload}>Thử lại</button></div>:<div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Sự kiện</th>
              <th>Loại</th>
              <th>Đối tượng</th>
              <th>Tên người dùng</th>
              <th>Mã người thực hiện</th>
              <th>Thời gian</th>
            </tr>
          </thead>
          <tbody>
            {(data||[]).map(a=><tr key={a.id}>
              <td><strong>{auditActionLabel(a.action)}</strong></td>
              <td>{auditEntityLabel(a.entity_type)}</td>
              <td>#{a.entity_id||'—'}</td>
              <td>{a.actor_name||'Không xác định'}</td>
              <td>{a.actor_id||'—'}</td>
              <td>{datefmt(a.created_at)}</td>
            </tr>)}
          </tbody>
        </table>
        {!data?.length&&<Empty label="Không có nhật ký phù hợp"/>}
      </div>}
    </section>
  </>
}
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
      <Route path="/invoices" element={<InvoicesPage user={user}/>}/>
      <Route path="/invoices/:id" element={<DetailPage user={user}/>}/>
      <Route path="/messages" element={<InvoiceMessagesPage key="direct" user={user}/>}/>
      <Route path="/invoices/:id/messages" element={<InvoiceMessagesRoute user={user}/>}/>
      <Route path="/upload" element={user.role==='employee'?<UploadPage/>:<Navigate to="/invoices"/>}/>
      <Route path="/travel" element={<TravelPage user={user}/>}/>
      <Route path="/approvals" element={user.role!=='employee'?<ApprovalsPage user={user}/>:<Navigate to="/"/>}/>
      <Route path="/schedule" element={<SchedulePage user={user}/>}/>
      <Route path="/ranking" element={<RankingPage/>}/>
      <Route path="/chat" element={<ChatPage key={user.id} user={user}/>}/>
      <Route path="/finance" element={<FinancePage user={user}/>}/>
      <Route path="/reports" element={user.role!=='employee'?<ReportsPage/>:<Navigate to="/"/>}/>
      <Route path="/users" element={user.role==='admin'?<UsersPage/>:<Navigate to="/"/>}/>
      <Route path="/audit" element={user.role==='admin'?<AuditPage/>:<Navigate to="/"/>}/>
      <Route path="/notifications" element={<NotificationsPage/>}/>
      <Route path="/profile" element={<ProfilePage user={user} onRefresh={refresh}/>}/>
      <Route path="*" element={<Navigate to="/"/>}/>
    </Routes>
  </Shell>;
}
