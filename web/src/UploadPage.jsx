import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight, Camera, CheckCircle2, CloudUpload, FileText, RefreshCw,
  RotateCcw, Upload, XCircle,
} from 'lucide-react';
import { api, approvalName, authStore, datefmt, money, ROOT } from './api';
import { invoiceStatusCounts, invoicesForApprovalStatus, UPLOAD_QUEUE_STAGES, uploadQueueStageState, validateInvoiceFile } from './uploadUtils';
import './UploadPage.css';

const statusLabel = value => ({
  valid: 'Valid', needs_review: 'Needs review', error: 'Error',
  draft: 'Draft', pending: 'Pending', approved: 'Approved', rejected: 'Rejected',
})[value] || value || '—';

const statusTone = value => ({
  valid: 'green', approved: 'green', done: 'green',
  needs_review: 'orange', pending: 'orange', uploading: 'blue',
  error: 'red', rejected: 'red', failed: 'red', draft: 'gray',
})[value] || 'gray';

function StatusBadge({ value, label }) {
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
      catch { payload = {}; }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(payload);
      const detail = typeof payload.detail === 'string' ? payload.detail : `HTTP ${xhr.status}`;
      reject(makeError(detail));
    });
    xhr.addEventListener('error', () => reject(makeError('Mất kết nối trong lúc tải lên. Hãy kiểm tra My invoices trước khi thử lại.')));
    xhr.addEventListener('timeout', () => reject(makeError('Hết thời gian chờ phản hồi. Hãy kiểm tra My invoices trước khi thử lại.')));
    xhr.send(form);
  });
}

function UploadQueueItem({ item, onRetry, onReview }) {
  const active = item.status === 'uploading';
  const completed = item.status === 'done';
  const stages = UPLOAD_QUEUE_STAGES.map(stage => ({
    ...stage,
    state: uploadQueueStageState(item, stage.id),
  }));
  const measuredProgress = active && item.phase === 'transfer' && Number.isFinite(item.progress);
  return <li className={`upload-queue-item queue-${item.status}`}>
    <div className="queue-file-icon">{completed ? <CheckCircle2 size={19}/> : item.status === 'failed' ? <XCircle size={19}/> : <FileText size={19}/>}</div>
    <div className="queue-file-main">
      <div className="queue-file-heading">
        <strong title={item.file.name}>{item.file.name}</strong>
        <small>{formatBytes(item.file.size)}</small>
      </div>
      <div className="queue-status-line">
        <StatusBadge value={item.status} label={item.status === 'done' ? 'Done' : item.status === 'failed' ? 'Failed' : item.status === 'uploading' ? item.phase === 'transfer' ? 'Uploading' : 'Processing' : 'Ready'}/>
        {item.invoice?.id && <span>Invoice #{item.invoice.id}</span>}
      </div>
      {active && <div className="queue-progress-wrap">
        {measuredProgress
          ? <div className="upload-progress-track" role="progressbar" aria-label={`Đã tải ${item.progress}% của ${item.file.name}`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={item.progress}><span style={{ width: `${item.progress}%` }}/></div>
          : <div className="upload-progress-track is-indeterminate" role="progressbar" aria-label={`Đang xử lý ${item.file.name}`}><span/></div>}
        {measuredProgress && <small>{item.progress}% uploaded</small>}
        {item.phase === 'processing' && <p className="queue-hint">Tệp đã gửi xong; Backend đang xử lý đồng bộ. API không báo tiến độ riêng cho OCR/Validation.</p>}
      </div>}
      {item.error && <p className="queue-error" role="alert">{item.error}</p>}
      {item.status === 'failed' && !item.retryable && <p className="queue-hint">Check My invoices before retrying. The server may already have received this file.</p>}
      {completed && <p className="queue-result">API đã lưu invoice #{item.invoice?.id}; validation: <strong>{statusLabel(item.invoice?.validation_status)}</strong>.</p>}
      {item.status === 'failed' && item.invoice?.id && <p className="queue-result">Invoice #{item.invoice.id} was saved, but the API returned a validation error. Review the invoice; this file will not be retried to avoid duplicates.</p>}
      <ol className="queue-stepper" aria-label={`Processing stages for ${item.file.name}`}>
        {stages.map((stage, index) => <li key={stage.id} className={`queue-step step-${stage.state}`} aria-current={stage.state === 'active' ? 'step' : undefined}>
          <span className="queue-step-marker">{stage.state === 'complete' ? <CheckCircle2 size={13}/> : stage.state === 'failed' ? <XCircle size={13}/> : index + 1}</span>
          <span className="queue-step-label">{stage.label}</span>
          {stage.state === 'unavailable' && <small>Not reported</small>}
        </li>)}
      </ol>
      {item.status !== 'done' && <p className="queue-ai-note">AI Extraction status is not provided by the current API.</p>}
    </div>
    <div className="queue-actions">
      {item.status === 'failed' && item.retryable && <button type="button" className="btn btn-small btn-muted" onClick={() => onRetry(item.id)}><RotateCcw size={14}/> Retry</button>}
      {completed && item.invoice?.id && <button type="button" className="textbtn" onClick={() => onReview(item.invoice.id)}>Review <ArrowRight size={14}/></button>}
    </div>
  </li>;
}

function MyInvoices({ invoices, busy, error, reload, onSubmit, submittingId, submitErrors, activeTab, setActiveTab, navigate }) {
  const counts = useMemo(() => invoiceStatusCounts(invoices), [invoices]);
  const rows = useMemo(() => invoicesForApprovalStatus(invoices, activeTab), [invoices, activeTab]);
  const tabs = [
    ['all', 'All'], ['draft', 'Draft'], ['pending', 'Pending'], ['approved', 'Approved'], ['rejected', 'Rejected'],
  ];
  return <section className="panel upload-invoices-panel">
    <div className="upload-section-heading">
      <div><h2>My invoices</h2><p>Review extracted details and follow approval status.</p></div>
      <button type="button" className="iconbtn" onClick={reload} aria-label="Refresh invoices" disabled={busy}><RefreshCw size={16}/></button>
    </div>
    <div className="upload-filter-tabs" role="tablist" aria-label="Filter invoices by approval status">
      {tabs.map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={activeTab === value} className={activeTab === value ? 'selected' : ''} onClick={() => setActiveTab(value)}>
        {label}<b>{busy ? '—' : counts[value]}</b>
      </button>)}
    </div>
    {busy ? <div className="upload-table-state"><RefreshCw size={17} className="spin"/> Loading invoices…</div>
      : error ? <div className="upload-table-state error" role="alert">{error}<button className="btn btn-small btn-muted" type="button" onClick={reload}>Try again</button></div>
      : rows.length === 0 ? <div className="upload-empty"><FileText size={30}/><strong>{invoices.length ? 'No invoices in this status' : 'No invoices yet'}</strong><span>{invoices.length ? 'Chọn tab khác để xem hóa đơn.' : 'Tải hóa đơn đầu tiên lên để bắt đầu.'}</span></div>
      : <div className="upload-invoice-scroll"><table className="upload-invoice-table"><thead><tr>
        <th>Invoice no.</th><th>Supplier</th><th>Date</th><th>Amount</th><th>Type</th><th>AI check</th><th>Approval</th><th>Action</th>
      </tr></thead><tbody>{rows.map(invoice => {
        const canSubmit = ['draft', 'rejected'].includes(invoice.approval_status);
        const reason = rejectionReason(invoice);
        return <tr key={invoice.id}>
          <td><strong>{invoice.invoice_number || `#${invoice.id}`}</strong>{reason && invoice.approval_status === 'rejected' && <small className="rejection-reason" title={reason}>Reason: {reason}</small>}</td>
          <td>{invoice.seller_name || <span className="muted-cell">Not extracted</span>}</td>
          <td>{datefmt(invoice.invoice_date)}</td>
          <td className="money">{invoice.total_amount == null ? '—' : money(invoice.total_amount)}</td>
          <td><span className="type-label">{{ einvoice: 'eInvoice', bill: 'Bill', unknown: 'Unknown' }[invoice.document_type] || '—'}</span></td>
          <td title="Đây là validation_status do Backend trả về; API hiện không có trạng thái AI riêng."><StatusBadge value={invoice.validation_status}/></td>
          <td><StatusBadge value={invoice.approval_status} label={approvalName(invoice.approval_status)}/></td>
          <td><div className="invoice-row-actions">
            <button type="button" className="btn btn-small btn-muted" onClick={() => navigate(`/invoices/${invoice.id}`)}>Details</button>
            {canSubmit && <button type="button" className="btn btn-small btn-primary" disabled={submittingId === invoice.id} onClick={() => onSubmit(invoice)}>{submittingId === invoice.id ? 'Sending…' : invoice.approval_status === 'rejected' ? 'Resubmit' : 'Submit'}</button>}
          </div>{submitErrors[invoice.id] && <small className="queue-error" role="alert">{submitErrors[invoice.id]}</small>}</td>
        </tr>;
      })}</tbody></table></div>}
  </section>;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const cameraInput = useRef(null);
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
    setInvoicesBusy(true);
    setInvoicesError('');
    try {
      const rows = await api('/invoices');
      setInvoiceData(Array.isArray(rows) ? rows : []);
    } catch (error) {
      setInvoicesError(error.message || 'Không tải được danh sách hóa đơn.');
    } finally {
      setInvoicesBusy(false);
    }
  }, []);

  useEffect(() => { void reloadInvoices(); }, [reloadInvoices]);

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
      if (invoice.validation_status === 'error') {
        setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'failed', phase: 'processing', failurePhase: 'validation', invoice, error: 'The API accepted the upload but returned validation_status=error.', retryable: false } : entry));
      } else {
        setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'done', phase: 'complete', invoice, progress: 100 } : entry));
      }
      await reloadInvoices();
    } catch (error) {
      setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'failed', phase: error.uploadFinished ? 'processing' : 'transfer', failurePhase: error.uploadFinished ? 'processing' : 'transfer', error: error.message || 'Upload failed.', retryable: Boolean(error.retryable), progress: error.uploadFinished ? 100 : entry.progress } : entry));
    }
  };

  const uploadSelected = async () => {
    if (uploading) return;
    const pending = queue.filter(item => item.status === 'queued').map(item => item.id);
    if (!pending.length) return;
    setUploading(true);
    for (const id of pending) await sendFile(id);
    setUploading(false);
  };

  const retryFile = async id => {
    if (uploading) return;
    setUploading(true);
    await sendFile(id);
    setUploading(false);
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
  return <div className="employee-upload-page">
    <header className="pagehead upload-pagehead">
      <div><small className="eyebrow">FINTECH OCR / WORKSPACE</small><h1>Upload invoices</h1><p>Add your receipts and review the extracted data.</p></div>
    </header>

    <div className="upload-top-grid">
      <section className="panel upload-card" aria-labelledby="upload-card-title">
        <div className="upload-section-heading"><div><h2 id="upload-card-title">Add your invoices</h2><p>Choose a document or drop it here.</p></div><span className="upload-limit">20 MB max / file</span></div>
        <div className={`upload-dropzone ${isDragging ? 'is-dragging' : ''}`} onDragOver={event => { event.preventDefault(); setIsDragging(true); }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false); }} onDrop={event => { event.preventDefault(); setIsDragging(false); addFiles(event.dataTransfer.files); }}>
          <div className="upload-icon-box"><CloudUpload size={25}/></div>
          <strong>Drag and drop PDF, JPG, PNG or XML</strong>
          <span>Up to 20 MB per file</span>
          <input ref={fileInput} type="file" accept=".pdf,.jpg,.jpeg,.png,.xml" multiple className="visually-hidden-file" aria-label="Choose invoice files" onChange={event => { addFiles(event.target.files); event.target.value = ''; }}/>
          <input ref={cameraInput} type="file" accept="image/*" capture="environment" className="visually-hidden-file" aria-label="Take invoice photo" onChange={event => { addFiles(event.target.files); event.target.value = ''; }}/>
          <div className="upload-choose-actions">
            <button type="button" className="btn btn-primary" onClick={() => fileInput.current?.click()}><Upload size={16}/>Choose files</button>
            <button type="button" className="btn btn-muted" onClick={() => cameraInput.current?.click()}><Camera size={16}/>Take photo</button>
          </div>
          <small>PDF, JPG, JPEG, PNG or XML · Maximum 20 MB each</small>
        </div>
        {queue.some(item => item.status === 'queued') && <div className="upload-submit-row"><span>{queue.filter(item => item.status === 'queued').length} file(s) ready</span><button type="button" className="btn btn-primary" disabled={uploading} onClick={uploadSelected}>{uploading ? 'Uploading…' : 'Upload selected'}<ArrowRight size={16}/></button></div>}
        {queue.some(item => item.status === 'failed') && <div className="upload-inline-note">Tệp lỗi định dạng hoặc vượt giới hạn chưa được gửi lên máy chủ.</div>}
      </section>

      <section className="panel processing-card" aria-labelledby="processing-title">
        <div className="upload-section-heading"><div><h2 id="processing-title">Processing queue</h2><p>Upload and processing status</p></div><span className="queue-count">{activeCount ? `${activeCount} processing` : readyCount ? `${readyCount} ready` : `${queue.length} files`}</span></div>
        {queue.length === 0 ? <div className="queue-empty"><FileText size={24}/><span>No files in the queue</span><small>Uploaded files will appear here.</small></div>
          : <ul className="upload-queue-list">{queue.map(item => <UploadQueueItem key={item.id} item={item} onRetry={retryFile} onReview={id => navigate(`/invoices/${id}`)}/>)}</ul>}
        {queue.length > 0 && <p className="queue-api-note">Progress shows measured browser upload bytes. Server processing is indeterminate because the API does not expose stage progress; AI Extraction status is unavailable.</p>}
      </section>
    </div>

    <MyInvoices invoices={invoiceData} busy={invoicesBusy} error={invoicesError} reload={reloadInvoices} onSubmit={submitInvoice} submittingId={submittingId} submitErrors={submitErrors} activeTab={activeTab} setActiveTab={setActiveTab} navigate={navigate}/>
  </div>;
}
