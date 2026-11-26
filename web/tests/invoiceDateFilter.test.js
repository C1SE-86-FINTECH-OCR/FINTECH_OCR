import test from 'node:test';
import assert from 'node:assert/strict';
import {invoiceDateRange,emptyProfileInvoiceRange,profileInvoiceQuery} from '../src/invoiceDateFilter.js';

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
test('Profile defaults to all personal invoices and supports clearing either date bound', () => {
  const all = '/profile/invoices?limit=20&offset=0';
  assert.equal(profileInvoiceQuery(emptyProfileInvoiceRange, 0, 20), all);
  assert.equal(profileInvoiceQuery({from: '2026-01-01', to: ''}, 1, 20),
    '/profile/invoices?limit=20&offset=20&invoice_date_from=2026-01-01');
  assert.equal(profileInvoiceQuery({from: '', to: '2026-02-01'}, 0, 20), all + '&invoice_date_to=2026-02-01');
  assert.equal(profileInvoiceQuery(emptyProfileInvoiceRange, 0, 20), all);
});
