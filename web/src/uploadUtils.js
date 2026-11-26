export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
export const UPLOAD_QUEUE_STAGES = [
  { id: 'upload', label: 'Tải lên' },
  { id: 'ocr', label: 'OCR' },
  { id: 'ai', label: 'Trích xuất AI' },
  { id: 'validation', label: 'Kiểm tra dữ liệu' },
  { id: 'done', label: 'Hoàn tất' },
];

const acceptedExtensions = new Set(['pdf', 'jpg', 'jpeg', 'png', 'xml']);

export function isInvoiceUploadResult(value) {
  const record = entry => entry != null && typeof entry === 'object' && !Array.isArray(entry);
  const records = entries => entries == null || (Array.isArray(entries) && entries.every(record));
  return record(value)
    && Number.isInteger(value.id) && value.id > 0
    && ['valid', 'needs_review', 'error'].includes(value.validation_status)
    && records(value.warnings)
    && (value.ocr == null || (record(value.ocr) && records(value.ocr.findings)
      && (value.ocr.llm == null || record(value.ocr.llm))));
}

export function uploadExtractionFailed(invoice) {
  return invoice?.ocr?.reason === 'extraction_failed' || invoice?.ocr?.used_pipeline === 'none'
    || invoice?.ocr?.findings?.some(finding => finding.code === 'EXTRACTION_FAILED');
}

export function validateInvoiceFile(file) {
  if (!file) return 'Chọn tệp hóa đơn trước khi tải lên.';
  const extension = String(file.name || '').split('.').pop().toLowerCase();
  if (!acceptedExtensions.has(extension)) return 'Chỉ chấp nhận PDF, JPG, JPEG, PNG hoặc XML.';
  if (!file.size) return 'Tệp rỗng, vui lòng chọn tệp khác.';
  if (file.size > MAX_UPLOAD_BYTES) return 'Mỗi tệp không được vượt quá 20 MB.';
  return '';
}

export function invoicesForApprovalStatus(invoices, status) {
  if (!Array.isArray(invoices)) return [];
  return status === 'all' ? invoices : invoices.filter(invoice => invoice.approval_status === status);
}

export function invoiceStatusCounts(invoices) {
  const rows = Array.isArray(invoices) ? invoices : [];
  return rows.reduce((counts, invoice) => {
    counts.all += 1;
    if (Object.hasOwn(counts, invoice.approval_status)) counts[invoice.approval_status] += 1;
    return counts;
  }, { all: 0, draft: 0, pending: 0, approved: 0, rejected: 0 });
}

export function uploadQueueStageState(item, stageId) {
  const invoice = item.invoice;
  const finished = ['done', 'failed'].includes(item.status);
  const hasResult = invoice?.id != null;
  const extractionFailed = uploadExtractionFailed(invoice);
  const storageFailed = invoice?.ocr?.reason === 'storage_mapping_failed';
  const isXml = invoice?.source_type === 'xml' || /\.xml$/i.test(item.file?.name || '');
  if (stageId === 'ai') {
    const llm = invoice?.ocr?.llm;
    if (llm?.status === 'grounded_proposal') {
      if (llm.merge_status === 'accepted') return 'complete';
      if (llm.merge_status === 'no_supported_proposal') return 'review';
      return 'unknown'; // Older results do not prove merge acceptance.
    }
    if (llm?.status === 'failed') return 'failed';
    if (['unconfigured', 'local_only', 'deferred', 'input_unavailable'].includes(llm?.status)
        || (item.status === 'failed' && (item.failurePhase || item.phase) === 'transfer')) return 'unavailable';
    if (finished || llm) return 'unknown';
    return 'pending'; // The synchronous API has no live AI-stage events.
  }
  if (item.status === 'queued') return 'pending';
  if (item.status === 'uploading') {
    if (item.phase === 'transfer') return stageId === 'upload' ? 'active' : 'pending';
    if (stageId === 'upload') return 'complete';
    // Upload completion proves transfer only, not the current server stage.
    // Keep server stages pending until the synchronous response supplies evidence.
    return 'pending';
  }
  if (hasResult && finished) {
    if (stageId === 'upload') return 'complete';
    if (stageId === 'ocr') {
      if (isXml) return 'unavailable';
      if (extractionFailed) return 'failed';
      if (invoice.ocr?.findings?.some(finding => finding.code === 'OCR_TEXT_UNAVAILABLE')
          || invoice.ocr?.truncated || invoice.warnings?.some(warning => warning.rule === 'EXTRACTION-COVERAGE')) return 'review';
      return invoice.ocr?.used_pipeline && (invoice.validation_status !== 'error' || storageFailed) ? 'complete' : 'unknown';
    }
    if (stageId === 'validation') {
      if (extractionFailed || storageFailed) return 'unavailable';
      if (invoice.validation_status === 'valid') return 'complete';
      if (invoice.validation_status === 'needs_review') return 'review';
      if (invoice.validation_status === 'error') return 'failed';
      return 'unknown';
    }
    // Finished describes the end of processing, never document verification.
    if (stageId === 'done') return extractionFailed || invoice.validation_status === 'error' ? 'failed' : 'complete';
  }
  if (item.status === 'failed') {
    const failurePhase = item.failurePhase || item.phase;
    if (stageId === 'done') return 'failed';
    if (failurePhase === 'processing') {
      if (stageId === 'upload') return 'complete';
      return 'unknown'; // A lost response cannot locate the failed server stage.
    } else if (failurePhase === 'ocr') {
      if (stageId === 'upload') return 'complete';
      if (stageId === 'ocr') return 'failed';
    } else if (failurePhase === 'transfer') return stageId === 'upload' ? 'failed' : 'unavailable';
  }
  return 'pending';
}
