import React,{createContext,useContext,useRef,useState,useEffect,useCallback} from 'react';
import {Routes,Route,NavLink,Navigate,useNavigate,useParams,useLocation,useSearchParams} from 'react-router-dom';
import {Home,FileUp,ClipboardCheck,CalendarDays,MessageSquare,ChartNoAxesCombined,Users,LogOut,Bell,UserCircle,Search,ArrowRight,Plus,FileText,CheckCircle2,XCircle,Clock3,RefreshCw,Download,ShieldCheck,Menu,X,Eye,Save,Send,ChevronLeft,ExternalLink,BarChart3,Trophy,Activity,AlertTriangle,Filter,Settings,Camera,ChevronDown,Pencil,UserRoundX,UserRoundCheck,Trash2} from 'lucide-react';
import {api,authStore,money,datefmt,roleName,approvalName,documentTypeName,ROOT} from './api';
import SpendingChart from './SpendingChart';
import QuickInvoiceSearch from './QuickInvoiceSearch';
import WorkspaceSearchPage from './WorkspaceSearchPage';
import EmployeeProfilePage from './EmployeeProfilePage';
import InvoiceDetailPage from './InvoiceDetailPage';
import UploadPage from './UploadPage';
import EmployeeSchedulePage from './SchedulePage';
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
          <button className="iconbtn bell" aria-label={unread>0?`Thông báo, ${unread} chưa đọc`:"Thông báo"} onClick={()=>n('/notifications')}><Bell size={19}/>{unread>0&&<i/>}</button>
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
 const [filters,setFilters]=useState({approval_status:'',validation_status:'',document_type:'',search:'',invoice_date_from:'',invoice_date_to:''});
 const [summary,setSummary]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 function queryString(){const params=new URLSearchParams();for(const [key,value] of Object.entries(filters))if(value)params.set(key,value);return params.toString()}
 async function loadSummary(){setBusy(true);setMessage('');try{setSummary(await api('/reports/summary'+(queryString()?`?${queryString()}`:'')))}catch(e){setMessage(e.message)}finally{setBusy(false)}}
 useEffect(()=>{loadSummary()},[]);
 async function exportNow(){setBusy(true);setMessage('');try{const nextSummary=await api('/reports/summary'+(queryString()?`?${queryString()}`:''));setSummary(nextSummary);if(!nextSummary.invoice_count){setMessage('Không có dữ liệu để xuất.');return}const response=await api('/reports/export'+(queryString()?`?${queryString()}`:''),{raw:true});const blob=await response.blob();const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='fintech_ocr_invoices.xlsx';anchor.click();URL.revokeObjectURL(url);setMessage('Đã tạo file Excel')}catch(e){setMessage(e.message)}finally{setBusy(false)}}
 function change(key,value){setFilters(current=>({...current,[key]:value}))}
 return <><Title title="Báo cáo" description="Xem dữ liệu hóa đơn và xuất báo cáo Excel cho bộ phận kế toán."/><section className="panel report-panel report-panel-wide"><div className="report-image"><ChartNoAxesCombined size={52}/></div><h3>Báo cáo hóa đơn</h3><p>Số lượng và tổng tiền được tính trên cùng tập hóa đơn đã áp dụng phân quyền như dữ liệu xuất.</p>
 <div className="report-filters">
  <label>Tìm hóa đơn / nhà cung cấp<input value={filters.search} onChange={e=>change('search',e.target.value)} placeholder="Số hóa đơn hoặc nhà cung cấp"/></label>
  <label>Trạng thái phê duyệt<select value={filters.approval_status} onChange={e=>change('approval_status',e.target.value)}><option value="">Tất cả</option>{['draft','pending','approved','rejected'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label>
  <label>Trạng thái kiểm tra<select value={filters.validation_status} onChange={e=>change('validation_status',e.target.value)}><option value="">Tất cả</option>{['valid','needs_review','error'].map(x=><option key={x} value={x}>{approvalName(x)}</option>)}</select></label>
  <label>Loại chứng từ<select value={filters.document_type} onChange={e=>change('document_type',e.target.value)}><option value="">Tất cả</option>{['einvoice','bill','unknown'].map(x=><option key={x} value={x}>{documentTypeName(x)}</option>)}</select></label>
  <label>Từ ngày hóa đơn<input type="date" value={filters.invoice_date_from} onChange={e=>change('invoice_date_from',e.target.value)}/></label>
  <label>Đến ngày hóa đơn<input type="date" value={filters.invoice_date_to} onChange={e=>change('invoice_date_to',e.target.value)}/></label>
 </div>
 <div className="report-actions"><button className="btn btn-secondary" disabled={busy} onClick={loadSummary}><Filter size={16}/>Áp dụng bộ lọc</button><button className="btn btn-primary" disabled={busy} onClick={exportNow}><Download size={17}/>Xuất Excel (.xlsx)</button></div>
 {summary&&<div className="report-summary" aria-live="polite"><div><small>Số hóa đơn trong kết quả</small><strong>{summary.invoice_count}</strong></div><div><small>Tổng tiền (VND)</small><strong>{money(summary.total_amount)}</strong></div></div>}
 <small>Tệp Excel gồm một dòng cho mỗi hóa đơn và một trang tính riêng cho các dòng hàng. Định dạng biểu mẫu theo Thông tư 78 cần Chủ sản phẩm xác nhận.</small></section><Notice message={message} onDismiss={()=>setMessage('')}/></>}
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
  const navigate=useNavigate();
  async function openNotification(item){
    try{
      await openNotificationAfterAccessCheck(item,api,markRead,navigate);
    }catch(actionError){setMessage(actionError.message);}
  }
  async function markAll(){try{await markAllRead();setMessage('');}catch(actionError){setMessage(actionError.message);}}
  return <><Title title="Thông báo" description="Cập nhật tình hình chứng từ, phê duyệt và lịch công tác sắp tới." action={<button className="btn btn-muted" onClick={markAll}>Đánh dấu tất cả đã đọc</button>}/>
    <section className="panel notif-list">{busy?<Loading/>:error?<p className="error">{error}</p>:(items||[]).map(item=><button className={'notif '+(!item.is_read?'unread':'')} key={item.id} onClick={()=>openNotification(item)}>
      <Bell size={19}/><span><strong>{item.title}</strong><small>{item.message}</small><small className="notif-type">{notificationTypeLabel(item.type)}</small><small>{formatNotificationTimestamp(item.created_at)}</small></span>{!item.is_read&&<span className="unread-dot"/>}
    </button>)}{!busy&&!error&&!items?.length&&<Empty label={String.fromCharCode(75,104,244,110,103,32,99,243,32,116,104,244,110,103,32,98,225,111)}/>}</section><Notice message={message} onDismiss={()=>setMessage('')}/></>;
}
function ProfilePage({user,onRefresh}){const[name,setName]=useState(user.full_name),[current,setCurrent]=useState(''),[next,setNext]=useState(''),[message,setMessage]=useState('');return <><Title title="Hồ sơ cá nhân" description="Quản lý thông tin cá nhân và bảo mật tài khoản."/><div className="two-col"><section className="panel"><h3>Thông tin cá nhân</h3><div className="profile-avatar">{user.full_name.slice(-2).toUpperCase()}</div><p>{user.email}</p><Pill>{roleName(user.role)}</Pill><form className="stack margin-top" onSubmit={async e=>{e.preventDefault();try{await api('/profile',{method:'PATCH',body:{full_name:name}});await onRefresh();setMessage('Đã lưu hồ sơ')}catch(e){setMessage(e.message)}}}><label>Họ và tên<input value={name} onChange={e=>setName(e.target.value)}/></label><label>Địa chỉ email<input value={user.email} disabled/></label><button className="btn btn-primary"><Save size={16}/>Lưu thay đổi</button></form></section><section className="panel"><h3>Đổi mật khẩu</h3><form className="stack margin-top" onSubmit={async e=>{e.preventDefault();try{await api('/profile/password',{method:'PUT',body:{current_password:current,new_password:next}});setCurrent('');setNext('');setMessage('Đã thay đổi mật khẩu')}catch(e){setMessage(e.message)}}}><label>Mật khẩu hiện tại<input type="password" value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>Mật khẩu mới<input type="password" minLength={8} value={next} onChange={e=>setNext(e.target.value)}/></label><button className="btn btn-primary"><ShieldCheck size={16}/>Cập nhật mật khẩu</button></form></section></div><Notice message={message} onDismiss={()=>setMessage('')}/></>}
function auditActionLabel(action){return ({'invoice.uploaded':'Tải hóa đơn lên','invoice.submitted':'Gửi hóa đơn phê duyệt','invoice.approved':'Phê duyệt hóa đơn','invoice.rejected':'Từ chối hóa đơn','schedule.created':'Tạo lịch công tác','schedule.updated':'Cập nhật lịch công tác','user.created':'Tạo người dùng','user.updated':'Cập nhật người dùng'})[action]||action}
function auditEntityLabel(entity){return ({invoice:'Hóa đơn',schedule:'Lịch công tác',user:'Tài khoản'})[entity]||entity}
function AuditPage(){const{data}=useLoad('/audit-logs');return <><Title title="Nhật ký kiểm toán" description="Theo dõi hoạt động bảo mật và quy trình trong hệ thống."/><section className="panel"><div className="table-scroll"><table><thead><tr><th>Sự kiện</th><th>Loại</th><th>Đối tượng</th><th>Mã người thực hiện</th><th>Thời gian</th></tr></thead><tbody>{(data||[]).map(a=><tr key={a.id}><td><strong>{auditActionLabel(a.action)}</strong></td><td>{auditEntityLabel(a.entity_type)}</td><td>#{a.entity_id||'—'}</td><td>{a.actor_id||'—'}</td><td>{datefmt(a.created_at)}</td></tr>)}</tbody></table>{!data?.length&&<Empty/>}</div></section></>}
export default function App(){const[user,setUser]=useState(null),[loading,setLoading]=useState(!!authStore.get());const refresh=useCallback(async()=>{let u=await api('/auth/me');setUser(u)},[]);useEffect(()=>{if(authStore.get())refresh().catch(()=>{authStore.set(null);setUser(null)}).finally(()=>setLoading(false))},[refresh]);async function logout(){try{await api('/auth/logout',{method:'POST'})}catch{}authStore.set(null);setUser(null)}if(loading)return <Loading/>;if(!user)return <Login onLogin={setUser}/>;return <Shell user={user} onLogout={logout}><Routes><Route path="/people/:id" element={<EmployeeProfilePage/>}/><Route path="/search" element={<WorkspaceSearchPage/>}/><Route path="/" element={<HomePage user={user}/>}/><Route path="/invoices" element={<InvoicesPage/>}/><Route path="/invoices/:id" element={<DetailPage user={user}/>}/><Route path="/upload" element={user.role==='employee'?<UploadPage/>:<Navigate to="/invoices"/>}/><Route path="/approvals" element={user.role!=='employee'?<ApprovalsPage/>:<Navigate to="/"/>}/><Route path="/schedule" element={<SchedulePage user={user}/>}/><Route path="/ranking" element={<RankingPage/>}/><Route path="/chat" element={<ChatPage/>}/><Route path="/reports" element={user.role!=='employee'?<ReportsPage/>:<Navigate to="/"/>}/><Route path="/users" element={user.role==='admin'?<UsersPage/>:<Navigate to="/"/>}/><Route path="/audit" element={user.role==='admin'?<AuditPage/>:<Navigate to="/"/>}/><Route path="/notifications" element={<NotificationsPage/>}/><Route path="/profile" element={<ProfilePage user={user} onRefresh={refresh}/>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></Shell>}
