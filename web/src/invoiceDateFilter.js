export function invoiceDateRange(period, value, quarter = '1') {
  if (!value || !['day', 'month', 'quarter', 'year'].includes(period)) return {};
  if (period === 'day') {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return {};
    return {invoice_date_from: value, invoice_date_to: value};
  }
  const year = Number(value.slice(0, 4));
  if (!Number.isInteger(year) || year < 1 || year > 9999) return {};
  let first = 1, last = 12;
  if (period === 'month') {
    if (!/^\d{4}-\d{2}$/.test(value)) return {};
    first = last = Number(value.slice(5));
  } else if (period === 'quarter') {
    if (!['1', '2', '3', '4'].includes(quarter)) return {};
    first = (Number(quarter) - 1) * 3 + 1;
    last = first + 2;
  }
  if (first < 1 || last > 12) return {};
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const prefix = String(year).padStart(4, '0');
  return {
    invoice_date_from: `${prefix}-${String(first).padStart(2, '0')}-01`,
    invoice_date_to: `${prefix}-${String(last).padStart(2, '0')}-${days[last - 1]}`,
  };
}
