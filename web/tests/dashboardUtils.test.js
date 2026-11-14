import test from 'node:test';
import assert from 'node:assert/strict';
import {
  currentDashboardMonth,
  formatCompactVnd,
  formatDashboardMonth,
  formatDashboardMonthTick,
  formatVnd,
  recentMonthlySeries,
} from '../src/dashboardUtils.js';

test('monthly series keeps the latest 12 months in chronological order and excludes old invoices', () => {
  const series = recentMonthlySeries([
    { month: '2017-10', amount: 900, invoice_count: 1 },
    { month: '2025-12', total_amount: 100, vat_amount: 8, invoice_count: 1 },
    { month: '2026-03', amount: 50, invoice_count: 1 },
    { month: '2026-11', amount: 300, invoice_count: 2 },
    { month: '2026-12', amount: 500, invoice_count: 1 },
  ], '2026-11');

  assert.equal(series.length, 12);
  assert.equal(series[0].month, '2025-12');
  assert.equal(series.at(-1).month, '2026-11');
  assert.deepEqual(series.filter(row => row.hasData).map(row => row.month), [
    '2025-12', '2026-03', '2026-11',
  ]);
  assert.equal(series.at(-1).amount, 300);
  assert.equal(series.at(-1).invoice_count, 2);
});

test('months with no invoices are explicit zero buckets rather than inferred spending', () => {
  const series = recentMonthlySeries([
    { month: '2026-01', amount: 120, invoice_count: 1 },
  ], '2026-02', 2);

  assert.deepEqual(series, [
    { month: '2026-01', amount: 120, vat_amount: 0, invoice_count: 1, hasData: true },
    { month: '2026-02', amount: 0, vat_amount: 0, invoice_count: 0, hasData: false },
  ]);
});

test('dashboard month boundaries use Asia/Ho_Chi_Minh', () => {
  assert.equal(currentDashboardMonth(new Date('2026-10-31T17:30:00.000Z')), '2026-11');
});

test('VND formatting handles null, zero, chart ticks and Vietnamese month labels', () => {
  assert.equal(formatVnd(null), '—');
  assert.match(formatVnd(200000), /200\.000/);
  assert.match(formatVnd(200000), /₫/);
  assert.match(formatVnd(0), /0/);
  assert.equal(formatCompactVnd(0), '0');
  assert.match(formatDashboardMonth('2026-11').toLowerCase(), /tháng 11/);
  assert.match(formatDashboardMonthTick('2026-11'), /11/);
});
