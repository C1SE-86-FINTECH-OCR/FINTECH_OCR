import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Eye, MapPin, Pencil, Plus, RefreshCw, UserRound, Users, X } from 'lucide-react';
import { api } from './api';
import './SchedulePage.css';

const ZONE = 'Asia/Ho_Chi_Minh';
const STATUS_CONFIG = {
  planned: { label: 'Đã lên lịch', description: 'Chuyến công tác đã được phân công.', color: '#2563EB', symbol: '○' },
  completed: { label: 'Đã hoàn thành', description: 'Chuyến công tác đã được xác nhận hoàn thành.', color: '#15803D', symbol: '✓' },
  cancelled: { label: 'Đã hủy', description: 'Chuyến công tác không còn được thực hiện.', color: '#DC2626', symbol: '×' },
};
const statusKey = status => status === 'completed' ? 'completed' : status === 'cancelled' ? 'cancelled' : 'planned';
const STATUS_KEYS = ['planned', 'completed', 'cancelled'];
const WEEKDAYS = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật'];
const fmtParts = (value, options) => Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: ZONE, ...options }).formatToParts(value).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
const dateKey = value => { const p = fmtParts(value, { year: 'numeric', month: '2-digit', day: '2-digit' }); return `${p.year}-${p.month}-${p.day}`; };
const fromKey = key => { const [y, m, d] = key.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d, 4)); };
const shiftDate = (date, days) => new Date(date.getTime() + days * 86400000);
const initials = name => (name || '').trim().split(/\s+/).slice(-2).map(x => x[0]).join('').toLocaleUpperCase('vi-VN') || 'NV';
const timeValue = value => new Intl.DateTimeFormat('vi-VN', { timeZone: ZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
const dateLabel = (value, options = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) => new Intl.DateTimeFormat('vi-VN', { timeZone: ZONE, ...options }).format(new Date(value));
const shortDateLabel = value => new Intl.DateTimeFormat('vi-VN', { timeZone: ZONE, day: '2-digit', month: '2-digit', year: 'numeric' }).format(value);
const inputDateTime = value => `${dateKey(new Date(value))}T${timeValue(value)}`;
const vietnamIso = value => { if (!value) return ''; const [day, time] = value.split('T'); return `${day}T${time}:00+07:00`; };
const defaultDateTime = (day, hour) => `${day}T${hour}:00`;

function getCalendarDays(anchor, view) {
  if (view === 'week') {
    const monday = shiftDate(anchor, -((anchor.getUTCDay() + 6) % 7));
    return Array.from({ length: 7 }, (_, i) => shiftDate(monday, i));
  }
  const first = new Date(Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth(), 1, 4));
  const start = shiftDate(first, -((first.getUTCDay() + 6) % 7));
  const last = new Date(Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth() + 1, 0, 4));
  const count = Math.ceil(((last - start) / 86400000 + 1) / 7) * 7;
  return Array.from({ length: count }, (_, i) => shiftDate(start, i));
}

export default function SchedulePage({ user }) {
  const reviewer = ['admin', 'accountant'].includes(user.role);
  const [items, setItems] = useState([]), [employees, setEmployees] = useState([]);
  const [anchor, setAnchor] = useState(() => fromKey(dateKey(new Date()))), [view, setView] = useState('month');
  const [employeeFilter, setEmployeeFilter] = useState(''), [statusFilter, setStatusFilter] = useState('');
  const [selectedDate, setSelectedDate] = useState(dateKey(new Date())), [selectedId, setSelectedId] = useState(null), [panel, setPanel] = useState('');
  const [form, setForm] = useState({ title: '', destination: '', day: dateKey(new Date()), starts: defaultDateTime(dateKey(new Date()), '09:00'), ends: defaultDateTime(dateKey(new Date()), '11:00'), assigned_to: '', notes: '' });
  const [editing, setEditing] = useState(false), [busy, setBusy] = useState(true), [employeeBusy, setEmployeeBusy] = useState(false), [saving, setSaving] = useState(false);
  const [error, setError] = useState(''), [message, setMessage] = useState('');
  const [datePickerOpen, setDatePickerOpen] = useState(false), [pickerAnchor, setPickerAnchor] = useState(() => fromKey(dateKey(new Date()))), [pickerPosition, setPickerPosition] = useState({ top: 0, left: 0 });
  const dateButtonRef = useRef(null), datePopupRef = useRef(null);
  const activeEmployees = employees.filter(x => x.role === 'employee' && x.status === 'active');
  const filterEmployees = useMemo(() => { const byId = new Map(activeEmployees.map(e => [String(e.id), e])); items.forEach(x => { if (!byId.has(String(x.assigned_to))) byId.set(String(x.assigned_to), { id: x.assigned_to, full_name: x.employee_name }); }); return [...byId.values()].sort((a, b) => a.full_name.localeCompare(b.full_name, 'vi')); }, [activeEmployees, items]);

  const load = useCallback(async () => {
    setBusy(true); setError('');
    try { const result = await api('/schedules'); setItems(Array.isArray(result) ? result : []); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!reviewer) return;
    let live = true; setEmployeeBusy(true);
    api('/directory/employees').then(rows => { if (live) setEmployees(Array.isArray(rows) ? rows : []); })
      .catch(e => { if (live) setError(e.message); }).finally(() => { if (live) setEmployeeBusy(false); });
    return () => { live = false; };
  }, [reviewer]);

  const filteredItems = useMemo(() => items.filter(item => (!employeeFilter || String(item.assigned_to) === employeeFilter) && (!statusFilter || statusKey(item.status) === statusFilter)), [items, employeeFilter, statusFilter]);
  const days = useMemo(() => getCalendarDays(anchor, view), [anchor, view]);
  const selected = items.find(item => Number(item.id) === Number(selectedId));
  const monthParts = fmtParts(anchor, { year: 'numeric', month: '2-digit' });
  const currentMonth = `${monthParts.year}-${monthParts.month}`;
  const monthItems = items.filter(item => dateKey(new Date(item.starts_at)).startsWith(currentMonth));
  const now = Date.now();
  const upcomingCount = monthItems.filter(x => ['planned', 'in_progress'].includes(x.status) && new Date(x.starts_at).getTime() >= now).length;
  const completedCount = monthItems.filter(x => x.status === 'completed').length;
  const cancelledCount = monthItems.filter(x => x.status === 'cancelled').length;
  const pickerParts = fmtParts(pickerAnchor, { year: 'numeric', month: '2-digit' });
  const pickerMonth = Number(pickerParts.month), pickerYear = Number(pickerParts.year);
  const pickerDays = useMemo(() => getCalendarDays(pickerAnchor, 'month'), [pickerAnchor]);
  const pickerYears = useMemo(() => Array.from({ length: 21 }, (_, i) => pickerYear - 10 + i), [pickerYear]);

  const openNotificationTrip = useCallback(() => {
    const targetId = Number(window.location.hash.match(/^#schedule-(\d+)$/)?.[1]);
    const target = items.find(x => Number(x.id) === targetId);
    if (!targetId || !target) return;
    const targetDay = dateKey(new Date(target.starts_at)); setAnchor(fromKey(targetDay)); setSelectedDate(targetDay); setEmployeeFilter(''); setStatusFilter('');
    setSelectedId(targetId); setPanel('detail');
    requestAnimationFrame(() => document.getElementById(`schedule-${targetId}`)?.scrollIntoView({ block: 'center' }));
  }, [items]);
  useEffect(() => { openNotificationTrip(); window.addEventListener('hashchange', openNotificationTrip); return () => window.removeEventListener('hashchange', openNotificationTrip); }, [openNotificationTrip]);

  const positionDatePicker = useCallback(() => {
    const rect = dateButtonRef.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(316, window.innerWidth - 24), height = 370;
    setPickerPosition({ left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)), top: rect.bottom + height + 12 > window.innerHeight ? Math.max(12, rect.top - height - 8) : rect.bottom + 8 });
  }, []);
  useEffect(() => {
    if (!datePickerOpen) return undefined;
    positionDatePicker();
    const onPointerDown = event => {
      if (!datePopupRef.current?.contains(event.target) && !dateButtonRef.current?.contains(event.target)) setDatePickerOpen(false);
    };
    const onKeyDown = event => { if (event.key === 'Escape') setDatePickerOpen(false); };
    document.addEventListener('pointerdown', onPointerDown); document.addEventListener('keydown', onKeyDown);
    window.addEventListener('resize', positionDatePicker); window.addEventListener('scroll', positionDatePicker, true);
    return () => { document.removeEventListener('pointerdown', onPointerDown); document.removeEventListener('keydown', onKeyDown); window.removeEventListener('resize', positionDatePicker); window.removeEventListener('scroll', positionDatePicker, true); };
  }, [datePickerOpen, positionDatePicker]);

  function move(direction) {
    const next = view === 'month'
      ? new Date(Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth() + direction, Math.min(Number(selectedDate.slice(-2)), new Date(Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth() + direction + 1, 0)).getUTCDate()), 4))
      : shiftDate(fromKey(selectedDate), direction * 7);
    const key = dateKey(next); setAnchor(fromKey(key)); setSelectedDate(key);
  }
  function today() { const key = dateKey(new Date()), todayDate = fromKey(key); setAnchor(todayDate); setSelectedDate(key); }
  function chooseDate(day) { const key = dateKey(day); setSelectedDate(key); setAnchor(fromKey(key)); setDatePickerOpen(false); }
  function setPickerMonth(month) { setPickerAnchor(new Date(Date.UTC(pickerYear, month - 1, 1, 4))); }
  function setPickerYear(year) { setPickerAnchor(new Date(Date.UTC(Number(year), pickerMonth - 1, 1, 4))); }
  function shiftPickerMonth(amount) { setPickerAnchor(new Date(Date.UTC(pickerYear, pickerMonth - 1 + amount, 1, 4))); }
  function shiftPickerYear(amount) { setPickerAnchor(new Date(Date.UTC(pickerYear + amount, pickerMonth - 1, 1, 4))); }
  function openDatePicker() { setPickerAnchor(fromKey(selectedDate)); setDatePickerOpen(open => !open); }
  function openCreate(day = selectedDate) {
    setSelectedDate(day); setSelectedId(null); setEditing(false); setError('');
    setForm({ title: '', destination: '', day, starts: defaultDateTime(day, '09:00'), ends: defaultDateTime(day, '11:00'), assigned_to: activeEmployees[0]?.id ? String(activeEmployees[0].id) : '', notes: '' });
    setPanel('form');
  }
  function openEdit(item) {
    setSelectedId(item.id); setEditing(true); setError('');
    setForm({ title: item.title || '', destination: item.destination || '', day: dateKey(new Date(item.starts_at)), starts: inputDateTime(item.starts_at), ends: inputDateTime(item.ends_at), assigned_to: String(item.assigned_to), notes: item.notes || '' });
    setPanel('form');
  }
  function openDay(day) { const key = dateKey(day); setAnchor(fromKey(key)); setSelectedDate(key); setSelectedId(null); setPanel('day'); if (reviewer) openCreate(key); }

  async function save(event) {
    event.preventDefault(); setError(''); setMessage('');
    if (!form.title.trim() || !form.destination.trim() || !form.day || !form.starts || !form.ends || !form.assigned_to) { setError('Vui lòng điền đầy đủ các trường bắt buộc.'); return; }
    const startsAt = vietnamIso(form.starts), endsAt = vietnamIso(form.ends);
    if (new Date(endsAt) <= new Date(startsAt)) { setError('Giờ kết thúc phải sau giờ bắt đầu.'); return; }
    const body = { title: form.title.trim(), destination: form.destination.trim(), starts_at: startsAt, ends_at: endsAt, assigned_to: Number(form.assigned_to), notes: form.notes.trim() || null };
    setSaving(true);
    try {
      const result = await api(editing ? `/schedules/${selectedId}` : '/schedules', { method: editing ? 'PATCH' : 'POST', body });
      setItems(current => editing ? current.map(x => x.id === result.id ? result : x).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)) : [...current, result].sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)));
      const resultDay = dateKey(new Date(result.starts_at)); setSelectedDate(resultDay); setAnchor(fromKey(resultDay)); setSelectedId(result.id); setPanel('detail'); setMessage(editing ? 'Đã cập nhật lịch công tác.' : 'Đã phân công lịch công tác.');
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  }

  async function changeStatus(item, status) {
    setError(''); setMessage('');
    try { const result = await api(`/schedules/${item.id}`, { method: 'PATCH', body: { status } }); setItems(current => current.map(x => x.id === result.id ? result : x)); setSelectedId(result.id); setPanel('detail'); setMessage(`Đã cập nhật trạng thái: ${STATUS_CONFIG[statusKey(result.status)].label}.`); }
    catch (e) { setError(e.message); }
  }

  const pageTitle = user.role === 'admin' ? 'Quản lý lịch công tác' : user.role === 'accountant' ? 'Lịch công tác' : 'Lịch công tác của tôi';
  const periodLabel = view === 'month' ? `Tháng ${Number(monthParts.month)} năm ${monthParts.year}` : `${shortDateLabel(days[0])} - ${shortDateLabel(days[6])}`;

  return <div className="schedule-page">
    <header className="pagehead schedule-page-head"><div><small className="eyebrow">FINTECH OCR / KHÔNG GIAN LÀM VIỆC</small><h1>{pageTitle}</h1><p>{reviewer ? 'Lập kế hoạch công tác và theo dõi lịch trình của nhóm.' : 'Theo dõi các chuyến công tác được phân công cho bạn.'}</p></div>
      {reviewer ? <button className="btn btn-primary" onClick={() => openCreate()}><Plus size={17}/>Tạo lịch công tác</button> : <span className="schedule-view-only"><Eye size={16}/>Chỉ xem</span>}
    </header>

    <div className="schedule-toolbar">
      <div className="schedule-filters">{reviewer && <>
        <label><Users size={16}/><select aria-label="Lọc theo nhân viên" value={employeeFilter} onChange={e => setEmployeeFilter(e.target.value)}><option value="">Tất cả nhân viên</option>{filterEmployees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}</select></label>
        <label><CalendarDays size={16}/><select aria-label="Lọc theo trạng thái" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="">Tất cả trạng thái</option>{STATUS_KEYS.map(key => <option key={key} value={key}>{STATUS_CONFIG[key].label}</option>)}</select></label>
      </>}</div>
    </div>

    <div className="schedule-layout">
      <section className="panel schedule-calendar-panel">
        <div className="schedule-calendar-head">
          <div className="schedule-nav-controls">
            <button className="iconbtn" aria-label="Kỳ trước" onClick={() => move(-1)}><ChevronLeft size={18}/></button>
            <button className="iconbtn" aria-label="Kỳ tiếp theo" onClick={() => move(1)}><ChevronRight size={18}/></button>
            <button className="btn btn-outline btn-small" onClick={today}>Hôm nay</button>
            <button ref={dateButtonRef} className="schedule-date-picker-trigger" aria-label="Mở bộ chọn ngày" aria-expanded={datePickerOpen} onClick={openDatePicker}><CalendarDays size={15}/><ChevronDown size={14}/></button>
            <h2 className="schedule-period-label">{periodLabel}</h2>
          </div>
          <div className="schedule-head-right"><span className="schedule-zone">GMT+7</span><div className="schedule-view-toggle"><button className={view === 'month' ? 'selected' : ''} onClick={() => { setView('month'); setAnchor(fromKey(selectedDate)); }}>Tháng</button><button className={view === 'week' ? 'selected' : ''} onClick={() => { setView('week'); setAnchor(fromKey(selectedDate)); }}>Tuần</button></div></div>
        </div>
        {datePickerOpen && <div ref={datePopupRef} className="schedule-date-picker-popup" style={pickerPosition} role="dialog" aria-label="Chọn ngày">
          <div className="schedule-picker-heading"><strong>Chọn ngày</strong><button className="iconbtn" aria-label="Đóng bộ chọn ngày" onClick={() => setDatePickerOpen(false)}><X size={16}/></button></div>
          <div className="schedule-picker-selects"><div className="schedule-picker-stepper"><button aria-label="Tháng trước" onClick={() => shiftPickerMonth(-1)}><ChevronLeft size={15}/></button><select aria-label="Chọn tháng" value={pickerMonth} onChange={e => setPickerMonth(Number(e.target.value))}>{Array.from({ length: 12 }, (_, i) => i + 1).map(month => <option key={month} value={month}>Tháng {month}</option>)}</select><button aria-label="Tháng sau" onClick={() => shiftPickerMonth(1)}><ChevronRight size={15}/></button></div><div className="schedule-picker-stepper"><button aria-label="Năm trước" onClick={() => shiftPickerYear(-1)}><ChevronLeft size={15}/></button><select aria-label="Chọn năm" value={pickerYear} onChange={e => setPickerYear(e.target.value)}>{pickerYears.map(year => <option key={year} value={year}>{year}</option>)}</select><button aria-label="Năm sau" onClick={() => shiftPickerYear(1)}><ChevronRight size={15}/></button></div></div>
          <div className="schedule-picker-weekdays">{['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'].map(day => <span key={day}>{day}</span>)}</div>
          <div className="schedule-picker-grid">{pickerDays.map(day => { const key = dateKey(day), isToday = key === dateKey(new Date()), selectedDay = key === selectedDate, inMonth = Number(key.slice(5, 7)) === pickerMonth; return <button key={key} className={`${!inMonth ? 'outside' : ''} ${isToday ? 'today' : ''} ${selectedDay ? 'chosen' : ''}`} onClick={() => chooseDate(day)} aria-label={dateLabel(day, { day: 'numeric', month: 'long', year: 'numeric' })} aria-pressed={selectedDay}>{Number(key.slice(-2))}</button>; })}</div>
        </div>}
        {busy ? <div className="loading"><RefreshCw size={17} className="spin"/>Đang tải lịch công tác…</div> : error && !items.length ? <div className="schedule-error">{error}<button className="btn btn-outline btn-small" onClick={load}>Thử lại</button></div> : <>
          <div className="schedule-weekdays">{WEEKDAYS.map(day => <span key={day}>{day}</span>)}</div>
          <div className={`schedule-grid ${view === 'week' ? 'schedule-grid-week' : ''}`}>{days.map(day => {
            const key = dateKey(day), isCurrentMonth = key.startsWith(currentMonth), isToday = key === dateKey(new Date());
            const dayItems = filteredItems.filter(item => dateKey(new Date(item.starts_at)) === key).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
            const visibleItems = dayItems.slice(0, 3), extra = dayItems.length - visibleItems.length;
            return <div key={key} className={`schedule-day ${view === 'month' && !isCurrentMonth ? 'outside-month' : ''} ${isToday ? 'is-today' : ''} ${selectedDate === key ? 'selected-day' : ''}`} onClick={() => openDay(day)}>
              <div className="schedule-day-label"><span>{Number(key.slice(-2))}</span></div>
              <div className="schedule-day-events">{visibleItems.map(item => { const state = STATUS_CONFIG[statusKey(item.status)]; return <button id={`schedule-${item.id}`} key={item.id} className="schedule-event" style={{ backgroundColor: state.color }} onClick={e => { e.stopPropagation(); setSelectedId(item.id); setSelectedDate(key); setPanel('detail'); }} title={`${item.title} · ${timeValue(item.starts_at)} · ${state.label} · ${item.employee_name}`}>
                <strong>{item.title}</strong><span className="schedule-event-meta"><time>{timeValue(item.starts_at)}</time><span className="schedule-event-state" aria-label={state.label}>{state.symbol}</span><i>{initials(item.employee_name)}</i></span>
              </button>; })}{extra > 0 && <button className="schedule-more" onClick={e => { e.stopPropagation(); setSelectedDate(key); setSelectedId(null); setPanel('day'); }}>+{extra} lịch khác</button>}</div>
            </div>;
          })}</div>
          <div className="schedule-calendar-footer"><span>{monthItems.length} chuyến trong tháng · {upcomingCount} sắp tới</span><span>{activeEmployees.length || (user.role === 'employee' ? 1 : 0)} nhân viên</span></div>
          <section className="schedule-legend" aria-label="Bảng chú thích màu trên lịch"><h3>Bảng chú thích màu trên lịch</h3><div className="schedule-legend-scroll"><table><thead><tr><th>Màu</th><th>Trạng thái</th><th>Mô tả</th></tr></thead><tbody>{STATUS_KEYS.map(key => <tr key={key}><td><span className="schedule-legend-swatch" style={{ backgroundColor: STATUS_CONFIG[key].color }}/></td><td>{STATUS_CONFIG[key].label}</td><td>{STATUS_CONFIG[key].description}</td></tr>)}</tbody></table></div></section>
        </>}
      </section>

      <aside className="panel schedule-side-panel">
        {!panel && <div className="schedule-panel-empty"><CalendarDays size={28}/><h3>Lịch trình công tác</h3><p>{reviewer ? 'Chọn một ngày để tạo lịch hoặc chọn chuyến đi để xem chi tiết.' : 'Chọn chuyến công tác trên lịch để xem thông tin chi tiết.'}</p></div>}
        {panel && <>
          <div className="schedule-side-head"><div><small>{panel === 'form' ? (editing ? 'CẬP NHẬT LỊCH' : 'PHÂN CÔNG CÔNG TÁC') : panel === 'day' ? 'LỊCH TRONG NGÀY' : 'CHI TIẾT CHUYẾN ĐI'}</small><h2>{panel === 'form' ? (editing ? 'Chỉnh sửa lịch' : 'Tạo lịch công tác') : panel === 'day' ? dateLabel(fromKey(selectedDate), { day: 'numeric', month: 'long' }) : 'Chi tiết chuyến đi'}</h2></div><button className="iconbtn" aria-label="Đóng bảng chi tiết" onClick={() => setPanel('')}><X size={20}/></button></div>
          {panel === 'form' && reviewer && <form className="schedule-form" onSubmit={save}>
            <p>{editing ? 'Cập nhật thông tin chuyến công tác đã phân công.' : 'Thêm chuyến công tác vào lịch của nhân viên.'}</p>
            <label>Tên chuyến công tác<input required maxLength="255" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Ví dụ: Gặp đối tác"/></label>
            <label>Ngày công tác<input required type="date" value={form.day} onChange={e => { const day = e.target.value; setForm({ ...form, day, starts: `${day}T${form.starts.slice(11, 16)}`, ends: `${day}T${form.ends.slice(11, 16)}` }); }}/></label>
            <div className="schedule-time-pair"><label>Giờ bắt đầu<input required type="time" value={form.starts.slice(11, 16)} onChange={e => setForm({ ...form, starts: `${form.day}T${e.target.value}` })}/></label><label>Giờ kết thúc<input required type="time" value={form.ends.slice(11, 16)} onChange={e => setForm({ ...form, ends: `${form.day}T${e.target.value}` })}/></label></div>
            <label>Địa điểm<input required maxLength="255" value={form.destination} onChange={e => setForm({ ...form, destination: e.target.value })} placeholder="Thành phố, địa chỉ"/></label>
            <label>Nhân viên được phân công<select required value={form.assigned_to} onChange={e => setForm({ ...form, assigned_to: e.target.value })} disabled={employeeBusy}><option value="">Chọn nhân viên</option>{activeEmployees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}</select></label>
            <label>Ghi chú<textarea rows="4" maxLength="5000" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder="Thông tin cần lưu ý (không bắt buộc)"/></label>
            {error && <p className="schedule-inline-error" role="alert">{error}</p>}
            <div className="schedule-form-actions"><button type="button" className="btn btn-outline" onClick={() => setPanel(editing ? 'detail' : '')}>Hủy</button><button className="btn btn-primary" disabled={saving || employeeBusy}>{saving ? 'Đang lưu…' : editing ? 'Lưu thay đổi' : 'Phân công'}</button></div>
          </form>}
          {panel === 'detail' && selected && <div className="schedule-detail">
            <span className="schedule-status-badge" style={{ backgroundColor: STATUS_CONFIG[statusKey(selected.status)].color }}>{STATUS_CONFIG[statusKey(selected.status)].label}</span><h3>{selected.title}</h3><p className="schedule-detail-destination">Chuyến công tác · {selected.destination}</p>
            <div className="schedule-detail-row"><CalendarDays/><span><small>Ngày và giờ</small><strong>{dateLabel(selected.starts_at)}</strong><small>{timeValue(selected.starts_at)} – {timeValue(selected.ends_at)} · GMT+7</small></span></div>
            <div className="schedule-detail-row"><MapPin/><span><small>Địa điểm</small><strong>{selected.destination}</strong></span></div>
            <div className="schedule-detail-row"><UserRound/><span><small>Nhân viên được phân công</small><strong>{selected.employee_name}</strong></span></div>
            <div className="schedule-detail-row"><Users/><span><small>Người phân công</small><strong>{selected.created_by_name || '—'}</strong><small>Thời gian phân công: {selected.created_at ? dateLabel(selected.created_at, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}</small></span></div>
            <div className="schedule-notes"><strong>Ghi chú</strong><p>{selected.notes || 'Không có ghi chú.'}</p></div>
            {!reviewer && <span className="schedule-view-only"><Eye size={15}/>Chỉ xem</span>}
            {reviewer && <div className="schedule-detail-actions"><button className="btn btn-outline" onClick={() => openEdit(selected)}><Pencil size={15}/>Chỉnh sửa</button>
              {selected.status !== 'completed' && selected.status !== 'cancelled' && <button className="btn btn-outline" onClick={() => changeStatus(selected, 'completed')}>Đánh dấu hoàn thành</button>}
              {selected.status !== 'cancelled' && selected.status !== 'completed' && <button className="btn btn-danger" onClick={() => changeStatus(selected, 'cancelled')}>Hủy lịch</button>}
              {selected.status !== 'completed' && selected.status !== 'cancelled' && <label className="schedule-status-change">Trạng thái<select value={statusKey(selected.status)} onChange={e => changeStatus(selected, e.target.value)}>{STATUS_KEYS.map(key => <option key={key} value={key}>{STATUS_CONFIG[key].label}</option>)}</select></label>}
            </div>}
            {error && <p className="schedule-inline-error" role="alert">{error}</p>}
          </div>}
          {panel === 'day' && <div className="schedule-day-list">{filteredItems.filter(item => dateKey(new Date(item.starts_at)) === selectedDate).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)).map(item => { const state = STATUS_CONFIG[statusKey(item.status)]; return <button key={item.id} className="schedule-day-list-item" onClick={() => { setSelectedId(item.id); setPanel('detail'); }}><span className="schedule-status-dot" style={{ backgroundColor: state.color }}>{state.symbol}</span><span><strong>{item.title}</strong><small>{timeValue(item.starts_at)} · {state.label} · {item.employee_name}</small></span><ChevronRight size={17}/></button>; })}{!filteredItems.some(item => dateKey(new Date(item.starts_at)) === selectedDate) && <p className="schedule-no-day">Chưa có chuyến công tác trong ngày này.</p>}{reviewer && <button className="btn btn-primary full" onClick={() => openCreate(selectedDate)}><Plus size={16}/>Tạo lịch trong ngày này</button>}</div>}
        </>}
      </aside>
    </div>

    <section className="schedule-stats">{[['Tổng chuyến trong tháng', monthItems.length, 'all'], ['Sắp tới', upcomingCount, 'planned'], ['Đã hoàn thành', completedCount, 'completed'], ['Đã hủy', cancelledCount, 'cancelled']].map(([label, count, color]) => <div className="panel schedule-stat" key={label}><small>{label}</small><strong className={`stat-${color}`}>{count}</strong></div>)}</section>
    {(error || message) && panel !== 'form' && <div className={error ? 'schedule-toast schedule-toast-error' : 'schedule-toast'} role={error ? 'alert' : 'status'}>{error || message}<button aria-label="Đóng thông báo" onClick={() => { setError(''); setMessage(''); }}>×</button></div>}
  </div>;
}
