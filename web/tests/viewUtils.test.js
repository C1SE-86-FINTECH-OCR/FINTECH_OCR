import test from 'node:test';
import assert from 'node:assert/strict';
import { formatScheduleDateTime, invoiceItemDrafts, invoiceItemPayload, localDateTimeToIso, moneyOrDash } from '../src/viewUtils.js';

test('invoice money rendering preserves null, blank and numeric zero distinctly', () => {
  assert.equal(moneyOrDash(null), '—');
  assert.equal(moneyOrDash(' '), '—');
  assert.equal(moneyOrDash(0), '0 đ');
  assert.equal(moneyOrDash(1000), '1.000 đ');
});

test('invoice item drafts and payload preserve null numeric fields and actual amount', () => {
  const apiItem = { description: 'Test service', unit: null, quantity: 1, unit_price: null, amount: 1000 };
  const draft = invoiceItemDrafts([apiItem]);
  assert.equal(draft[0].unit_price, '');
  const payload = invoiceItemPayload(draft);
  assert.deepEqual(payload[0], {
    description: 'Test service', unit: null, quantity: 1, unit_price: null, amount: 1000,
  });
  assert.equal(apiItem.amount, 1000);
});

test('invalid blank line description or amount remains detectable for validation', () => {
  const [row] = invoiceItemPayload([{ description: '  ', quantity: '', unit_price: '', amount: '' }]);
  assert.equal(row.description, '');
  assert.equal(row.quantity, null);
  assert.equal(row.unit_price, null);
  assert.equal(row.amount, null);
});

test('schedule time display includes date and hours; local datetime input serializes to ISO', () => {
  const previousTz = process.env.TZ;
  process.env.TZ = 'Asia/Ho_Chi_Minh';
  try {
    assert.match(formatScheduleDateTime('2026-11-14T03:00:00.000Z'), /14\/11\/2026.*10:00/);
    assert.equal(localDateTimeToIso('2026-11-14T10:00'), '2026-11-14T03:00:00.000Z');
  } finally {
    if (previousTz === undefined) delete process.env.TZ;
    else process.env.TZ = previousTz;
  }
});
