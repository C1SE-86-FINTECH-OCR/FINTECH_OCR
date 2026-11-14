import test from 'node:test';
import assert from 'node:assert/strict';
import { formatLookupTimestamp, initialLookupOutcome, isSafeHttpUrl } from '../src/lookupUtils.js';

test('manual tax lookup has no preselected outcome', () => {
  assert.equal(initialLookupOutcome, '');
});

test('QR link accepts only absolute HTTP and HTTPS URLs', () => {
  assert.equal(isSafeHttpUrl('https://tax.example.vn/invoice?id=1'), true);
  assert.equal(isSafeHttpUrl('http://tax.example.vn/invoice?id=1'), true);
  assert.equal(isSafeHttpUrl('javascript:alert(1)'), false);
  assert.equal(isSafeHttpUrl('ftp://tax.example.vn/invoice'), false);
  assert.equal(isSafeHttpUrl('https://user:pass@tax.example.vn/invoice'), false);
  assert.equal(isSafeHttpUrl('//tax.example.vn/invoice'), false);
  assert.equal(isSafeHttpUrl('https:///missing-host'), false);
  assert.equal(isSafeHttpUrl(null), false);
});

test('lookup history timestamp is rendered in the project business timezone', () => {
  const formatted = formatLookupTimestamp('2026-11-09T02:30:00.000Z');
  assert.match(formatted, /09\/11\/2026/);
  assert.match(formatted, /09:30/);
  assert.equal(formatLookupTimestamp('invalid'), '—');
});
