import test from 'node:test';
import assert from 'node:assert/strict';
import { getQuickDateRange } from '../src/reportDateRanges.js';

test('previous month range handles dates 29, 30, and 31 without rolling forward', () => {
  for (const day of [29, 30, 31]) {
    const range = getQuickDateRange('prev', new Date(`2026-03-${day}T12:00:00+07:00`));
    assert.deepEqual(range, { from: '2026-02-01', to: '2026-02-28' });
  }
});

test('previous month range handles leap February and year rollover in Vietnam time', () => {
  assert.deepEqual(getQuickDateRange('prev', new Date('2024-03-31T23:30:00+07:00')), {
    from: '2024-02-01', to: '2024-02-29',
  });
  assert.deepEqual(getQuickDateRange('prev', new Date('2025-01-31T23:30:00+07:00')), {
    from: '2024-12-01', to: '2024-12-31',
  });
});

test('quick ranges use the Vietnam calendar date even when UTC is the previous day', () => {
  assert.deepEqual(getQuickDateRange('today', new Date('2026-10-31T18:00:00Z')), {
    from: '2026-11-01', to: '2026-11-01',
  });
});
