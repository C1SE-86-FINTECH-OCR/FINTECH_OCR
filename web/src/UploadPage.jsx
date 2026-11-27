import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, CheckCircle2, CircleHelp, CloudUpload, FileText, LoaderCircle,
  Minus, RefreshCw, RotateCcw, ScanText, ShieldCheck, Sparkles, XCircle,
} from 'lucide-react';
import { api, approvalName, authStore, datefmt, money, ROOT } from './api';
import { invoiceStatusCounts, invoicesForApprovalStatus, isInvoiceUploadResult, UPLOAD_QUEUE_STAGES, uploadExtractionFailed, uploadQueueStageState, validateInvoiceFile } from './uploadUtils';
import './UploadPage.css';
import { aiProcessingState, invoiceProcessingState } from './ocrRuntimeInfo';

const statusLabel = value => ({
  valid: 'Hợp lệ', needs_review: 'Cần kiểm tra', error: 'Lỗi',
  pending: 'Chờ xử lý', approved: 'Đã phê duyệt', rejected: 'Đã từ chối',
})[value] || value || '—';

const statusTone = value => ({
  valid: 'green', approved: 'green', done: 'green',
  needs_review: 'orange', pending: 'orange', uploading: 'blue',
  error: 'red', rejected: 'red', failed: 'red', draft: 'gray',
})[value] || 'gray';

function StatusBadge({ value, label }) {
  if (value === 'draft') return null;
  return <span className={`pill pill-${statusTone(value)}`}>{label || statusLabel(value)}</span>;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function localId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function rejectionReason(invoice) {
  if (invoice.rejection_reason) return invoice.rejection_reason;
  const history = Array.isArray(invoice.history) ? [...invoice.history].reverse() : [];
  return history.find(entry => entry.action === 'rejected' && entry.reason)?.reason || '';
}

function uploadInvoiceFile(file, { onProgress, onUploaded }) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append('file', file);
    let uploadFinished = false;
    const makeError = message => {
      const error = new Error(message);
      error.status = xhr.status;
      error.uploadFinished = uploadFinished;
      // Receiving 4xx rejection is different from losing a processing response.
      const rejected = [400, 401, 403, 404, 405, 413, 415, 422, 429].includes(xhr.status);
      error.failurePhase = rejected ? 'transfer' : (uploadFinished || xhr.status >= 200 ? 'processing' : 'transfer');
      error.retryable = xhr.status === 429;
      return error;
    };

    xhr.open('POST', `${ROOT}/invoices/upload`);
    const token = authStore.get();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.upload.addEventListener('progress', event => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    });
    xhr.upload.addEventListener('load', () => {
      uploadFinished = true;
      onUploaded();
    });
    xhr.addEventListener('load', () => {
      let payload;
      try { payload = xhr.responseText ? JSON.parse(xhr.responseText) : {}; }
      catch { payload = null; }
      if (xhr.status >= 200 && xhr.status < 300) {
        if (!isInvoiceUploadResult(payload)) {
          return reject(makeError('Phản hồi xử lý không hợp lệ. Kiểm tra danh sách hóa đơn trước khi tải lại.'));
        }
        return resolve(payload);
      }
      const detail = typeof payload?.detail === 'string' ? payload.detail : `HTTP ${xhr.status}`;
      reject(makeError(detail));
    });
    xhr.addEventListener('error', () => reject(makeError('Mất kết nối trong lúc tải lên. Hãy kiểm tra Danh sách hóa đơn trước khi thử lại.')));
    xhr.addEventListener('timeout', () => reject(makeError('Hết thời gian chờ phản hồi. Hãy kiểm tra Danh sách hóa đơn trước khi thử lại.')));
    xhr.addEventListener('abort', () => reject(makeError('Đã ngắt kết nối tải lên. Kiểm tra danh sách hóa đơn trước khi tải lại.')));
    xhr.send(form);
  });
}

const queueStageIcons = { upload: CloudUpload, ocr: ScanText, ai: Sparkles, validation: ShieldCheck, done: CheckCircle2 };

function UploadQueueStepper({ item }) {
  return <ol className="queue-stepper" aria-label="Các bước xử lý tệp">
    {UPLOAD_QUEUE_STAGES.map(stage => {
      const state = uploadQueueStageState(item, stage.id);
      const warning = state === 'review' || (stage.id === 'ai' && state === 'failed');
      const Icon = state === 'complete' ? CheckCircle2 : state === 'active' ? LoaderCircle
        : warning ? AlertTriangle : state === 'failed' ? XCircle : state === 'unavailable' ? Minus
          : state === 'unknown' ? CircleHelp : queueStageIcons[stage.id];
      const description = state === 'complete' ? (stage.id === 'done' ? 'Đã kết thúc' : 'Xong')
        : state === 'active' ? 'Đang tải lên' : state === 'review' ? 'Cần kiểm tra'
          : state === 'failed' ? (stage.id === 'ai' ? 'Không khả dụng' : 'Thất bại')
            : state === 'unavailable' ? 'Bỏ qua' : state === 'unknown' ? 'Chưa xác định' : 'Chờ kết quả';
      return <li key={stage.id} className={`queue-step state-${warning ? 'review' : state}`}
        aria-current={state === 'active' ? 'step' : undefined}
        title={stage.id === 'done' ? `${description} · Hoàn tất xử lý không có nghĩa là đã xác minh hóa đơn.` : `${stage.label}: ${description}`}>
        <span className="queue-step-icon"><Icon size={15} className={state === 'active' ? 'queue-spinner' : undefined} aria-hidden="true"/></span>
        <span className="queue-step-label">{stage.label}</span>
        <small>{description}</small>
      </li>;
    })}
  </ol>;
}

function UploadQueueItem({ item, onRetry, onReview }) {
  const active = item.status === 'uploading';
  const outcome = item.status === 'failed' ? { label: 'Xử lý thất bại', tone: 'red' }
    : active ? { label: 'Đang xử lý', tone: 'blue' }
      : item.status === 'done' ? invoiceProcessingState(item.invoice) : { label: 'Sẵn sàng tải lên', tone: 'gray' };
  const ai = aiProcessingState(item.invoice?.ocr);
  const Icon = outcome.tone === 'red' ? XCircle : outcome.tone === 'orange' ? AlertTriangle
    : outcome.tone === 'green' ? CheckCircle2 : FileText;
  const measuredProgress = active && item.phase === 'transfer' && Number.isFinite(item.progress);
  const fileIssue = validateInvoiceFile(item.file);
  const localResult = item.invoice?.id != null && !uploadExtractionFailed(item.invoice)
    && item.invoice?.validation_status !== 'error';
  const localMethod = item.invoice?.source_type === 'xml' || /\.xml$/i.test(item.file.name) ? 'kết quả XML tại máy' : 'OCR dự phòng';
  const deferred = item.invoice?.ocr?.llm?.status === 'deferred';
  const warning = fileIssue || (deferred && localResult ? 'AI tạm hoãn · Đã sử dụng kết quả tại máy' : '')
    || (ai?.fallback ? (item.invoice?.ocr?.llm?.status === 'failed' && localResult && localMethod === 'OCR dự phòng'
    ? 'AI tạm thời không khả dụng · Đã sử dụng OCR dự phòng'
    : `${ai.label}${localResult ? ` · Đã sử dụng ${localMethod}` : ''}`) : '')
    || (item.status === 'failed' ? 'Không thể hoàn tất xử lý. Mở Chi tiết để xem lỗi.' : '');
  return <li className={`upload-queue-item queue-tone-${outcome.tone}`}>
    <div className="queue-file-icon"><Icon size={21} aria-hidden="true"/></div>
    <div className="queue-file-main">
      <div className="queue-file-heading">
        <strong title={item.file.name}>{item.file.name}</strong>
        <small>{formatBytes(item.file.size)}</small>
      </div>
      <div className="queue-status-line" role="status">
        {active && <LoaderCircle size={13} className="queue-spinner" aria-hidden="true"/>}
        <span className={`pill pill-${outcome.tone}`}>{outcome.label}</span>
      </div>
    </div>
    <div className="queue-actions">
      {item.status === 'failed' && item.retryable && <button type="button" className="btn btn-small btn-muted" onClick={() => onRetry(item.id)}><RotateCcw size={14}/>Thử lại</button>}
      {item.invoice?.id && <button type="button" className="textbtn" onClick={() => onReview(item.invoice.id)}>Xem chi tiết<ArrowRight size={14}/></button>}
    </div>
    <UploadQueueStepper item={item}/>
    {measuredProgress && <div className="queue-progress-wrap">
      <div className="upload-progress-track" role="progressbar" aria-label={`Đã tải ${item.progress}% của ${item.file.name}`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={item.progress}><span style={{ width: `${item.progress}%` }}/></div>
      <small>{item.progress}% đã tải lên</small>
    </div>}
    {warning && <p className={`queue-warning ${outcome.tone === 'red' ? 'is-error' : ''}`} role={outcome.tone === 'red' ? 'alert' : 'status'}>{warning}</p>}
    {(item.error || item.invoice?.ocr || item.invoice?.warnings?.length > 0) && <details className="queue-diagnostics">
      <summary>Chi tiết</summary>
      {item.error && <p>{item.error}</p>}
      {item.status === 'failed' && !fileIssue && !item.retryable && <p>Kiểm tra danh sách hóa đơn trước khi tải lại để tránh tạo bản trùng.</p>}
      {item.invoice && <pre>{JSON.stringify({ ocr: item.invoice.ocr, warnings: item.invoice.warnings }, null, 2)}</pre>}
    </details>}
  </li>;
}

function MyInvoices({ invoices, busy, error, reload, onSubmit, submittingId, submitErrors, activeTab, setActiveTab, navigate }) {
  const counts = useMemo(() => invoiceStatusCounts(invoices), [invoices]);
  const rows = useMemo(() => invoicesForApprovalStatus(invoices, activeTab), [invoices, activeTab]);
  const tabs = [
    ['all', 'Tất cả'],['pending', 'Chờ xử lý'], ['approved', 'Đã phê duyệt'], ['rejected', 'Đã từ chối'],
  ];
  return <section className="panel upload-invoices-panel">
    <div className="upload-section-heading">
      <div><h2>Danh sách hóa đơn</h2><p>Xem thông tin đã trích xuất và theo dõi trạng thái phê duyệt.</p></div>
      <button type="button" className="iconbtn" onClick={reload} aria-label="Làm mới danh sách hóa đơn" disabled={busy}><RefreshCw size={16}/></button>
    </div>
    <div className="upload-filter-tabs" role="tablist" aria-label="Lọc hóa đơn theo trạng thái phê duyệt">
      {tabs.map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={activeTab === value} className={activeTab === value ? 'selected' : ''} onClick={() => setActiveTab(value)}>
        {label}<b>{busy ? '—' : counts[value]}</b>
      </button>)}
    </div>
    {busy ? <div className="upload-table-state"><RefreshCw size={17} className="spin"/> Đang tải danh sách hóa đơn…</div>
      : error ? <div className="upload-table-state error" role="alert">{error}<button className="btn btn-small btn-muted" type="button" onClick={reload}>Thử lại</button></div>
      : rows.length === 0 ? <div className="upload-empty"><FileText size={30}/><strong>{invoices.length ? 'Không có hóa đơn ở trạng thái này' : 'Chưa có hóa đơn'}</strong><span>{invoices.length ? 'Chọn tab khác để xem hóa đơn.' : 'Tải hóa đơn đầu tiên lên để bắt đầu.'}</span></div>
      : <div className="upload-invoice-scroll"><table className="upload-invoice-table"><thead><tr>
        <th>Số hóa đơn</th><th>Nhà cung cấp</th><th>Ngày</th><th>Số tiền</th><th>Loại</th><th>Kiểm tra dữ liệu</th><th>Phê duyệt</th><th>Thao tác</th>
      </tr></thead><tbody>{rows.map(invoice => {
        const canSubmit = ['draft', 'rejected'].includes(invoice.approval_status);
        const reason = rejectionReason(invoice);
        return <tr key={invoice.id}>
          <td><strong>{invoice.invoice_number || `#${invoice.id}`}</strong>{reason && invoice.approval_status === 'rejected' && <small className="rejection-reason" title={reason}>Lý do: {reason}</small>}</td>
          <td>{invoice.seller_name || <span className="muted-cell">Chưa trích xuất</span>}</td>
          <td>{datefmt(invoice.invoice_date)}</td>
          <td className="money">{invoice.total_amount == null ? '—' : money(invoice.total_amount)}</td>
          <td><span className="type-label">{{ einvoice: 'Hóa đơn điện tử', bill: 'Chứng từ', unknown: 'Chưa xác định' }[invoice.document_type] || '—'}</span></td>
          <td><StatusBadge value={invoice.validation_status} label={invoice.validation_status === 'valid' ? 'Đã kiểm tra dữ liệu' : statusLabel(invoice.validation_status)}/></td>
          <td><StatusBadge value={invoice.approval_status} label={approvalName(invoice.approval_status)}/></td>
          <td><div className="invoice-row-actions">
            <button type="button" className="btn btn-small btn-muted" onClick={() => navigate(`/invoices/${invoice.id}`)}>Chi tiết</button>
            {canSubmit && <button type="button" className="btn btn-small btn-primary" disabled={submittingId === invoice.id} onClick={() => onSubmit(invoice)}>{submittingId === invoice.id ? 'Đang gửi…' : invoice.approval_status === 'rejected' ? 'Gửi lại' : 'Gửi phê duyệt'}</button>}
          </div>{submitErrors[invoice.id] && <small className="queue-error" role="alert">{submitErrors[invoice.id]}</small>}</td>
        </tr>;
      })}</tbody></table></div>}
  </section>;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const dragDepth = useRef(0);
  const uploadLock = useRef(false);
  const invoiceRequest = useRef(0);
  const [queue, setQueue] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [invoiceData, setInvoiceData] = useState([]);
  const [invoicesBusy, setInvoicesBusy] = useState(true);
  const [invoicesError, setInvoicesError] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [submittingId, setSubmittingId] = useState(null);
  const [submitErrors, setSubmitErrors] = useState({});

  const reloadInvoices = useCallback(async () => {
    const request = ++invoiceRequest.current;
    setInvoicesBusy(true);
    setInvoicesError('');
    try {
      const rows = await api('/invoices');
      if (request !== invoiceRequest.current) return;
      if (!Array.isArray(rows) || rows.some(row => !row || typeof row !== 'object'
          || Array.isArray(row) || !Number.isInteger(row.id) || row.id <= 0)) {
        throw new Error('Phản hồi danh sách hóa đơn không hợp lệ.');
      }
      setInvoiceData(rows);
    } catch (error) {
      if (request !== invoiceRequest.current) return;
      setInvoicesError(error.message || 'Không tải được danh sách hóa đơn.');
    } finally {
      if (request === invoiceRequest.current) setInvoicesBusy(false);
    }
  }, []);

  useEffect(() => {
    void reloadInvoices();
    return () => { invoiceRequest.current += 1; };
  }, [reloadInvoices]);

  const addFiles = files => {
    const additions = Array.from(files || []).map(file => {
      const error = validateInvoiceFile(file);
      return { id: localId(), file, status: error ? 'failed' : 'queued', phase: error ? 'transfer' : null, error, retryable: false };
    });
    if (additions.length) setQueue(current => [...current, ...additions]);
  };

  const sendFile = async id => {
    const item = queue.find(entry => entry.id === id);
    if (!item || item.status === 'uploading' || validateInvoiceFile(item.file)) return;
    setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'uploading', phase: 'transfer', progress: null, error: '', retryable: false, invoice: null } : entry));
    try {
      const invoice = await uploadInvoiceFile(item.file, {
        onProgress: progress => setQueue(current => current.map(entry => entry.id === id ? { ...entry, progress } : entry)),
        onUploaded: () => setQueue(current => current.map(entry => entry.id === id ? { ...entry, phase: 'processing', progress: 100 } : entry)),
      });
      if (invoice.validation_status === 'error' || uploadExtractionFailed(invoice)) {
        const extractionFailed = uploadExtractionFailed(invoice);
        const storageFailed = invoice.ocr?.reason === 'storage_mapping_failed';
        setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'failed', phase: 'processing', failurePhase: extractionFailed ? 'ocr' : storageFailed ? 'processing' : 'validation', invoice, error: extractionFailed ? 'Đã nhận tệp nhưng trích xuất thất bại.' : storageFailed ? 'Chưa lưu được các trường trích xuất; tệp gốc và bằng chứng được giữ lại.' : 'Đã nhận tệp nhưng bước kiểm tra dữ liệu gặp lỗi.', retryable: false } : entry));
      } else {
        setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'done', phase: 'complete', invoice, progress: 100 } : entry));
      }
      await reloadInvoices();
    } catch (error) {
      const failurePhase = error.failurePhase || (error.uploadFinished ? 'processing' : 'transfer');
      setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'failed', phase: failurePhase, failurePhase, error: error.message || "Tải lên thất bại.", retryable: Boolean(error.retryable), progress: error.uploadFinished ? 100 : entry.progress } : entry));
      // A server-side commit may have succeeded even if its response was lost.
      if (failurePhase === 'processing') await reloadInvoices();
    }
  };

  const uploadSelected = async () => {
    if (uploadLock.current) return;
    const pending = queue.filter(item => item.status === 'queued').map(item => item.id);
    if (!pending.length) return;
    uploadLock.current = true;
    setUploading(true);
    try {
      for (const id of pending) await sendFile(id);
    } finally {
      uploadLock.current = false;
      setUploading(false);
    }
  };

  const retryFile = async id => {
    if (uploadLock.current) return;
    uploadLock.current = true;
    setUploading(true);
    try {
      await sendFile(id);
    } finally {
      uploadLock.current = false;
      setUploading(false);
    }
  };

  const submitInvoice = async invoice => {
    setSubmittingId(invoice.id);
    setSubmitErrors(current => ({ ...current, [invoice.id]: '' }));
    try {
      await api(`/invoices/${invoice.id}/submit`, { method: 'POST' });
      await reloadInvoices();
    } catch (error) {
      setSubmitErrors(current => ({ ...current, [invoice.id]: error.message || 'Không gửi được hóa đơn.' }));
    } finally {
      setSubmittingId(null);
    }
  };

  const activeCount = queue.filter(item => item.status === 'uploading').length;
  const readyCount = queue.filter(item => item.status === 'queued').length;
  const reviewCount = queue.filter(item => item.status === 'done' && invoiceProcessingState(item.invoice).tone === 'orange').length;
  return <div className="employee-upload-page">
    <header className="pagehead upload-pagehead">
      <div><small className="eyebrow">FINTECH OCR / KHÔNG GIAN LÀM VIỆC</small><h1>Tải hóa đơn lên</h1><p>Tải hóa đơn để tự động trích xuất thông tin.</p></div>
    </header>

    <div className="upload-top-grid">
      <section className="panel upload-card" aria-labelledby="upload-card-title">
        <div className="upload-section-heading"><div><h2 id="upload-card-title">Thêm hóa đơn</h2><p>Chọn một hoặc nhiều tệp từ thiết bị.</p></div></div>
        <button type="button" className={`upload-dropzone ${isDragging ? 'is-dragging' : ''}`}
          aria-label={isDragging ? 'Thả tệp để tải lên' : 'Nhấn vào đây hoặc kéo thả hóa đơn'} aria-describedby="upload-file-formats"
          onClick={() => fileInput.current?.click()}
          onDragEnter={event => {
            if (!Array.from(event.dataTransfer.types || []).includes('Files')) return;
            event.preventDefault();
            dragDepth.current += 1;
            setIsDragging(true);
          }}
          onDragOver={event => {
            if (!Array.from(event.dataTransfer.types || []).includes('Files')) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
          }}
          onDragLeave={() => {
            dragDepth.current = Math.max(0, dragDepth.current - 1);
            if (dragDepth.current === 0) setIsDragging(false);
          }}
          onDrop={event => {
            event.preventDefault();
            dragDepth.current = 0;
            setIsDragging(false);
            addFiles(event.dataTransfer.files);
          }}>
          <span className="upload-icon-box"><CloudUpload size={68} strokeWidth={1.5} aria-hidden="true"/></span>
          <strong aria-live="polite" aria-atomic="true">{isDragging ? 'Thả tệp để tải lên' : 'Nhấn vào đây hoặc kéo thả hóa đơn'}</strong>
          <span id="upload-file-formats">PDF, JPG, PNG, XML · Tối đa 20 MB/tệp</span>
        </button>
        <input ref={fileInput} type="file" accept=".pdf,.jpg,.jpeg,.png,.xml" multiple tabIndex={-1} className="visually-hidden-file" aria-label="Chọn hóa đơn" onChange={event => { addFiles(event.target.files); event.target.value = ''; }}/>
        {queue.some(item => item.status === 'queued') && <div className="upload-submit-row"><span>{readyCount} tệp đã chọn</span><button type="button" className="btn btn-primary" disabled={uploading} onClick={uploadSelected}>{uploading ? 'Đang tải lên…' : 'Tải hóa đơn lên'}<ArrowRight size={16}/></button></div>}
      </section>

      <section className="panel processing-card" aria-labelledby="processing-title">
        <div className="upload-section-heading"><h2 id="processing-title">Hàng đợi xử lý</h2></div>
        <dl className="queue-stats" aria-label="Thống kê hàng đợi" aria-live="polite" aria-atomic="true">
          <div><dt>Tổng tệp</dt><dd>{queue.length}</dd></div>
          <div className={activeCount ? 'has-active' : ''}><dt>Đang xử lý</dt><dd>{activeCount}</dd></div>
          <div className={reviewCount ? 'has-review' : ''}><dt>Cần kiểm tra</dt><dd>{reviewCount}</dd></div>
        </dl>
        {queue.length === 0 ? <div className="queue-empty"><FileText size={18} aria-hidden="true"/><span>Hàng đợi chưa có tệp</span></div>
          : <ul className={`upload-queue-list${queue.length > 1 ? ' has-multiple' : ''}`} tabIndex={queue.length > 1 ? 0 : undefined} aria-label="Danh sách tệp đang tải và đã xử lý">{queue.map(item => <UploadQueueItem key={item.id} item={item} onRetry={retryFile} onReview={id => navigate(`/invoices/${id}`)}/>)}</ul>}
      </section>
    </div>

    <MyInvoices invoices={invoiceData} busy={invoicesBusy} error={invoicesError} reload={reloadInvoices} onSubmit={submitInvoice} submittingId={submittingId} submitErrors={submitErrors} activeTab={activeTab} setActiveTab={setActiveTab} navigate={navigate}/>
  </div>;
}
