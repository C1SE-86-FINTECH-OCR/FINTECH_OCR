import React,{createContext,useContext,useRef,useState,useEffect,useCallback} from 'react';
import {Routes,Route,NavLink,Navigate,useNavigate,useParams,useLocation} from 'react-router-dom';
import {Home,FileUp,ClipboardCheck,CalendarDays,MessageSquare,ChartNoAxesCombined,Users,LogOut,Bell,UserCircle,Search,ArrowRight,Plus,FileText,CheckCircle2,XCircle,Clock3,RefreshCw,Download,ShieldCheck,Menu,X,Eye,EyeOff,Save,Send,ChevronLeft,ExternalLink,BarChart3,Trophy,Activity,AlertTriangle,Filter,Settings,Camera,ChevronDown,LockKeyhole,FileCode2} from 'lucide-react';
import {api,authStore,money,datefmt,roleName,approvalName,documentTypeName,ROOT} from './api';
import SpendingChart from './SpendingChart';
import InvoiceDetailPage from './InvoiceDetailPage';
import UploadPage from './UploadPage';
import EmployeeSchedulePage from './SchedulePage';
import './profile.css';
import { formatNotificationTimestamp, markAllNotificationsReadAfterSuccess, markNotificationReadAfterSuccess, notificationTypeLabel, openNotificationAfterAccessCheck, unreadNotificationCount } from './notificationState';

function useLoad(path,dependencies=[]){const [data,setData]=useState(null),[busy,setBusy]=useState(true),[error,setError]=useState('');const reload=useCallback(()=>{setBusy(true);setError('');api(path).then(setData).catch(e=>setError(e.message)).finally(()=>setBusy(false))},[path]);useEffect(()=>reload(),[reload]);return {data,busy,error,reload,setData,setError}}
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
return <div className="login-wrap"><div className="login-aside"><div className="brand brand-light"><span className="brand-symbol">◈</span><span>FINTECH<strong>OCR / KHÔNG GIAN LÀM VIỆC</strong></span></div><div><p className="overline">KHÔNG GIAN QUẢN LÝ CHI TIÊU NỘI BỘ</p><h1>Từ hóa đơn giấy<br/>đến<em>dữ liệu chuẩn xác.</em></h1><p>Số hóa. Kiểm tra. Phê duyệt.<br/>Mọi công cụ cần thiết cho nhóm, trong một không gian làm việc.</p></div><div className="login-chips"><span>OCR có AI hỗ trợ</span><span>Quy trình phê duyệt</span><span>Phân tích tài chính</span></div></div><div className="login-pane"><div className="login-box"><div className="logo-circle">◈</div><small className="eyebrow">CHÀO MỪNG BẠN TRỞ LẠI</small><h2>Đăng nhập</h2><p>Truy cập không gian làm việc FINTECH OCR</p><form onSubmit={submit} className="stack"><label>Địa chỉ email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Mật khẩu<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<p className="error">{error}</p>}<button className="btn btn-primary full" disabled={loading}>{loading?"Đang đăng nhập...":"Đăng nhập vào hệ thống"} <ArrowRight size={17}/></button></form><div className="demo-account"><strong>TÀI KHOẢN DÙNG THỬ</strong>{['employee','accountant','admin'].map(role=><button key={role} onClick={()=>{setEmail(role+'@fintech.local');setPassword('Password@123')}}>{roleName(role)}<span>Dùng tài khoản này ↗</span></button>)}<small>M\u1eadt kh\u1ea9u: Password@123 · Chỉ dùng để phát triển</small></div></div></div></div>}
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
        <div className="brand"><span className="brand-symbol">{'\u25c8'}</span><span>FINTECH<strong>OCR / KHÔNG GIAN LÀM VIỆC</strong></span></div>
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
        <div className="top-right"><span className="topsearch"><Search size={16}/>Tìm hóa đơn, nhà cung cấp...</span>
          <button className="iconbtn bell" aria-label={unread>0?`Thông báo, ${unread} chưa đọc`:"Thông báo"} onClick={()=>n('/notifications')}><Bell size={19}/>{unread>0&&<i/>}</button>
          <button className="userchip" onClick={()=>n('/profile')}><ProfileAvatar user={user}/><span className="userchip-name">{user.full_name}</span><ChevronDown size={15}/></button>

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
    ["Danh sách hóa đơn", summary.total_invoices, FileText],
    ["Đã phê duyệt", summary.approved, CheckCircle2],
    ["Chờ phê duyệt", summary.pending, Clock3],
    ["Đã từ chối", summary.rejected, XCircle],
  ];

  return <>
    <Title
      title={'Chào mừng trở lại, ' + user.full_name.split(' ').slice(-2).join(' ')}
      description={employee ? "Quản lý chi phí và các chuyến công tác sắp tới tại một nơi." : "Tổng quan nhanh về không gian tài chính của bạn."}
      action={<button className="btn btn-primary" onClick={() => navigate(employee ? '/upload' : '/approvals')}><Plus size={16}/>{employee ? "Tải hóa đơn lên" : "Xem hóa đơn đang chờ phê duyệt"}</button>}
    />
    {busy ? <Loading/> : error ? <p className="error">{error}</p> : <>
      <div className="kpi-grid">
        {stats.map(([name, value, Icon]) => <div className="kpi" key={name}>
          <div className="kpi-label">{name}<Icon size={20}/></div>
          <strong>{value ?? '—'}</strong>
          <small>{name === "Đã phê duyệt" ? "Đã xử lý thành công" : name === "Chờ phê duyệt" ? "Chờ xem xét" : "Trong hệ thống"}</small>
        </div>)}
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
function InvoicesPage(){const[search,setSearch]=useState(''),[status,setStatus]=useState('');const {data,busy,reload,error}=useLoad('/invoices');const n=useNavigate();let rows=(data||[]).filter(i=>(i.invoice_number+' '+i.seller_name+' '+i.filename).toLowerCase().includes(search.toLowerCase())&&(!status||i.approval_status===status));return <><Title title="Hóa đơn" description="Tìm kiếm, lọc và xem dữ liệu hóa đơn."/><div className="panel"><div className="filters"><label className="searchbox"><Search size={17}/><input placeholder="Tìm số hóa đơn hoặc nhà cung cấp..." value={search} onChange={e=>setSearch(e.target.value)}/></label><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">Tất cả trạng thái</option>{['draft','pending','approved','rejected'].map(s=><option key={s} value={s}>{approvalName(s)}</option>)}</select><button className="btn btn-muted" onClick={reload}><RefreshCw size={16}/></button></div>{busy?<Loading/>:error?<p className="error">{error}</p>:<div className="table-scroll"><table><thead><tr><th>Hóa đơn</th><th>Nhà cung cấp</th><th>Ngày</th><th>Số tiền</th><th>Kiểm tra dữ liệu</th><th>Phê duyệt</th><th>Tra cứu thuế</th><th></th></tr></thead><tbody>{rows.map(i=><tr key={i.id}><td><strong>{i.invoice_number||'#'+i.id}</strong><small>{documentTypeName(i.document_type)}</small></td><td>{i.seller_name||'Chưa trích xuất'}</td><td>{datefmt(i.invoice_date)}</td><td className="money">{money(i.total_amount)}</td><td><Status value={i.validation_status}/></td><td><Status value={i.approval_status}/></td><td><Status value={i.lookup_status}/></td><td><button className="btn btn-small btn-muted" onClick={()=>n('/invoices/'+i.id)}>Chi tiết<ArrowRight size={14}/></button></td></tr>)}</tbody></table>{!rows.length&&<Empty label="Không có hóa đơn phù hợp"/>}</div>}</div></>}
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
function RankingPage(){const[period,setPeriod]=useState('all');const{data,busy}=useLoad('/ranking?period='+period);return <><Title title="Xếp hạng chuyến công tác đã hoàn thành" description="Xếp hạng nhân viên theo số chuyến công tác đã hoàn thành; không tính chuyến đã lên kế hoạch hoặc đã hủy."/><section className="panel"><div className="filters"><h3>Bảng xếp hạng nhóm</h3><select value={period} onChange={e=>setPeriod(e.target.value)}><option value="all">Toàn bộ thời gian</option><option value="month">Tháng này</option><option value="quarter">Quý này</option><option value="year">Năm nay</option></select></div>{busy?<Loading/>:<div className="ranking">{(data||[]).map((r,i)=><div className="rankrow" key={r.user_id}><span className="rank">#{i+1}</span><span className="avatar">{r.full_name.slice(-2).toUpperCase()}</span><strong>{r.full_name}</strong><span className="rank-score">{r.completed}đã hoàn thành</span></div>)}{!data?.length&&<Empty label="Chưa có chuyến công tác hoàn thành trong kỳ"/>}</div>}</section></>}
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
 <small>Tệp Excel gồm một dòng cho mỗi hóa đơn và một trang tính riêng cho các dòng hàng. Định dạng biểu mẫu theo Thông tư 78 cần Ch\u1ee7 s\u1ea3n ph\u1ea9m xác nhận.</small></section><Notice message={message} onDismiss={()=>setMessage('')}/></>}
function UsersPage(){const{data,reload}=useLoad('/users'),[open,setOpen]=useState(false),[form,setForm]=useState({full_name:'',email:'',password:'',role:'employee'}),[message,setMessage]=useState('');async function create(e){e.preventDefault();try{await api('/users',{method:'POST',body:form});reload();setOpen(false);setMessage('Đã tạo người dùng')}catch(e){setMessage(e.message)}}async function toggle(u){try{await api('/users/'+u.id,{method:'PATCH',body:{status:u.status==='active'?'disabled':'active'}});reload()}catch(e){setMessage(e.message)}}return <><Title title="Quản lý người dùng" description="Quản lý quyền truy cập, vai trò và trạng thái tài khoản. Lịch sử tài khoản được lưu giữ." action={<button className="btn btn-primary" onClick={()=>setOpen(!open)}><Plus size={17}/>Thêm người dùng</button>}/><div className="two-col"><section className="panel"><h3>Người dùng trong hệ thống<Pill>{data?.length||0}tài khoản</Pill></h3><div className="user-list">{(data||[]).map(u=><div className="user-row" key={u.id}><span className="avatar">{u.full_name.slice(-2).toUpperCase()}</span><div><strong>{u.full_name}</strong><small>{u.email}</small></div><Pill>{roleName(u.role)}</Pill><Pill type={u.status==='active'?'green':'red'}>{approvalName(u.status)}</Pill><button title="Kích hoạt / khóa tài khoản" className="iconbtn" onClick={()=>toggle(u)}><Settings size={16}/></button></div>)}</div></section><section className="panel">{open?<><h3>Thêm người dùng</h3><form className="stack" onSubmit={create}><label>Họ và tên<input required value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><label>Địa chỉ email<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Mật khẩu tạm thời<input type="password" required minLength={8} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Vai trò<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>{['employee','accountant','admin'].map(x=><option key={x} value={x}>{roleName(x)}</option>)}</select></label><button className="btn btn-primary"><Plus size={16}/>Tạo người dùng</button></form></>:<div className="center-helper"><Users size={34}/><h3>Tài khoản và quyền truy cập</h3><p>Chỉ quản trị viên được tạo, chỉnh sửa, kích hoạt và khóa tài khoản. Chọn “Thêm người dùng” để tạo tài khoản.</p></div>}</section></div><Notice message={message} onDismiss={()=>setMessage('')}/></>}
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

function initials(name=''){return name.split(/\s+/).filter(Boolean).slice(-2).map(part=>part[0]).join('').toUpperCase()||'U'}
function ProfileAvatar({user,className=''}){const[src,setSrc]=useState('');useEffect(()=>{let active=true;if(!user.avatar_url){setSrc('');return}api('/profile/avatar',{raw:true}).then(r=>r.blob()).then(blob=>{if(active)setSrc(URL.createObjectURL(blob))}).catch(()=>setSrc(''));return()=>{active=false}},[user.avatar_url,user.id]);return <span className={'profile-photo '+className}>{src?<img src={src} alt=""/>:initials(user.full_name)}</span>}
const passwordRules=value=>value.length>=8&&/[A-Z]/.test(value)&&/[a-z]/.test(value)&&/\d/.test(value)&&/[^A-Za-z0-9]/.test(value);
function ProfilePage({user,onRefresh}){
 const navigate=useNavigate();const {data:profile,reload:reloadProfile}=useLoad('/profile');const {data:invoices,busy,error,reload}=useLoad('/invoices?limit=250');
 const [modal,setModal]=useState(''),[message,setMessage]=useState(''),[saving,setSaving]=useState(false);const [form,setForm]=useState({full_name:user.full_name,phone:'',team:''}),[photo,setPhoto]=useState(null),[photoPreview,setPhotoPreview]=useState('');const [password,setPassword]=useState({current_password:'',new_password:'',confirm_password:''}),[visible,setVisible]=useState({});const current=profile||user;
 useEffect(()=>{if(profile)setForm({full_name:profile.full_name||'',phone:profile.phone||'',team:profile.team||''})},[profile]);
 function openEdit(){setForm({full_name:current.full_name||'',phone:current.phone||'',team:current.team||''});setPhoto(null);setPhotoPreview('');setModal('edit')}
 function choosePhoto(file){if(!file)return;if(!['image/jpeg','image/png'].includes(file.type)){setMessage('Choose a JPG or PNG image');return}if(file.size>5*1024*1024){setMessage('Image must be no larger than 5 MB');return}setPhoto(file);setPhotoPreview(URL.createObjectURL(file))}
 async function saveProfile(e){e.preventDefault();if(form.full_name.trim().length<2){setMessage('Name must contain at least 2 characters');return}if(form.phone&&!/^[+()\-\d .]{7,30}$/.test(form.phone.trim())){setMessage('Enter a valid phone number');return}setSaving(true);setMessage('');try{if(photo){const body=new FormData();body.append('file',photo);await api('/profile/avatar',{method:'POST',body})}await api('/profile',{method:'PATCH',body:{full_name:form.full_name.trim(),phone:form.phone.trim()||null,team:form.team.trim()||null}});await Promise.all([onRefresh(),reloadProfile()]);setModal('');setMessage('Profile updated successfully')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
 async function changePassword(e){e.preventDefault();setMessage('');if(password.new_password!==password.confirm_password){setMessage('New passwords do not match');return}if(!passwordRules(password.new_password)){setMessage('Use at least 8 characters with uppercase, lowercase, a number, and a special character');return}setSaving(true);try{await api('/profile/password',{method:'PUT',body:{current_password:password.current_password,new_password:password.new_password}});setPassword({current_password:'',new_password:'',confirm_password:''});setModal('');setMessage('Password changed successfully')}catch(e){setMessage(e.message)}finally{setSaving(false)}}
 function pwField(key,label){return <label className="password-field">{label}<span><input required minLength={key==='new_password'||key==='confirm_password'?8:undefined} type={visible[key]?'text':'password'} value={password[key]} onChange={e=>setPassword({...password,[key]:e.target.value})}/><button type="button" aria-label={visible[key]?'Hide password':'Show password'} onClick={()=>setVisible({...visible,[key]:!visible[key]})}>{visible[key]?<EyeOff size={19}/>:<Eye size={19}/>}</button></span></label>}
 return <><Title title="My Profile" description="Manage your personal details and keep track of your receipts."/><div className="profile-overview"><section className="panel profile-identity"><ProfileAvatar user={current}/><button type="button" className="textbtn profile-photo-trigger" onClick={openEdit}><Camera size={15}/> Change photo</button><h2>{current.full_name}</h2><Pill><LockKeyhole size={13}/>{roleName(current.role)}</Pill><label className="profile-readonly-label">Email <LockKeyhole size={14}/></label><div className="profile-readonly">{current.email}</div></section><section className="panel profile-information"><div className="profile-section-heading"><h3>Personal information</h3>{current.employee_code&&<span>Employee ID - {current.employee_code}</span>}</div><div className="profile-field"><label>Full name</label><div>{current.full_name}</div></div><div className="profile-field-pair"><div className="profile-field"><label>Phone</label><div>{current.phone||'Not provided'}</div></div><div className="profile-field"><label>Team</label><div>{current.team||'Not provided'}</div></div></div><div className="profile-actions"><button className="btn btn-outline" onClick={openEdit}>Edit Profile</button><button className="textbtn change-password-link" onClick={()=>{setPassword({current_password:'',new_password:'',confirm_password:''});setModal('password')}}><LockKeyhole size={17}/> Change password</button><span className="readonly-badge"><LockKeyhole size={15}/> Read only</span></div></section></div><section className="panel receipts-panel"><div className="receipts-heading"><h3>{user.role==='employee'?'My submitted receipts':'Workspace receipts'}</h3><span>{Array.isArray(invoices)?invoices.length:0}</span></div>{busy?<Loading/>:error?<div className="profile-invoice-state"><p className="error">{error}</p><button className="btn btn-outline" onClick={reload}>Try again</button></div>:!invoices?.length?<Empty label="No receipts yet"/>:<div className="receipt-grid">{invoices.map(item=><button className="receipt-card" key={item.id} onClick={()=>navigate('/invoices/'+item.id)}><span className="receipt-thumb"><InvoiceThumbnail invoice={item}/></span><span className="receipt-meta"><span>{datefmt(item.invoice_date||item.created_at)}</span><Status value={item.approval_status}/></span><strong>{item.seller_name||item.filename}</strong></button>)}</div>}</section>{modal&&<div className="modal-backdrop" onMouseDown={e=>e.target===e.currentTarget&&setModal('')}><section className="profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title"><header><h2 id="profile-modal-title">{modal==='edit'?'Edit Profile':'Change password'}</h2><button className="iconbtn" aria-label="Close" onClick={()=>setModal('')}><X size={22}/></button></header>{modal==='edit'?<form onSubmit={saveProfile}><p className="modal-description">Update your personal details. Your role and email cannot be changed.</p><div className="modal-avatar-row"><span className="profile-photo">{photoPreview?<img src={photoPreview} alt="Preview"/>:<ProfileAvatar user={current}/>}</span><div><label className="btn btn-outline photo-select">Change profile photo<input type="file" accept="image/jpeg,image/png" onChange={e=>choosePhoto(e.target.files?.[0])}/></label><small>JPG or PNG - Up to 5 MB</small></div></div><label className="modal-field">Full name<input required minLength="2" maxLength="150" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><div className="modal-field-pair"><label className="modal-field">Phone<input type="tel" maxLength="30" value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label><label className="modal-field">Team<input maxLength="120" value={form.team} onChange={e=>setForm({...form,team:e.target.value})}/></label></div><label className="modal-field readonly-input">Email <LockKeyhole size={14}/><input value={current.email} disabled/></label><label className="modal-field readonly-input">Role <LockKeyhole size={14}/><input value={roleName(current.role)} disabled/></label><footer><button type="button" className="btn btn-outline" onClick={()=>setModal('')}>Cancel</button><button className="btn btn-primary" disabled={saving}>{saving?'Saving...':'Save changes'}</button></footer></form>:<form onSubmit={changePassword}><p className="modal-description">Protect your account with a unique password that you have not used before.</p>{pwField('current_password','Current password')}{pwField('new_password','New password')}{pwField('confirm_password','Confirm new password')}<small className="password-hint">At least 8 characters with uppercase, lowercase, a number, and a special character.</small><footer><button type="button" className="btn btn-outline" onClick={()=>setModal('')}>Cancel</button><button className="btn btn-primary" disabled={saving}>{saving?'Saving...':'Change password'}</button></footer></form>}</section></div>}<Notice message={message} onDismiss={()=>setMessage('')}/></>}
function InvoiceThumbnail({invoice}){const[src,setSrc]=useState(''),[kind,setKind]=useState('loading');useEffect(()=>{let active=true,objectUrl='';setSrc('');setKind('loading');api(`/invoices/${invoice.id}/thumbnail`,{raw:true}).then(async response=>{const type=response.headers.get('content-type')||'';if(type.includes('application/json')){const result=await response.json();if(active)setKind(result.kind==='xml'?'xml':'default');return}if(!type.startsWith('image/'))throw new Error('Thumbnail is unavailable');const blob=await response.blob();objectUrl=URL.createObjectURL(blob);if(active){setSrc(objectUrl);setKind('image')}else URL.revokeObjectURL(objectUrl)}).catch(()=>{if(active)setKind('default')});return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl)}},[invoice.id]);if(kind==='loading')return <span className="receipt-thumb-loading" role="status" aria-label="Loading thumbnail"><RefreshCw size={20} className="spin"/></span>;if(kind==='image')return <img src={src} alt={`Invoice ${invoice.filename||invoice.id}`}/>;if(kind==='xml')return <span className="receipt-document receipt-xml"><FileCode2 size={38}/><small>XML</small></span>;return <span className="receipt-document"><FileText size={34}/><small>{invoice.filename?.split('.').pop()?.toUpperCase()||'FILE'}</small></span>}

function auditActionLabel(action){return ({'invoice.uploaded':'Tải hóa đơn lên','invoice.submitted':'Gửi hóa đơn phê duyệt','invoice.approved':'Phê duyệt hóa đơn','invoice.rejected':'Từ chối hóa đơn','schedule.created':'Tạo lịch công tác','schedule.updated':'Cập nhật lịch công tác','user.created':'Tạo người dùng','user.updated':'Cập nhật người dùng'})[action]||action}
function auditEntityLabel(entity){return ({invoice:'Hóa đơn',schedule:'Lịch công tác',user:'Tài khoản'})[entity]||entity}
function AuditPage(){const{data}=useLoad('/audit-logs');return <><Title title="Nhật ký kiểm toán" description="Theo dõi hoạt động bảo mật và quy trình trong hệ thống."/><section className="panel"><div className="table-scroll"><table><thead><tr><th>Sự kiện</th><th>Loại</th><th>Đối tượng</th><th>Mã người thực hiện</th><th>Thời gian</th></tr></thead><tbody>{(data||[]).map(a=><tr key={a.id}><td><strong>{auditActionLabel(a.action)}</strong></td><td>{auditEntityLabel(a.entity_type)}</td><td>#{a.entity_id||'—'}</td><td>{a.actor_id||'—'}</td><td>{datefmt(a.created_at)}</td></tr>)}</tbody></table>{!data?.length&&<Empty/>}</div></section></>}
export default function App(){const[user,setUser]=useState(null),[loading,setLoading]=useState(!!authStore.get());const refresh=useCallback(async()=>{let u=await api('/auth/me');setUser(u)},[]);useEffect(()=>{if(authStore.get())refresh().catch(()=>{authStore.set(null);setUser(null)}).finally(()=>setLoading(false))},[refresh]);async function logout(){try{await api('/auth/logout',{method:'POST'})}catch{}authStore.set(null);setUser(null)}if(loading)return <Loading/>;if(!user)return <Login onLogin={setUser}/>;return <Shell user={user} onLogout={logout}><Routes><Route path="/" element={<HomePage user={user}/>}/><Route path="/invoices" element={<InvoicesPage/>}/><Route path="/invoices/:id" element={<DetailPage user={user}/>}/><Route path="/upload" element={user.role==='employee'?<UploadPage/>:<Navigate to="/invoices"/>}/><Route path="/approvals" element={user.role!=='employee'?<ApprovalsPage/>:<Navigate to="/"/>}/><Route path="/schedule" element={<SchedulePage user={user}/>}/><Route path="/ranking" element={<RankingPage/>}/><Route path="/chat" element={<ChatPage/>}/><Route path="/reports" element={user.role!=='employee'?<ReportsPage/>:<Navigate to="/"/>}/><Route path="/users" element={user.role==='admin'?<UsersPage/>:<Navigate to="/"/>}/><Route path="/audit" element={user.role==='admin'?<AuditPage/>:<Navigate to="/"/>}/><Route path="/notifications" element={<NotificationsPage/>}/><Route path="/profile" element={<ProfilePage user={user} onRefresh={refresh}/>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></Shell>}
