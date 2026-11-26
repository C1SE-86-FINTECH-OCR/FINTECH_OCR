const HCMC_TIME_ZONE = 'Asia/Ho_Chi_Minh';

export function currentDashboardMonth(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: HCMC_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
  }).formatToParts(now);
  const year = parts.find(part => part.type === 'year')?.value;
  const month = parts.find(part => part.type === 'month')?.value;
  return year && month ? `${year}-${month}` : '';
}

function monthIndex(value) {
  const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value || '');
  return match ? Number(match[1]) * 12 + Number(match[2]) - 1 : null;
}

export function recentMonthlySeries(rows, currentMonth = currentDashboardMonth(), count = 12) {
  const current = monthIndex(currentMonth);
  if (current == null || !Number.isInteger(count) || count < 1) return [];

  const first = current - count + 1;
  const byMonth = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    const index = monthIndex(row?.month);
    if (index == null || index < first || index > current) continue;
    const existing = byMonth.get(row.month) || { amount: 0, vat_amount: 0, invoice_count: 0 };
    const amount = Number(row.amount ?? row.total_amount ?? 0);
    const vat = Number(row.vat_amount ?? 0);
    const invoices = Number(row.invoice_count ?? 0);
    byMonth.set(row.month, {
      amount: existing.amount + (Number.isFinite(amount) ? amount : 0),
      vat_amount: existing.vat_amount + (Number.isFinite(vat) ? vat : 0),
      invoice_count: existing.invoice_count + (Number.isFinite(invoices) ? invoices : 0),
    });
  }

  return Array.from({ length: count }, (_, offset) => {
    const index = first + offset;
    const year = Math.floor(index / 12);
    const month = String(index % 12 + 1).padStart(2, '0');
    const key = `${year}-${month}`;
    const values = byMonth.get(key) || { amount: 0, vat_amount: 0, invoice_count: 0 };
    return { month: key, ...values, hasData: values.invoice_count > 0 };
  });
}

function monthDate(value) {
  return monthIndex(value) == null ? null : new Date(`${value}-01T00:00:00.000Z`);
}

export function formatDashboardMonth(value) {
  const date = monthDate(value);
  return date ? new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'UTC', month: 'long', year: 'numeric',
  }).format(date) : '—';
}

export function formatDashboardMonthTick(value) {
  const date = monthDate(value);
  if (!date) return '';
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const y = String(date.getUTCFullYear()).slice(-2);
  return `T${m}/${y}`;
}

export function formatVnd(value) {
  if (value == null || (typeof value === 'string' && value.trim() === '')) return '—';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return '—';
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency', currency: 'VND', maximumFractionDigits: 0,
  }).format(amount);
}

export function formatCompactVnd(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return '—';
  return new Intl.NumberFormat('vi-VN', {
    notation: 'compact', maximumFractionDigits: 1,
  }).format(amount);
}
