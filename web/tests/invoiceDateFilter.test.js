import test from 'node:test';
import assert from 'node:assert/strict';
import {invoiceDateRange} from '../src/invoiceDateFilter.js';

test('invoice date bounds include the entire selected period', () => {
  assert.deepEqual(invoiceDateRange('day','2026-11-25'), {invoice_date_from:'2026-11-25', invoice_date_to:'2026-11-25'});
  assert.equal(invoiceDateRange('month','2024-02').invoice_date_to,'2024-02-29');
  assert.equal(invoiceDateRange('month','2026-02').invoice_date_to,'2026-02-28');
  assert.deepEqual(invoiceDateRange('quarter','2026','4'), {invoice_date_from:'2026-10-01', invoice_date_to:'2026-12-31'});
  assert.deepEqual(invoiceDateRange('year','2026'), {invoice_date_from:'2026-01-01', invoice_date_to:'2026-12-31'});
  assert.deepEqual(invoiceDateRange('','2026'), {});
  assert.deepEqual(invoiceDateRange('month','2026-13'), {});
  assert.deepEqual(invoiceDateRange('quarter','','1'), {});
});
