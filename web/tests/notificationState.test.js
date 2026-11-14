import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatNotificationTimestamp,
  markAllNotificationsReadAfterSuccess,
  markNotificationReadAfterSuccess,
  openNotificationAfterAccessCheck,
  notificationTarget,
  notificationTypeLabel,
  setNotificationRead,
  unreadNotificationCount,
} from '../src/notificationState.js';

const sample = [
  { id: 10, is_read: false, invoice_id: 7, schedule_id: null },
  { id: 11, is_read: true, invoice_id: null, schedule_id: 4 },
  { id: 12, is_read: false, invoice_id: null, schedule_id: null },
];

test('notification event type labels and timestamps are readable in business timezone', () => {
  assert.equal(notificationTypeLabel('invoice_decision'), 'Approval decision');
  assert.equal(notificationTypeLabel(null), 'General');
  assert.match(formatNotificationTimestamp('2026-11-09T02:30:00.000Z'), /09\/11\/2026 09:30/);
  assert.equal(formatNotificationTimestamp('invalid'), '—');
});

test('unread count changes once and read updates are immutable/idempotent', () => {
  const once = setNotificationRead(sample, 10);
  const twice = setNotificationRead(once, 10);
  assert.equal(unreadNotificationCount(sample), 2);
  assert.equal(unreadNotificationCount(once), 1);
  assert.equal(unreadNotificationCount(twice), 1);
  assert.equal(sample[0].is_read, false);
});

test('mark-read commits only after the API request succeeds and skips already-read rows', async () => {
  let current = sample;
  let requests = 0;
  const setItems = updater => { current = updater(current); };
  await assert.rejects(markNotificationReadAfterSuccess(
    current, 10, async () => { requests += 1; throw new Error('HTTP 500'); }, setItems,
  ), /HTTP 500/);
  assert.equal(unreadNotificationCount(current), 2);
  assert.equal(requests, 1);

  await markNotificationReadAfterSuccess(current, 10, async () => { requests += 1; }, setItems);
  await markNotificationReadAfterSuccess(current, 10, async () => { requests += 1; }, setItems);
  assert.equal(unreadNotificationCount(current), 1);
  assert.equal(requests, 2);
});

test('mark-all commits all read state only after API success', async () => {
  let current = sample;
  const setItems = updater => { current = updater(current); };
  await assert.rejects(markAllNotificationsReadAfterSuccess(async () => { throw new Error('offline'); }, setItems));
  assert.equal(unreadNotificationCount(current), 2);
  await markAllNotificationsReadAfterSuccess(async () => ({ ok: true }), setItems);
  assert.equal(unreadNotificationCount(current), 0);
});

test('notification destination follows its linked invoice or schedule', () => {
  assert.deepEqual(notificationTarget(sample[0]), { kind: 'invoice', path: '/invoices/7' });
  assert.deepEqual(notificationTarget(sample[1]), { kind: 'schedule', path: '/schedule#schedule-4' });
  assert.equal(notificationTarget(sample[2]), null);
});

test('opening a notification verifies access before marking it read and navigating', async () => {
  const calls = [];
  const note = sample[0];
  await openNotificationAfterAccessCheck(
    note,
    async path => { calls.push(`get:${path}`); return { id: 7 }; },
    async id => { calls.push(`read:${id}`); },
    path => { calls.push(`navigate:${path}`); },
  );
  assert.deepEqual(calls, ['get:/invoices/7', 'read:10', 'navigate:/invoices/7']);

  calls.length = 0;
  await assert.rejects(openNotificationAfterAccessCheck(
    sample[1],
    async path => { calls.push(`get:${path}`); return []; },
    async id => { calls.push(`read:${id}`); },
    path => { calls.push(`navigate:${path}`); },
  ), /do not have access/);
  assert.deepEqual(calls, ['get:/schedules']);
});
