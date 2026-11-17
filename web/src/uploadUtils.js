export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
export const UPLOAD_QUEUE_STAGES = [
  { id: 'upload', label: 'Tải lên' },
  { id: 'ocr', label: 'OCR' },
  { id: 'ai', label: 'Trích xuất AI' },
  { id: 'validation', label: 'Kiểm tra dữ liệu' },
  { id: 'done', label: 'Hoàn tất' },
];

const acceptedExtensions = new Set(['pdf', 'jpg', 'jpeg', 'png', 'xml']);

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
  if (stageId === 'ai') return 'unavailable';
  if (item.status === 'queued') return 'pending';
  if (item.status === 'uploading') {
    if (item.phase === 'transfer') return stageId === 'upload' ? 'active' : 'pending';
    if (stageId === 'upload') return 'complete';
    if (stageId === 'ocr') return 'active';
    if (stageId === 'validation') return 'pending';
    return 'pending';
  }
  if (item.status === 'done') {
    if (stageId === 'done') return 'complete';
    return ['upload', 'ocr', 'validation'].includes(stageId) ? 'complete' : 'pending';
  }
  if (item.status === 'failed') {
    if (item.failurePhase === 'validation') {
      if (stageId === 'upload' || stageId === 'ocr') return 'complete';
      if (stageId === 'validation') return 'failed';
    } else if (item.failurePhase === 'processing') {
      if (stageId === 'upload') return 'complete';
    } else if (item.failurePhase === 'ocr') {
      if (stageId === 'upload') return 'complete';
      if (stageId === 'ocr') return 'failed';
    } else if (item.failurePhase === 'transfer' && stageId === 'upload') return 'failed';
  }
  return 'pending';
}
