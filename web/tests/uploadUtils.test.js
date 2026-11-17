import test from 'node:test';
import assert from 'node:assert/strict';
import { MAX_UPLOAD_BYTES, UPLOAD_QUEUE_STAGES, invoiceStatusCounts, invoicesForApprovalStatus, uploadQueueStageState, validateInvoiceFile } from '../src/uploadUtils.js';

test('accepts supported invoice extensions case-insensitively within 20 MB', () => {
  for (const name of ['receipt.PDF', 'receipt.jpg', 'receipt.JPEG', 'receipt.png', 'receipt.xml']) {
    assert.equal(validateInvoiceFile({ name, size: 1024 }), '');
  }
  assert.equal(MAX_UPLOAD_BYTES, 20 * 1024 * 1024);
});

test('rejects unsupported, empty, and oversized files before API upload', () => {
  assert.match(validateInvoiceFile({ name: 'invoice.exe', size: 20 }), /Chỉ chấp nhận/);
  assert.match(validateInvoiceFile({ name: 'invoice.pdf', size: 0 }), /Tệp rỗng/);
  assert.match(validateInvoiceFile({ name: 'invoice.pdf', size: MAX_UPLOAD_BYTES + 1 }), /20 MB/);
  assert.match(validateInvoiceFile(null), /Chọn tệp/);
});

test('filters invoices by approval status and computes tab counts from API rows', () => {
  const invoices = [
    { id: 1, approval_status: 'draft' },
    { id: 2, approval_status: 'pending' },
    { id: 3, approval_status: 'approved' },
    { id: 4, approval_status: 'rejected' },
    { id: 5, approval_status: 'rejected' },
  ];
  assert.deepEqual(invoicesForApprovalStatus(invoices, 'all'), invoices);
  assert.deepEqual(invoicesForApprovalStatus(invoices, 'rejected').map(row => row.id), [4, 5]);
  assert.deepEqual(invoiceStatusCounts(invoices), { all: 5, draft: 1, pending: 1, approved: 1, rejected: 2 });
});

test('maps queue stages to ready, measured upload, and server processing states', () => {
  assert.deepEqual(UPLOAD_QUEUE_STAGES.map(({ id }) => id), ['upload', 'ocr', 'ai', 'validation', 'done']);
  const queued = { status: 'queued' };
  assert.equal(uploadQueueStageState(queued, 'upload'), 'pending');
  assert.equal(uploadQueueStageState(queued, 'ai'), 'unavailable');

  const transferring = { status: 'uploading', phase: 'transfer' };
  assert.equal(uploadQueueStageState(transferring, 'upload'), 'active');
  assert.equal(uploadQueueStageState(transferring, 'ocr'), 'pending');

  const processing = { status: 'uploading', phase: 'processing' };
  assert.equal(uploadQueueStageState(processing, 'upload'), 'complete');
  assert.equal(uploadQueueStageState(processing, 'ocr'), 'active');
  assert.equal(uploadQueueStageState(processing, 'validation'), 'pending');
});

test('marks returned completion and validation failures without claiming AI progress', () => {
  const done = { status: 'done' };
  assert.equal(uploadQueueStageState(done, 'upload'), 'complete');
  assert.equal(uploadQueueStageState(done, 'ocr'), 'complete');
  assert.equal(uploadQueueStageState(done, 'validation'), 'complete');
  assert.equal(uploadQueueStageState(done, 'done'), 'complete');
  assert.equal(uploadQueueStageState(done, 'ai'), 'unavailable');

  const validationFailed = { status: 'failed', failurePhase: 'validation' };
  assert.equal(uploadQueueStageState(validationFailed, 'upload'), 'complete');
  assert.equal(uploadQueueStageState(validationFailed, 'ocr'), 'complete');
  assert.equal(uploadQueueStageState(validationFailed, 'validation'), 'failed');

  const transferFailed = { status: 'failed', failurePhase: 'transfer' };
  assert.equal(uploadQueueStageState(transferFailed, 'upload'), 'failed');
});
