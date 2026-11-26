import test from 'node:test';
import assert from 'node:assert/strict';
import {reportQueries} from '../src/reportQueries.js';

test('summary, preview and export share applied search, status and dates', () => {
  const filters = {
    search: 'Đặng & 0101',
    approval_status: 'approved',
    invoice_date_from: '2026-01-01',
    invoice_date_to: '2026-01-31',
    seller_name: '',
  };
  const paths = reportQueries(filters, {page: 2, pageSize: 10, sortBy: 'total', sortOrder: 'asc'});
  const params = Object.fromEntries(Object.entries(paths).map(([key, path]) => [
    key, Object.fromEntries(new URL(path, 'http://example.test').searchParams),
  ]));
  const {seller_name, ...applied} = filters;
  assert.deepEqual(params.summary, applied);
  assert.deepEqual(params.export, {...applied, sort_by: 'total', sort_order: 'asc'});
  assert.deepEqual(params.preview, {...params.export, limit: '10', offset: '20'});

  const cleared = reportQueries({...filters, search: ''}, {page: 0, pageSize: 10, sortBy: 'total', sortOrder: 'asc'});
  const clearedPreview = new URL(cleared.preview, 'http://example.test').searchParams;
  assert.equal(clearedPreview.has('search'), false);
  assert.equal(clearedPreview.get('approval_status'), 'approved');
  assert.equal(clearedPreview.get('offset'), '0');
});
