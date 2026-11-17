import React, { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { api } from './api';
import { formatScheduleDateTime, localDateTimeToIso } from './viewUtils';

const statuses = ['planned', 'in_progress', 'completed', 'cancelled'];
const statusLabels = { planned: 'Đã lên kế hoạch', in_progress: 'Đang thực hiện', completed: 'Hoàn thành', cancelled: 'Đã hủy' };

export default function SchedulePage({ user }) {
  const [items, setItems] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [form, setForm] = useState({ title: '', destination: '', starts_at: '', ends_at: '', assigned_to: '' });
  const [busy, setBusy] = useState(true);
  const [employeeBusy, setEmployeeBusy] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const reviewer = user.role === 'accountant' || user.role === 'admin';
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'local';

  async function load() {
    setBusy(true); setError('');
    try {
      const result = await api('/schedules');
      setItems(Array.isArray(result) ? result : []);
    } catch (loadError) { setError(loadError.message); }
    finally { setBusy(false); }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (busy) return;
    const targetId = window.location.hash.slice(1);
    if (!targetId.startsWith('schedule-')) return;
    const id = Number(targetId.slice('schedule-'.length));
    if (!items.some(item => Number(item.id) === id)) return;
    requestAnimationFrame(() => document.getElementById(targetId)?.scrollIntoView({ block: 'center' }));
  }, [busy, items]);
  useEffect(() => {
    if (!reviewer) { setEmployeeBusy(false); return; }
    let active = true;
    api('/directory/employees').then(result => { if (active) setEmployees(Array.isArray(result) ? result : []); })
      .catch(loadError => { if (active) setError(loadError.message); })
      .finally(() => { if (active) setEmployeeBusy(false); });
    return () => { active = false; };
  }, [reviewer]);

  async function create(event) {
    event.preventDefault(); setMessage(''); setError('');
    try {
      const startsAt = localDateTimeToIso(form.starts_at);
      const endsAt = localDateTimeToIso(form.ends_at);
      if (new Date(endsAt) <= new Date(startsAt)) throw new Error('Giờ kết thúc phải sau giờ bắt đầu.');
      const result = await api('/schedules', { method: 'POST', body: { ...form, assigned_to: Number(form.assigned_to), starts_at: startsAt, ends_at: endsAt } });
      setMessage(`Đã tạo lịch #${result.id} · ${formatScheduleDateTime(result.starts_at)} – ${formatScheduleDateTime(result.ends_at)} (${timeZone}).`);
      setForm({ title: '', destination: '', starts_at: '', ends_at: '', assigned_to: '' });
      await load();
    } catch (createError) { setMessage(createError.message); }
  }

  async function setStatus(id, status) {
    setMessage(''); setError('');
    try {
      const result = await api(`/schedules/${id}`, { method: 'PATCH', body: { status } });
      setMessage(`Đã cập nhật trạng thái chuyến đi: ${statusLabels[result.status] || result.status}.`);
      await load();
    } catch (updateError) { setMessage(updateError.message); }
  }

  return <>
    <header className="pagehead"><div><small className="eyebrow">FINTECH OCR / KHÔNG GIAN LÀM VIỆC</small><h1>Lịch công tác của tôi</h1><p>{reviewer ? "Lập kế hoạch công tác và giúp cả nhóm luôn nắm được thông tin." : "Các chuyến công tác được phân công cho bạn."}</p></div></header>
    <div className="two-col">
      <section className="panel"><h3>{reviewer ? "Lịch công tác của nhóm" : "Lịch được phân công"}</h3><p className="timezone-note">Thời gian theo múi giờ trình duyệt:{timeZone}. Thời gian từ API được đọc theo định dạng ISO.</p>
        {busy ? <div className="loading">Đang tải lịch công tác…</div> : error ? <p className="error">{error}</p> : <div className="trip-list spaced">{items.map(item => {
          const start = new Date(item.starts_at);
          return <div id={`schedule-${item.id}`} className="schedule-entry" key={item.id}>
            <div className="datebox"><strong>{Number.isNaN(start.getTime()) ? '—' : start.getDate()}</strong><span>{Number.isNaN(start.getTime()) ? '' : start.toLocaleString('vi-VN', { month: 'short' })}</span></div>
            <div className="schedule-meta"><strong>{item.title}</strong><small>{formatScheduleDateTime(item.starts_at)} – {formatScheduleDateTime(item.ends_at)}</small><small>Địa điểm: {item.destination || '—'}</small><small>Phụ trách: {item.employee_name || '—'}</small></div>
            <div className="schedule-state"><span className={`pill ${item.status === 'completed' ? 'pill-green' : ''}`}>{statusLabels[item.status] || item.status || '—'}</span>{reviewer && <select aria-label={`Cập nhật chuyến công tác ${item.id} trạng thái`} value={item.status} onChange={event => setStatus(item.id, event.target.value)} className="tiny-select">{statuses.map(status => <option key={status} value={status}>{statusLabels[status]}</option>)}</select>}</div>
          </div>;
        })}{!items.length && <div className="empty">Chưa có lịch công tác.</div>}</div>}
      </section>
      {reviewer && <section className="panel"><h3>Tạo lịch công tác</h3>{employeeBusy ? <div className="loading">Đang tải danh sách Nhân viên…</div> : <form className="stack" onSubmit={create}>
        <label>Tên chuyến công tác<input required value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} placeholder="Gặp khách hàng" /></label>
        <label>Địa điểm<input required value={form.destination} onChange={event => setForm({ ...form, destination: event.target.value })} placeholder="Hà Nội" /></label>
        <label>Nhân viên<select required value={form.assigned_to} onChange={event => setForm({ ...form, assigned_to: event.target.value })}><option value="">Chọn nhân viên</option>{employees.filter(employee => employee.role === 'employee' && employee.status === 'active').map(employee => <option key={employee.id} value={employee.id}>{employee.full_name}</option>)}</select></label>
        <label>Ngày giờ bắt đầu<input type="datetime-local" required value={form.starts_at} onChange={event => setForm({ ...form, starts_at: event.target.value })} /></label>
        <label>Ngày giờ kết thúc<input type="datetime-local" required value={form.ends_at} onChange={event => setForm({ ...form, ends_at: event.target.value })} /></label>
        <small>Thời gian được chuyển từ múi giờ trình duyệt sang UTC theo định dạng ISO để gửi tới API.</small>
        <button className="btn btn-primary"><Plus size={17}/>Tạo chuyến công tác</button>
      </form>}</section>}
    </div>
    {message && <div className="toast" role="status">{message}<button aria-label="Đóng thông báo" onClick={() => setMessage('')}>×</button></div>}
  </>;
}
