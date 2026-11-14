export function moneyOrDash(value) {
  if (value == null || (typeof value === 'string' && value.trim() === '')) return '—';
  const amount = typeof value === 'number' ? value : Number(String(value).trim());
  if (!Number.isFinite(amount)) return '—';
  return `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(amount)} đ`;
}

export function invoiceItemDrafts(items) {
  return (Array.isArray(items) ? items : []).map(item => ({
    description: item.description ?? '',
    unit: item.unit ?? '',
    quantity: item.quantity == null ? '' : String(item.quantity),
    unit_price: item.unit_price == null ? '' : String(item.unit_price),
    amount: item.amount == null ? '' : String(item.amount),
  }));
}

function nullableNumber(value) {
  if (value == null || String(value).trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function invoiceItemPayload(items) {
  return (Array.isArray(items) ? items : []).map(item => ({
    description: String(item.description ?? '').trim(),
    unit: String(item.unit ?? '').trim() || null,
    quantity: nullableNumber(item.quantity),
    unit_price: nullableNumber(item.unit_price),
    amount: nullableNumber(item.amount),
  }));
}

export function formatScheduleDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const dateText = new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(date);
  const timeText = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date);
  return `${dateText} ${timeText}`;
}

export function localDateTimeToIso(value) {
  if (!value) throw new Error('Cần nhập ngày và giờ.');
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error('Ngày giờ không hợp lệ.');
  return date.toISOString();
}
