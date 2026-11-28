import React, {useEffect, useState} from 'react';
import {Clock3, AlertTriangle, CheckCircle2, Settings2, Save} from 'lucide-react';
import {api} from './api';
import './approvalSla.css';

const labels={in_time:'Trong hạn',due_soon:'Sắp đến hạn',overdue:'Quá hạn',approved:'Đã phê duyệt',rejected:'Đã từ chối',returned:'Đã trả về bổ sung',unknown:'Thiếu lịch sử xử lý'};
const stamp=value=>value?new Intl.DateTimeFormat('vi-VN',{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Ho_Chi_Minh'}).format(new Date(value)):'Chưa ghi nhận';
const duration=seconds=>{const hours=Math.ceil(seconds/3600);return hours>=24?`${Math.floor(hours/24)} ngày${hours%24?` ${hours%24} giờ`:''}`:`${hours} giờ`;};

export function SLABadge({sla}) {
 if(!sla)return <span className="sla-muted">Chưa có hạn được ghi nhận</span>;
 const closed=Boolean(sla.processed_at),late=sla.overdue_seconds>0;
 return <div className="sla-status"><span className={`sla-badge sla-${sla.status}`}>{sla.status==='overdue'?<AlertTriangle size={13}/>:sla.status==='approved'?<CheckCircle2 size={13}/>:<Clock3 size={13}/>} {labels[sla.status]||'Chưa xác định'}</span><small>Gửi: {stamp(sla.submitted_at)}</small><small>{sla.status==='unknown'?'Chưa đủ bằng chứng tính thời gian xử lý':closed?`Xử lý ${stamp(sla.processed_at)}${late?' · Trễ '+duration(sla.overdue_seconds):''}`:late?`Quá hạn ${duration(sla.overdue_seconds)}`:`Còn ${duration(sla.remaining_working_seconds)} làm việc`}</small><small>Hạn: {stamp(sla.due_at)}</small></div>;
}

function useSummary(revision) {
 const[data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;async function load(){try{const next=await api('/approval-sla/summary');if(active){setData(next);setError('');}}catch(e){if(active)setError(e.message);}}load();const timer=setInterval(load,60000);return()=>{active=false;clearInterval(timer);};},[revision]);
 return {data,error};
}

export function SLAOverview({user,onChange,filter='',onFilter,sort='',onSort}) {
 const {data,error}=useSummary();
 useEffect(()=>{if(data&&onChange)onChange(data);},[data,onChange]);
 return <section className="panel sla-panel"><div className="panel-heading"><div><h3><Clock3 size={18}/> Thời hạn phê duyệt</h3><small>Theo ngày làm việc · Giờ Việt Nam · Không tự động quyết định</small></div></div>
 {error?<p className="error" role="alert">Không tải được thời hạn: {error}</p>:!data?<p className="sla-muted" role="status">Đang tải thời hạn…</p>:<>
 <div className="kpi-grid sla-kpis">{[['Đang chờ phê duyệt',data.pending,''],['Trong hạn',data.counts.in_time,'in_time'],['Sắp đến hạn',data.counts.due_soon,'due_soon'],['Quá hạn',data.counts.overdue,'overdue']].map(([label,value,key])=><div className="kpi" key={label}><span className="kpi-label">{label}</span><strong className={`sla-number-${key}`}>{value}</strong></div>)}</div>
 {data.untracked_pending>0&&<p className="sla-muted">{data.untracked_pending} yêu cầu đang chờ chưa đủ lịch sử gửi để tính hạn; không tự gán ngày gửi.</p>}
 {user.role==='admin'&&<><div className="sla-metrics"><span>Đã xử lý: <b>{data.completed}</b></span><span>Đúng hạn: <b>{data.on_time}</b></span><span>Trễ hạn: <b>{data.late}</b></span><span>Tỷ lệ đúng hạn: <b>{data.on_time_percent==null?'Chưa có dữ liệu':data.on_time_percent+'%'}</b></span><span>Trung bình: <b>{data.average_working_hours==null?'Chưa có dữ liệu':data.average_working_hours+' giờ làm việc'}</b></span></div><SLAPolicy/></>}
 {onFilter&&<div className="filters sla-filters"><label>Thời hạn<select value={filter} onChange={e=>onFilter(e.target.value)}><option value="">Tất cả thời hạn</option>{['in_time','due_soon','overdue'].map(s=><option key={s} value={s}>{labels[s]}</option>)}<option value="unknown">Chưa đủ lịch sử gửi</option></select></label><label>Sắp xếp<select value={sort} onChange={e=>onSort(e.target.value)}><option value="">Thứ tự hiện tại</option><option value="urgent">Mức độ khẩn cấp</option><option value="remaining">Thời gian còn lại ít nhất</option></select></label></div>}
 <small className="sla-muted">Chỉ có hạn khi có lịch sử gửi yêu cầu đáng tin cậy. Một ngày làm việc tương ứng một ngày lịch không phải cuối tuần hoặc ngày lễ đã cấu hình.</small>
 </>}
 </section>;
}

export function SLADetail({invoiceId,revision}) {
 const {data,error}=useSummary(revision),sla=data?.invoices?.[invoiceId];
 const cycles=data?.history?.filter(row=>row.invoice_id===invoiceId)||[];
 return <section className="panel sla-panel"><div className="panel-heading"><h3><Clock3 size={18}/> Tiến trình phê duyệt</h3>{sla&&<SLABadge sla={sla}/>}</div>
 {error?<p className="error">{error}</p>:!data?<p role="status">Đang tải…</p>:!sla?<p className="sla-muted">Chưa có yêu cầu gửi duyệt được ghi nhận.</p>:<><div className="sla-metrics"><span>Gửi yêu cầu: <b>{stamp(sla.submitted_at)}</b></span><span>Hạn phê duyệt: <b>{stamp(sla.due_at)}</b></span><span>Quy định: <b>{sla.working_days} ngày làm việc</b></span></div>{sla.status!=='unknown'&&<progress className={`sla-progress sla-${sla.status}`} value={sla.progress} max="100" aria-label="Thời gian phê duyệt đã sử dụng"/>}<div className="sla-stages"><span>Đã gửi</span><span>{sla.processed_at?'Đã xử lý':'Chờ người có thẩm quyền'}</span></div><details className="sla-history"><summary>Lịch sử thời hạn ({cycles.length} chu kỳ)</summary>{cycles.map(c=><div key={c.id}><strong>{stamp(c.submitted_at)}</strong><SLABadge sla={c}/></div>)}</details></>}
 </section>;
}

function SLAPolicy(){
 const[data,setData]=useState(null),[days,setDays]=useState(3),[holidays,setHolidays]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[saved,setSaved]=useState(false);
 useEffect(()=>{let active=true;api('/approval-sla/policy').then(p=>{if(active){setData(p);setDays(p.days);setHolidays(p.holidays.join('\n'));}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
 async function save(e){e.preventDefault();if(busy||!data)return;setBusy(true);setError('');setSaved(false);try{const dates=holidays.split(/[\n,]+/).map(v=>v.trim()).filter(Boolean);if(dates.some(v=>!/^\d{4}-\d{2}-\d{2}$/.test(v)))throw new Error('Ngày nghỉ cần có định dạng YYYY-MM-DD, mỗi ngày một dòng.');const p=await api('/approval-sla/policy',{method:'PUT',body:{days:Number(days),holidays:dates,version:data.version}});setData(p);setDays(p.days);setHolidays(p.holidays.join('\n'));setSaved(true);}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <details className="sla-policy"><summary><Settings2 size={15}/> Quy định và lịch nghỉ lễ</summary><form onSubmit={save} className="sla-policy-form"><label>Số ngày làm việc<input type="number" min="1" max="90" required value={days} onChange={e=>setDays(e.target.value)}/></label><label>Ngày nghỉ lễ (YYYY-MM-DD, mỗi ngày một dòng)<textarea rows="4" value={holidays} onChange={e=>setHolidays(e.target.value)} placeholder="YYYY-MM-DD"/></label><p className="sla-muted">Chỉ áp dụng cho yêu cầu gửi sau khi lưu; các hạn đã ghi nhận được giữ nguyên.</p>{error&&<p className="error" role="alert">{error}</p>}{saved&&<p role="status">Đã lưu quy định.</p>}<button className="btn btn-primary" disabled={busy||!data}><Save size={15}/>{busy?'Đang lưu…':'Lưu quy định'}</button></form><details className="sla-history"><summary>Lịch sử thay đổi ({data?.history?.length||0})</summary>{data?.history?.map(p=><p key={p.id}>{stamp(p.created_at)} · {p.days} ngày làm việc · {p.holidays.length} ngày nghỉ · Người cập nhật #{p.actor_id}</p>)}</details></details>;
}
