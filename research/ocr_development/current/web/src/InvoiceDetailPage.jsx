import {SLADetail} from './ApprovalSLA.jsx';
import InvoiceVerificationReport from './InvoiceVerificationReport.jsx';
import {ExpenseCategoryEditor} from './FinancePage.jsx';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronLeft, ExternalLink, FileText, LoaderCircle, Maximize2, Minimize2, MoveHorizontal, Plus, Save, Trash2, XCircle, ZoomIn, ZoomOut } from 'lucide-react';
import { api, approvalName, datefmt, documentTypeName } from './api';
import { invoiceItemDrafts, invoiceItemPayload, moneyOrDash, nullableNumber } from './viewUtils';
import { formatLookupTimestamp, initialLookupOutcome, isSafeHttpUrl } from './lookupUtils';
import { invoiceProcessingState, invoiceStatusNotes, llmRuntimeNotice, ocrFindingLabel, ocrRuntimeNotice } from './ocrRuntimeInfo';
import PdfDocumentViewer from './PdfDocumentViewer';
import './InvoiceDetailPage.css';

const editableFields = [
  ['invoice_number', 'Số hóa đơn'], ['invoice_symbol', 'Ký hiệu hóa đơn'], ['invoice_date', 'Ngày lập'],
  ['seller_name', 'Nhà cung cấp'], ['seller_tax_code', 'Mã số thuế nhà cung cấp'], ['buyer_name', 'Người mua'],
  ['buyer_tax_code', 'Mã số thuế người mua'], ['subtotal', 'Tiền trước thuế'], ['vat_rate', 'Thuế suất VAT (%)'],
  ['vat_amount', 'Tiền thuế VAT'], ['total_amount', 'Tổng tiền'],
];

const fieldGroups = [
  { id: 'invoice', title: 'Thông tin hóa đơn', keys: ['invoice_number', 'invoice_symbol', 'invoice_date'] },
  { id: 'parties', title: 'Người bán / người mua', keys: ['seller_name', 'seller_tax_code', 'buyer_name', 'buyer_tax_code'] },
  { id: 'payment', title: 'Thuế và thanh toán', keys: ['subtotal', 'vat_rate', 'vat_amount', 'total_amount'] },
];
const numericFields = new Set(['subtotal', 'vat_rate', 'vat_amount', 'total_amount']);

function invoiceDraft(data) {
  return {
    ...Object.fromEntries(editableFields.map(([key]) => [key, data[key] ?? ''])),
    items: invoiceItemDrafts(data.items),
  };
}

export default function InvoiceDetailPage({ user, id, data, busy, error, reload, onChanged }) {
  const [form, setForm] = useState(null);
  const [categoryRevision,setCategoryRevision]=useState(0);
  const [message, setMessage] = useState('');
  const [reject, setReject] = useState('');
  const [lookup, setLookup] = useState(initialLookupOutcome);
  const [lookupNote, setLookupNote] = useState('');
  const [original, setOriginal] = useState({ loading: false, url: '', kind: '', text: '', error: '' });
  const [savedDraft, setSavedDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [previewZoom, setPreviewZoom] = useState(null);
  const [pdfStatus, setPdfStatus] = useState('loading');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const previewRef = useRef(null);
  const viewScope = useRef({ id });
  if (viewScope.current?.id !== id) viewScope.current = { id };
  const saveLock = useRef(false);
  const formOwner = useRef(null);
  const draftState = useRef({ form: null, savedDraft: '' });
  draftState.current = { form, savedDraft };
  const pendingSavedDraft = useRef(null);
  const dataMatches = data != null && String(data.id) === String(id);
  // Attach once for each invoice/table mount, not on every input change.
  const attachItemsScroll = useCallback(element => {
    if (element) element.scrollLeft = 0;
  }, [id]);
  const { data: corrections, reload: reloadCorrections, error: correctionError } = useCorrections(id);
  const { data: lookupHistory, reload: reloadLookupHistory, error: lookupHistoryError, busy: lookupHistoryBusy } = useLookupHistory(id);
  const canEdit = dataMatches && user.role === 'employee' && ['draft', 'rejected'].includes(data?.approval_status);
  const isReviewer = user.role === 'accountant' || user.role === 'admin';

  useEffect(() => { setLookup(initialLookupOutcome); setLookupNote(''); }, [id]);
  useEffect(() => {
    if (viewScope.current?.id !== id) viewScope.current = { id };
    const scope = viewScope.current;
    formOwner.current = null;
    pendingSavedDraft.current = null;
    saveLock.current = false;
    setForm(null);
    setSavedDraft('');
    setMessage('');
    setSaving(false);
    return () => { if (viewScope.current === scope) viewScope.current = null; };
  }, [id]);

  useEffect(() => {
    if (!data || String(data.id) !== String(id)) { setForm(null); return; }
    const draft = invoiceDraft(data);
    const snapshot = JSON.stringify(draft);
    if (pendingSavedDraft.current !== null && snapshot !== pendingSavedDraft.current) {
      setMessage('Dữ liệu tải lại chưa khớp phản hồi lưu; bản vừa lưu được giữ nguyên.');
      return;
    }
    pendingSavedDraft.current = null;
    const current = draftState.current;
    if (formOwner.current === id && current.form && JSON.stringify(current.form) !== current.savedDraft) {
      setMessage('Đã tải lại dữ liệu; các thay đổi chưa lưu của bạn được giữ nguyên.');
      return;
    }
    formOwner.current = id;
    setForm(draft);
    setSavedDraft(snapshot);
  }, [data, id]);


  useEffect(() => { setPreviewZoom(null); setPdfStatus('loading'); }, [id]);
  useEffect(() => {
    const handleFullscreen = () => setIsFullscreen(document.fullscreenElement === previewRef.current && document.fullscreenElement != null);
    document.addEventListener('fullscreenchange', handleFullscreen);
    return () => document.removeEventListener('fullscreenchange', handleFullscreen);
  }, []);

  useEffect(() => {
    if (!dataMatches) return undefined;
    let cancelled = false;
    let objectUrl = '';
    setOriginal({ loading: true, url: '', kind: '', text: '', error: '' });
    api(`/invoices/${id}/file`, { raw: true }).then(async response => {
      const blob = await response.blob();
      const extension = String(data.filename || '').split('.').pop().toLowerCase();
      const kind = ['jpg', 'jpeg', 'png'].includes(extension) ? 'image' : extension === 'xml' ? 'xml' : 'pdf';
      const text = kind === 'xml' ? await blob.text() : '';
      objectUrl = URL.createObjectURL(blob);
      if (cancelled) { URL.revokeObjectURL(objectUrl); return; }
      setOriginal({ loading: false, url: objectUrl, kind, text, error: '' });
    }).catch(fetchError => {
      if (!cancelled) setOriginal({ loading: false, url: '', kind: '', text: '', error: fetchError.message || "Không tải được tệp gốc." });
    });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id, data?.id, data?.filename]);

  async function send(path, body, method = 'POST') {
    const scope = viewScope.current;
    if (!scope || !dataMatches || (method === 'PUT' && saveLock.current)) return;
    setMessage('');
    if (method === 'PUT') { saveLock.current = true; setSaving(true); }
    try {
      const result = await api(path, { method, body });
      if (viewScope.current !== scope) return;
      if (method === 'PUT') {
        if (String(result?.id) !== String(id) || !Array.isArray(result?.items)) {
          throw new Error('Chưa nhận được dữ liệu lưu hợp lệ; bản chỉnh sửa được giữ lại.');
        }
        const draft = invoiceDraft(result);
        const snapshot = JSON.stringify(draft);
        draftState.current = { form: draft, savedDraft: snapshot };
        pendingSavedDraft.current = snapshot;
        formOwner.current = id;
        setForm(draft);
        setSavedDraft(snapshot);
      }
      if (path.endsWith('/lookup')) { setLookup(initialLookupOutcome); setLookupNote(''); }
      setMessage(method === 'PUT' ? 'Đã lưu thay đổi.' : 'Thao tác thành công.');
      reload();
      reloadCorrections();
      reloadLookupHistory();
      onChanged?.();
    } catch (sendError) { if (viewScope.current === scope) setMessage(sendError.message); }
    finally { if (method === 'PUT' && viewScope.current === scope) { saveLock.current = false; setSaving(false); } }
  }

  function save() {
    if (saving || saveLock.current || !form || !dataMatches || formOwner.current !== id) return;
    try {
      const baseline = JSON.parse(savedDraft || '{}');
      const itemsChanged = JSON.stringify(form.items) !== JSON.stringify(baseline.items);
      const items = itemsChanged ? invoiceItemPayload(form.items) : null;
      if (items?.some(item => !item.description)) {
        setMessage('Mỗi dòng cần có mô tả. Cột số không có trên chứng từ được để trống; hệ thống sẽ kiểm tra theo loại chứng từ.');
        return;
      }
      const body = Object.fromEntries(Object.entries(form).filter(([key, value]) => key !== 'items'
        && value !== baseline[key]).map(([key, value]) => [
        key, ['subtotal', 'vat_rate', 'vat_amount', 'total_amount'].includes(key) ? nullableNumber(value)
          : value == null || (typeof value === 'string' && value.trim() === '') ? null : value,
      ]));
      if (itemsChanged) body.items = items;
      if (!Object.keys(body).length) return;
      send(`/invoices/${id}`, body, 'PUT');
    } catch (error) {
      setMessage(error.message || 'Giá trị số không hợp lệ; dữ liệu chưa được lưu.');
    }
  }

  function updateItem(index, field, value) {
    setForm(current => ({ ...current, items: current.items.map((item, row) => row === index ? { ...item, [field]: value } : item) }));
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement === previewRef.current) await document.exitFullscreen();
      else if (previewRef.current?.requestFullscreen) await previewRef.current.requestFullscreen();
      else setMessage('Trình duyệt chưa hỗ trợ toàn màn hình. Bạn có thể mở tệp gốc để xem rộng hơn.');
    } catch {
      setMessage('Không thể mở toàn màn hình. Bạn có thể mở tệp gốc để xem rộng hơn.');
    }
  }

  if (busy || (!error && data && !dataMatches)) return <><PageTitle title="Chi tiết hóa đơn"/><div className="loading">Đang tải hóa đơn…</div></>;
  if (error || !data) return <><PageTitle title="Chi tiết hóa đơn"/><p className="error">{error || "Không tìm thấy hóa đơn."}</p></>;

  const processing = invoiceProcessingState(data);
  const notes = invoiceStatusNotes(data);
  const ProcessingIcon = processing.tone === 'red' ? XCircle : processing.tone === 'orange' ? AlertTriangle : CheckCircle2;
  const warnings = Array.isArray(data.warnings) ? data.warnings : [];
  const findings = Array.isArray(data.ocr?.findings) ? data.ocr.findings : [];
  const hasUnsavedChanges = form != null && JSON.stringify(form) !== savedDraft;
  const canZoom = !!original.url && (original.kind === 'image' || (original.kind === 'pdf' && pdfStatus === 'ready'));
  const showZoomControls = ['image', 'pdf'].includes(original.kind) && !(original.kind === 'pdf' && pdfStatus === 'fallback');

  return <>
    <PageTitle title="Chi tiết hóa đơn" description="Xem chứng từ và thông tin đã trích xuất." action={<button className="btn btn-muted" onClick={() => history.back()}><ChevronLeft size={16}/>Quay lại</button>}/>
    <SLADetail invoiceId={data.id} revision={JSON.stringify([data.approval_status,data.history])}/>
    <ExpenseCategoryEditor invoiceId={data.id} onChange={()=>setCategoryRevision(value=>value+1)}/>
    <InvoiceVerificationReport canAssess={isReviewer} invoiceId={data.id} revision={JSON.stringify([categoryRevision,data.updated_at,data.items,data.subtotal,data.vat_rate,data.vat_amount,data.total_amount])}/>
    <div className="invoice-detail-layout">
    <div className="detail-grid invoice-detail-grid">
      <section className="panel original invoice-original-panel" ref={previewRef}>
        <div className="panel-heading"><h3>Chứng từ gốc</h3><span className="pill">{documentTypeName(data.document_type)}</span></div>
        <div className="invoice-preview-toolbar" role="toolbar" aria-label="Điều khiển chứng từ gốc">
          {showZoomControls && <><button type="button" className="iconbtn" disabled={!canZoom || (previewZoom ?? 100) <= 50} aria-label="Thu nhỏ chứng từ" title="Thu nhỏ" onClick={() => setPreviewZoom(value => Math.max(50, (value ?? 100) - 25))}><ZoomOut size={17}/></button>
          <span className="preview-zoom-label" title="Tỷ lệ so với chiều rộng khung xem">{previewZoom == null ? 'Vừa chiều rộng' : `${previewZoom}%`}</span>
          <button type="button" className="iconbtn" disabled={!canZoom || (previewZoom ?? 100) >= 250} aria-label="Phóng to chứng từ" title="Phóng to" onClick={() => setPreviewZoom(value => Math.min(250, (value ?? 100) + 25))}><ZoomIn size={17}/></button>
          <button type="button" className="iconbtn" disabled={!canZoom} aria-label="Căn vừa chiều rộng" title="Vừa chiều rộng" onClick={() => setPreviewZoom(null)}><MoveHorizontal size={17}/></button></>}
          {!showZoomControls && <span className="preview-zoom-label">{original.kind === 'xml' ? 'Chứng từ XML' : 'Chứng từ gốc'}</span>}
          <button type="button" className="iconbtn preview-fullscreen" disabled={!original.url} aria-label={isFullscreen ? 'Thoát toàn màn hình' : 'Xem toàn màn hình'} title={isFullscreen ? 'Thoát toàn màn hình' : 'Toàn màn hình'} onClick={toggleFullscreen}>{isFullscreen ? <Minimize2 size={17}/> : <Maximize2 size={17}/>}</button>
        </div>
        <div className={`file-viewer invoice-file-viewer viewer-${original.kind}`}>
          {original.loading ? <div className="loading">Đang tải chứng từ gốc…</div> : original.error ? <p className="error">{original.error}</p> : original.kind === 'image' ? <div className="invoice-image-canvas"><img src={original.url} style={{ width: previewZoom == null ? '100%' : `${previewZoom}%` }} alt={data.filename || "Hóa đơn gốc"} /></div> : original.kind === 'xml' ? <pre>{original.text}</pre> : original.url ? <PdfDocumentViewer key={original.url} url={original.url} zoom={previewZoom} onStatusChange={setPdfStatus}/> : <div className="empty"><FileText size={30}/><span>Không thể hiển thị chứng từ gốc</span></div>}
        </div>
        <div className="invoice-original-footer"><p className="file-name" title={data.filename}>{data.filename}</p><button type="button" className="btn btn-outline btn-small" disabled={!original.url} onClick={() => window.open(original.url, '_blank', 'noopener,noreferrer')}><ExternalLink size={15}/>Mở tệp gốc</button></div>
      </section>

      <section className="panel invoice-data-panel">
        <div className="panel-heading"><div><h3>Hóa đơn {data.invoice_number || `#${id}`}</h3><span className="helper">{data.seller_name || "Chưa xác định nhà cung cấp"}</span></div><Status value={data.approval_status}/></div>
        <div className="invoice-meta-row"><Status value={data.lookup_status} label={`Thuế: ${approvalName(data.lookup_status) || 'Chưa tra cứu'}`}/></div>
        <section className={`invoice-status-summary status-${processing.tone}`} aria-label="Trạng thái trích xuất">
          <div className="invoice-status-heading" role={processing.tone === 'red' ? 'alert' : 'status'}>
            <span className="invoice-status-icon"><ProcessingIcon size={20} aria-hidden="true"/></span>
            <div><strong>{processing.label}</strong><ul className="invoice-status-notes">{notes.map(note => <li key={note.key} className={`tone-${note.tone}`}>{note.label}</li>)}</ul></div>
          </div>
          {(data.ocr || warnings.length > 0) && <details className="invoice-diagnostics">
            <summary>Chi tiết<span>{warnings.length > 0 ? `${warnings.length} cảnh báo` : 'Thông tin xử lý'}</span></summary>
            <div className="invoice-diagnostics-content">
              {warnings.length > 0 && <><h4>Cảnh báo kiểm tra dữ liệu</h4><ul className="diagnostic-warnings">{warnings.map((warning, index) => <li key={`${warning.rule}-${index}`}><code>{warning.rule}</code><p>{warning.message}</p></li>)}</ul></>}
              {data.ocr?.confidence?.reason && !warnings.some(warning => warning.rule === 'CONFIDENCE' && warning.message === data.ocr.confidence.reason) && <p>{data.ocr.confidence.reason}</p>}
              {data.ocr?.confidence?.quality_preview?.components && <div className="quality-preview"><h4>Điểm chất lượng thử nghiệm (chưa phê duyệt)</h4><p>Ngưỡng đề xuất 90%; điểm không phải xác suất OCR chính xác và không thay thế đối chiếu chứng từ.</p><ul>{[['completeness','Độ đầy đủ (25%)'],['source_evidence','Bằng chứng nguồn (35%)'],['financial_consistency','Nhất quán tài chính (25%)'],['coverage','Độ bao phủ (15%)']].map(([key,label]) => <li key={key}>{label}: {Math.round(data.ocr.confidence.quality_preview.components[key] * 1000) / 10}%</li>)}</ul></div>}
              {ocrRuntimeNotice(data.ocr) && <p>{ocrRuntimeNotice(data.ocr)}</p>}
              {llmRuntimeNotice(data.ocr) && <p>{llmRuntimeNotice(data.ocr)}</p>}
              {findings.length > 0 && <><h4>Ghi nhận trích xuất ({findings.length})</h4><ul className="diagnostic-findings">{findings.map((finding, index) => <li key={index}><details>
                <summary>{ocrFindingLabel(finding)}{finding?.page != null && ` · Trang ${finding.page}`}{finding?.line != null && ` · Dòng ${finding.line}`}</summary>
                <pre>{JSON.stringify(finding, null, 2)}</pre>
              </details></li>)}</ul></>}
              {data.ocr && <details className="diagnostic-raw"><summary>Thông tin chẩn đoán</summary><pre>{JSON.stringify(data.ocr, null, 2)}</pre></details>}
            </div>
          </details>}
        </section>
        {isSafeHttpUrl(data.qr_url) && <p className="helper"><a href={data.qr_url} target="_blank" rel="noopener noreferrer">Mở liên kết QR<ExternalLink size={13}/></a></p>}
        {form && fieldGroups.map(group => <section key={group.id} className="invoice-field-group" data-group={group.id} aria-labelledby={`invoice-group-${group.id}`}>
          <h4 id={`invoice-group-${group.id}`}>{group.title}</h4>
          <div className="field-grid">{group.keys.map(key => {
            const label = editableFields.find(([field]) => field === key)[1];
            const missing = String(form[key] ?? '').trim() === '';
            const isName = key === 'seller_name' || key === 'buyer_name';
            return <label key={key} data-field={key} className={missing ? 'field-needs-review' : ''}>
              <span className="field-label">{label}{missing && <em className="field-review-flag">Chưa trích xuất</em>}</span>
              <input type={key === 'invoice_date' ? 'date' : numericFields.has(key) ? 'number' : 'text'} step={numericFields.has(key) ? '0.01' : undefined} title={isName ? form[key] : undefined} disabled={!canEdit || saving} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/>
            </label>;
          })}</div>
        </section>)}
      </section>

    </div>
      <section className="panel invoice-items-panel" aria-labelledby="invoice-items-title">
        <div className="line-items-heading"><div><h3 id="invoice-items-title">Hàng hóa/dịch vụ</h3><span className="helper">{form?.items?.length || 0} dòng hàng</span></div>{canEdit && <button type="button" className="btn btn-muted btn-small" disabled={!form || saving} onClick={() => setForm(current => ({ ...current, items: [...current.items, { description: '', unit: '', quantity: '', unit_price: '', amount: '' }] }))}><Plus size={15}/>Thêm dòng hàng</button>}</div>
        {form?.items?.length ? <div className="line-items-scroll" ref={attachItemsScroll} dir="ltr" tabIndex={0} role="region" aria-label="Bảng hàng hóa và dịch vụ, cuộn ngang để xem các cột"><div className={`line-item-table${canEdit ? '' : ' is-readonly'}`}>
          <div className="line-item-row line-item-header"><span>Tên hàng hóa/dịch vụ</span><span>Đơn vị</span><span>Số lượng</span><span>Đơn giá</span><span>Số tiền</span>{canEdit && <span/>}</div>
          {form.items.map((item, index) => <div className="line-item-row" key={index}>
            <input type="text" aria-label={`Dòng hàng ${index + 1} tên`} title={item.description} disabled={!canEdit || saving} value={item.description} onChange={event => updateItem(index, 'description', event.target.value)} />
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} đơn vị`} disabled={saving} value={item.unit} maxLength={30} onChange={event => updateItem(index, 'unit', event.target.value)} placeholder="—" /> : <span>{item.unit || '—'}</span>}
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} số lượng`} disabled={saving} type="number" min="0" step="any" value={item.quantity} onChange={event => updateItem(index, 'quantity', event.target.value)} placeholder="—" /> : <span>{item.quantity === '' ? '—' : item.quantity}</span>}
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} đơn giá`} disabled={saving} type="number" min="0" step="any" value={item.unit_price} onChange={event => updateItem(index, 'unit_price', event.target.value)} placeholder="—" /> : <span className="line-item-money">{moneyOrDash(item.unit_price)}</span>}
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} thành tiền`} disabled={saving} type="number" min="0" step="any" value={item.amount} onChange={event => updateItem(index, 'amount', event.target.value)} placeholder="—" /> : <span className="line-item-money">{moneyOrDash(item.amount)}</span>}
            {canEdit && <button type="button" className="iconbtn" disabled={saving} aria-label={`Xóa dòng hàng ${index + 1}`} onClick={() => setForm(current => ({ ...current, items: current.items.filter((_, row) => row !== index) }))}><Trash2 size={16}/></button>}
          </div>)}
        </div></div> : <div className="empty line-items-empty">Chưa có dữ liệu dòng hàng.</div>}
      </section>
      {canEdit && <div className={`invoice-save-bar${hasUnsavedChanges || saving ? ' is-active' : ' is-clean'}`}>
        <span className={`invoice-draft-state${hasUnsavedChanges ? ' is-dirty' : ''}`} role="status">{saving ? 'Đang lưu thay đổi…' : hasUnsavedChanges ? 'Có thay đổi chưa lưu' : 'Không có thay đổi chưa lưu'}</span>
        <button type="button" className="btn btn-primary" disabled={saving || !form} onClick={save}>{saving ? <LoaderCircle size={16} className="spin"/> : <Save size={16}/>}Lưu thay đổi và kiểm tra lại</button>
      </div>}
    </div>

    <section className="panel action-panel">
      <div><h3>Quy trình phê duyệt</h3><p>Trạng thái kiểm tra, phê duyệt và tra cứu thuế được quản lý độc lập.</p></div>
      <div className="action-buttons">{canEdit && <button className="btn btn-primary" onClick={() => send(`/invoices/${id}/submit`)}><span>Gửi phê duyệt</span></button>}
        {isReviewer && data.approval_status === 'pending' && <><button className="btn btn-primary" onClick={() => send(`/invoices/${id}/approval`, { action: 'approved', reason: reject || null })}>Phê duyệt</button><input className="reason" placeholder="Ghi chú quyết định (bắt buộc khi từ chối)" value={reject} onChange={event => setReject(event.target.value)}/><button className="btn btn-outline" onClick={() => send(`/invoices/${id}/approval`, { action: 'rejected', reason: reject })}>Từ chối</button></>}</div>
      {isReviewer && <div className="lookup"><h3>Tra cứu thuế bán thủ công</h3>
        {data.document_type === 'einvoice' ? <><p>Đối chiếu số hóa đơn, ký hiệu, ngày lập, nhà cung cấp, mã số thuế và tổng tiền ở trên với cổng tra cứu chính thức. Hệ thống không tự động thu thập dữ liệu từ cổng và không chứng nhận tính hợp pháp. Nếu cổng không khả dụng, hãy giữ nguyên trạng thái và thử lại sau.</p><div className="action-buttons"><a className="btn btn-muted" href="https://hoadondientu.gdt.gov.vn/" target="_blank" rel="noopener noreferrer">Mở cổng tra cứu thuế<ExternalLink size={15}/></a><select aria-label="Kết quả tra cứu thủ công" value={lookup} onChange={event => setLookup(event.target.value)}><option value="">Chọn kết quả sau khi đối chiếu</option><option value="verified">Đã xác minh</option><option value="mismatch">Không khớp</option><option value="not_found">Không tìm thấy</option></select><input aria-label="Ghi chú tra cứu" placeholder="Ghi chú đối chiếu (không bắt buộc)" value={lookupNote} onChange={event => setLookupNote(event.target.value)}/><button className="btn btn-primary" disabled={!lookup} onClick={() => send(`/invoices/${id}/lookup`, { result: lookup, note: lookupNote.trim() || null })}>Lưu kết quả tra cứu</button></div></> : data.document_type === 'bill' ? <p>Chứng từ này không thuộc diện tra cứu trên cổng thuế; kế toán tiếp tục kiểm tra thủ công.</p> : <p>Chưa xác định được loại chứng từ. Chưa thể thực hiện tra cứu; hãy kiểm tra chứng từ gốc và phân loại trước khi ghi nhận kết quả.</p>}
      </div>}
      <HistoryDisclosure title="Lịch sử tra cứu thuế" count={lookupHistory?.length || 0} error={lookupHistoryError} busy={lookupHistoryBusy}>
        {lookupHistory?.map(entry => <p key={entry.id}><b>{approvalName(entry.result)}</b> · {entry.checked_by_name || `Người dùng #${entry.checked_by}`} · {formatLookupTimestamp(entry.checked_at)}{entry.note && ` · ${entry.note}`}</p>)}
      </HistoryDisclosure>
      <HistoryDisclosure title="Lịch sử phê duyệt" count={data.history?.length || 0}>
        {data.history?.map((entry, index) => <p key={index}>{workflowActionName(entry.action)} · {datefmt(entry.created_at)} {entry.reason && `· ${entry.reason}`}</p>)}
      </HistoryDisclosure>
      <HistoryDisclosure title="Lịch sử chỉnh sửa" count={corrections?.length || 0} error={correctionError} busy={corrections == null && !correctionError}>
        {corrections?.map(entry => <p key={entry.id}><b>{correctionFieldName(entry.field_name)}</b>: {entry.old_value ?? '—'} → {entry.new_value ?? '—'} · {datefmt(entry.corrected_at)}</p>)}
      </HistoryDisclosure>
    </section>
    {message && <div className="toast" role="alert">{message}<button aria-label="Đóng thông báo" onClick={() => setMessage('')}>×</button></div>}
  </>;
}

function HistoryDisclosure({ title, count, error, busy, children }) {
  return <div className="invoice-history-group">
    {error && <p className="error" role="alert">{title}: {error}</p>}
    <details className="history invoice-history">
      <summary><strong>{title}</strong><span>{error ? 'Không tải được' : busy ? 'Đang tải…' : count ? `${count} mục` : 'Chưa có dữ liệu'}</span></summary>
      <div className="invoice-history-content">{busy ? <p>Đang tải lịch sử…</p> : error ? <p>Chưa thể hiển thị lịch sử.</p> : count ? children : <p>Chưa có dữ liệu lịch sử.</p>}</div>
    </details>
  </div>;
}

function useCorrections(id) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [reloadToken, setReloadToken] = useState(0);
  const reload = () => setReloadToken(value => value + 1);
  useEffect(() => {
    let active = true;
    setError('');
    api(`/invoices/${id}/corrections`).then(value => { if (active) setData(value); }).catch(loadError => { if (active) { setData([]); setError(loadError.message); } });
    return () => { active = false; };
  }, [id, reloadToken]);
  return { data, error, reload };
}

function useLookupHistory(id) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const reload = () => setReloadToken(value => value + 1);
  useEffect(() => {
    let active = true;
    setError('');
    setBusy(true);
    api(`/invoices/${id}/lookups`).then(value => { if (active) setData(value); }).catch(loadError => { if (active) { setData([]); setError(loadError.message); } }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [id, reloadToken]);
  return { data, error, busy, reload };
}

function workflowActionName(action) { return ({ submitted: 'Đã gửi phê duyệt', approved: 'Đã phê duyệt', rejected: 'Đã từ chối' })[action] || approvalName(action) || action; }
function correctionFieldName(field) { return ({ invoice_number: 'Số hóa đơn', invoice_symbol: 'Ký hiệu hóa đơn', invoice_date: 'Ngày lập', seller_name: 'Nhà cung cấp', seller_tax_code: 'Mã số thuế nhà cung cấp', buyer_name: 'Người mua', buyer_tax_code: 'Mã số thuế người mua', subtotal: 'Tiền trước thuế', vat_rate: 'Thuế suất VAT', vat_amount: 'Tiền thuế VAT', total_amount: 'Tổng tiền' })[field] || field; }
function PageTitle({ title, description, action }) { return <header className="pagehead"><div><small className="eyebrow">FINTECH OCR / KHÔNG GIAN LÀM VIỆC</small><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-action">{action}</div>}</header>; }
function Status({ value, label }) { if (value === 'draft') return null; const type = value === 'approved' || value === 'valid' || value === 'verified' || value === 'completed' ? 'pill-green' : value === 'rejected' || value === 'error' || value === 'mismatch' ? 'pill-red' : value === 'pending' || value === 'needs_review' ? 'pill-orange' : ''; return <span className={'pill '+type}>{label || approvalName(value) || value || '\u2014'}</span>; }
