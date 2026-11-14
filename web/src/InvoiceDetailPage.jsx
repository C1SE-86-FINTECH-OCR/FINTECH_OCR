import React, { useEffect, useState } from 'react';
import { AlertTriangle, ChevronLeft, ExternalLink, FileText, Plus, Save, Trash2 } from 'lucide-react';
import { api, datefmt } from './api';
import { invoiceItemDrafts, invoiceItemPayload, moneyOrDash } from './viewUtils';
import { formatLookupTimestamp, initialLookupOutcome, isSafeHttpUrl } from './lookupUtils';

const editableFields = [
  ['invoice_number', 'Invoice no.'], ['invoice_symbol', 'Invoice symbol'], ['invoice_date', 'Issue date'],
  ['seller_name', 'Supplier'], ['seller_tax_code', 'Supplier tax code'], ['buyer_name', 'Buyer'],
  ['buyer_tax_code', 'Buyer tax code'], ['subtotal', 'Subtotal'], ['vat_rate', 'VAT rate (%)'],
  ['vat_amount', 'VAT amount'], ['total_amount', 'Total amount'],
];

export default function InvoiceDetailPage({ user, id, data, busy, error, reload, onChanged }) {
  const [form, setForm] = useState(null);
  const [message, setMessage] = useState('');
  const [reject, setReject] = useState('');
  const [lookup, setLookup] = useState(initialLookupOutcome);
  const [lookupNote, setLookupNote] = useState('');
  const [original, setOriginal] = useState({ loading: false, url: '', kind: '', text: '', error: '' });
  const { data: corrections, reload: reloadCorrections, error: correctionError } = useCorrections(id);
  const { data: lookupHistory, reload: reloadLookupHistory, error: lookupHistoryError, busy: lookupHistoryBusy } = useLookupHistory(id);
  const canEdit = user.role === 'employee' && ['draft', 'rejected'].includes(data?.approval_status);
  const isReviewer = user.role === 'accountant' || user.role === 'admin';

  useEffect(() => { setLookup(initialLookupOutcome); setLookupNote(''); }, [id]);

  useEffect(() => {
    if (!data) { setForm(null); return; }
    setForm({
      ...Object.fromEntries(editableFields.map(([key]) => [key, data[key] ?? ''])),
      items: invoiceItemDrafts(data.items),
    });
  }, [data]);

  useEffect(() => {
    if (!data?.id) return undefined;
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
      if (!cancelled) setOriginal({ loading: false, url: '', kind: '', text: '', error: fetchError.message || 'Could not load the original file.' });
    });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id, data?.id, data?.filename]);

  async function send(path, body, method = 'POST') {
    setMessage('');
    try {
      const result = await api(path, { method, body });
      if (path.endsWith('/lookup')) { setLookup(initialLookupOutcome); setLookupNote(''); }
      setMessage(method === 'PUT' ? `Changes saved. Validation: ${result?.validation_status || 'updated'}.` : 'Thao tác thành công.');
      reload();
      reloadCorrections();
      reloadLookupHistory();
      onChanged?.();
    } catch (sendError) { setMessage(sendError.message); }
  }

  function save() {
    const items = invoiceItemPayload(form.items);
    if (items.some(item => !item.description || item.amount == null)) {
      setMessage('Mỗi dòng hàng cần có tên và thành tiền hợp lệ. Đơn giá hoặc số lượng chưa có có thể để trống.');
      return;
    }
    const body = Object.fromEntries(Object.entries(form).filter(([key]) => key !== 'items').map(([key, value]) => [
      key, value === '' ? null : ['subtotal', 'vat_rate', 'vat_amount', 'total_amount'].includes(key) ? Number(value) : value,
    ]));
    body.items = items;
    send(`/invoices/${id}`, body, 'PUT');
  }

  function updateItem(index, field, value) {
    setForm(current => ({ ...current, items: current.items.map((item, row) => row === index ? { ...item, [field]: value } : item) }));
  }

  if (busy) return <><PageTitle title="Invoice detail"/><div className="loading">Loading invoice…</div></>;
  if (error || !data) return <><PageTitle title="Invoice detail"/><p className="error">{error || 'Invoice unavailable.'}</p></>;

  return <>
    <PageTitle title="Invoice detail" description="Compare the original document with extracted data, then review or approve." action={<button className="btn btn-muted" onClick={() => history.back()}><ChevronLeft size={16}/> Back</button>}/>
    <div className="detail-grid">
      <section className="panel original">
        <div className="panel-heading"><h3>Original document</h3><span className="pill">{data.document_type}</span></div>
        <div className="file-viewer">
          {original.loading ? <div className="loading">Loading original document…</div> : original.error ? <p className="error">{original.error}</p> : original.kind === 'image' ? <img src={original.url} alt={data.filename || 'Original invoice'} /> : original.kind === 'xml' ? <pre>{original.text}</pre> : original.url ? <iframe title="Original invoice PDF" src={original.url} /> : <div className="empty"><FileText size={30}/><span>Original document unavailable</span></div>}
        </div>
        <p className="file-name">{data.filename}</p>
        <button className="btn btn-outline" disabled={!original.url} onClick={() => window.open(original.url, '_blank', 'noopener,noreferrer')}><ExternalLink size={16}/> Open original file</button>
      </section>

      <section className="panel">
        <div className="panel-heading"><div><h3>Invoice {data.invoice_number || `#${id}`}</h3><span className="helper">{data.seller_name || 'Unknown supplier'}</span></div><Status value={data.approval_status}/></div>
        <div className="pill-row"><Status value={data.validation_status}/><Status value={data.lookup_status}/><span className="pill" title="Completeness ratio of core extracted fields; it is not measured OCR accuracy.">Fields present · {Math.round((data.confidence_score ?? 0) * 100)}%</span></div>
        {isSafeHttpUrl(data.qr_url) && <p className="helper">Invoice QR link: <a href={data.qr_url} target="_blank" rel="noopener noreferrer">{data.qr_url}</a></p>}
        <div className="field-grid">{form && editableFields.map(([key, label]) => <label key={key}>{label}<input type={key === 'invoice_date' ? 'date' : ['subtotal', 'vat_rate', 'vat_amount', 'total_amount'].includes(key) ? 'number' : 'text'} step={['subtotal', 'vat_rate', 'vat_amount', 'total_amount'].includes(key) ? '0.01' : undefined} disabled={!canEdit} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/></label>)}</div>

        <div className="line-items-heading"><h3>Line items</h3>{canEdit && <button className="btn btn-muted btn-small" onClick={() => setForm(current => ({ ...current, items: [...current.items, { description: '', unit: '', quantity: '', unit_price: '', amount: '' }] }))}><Plus size={15}/> Add item</button>}</div>
        {form?.items?.length ? <div className="line-items-scroll"><div className="line-item-table">
          <div className="line-item-row line-item-header"><span>Item name</span><span>Quantity</span><span>Unit price</span><span>Amount</span>{canEdit && <span/>}</div>
          {form.items.map((item, index) => <div className="line-item-row" key={index}>
            <input aria-label={`Item ${index + 1} name`} disabled={!canEdit} value={item.description} onChange={event => updateItem(index, 'description', event.target.value)} />
            {canEdit ? <input aria-label={`Item ${index + 1} quantity`} type="number" min="0" step="any" value={item.quantity} onChange={event => updateItem(index, 'quantity', event.target.value)} placeholder="—" /> : <span>{item.quantity === '' ? '—' : item.quantity}</span>}
            {canEdit ? <input aria-label={`Item ${index + 1} unit price`} type="number" min="0" step="any" value={item.unit_price} onChange={event => updateItem(index, 'unit_price', event.target.value)} placeholder="—" /> : <span className="line-item-money">{moneyOrDash(item.unit_price)}</span>}
            {canEdit ? <input aria-label={`Item ${index + 1} amount`} type="number" min="0" step="any" value={item.amount} onChange={event => updateItem(index, 'amount', event.target.value)} placeholder="Required" /> : <span className="line-item-money">{moneyOrDash(item.amount)}</span>}
            {canEdit && <button className="iconbtn" aria-label={`Remove item ${index + 1}`} onClick={() => setForm(current => ({ ...current, items: current.items.filter((_, row) => row !== index) }))}><Trash2 size={16}/></button>}
          </div>)}
        </div></div> : <div className="empty line-items-empty">No line items returned by the API.</div>}
        {canEdit && <button className="btn btn-primary" onClick={save}><Save size={16}/> Save changes &amp; re-validate</button>}
        {data.warnings?.length > 0 && <div className="warning-box"><AlertTriangle size={18}/><div><strong>Validation findings · {data.validation_status}</strong>{data.warnings.map((warning, index) => <p key={`${warning.rule}-${index}`}>{warning.rule ? `${warning.rule}: ` : ''}{warning.message}</p>)}</div></div>}
        {!data.warnings?.length && <p className="helper">Current validation status: {data.validation_status || '—'}</p>}
      </section>
    </div>

    <section className="panel action-panel">
      <div><h3>Approval workflow</h3><p>Validation, approval and tax lookup are independent statuses.</p></div>
      <div className="action-buttons">{canEdit && <button className="btn btn-primary" onClick={() => send(`/invoices/${id}/submit`)}><span>Submit for approval</span></button>}
        {isReviewer && data.approval_status === 'pending' && <><button className="btn btn-primary" onClick={() => send(`/invoices/${id}/approval`, { action: 'approved' })}>Approve</button><input className="reason" placeholder="Rejection reason (required)" value={reject} onChange={event => setReject(event.target.value)}/><button className="btn btn-outline" onClick={() => send(`/invoices/${id}/approval`, { action: 'rejected', reason: reject })}>Reject</button></>}</div>
      {isReviewer && <div className="lookup"><h3>Semi-manual tax lookup</h3>
        {data.document_type === 'einvoice' ? <><p>Compare the invoice number, symbol, issue date, supplier and tax code, and total above on the official portal. The system does not scrape the portal or certify legal validity. If the portal is unavailable, leave the current status unchanged and try again later.</p><div className="action-buttons"><a className="btn btn-muted" href="https://hoadondientu.gdt.gov.vn/" target="_blank" rel="noopener noreferrer">Open tax portal <ExternalLink size={15}/></a><select aria-label="Manual lookup outcome" value={lookup} onChange={event => setLookup(event.target.value)}><option value="">Select outcome after comparison</option><option value="verified">Verified</option><option value="mismatch">Mismatch</option><option value="not_found">Not found</option></select><input aria-label="Lookup note" placeholder="Optional comparison note" value={lookupNote} onChange={event => setLookupNote(event.target.value)}/><button className="btn btn-primary" disabled={!lookup} onClick={() => send(`/invoices/${id}/lookup`, { result: lookup, note: lookupNote.trim() || null })}>Save lookup result</button></div></> : data.document_type === 'bill' ? <p>This bill is not applicable for tax-portal lookup; accountant review remains manual.</p> : <p>Document type is unknown. Lookup handling is not configured; review the original document and classification before any manual outcome.</p>}
      </div>}
      <div className="history lookup-history"><strong>Tax lookup history</strong>{lookupHistoryError ? <p className="error">{lookupHistoryError}</p> : lookupHistoryBusy ? <p>Loading lookup history…</p> : lookupHistory?.length ? lookupHistory.map(entry => <p key={entry.id}><b>{entry.result}</b> · {entry.checked_by_name || `User #${entry.checked_by}`} · {formatLookupTimestamp(entry.checked_at)}{entry.note && ` · ${entry.note}`}</p>) : <p>No lookup records.</p>}</div>
      <div className="history"><strong>Approval history</strong>{data.history?.length ? data.history.map((entry, index) => <p key={index}>{entry.action} · {datefmt(entry.created_at)} {entry.reason && `· ${entry.reason}`}</p>) : <p>No history yet.</p>}</div>
      <div className="history correction-history"><strong>Correction history</strong>{correctionError ? <p className="error">{correctionError}</p> : corrections?.length ? corrections.map(entry => <p key={entry.id}><b>{entry.field_name}</b>: {entry.old_value ?? '—'} → {entry.new_value ?? '—'} · {datefmt(entry.corrected_at)}</p>) : <p>No corrections recorded.</p>}</div>
    </section>
    {message && <div className="toast" role="alert">{message}<button aria-label="Dismiss message" onClick={() => setMessage('')}>×</button></div>}
  </>;
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

function PageTitle({ title, description, action }) { return <header className="pagehead"><div><small className="eyebrow">FINTECH OCR / WORKSPACE</small><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-action">{action}</div>}</header>; }
function Status({ value }) { const type = value === 'approved' || value === 'valid' || value === 'verified' || value === 'completed' ? 'pill-green' : value === 'rejected' || value === 'error' || value === 'mismatch' ? 'pill-red' : value === 'pending' || value === 'needs_review' ? 'pill-orange' : ''; return <span className={`pill ${type}`}>{({draft:'Nháp',pending:'Chờ duyệt',approved:'Đã duyệt',rejected:'Từ chối',valid:'Hợp lệ',needs_review:'Cần kiểm tra',error:'Lỗi',verified:'Đã xác minh',mismatch:'Không khớp',not_found:'Không tìm thấy',not_checked:'Chưa tra cứu',einvoice:'Hóa đơn điện tử',bill:'Chứng từ',unknown:'Chưa xác định'})[value] || value || '—'}</span>; }
