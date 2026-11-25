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
  valid: 'Hợp lệ', needs_review: 'Cần kiểm tra', error: 'Lỗi',
  draft: 'Nháp', pending: 'Chờ xử lý', approved: 'Đã phê duyệt', rejected: 'Đã từ chối',
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
    xhr.addEventListener('error', () => reject(makeError('Mất kết nối trong lúc tải lên. Hãy kiểm tra Danh sách hóa đơn trước khi thử lại.')));
    xhr.addEventListener('timeout', () => reject(makeError('Hết thời gian chờ phản hồi. Hãy kiểm tra Danh sách hóa đơn trước khi thử lại.')));
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
        <StatusBadge value={item.status} label={item.status === 'done' ? 'Hoàn tất' : item.status === 'failed' ? 'Thất bại' : item.status === 'uploading' ? item.phase === 'transfer' ? 'Đang tải lên' : 'Đang xử lý' : 'Sẵn sàng'}/>
        {item.invoice?.id && <span>Hóa đơn #{item.invoice.id}</span>}
      </div>
      {active && <div className="queue-progress-wrap">
        {measuredProgress
          ? <div className="upload-progress-track" role="progressbar" aria-label={`Đã tải ${item.progress}% của ${item.file.name}`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={item.progress}><span style={{ width: `${item.progress}%` }}/></div>
          : <div className="upload-progress-track is-indeterminate" role="progressbar" aria-label={`Đang xử lý ${item.file.name}`}><span/></div>}
        {measuredProgress && <small>{item.progress}% đã tải lên</small>}
        {item.phase === 'processing' && <p className="queue-hint">Tệp đã gửi xong; Backend đang xử lý đồng bộ. API không báo tiến độ riêng cho OCR/Validation.</p>}
      </div>}
      {item.error && <p className="queue-error" role="alert">{item.error}</p>}
      {item.status === 'failed' && !item.retryable && <p className="queue-hint">Hãy kiểm tra Danh sách hóa đơn trước khi gửi lại. Máy chủ có thể đã nhận được tệp.</p>}
      {completed && <p className="queue-result">API đã lưu hóa đơn #{item.invoice?.id}; trạng thái kiểm tra:<strong>{statusLabel(item.invoice?.validation_status)}</strong>.</p>}
      {item.status === 'failed' && item.invoice?.id && <p className="queue-result">Hóa đơn #{item.invoice.id} đã được lưu nhưng API báo lỗi kiểm tra. Hãy xem lại hóa đơn; tệp sẽ không được gửi lại để tránh trùng lặp.</p>}
      <ol className="queue-stepper" aria-label={`Các bước xử lý của tệp ${item.file.name}`}>
        {stages.map((stage, index) => <li key={stage.id} className={`queue-step step-${stage.state}`} aria-current={stage.state === 'active' ? 'step' : undefined}>
          <span className="queue-step-marker">{stage.state === 'complete' ? <CheckCircle2 size={13}/> : stage.state === 'failed' ? <XCircle size={13}/> : index + 1}</span>
          <span className="queue-step-label">{stage.label}</span>
          {stage.state === 'unavailable' && <small>Chưa có dữ liệu</small>}
        </li>)}
      </ol>
      {item.status !== 'done' && <p className="queue-ai-note">API hiện tại chưa cung cấp trạng thái trích xuất AI.</p>}
    </div>
    <div className="queue-actions">
      {item.status === 'failed' && item.retryable && <button type="button" className="btn btn-small btn-muted" onClick={() => onRetry(item.id)}><RotateCcw size={14}/>Thử lại</button>}
      {completed && item.invoice?.id && <button type="button" className="textbtn" onClick={() => onReview(item.invoice.id)}>Xem chi tiết<ArrowRight size={14}/></button>}
    </div>
  </li>;
}

function MyInvoices({ invoices, busy, error, reload, onSubmit, submittingId, submitErrors, activeTab, setActiveTab, navigate }) {
  const counts = useMemo(() => invoiceStatusCounts(invoices), [invoices]);
  const rows = useMemo(() => invoicesForApprovalStatus(invoices, activeTab), [invoices, activeTab]);
  const tabs = [
    ['all', 'Tất cả'], ['pending', 'Chờ xử lý'], ['approved', 'Đã phê duyệt'], ['rejected', 'Đã từ chối'],
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
        <th>Số hóa đơn</th><th>Nhà cung cấp</th><th>Ngày</th><th>Số tiền</th><th>Loại</th><th>Kiểm tra AI</th><th>Phê duyệt</th><th>Thao tác</th>
      </tr></thead><tbody>{rows.map(invoice => {
        const canSubmit = ['draft', 'rejected'].includes(invoice.approval_status);
        const reason = rejectionReason(invoice);
        return <tr key={invoice.id}>
          <td><strong>{invoice.invoice_number || `#${invoice.id}`}</strong>{reason && invoice.approval_status === 'rejected' && <small className="rejection-reason" title={reason}>Lý do: {reason}</small>}</td>
          <td>{invoice.seller_name || <span className="muted-cell">Chưa trích xuất</span>}</td>
          <td>{datefmt(invoice.invoice_date)}</td>
          <td className="money">{invoice.total_amount == null ? '—' : money(invoice.total_amount)}</td>
          <td><span className="type-label">{{ einvoice: 'Hóa đơn điện tử', bill: 'Chứng từ', unknown: 'Chưa xác định' }[invoice.document_type] || '—'}</span></td>
          <td title="Đây là validation_status do Backend trả về; API hiện không có trạng thái AI riêng."><StatusBadge value={invoice.validation_status}/></td>
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
        setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'failed', phase: 'processing', failurePhase: 'validation', invoice, error: 'API đã nhận tệp nhưng trả về trạng thái kiểm tra là lỗi.', retryable: false } : entry));
      } else {
        setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'done', phase: 'complete', invoice, progress: 100 } : entry));
      }
      await reloadInvoices();
    } catch (error) {
      setQueue(current => current.map(entry => entry.id === id ? { ...entry, status: 'failed', phase: error.uploadFinished ? 'processing' : 'transfer', failurePhase: error.uploadFinished ? 'processing' : 'transfer', error: error.message || "Tải lên thất bại.", retryable: Boolean(error.retryable), progress: error.uploadFinished ? 100 : entry.progress } : entry));
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
      <div><small className="eyebrow">FINTECH OCR / KHÔNG GIAN LÀM VIỆC</small><h1>Tải hóa đơn lên</h1><p>Tải chứng từ lên và xem lại dữ liệu đã trích xuất.</p></div>
    </header>

    <div className="upload-top-grid">
      <section className="panel upload-card" aria-labelledby="upload-card-title">
        <div className="upload-section-heading"><div><h2 id="upload-card-title">Thêm hóa đơn</h2><p>Chọn tệp hoặc kéo thả vào đây.</p></div><span className="upload-limit">Tối đa 20 MB / tệp</span></div>
        <div className={`upload-dropzone ${isDragging ? 'is-dragging' : ''}`} onDragOver={event => { event.preventDefault(); setIsDragging(true); }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false); }} onDrop={event => { event.preventDefault(); setIsDragging(false); addFiles(event.dataTransfer.files); }}>
          <div className="upload-icon-box"><CloudUpload size={25}/></div>
          <strong>Kéo thả tệp PDF, JPG, PNG hoặc XML</strong>
          <span>Tối đa 20 MB mỗi tệp</span>
          <input ref={fileInput} type="file" accept=".pdf,.jpg,.jpeg,.png,.xml" multiple className="visually-hidden-file" aria-label="Chọn tệp hóa đơn" onChange={event => { addFiles(event.target.files); event.target.value = ''; }}/>
          <input ref={cameraInput} type="file" accept="image/*" capture="environment" className="visually-hidden-file" aria-label="Chụp ảnh hóa đơn" onChange={event => { addFiles(event.target.files); event.target.value = ''; }}/>
          <div className="upload-choose-actions">
            <button type="button" className="btn btn-primary" onClick={() => fileInput.current?.click()}><Upload size={16}/>Chọn tệp</button>
            <button type="button" className="btn btn-muted" onClick={() => cameraInput.current?.click()}><Camera size={16}/>Chụp ảnh</button>
          </div>
          <small>PDF, JPG, JPEG, PNG hoặc XML · Tối đa 20 MB mỗi tệp</small>
        </div>
        {queue.some(item => item.status === 'queued') && <div className="upload-submit-row"><span>{queue.filter(item => item.status === 'queued').length} tệp sẵn sàng</span><button type="button" className="btn btn-primary" disabled={uploading} onClick={uploadSelected}>{uploading ? 'Đang tải lên…' : 'Tải các tệp đã chọn'}<ArrowRight size={16}/></button></div>}
        {queue.some(item => item.status === 'failed') && <div className="upload-inline-note">Tệp lỗi định dạng hoặc vượt giới hạn chưa được gửi lên máy chủ.</div>}
      </section>

      <section className="panel processing-card" aria-labelledby="processing-title">
        <div className="upload-section-heading"><div><h2 id="processing-title">Hàng đợi xử lý</h2><p>Trạng thái tải lên và xử lý</p></div><span className="queue-count">{activeCount ? `${activeCount} tệp đang xử lý` : readyCount ? `${readyCount} tệp sẵn sàng` : `${queue.length} tệp`}</span></div>
        {queue.length === 0 ? <div className="queue-empty"><FileText size={24}/><span>Hàng đợi chưa có tệp</span><small>Tệp được tải lên sẽ hiển thị tại đây.</small></div>
          : <ul className="upload-queue-list">{queue.map(item => <UploadQueueItem key={item.id} item={item} onRetry={retryFile} onReview={id => navigate(`/invoices/${id}`)}/>)}</ul>}
        {queue.length > 0 && <p className="queue-api-note">Phần trăm phản ánh dữ liệu trình duyệt đã tải lên thực tế. Tiến trình máy chủ không xác định vì API không cung cấp tiến độ từng bước; chưa có trạng thái Trích xuất AI.</p>}
      </section>
    </div>

    <MyInvoices invoices={invoiceData} busy={invoicesBusy} error={invoicesError} reload={reloadInvoices} onSubmit={submitInvoice} submittingId={submittingId} submitErrors={submitErrors} activeTab={activeTab} setActiveTab={setActiveTab} navigate={navigate}/>
  </div>;
}
