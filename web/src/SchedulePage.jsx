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
    <header className="pagehead"><div><small className="eyebrow">FINTECH OCR / WORKSPACE</small><h1>My schedule</h1><p>{reviewer ? 'Plan business trips and keep your team on the same page.' : 'Your assigned business trips.'}</p></div></header>
    <div className="two-col">
      <section className="panel"><h3>{reviewer ? 'Team schedule' : 'Assigned schedule'}</h3><p className="timezone-note">Times shown in this browser timezone: {timeZone}. API timestamps are parsed as ISO dates.</p>
        {busy ? <div className="loading">Đang tải lịch công tác…</div> : error ? <p className="error">{error}</p> : <div className="trip-list spaced">{items.map(item => {
          const start = new Date(item.starts_at);
          return <div id={`schedule-${item.id}`} className="schedule-entry" key={item.id}>
            <div className="datebox"><strong>{Number.isNaN(start.getTime()) ? '—' : start.getDate()}</strong><span>{Number.isNaN(start.getTime()) ? '' : start.toLocaleString('vi-VN', { month: 'short' })}</span></div>
            <div className="schedule-meta"><strong>{item.title}</strong><small>{formatScheduleDateTime(item.starts_at)} – {formatScheduleDateTime(item.ends_at)}</small><small>Địa điểm: {item.destination || '—'}</small><small>Phụ trách: {item.employee_name || '—'}</small></div>
            <div className="schedule-state"><span className={`pill ${item.status === 'completed' ? 'pill-green' : ''}`}>{statusLabels[item.status] || item.status || '—'}</span>{reviewer && <select aria-label={`Update trip ${item.id} status`} value={item.status} onChange={event => setStatus(item.id, event.target.value)} className="tiny-select">{statuses.map(status => <option key={status} value={status}>{statusLabels[status]}</option>)}</select>}</div>
          </div>;
        })}{!items.length && <div className="empty">Chưa có lịch công tác.</div>}</div>}
      </section>
      {reviewer && <section className="panel"><h3>New schedule</h3>{employeeBusy ? <div className="loading">Đang tải danh sách Employee…</div> : <form className="stack" onSubmit={create}>
        <label>Trip name<input required value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} placeholder="Client meeting" /></label>
        <label>Destination<input required value={form.destination} onChange={event => setForm({ ...form, destination: event.target.value })} placeholder="Hà Nội" /></label>
        <label>Employee<select required value={form.assigned_to} onChange={event => setForm({ ...form, assigned_to: event.target.value })}><option value="">Select employee</option>{employees.filter(employee => employee.role === 'employee' && employee.status === 'active').map(employee => <option key={employee.id} value={employee.id}>{employee.full_name}</option>)}</select></label>
        <label>Start date and time<input type="datetime-local" required value={form.starts_at} onChange={event => setForm({ ...form, starts_at: event.target.value })} /></label>
        <label>End date and time<input type="datetime-local" required value={form.ends_at} onChange={event => setForm({ ...form, ends_at: event.target.value })} /></label>
        <small>Times are converted from the browser timezone to ISO UTC for the API.</small>
        <button className="btn btn-primary"><Plus size={17}/> Create trip</button>
      </form>}</section>}
    </div>
    {message && <div className="toast" role="status">{message}<button aria-label="Dismiss message" onClick={() => setMessage('')}>×</button></div>}
  </>;
}
