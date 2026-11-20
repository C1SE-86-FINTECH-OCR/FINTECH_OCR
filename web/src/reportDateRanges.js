const VIETNAM_ZONE = 'Asia/Ho_Chi_Minh';

function vietnamDateParts(now) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: VIETNAM_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now);
  return Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, Number(part.value)]));
}

function key(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export function getQuickDateRange(kind, now = new Date()) {
  const { year, month, day } = vietnamDateParts(now);
  if (kind === 'today') return { from: key(year, month, day), to: key(year, month, day) };
  if (kind === 'month') return { from: key(year, month, 1), to: key(year, month, day) };
  if (kind === 'prev') {
    const previousMonth = new Date(Date.UTC(year, month - 2, 1));
    const previousYear = previousMonth.getUTCFullYear();
    const previousMonthNumber = previousMonth.getUTCMonth() + 1;
    const lastDay = new Date(Date.UTC(year, month - 1, 0)).getUTCDate();
    return { from: key(previousYear, previousMonthNumber, 1), to: key(previousYear, previousMonthNumber, lastDay) };
  }
  if (kind === 'year') return { from: key(year, 1, 1), to: key(year, month, day) };
  throw new RangeError(`Unknown quick date range: ${kind}`);
}
