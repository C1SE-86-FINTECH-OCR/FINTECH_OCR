import test from 'node:test';
import assert from 'node:assert/strict';
import { tripOccursOnDate, vietnamDateTime } from '../src/scheduleDates.js';

test('multi-day trip is visible on every included date, including both endpoints', () => {
  const trip = { start_date: '2026-11-19', end_date: '2026-11-21' };
  for (const day of ['2026-11-19', '2026-11-20', '2026-11-21']) assert.equal(tripOccursOnDate(trip, day), true);
  assert.equal(tripOccursOnDate(trip, '2026-11-18'), false);
  assert.equal(tripOccursOnDate(trip, '2026-11-22'), false);
});

test('legacy trips fall back to their stored timestamps and one-day trips stay on one date', () => {
  const trip = { starts_at: '2026-11-19T02:00:00+00:00', ends_at: '2026-11-19T05:00:00+00:00' };
  assert.equal(tripOccursOnDate(trip, '2026-11-19'), true);
  assert.equal(tripOccursOnDate(trip, '2026-11-20'), false);
});

test('date and time values are sent to the existing API as GMT+7 instants', () => {
  assert.equal(vietnamDateTime('2026-11-19', '09:30'), '2026-11-19T09:30:00+07:00');
});
