import React, { useEffect, useState } from 'react';
import { AlertTriangle, ChevronLeft, ExternalLink, FileText, Plus, Save, Trash2 } from 'lucide-react';
import { api, approvalName, datefmt, documentTypeName } from './api';
import { invoiceItemDrafts, invoiceItemPayload, moneyOrDash } from './viewUtils';
import { formatLookupTimestamp, initialLookupOutcome, isSafeHttpUrl } from './lookupUtils';

const editableFields = [
  ['invoice_number', 'Số hóa đơn'], ['invoice_symbol', 'Ký hiệu hóa đơn'], ['invoice_date', 'Ngày lập'],
  ['seller_name', 'Nhà cung cấp'], ['seller_tax_code', 'Mã số thuế nhà cung cấp'], ['buyer_name', 'Người mua'],
  ['buyer_tax_code', 'Mã số thuế người mua'], ['subtotal', 'Tiền trước thuế'], ['vat_rate', 'Thuế suất VAT (%)'],
  ['vat_amount', 'Tiền thuế VAT'], ['total_amount', 'Tổng tiền'],
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
      if (!cancelled) setOriginal({ loading: false, url: '', kind: '', text: '', error: fetchError.message || "Không tải được tệp gốc." });
    });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id, data?.id, data?.filename]);

  async function send(path, body, method = 'POST') {
    setMessage('');
    try {
      const result = await api(path, { method, body });
      if (path.endsWith('/lookup')) { setLookup(initialLookupOutcome); setLookupNote(''); }
      setMessage(method === 'PUT' ? `Đã lưu thay đổi. Trạng thái kiểm tra: ${approvalName(result?.validation_status) || 'Đã cập nhật'}.` : 'Thao tác thành công.');
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

  if (busy) return <><PageTitle title="Chi tiết hóa đơn"/><div className="loading">Đang tải hóa đơn…</div></>;
  if (error || !data) return <><PageTitle title="Chi tiết hóa đơn"/><p className="error">{error || "Không tìm thấy hóa đơn."}</p></>;

  return <>
    <PageTitle title="Chi tiết hóa đơn" description="Đối chiếu chứng từ gốc với dữ liệu trích xuất, sau đó xem xét hoặc phê duyệt." action={<button className="btn btn-muted" onClick={() => history.back()}><ChevronLeft size={16}/>Quay lại</button>}/>
    <div className="detail-grid">
      <section className="panel original">
        <div className="panel-heading"><h3>Chứng từ gốc</h3><span className="pill">{documentTypeName(data.document_type)}</span></div>
        <div className="file-viewer">
          {original.loading ? <div className="loading">Đang tải chứng từ gốc…</div> : original.error ? <p className="error">{original.error}</p> : original.kind === 'image' ? <img src={original.url} alt={data.filename || "Hóa đơn gốc"} /> : original.kind === 'xml' ? <pre>{original.text}</pre> : original.url ? <iframe title="Tệp PDF hóa đơn gốc" src={original.url} /> : <div className="empty"><FileText size={30}/><span>Không thể hiển thị chứng từ gốc</span></div>}
        </div>
        <p className="file-name">{data.filename}</p>
        <button className="btn btn-outline" disabled={!original.url} onClick={() => window.open(original.url, '_blank', 'noopener,noreferrer')}><ExternalLink size={16}/>Mở tệp gốc</button>
      </section>

      <section className="panel">
        <div className="panel-heading"><div><h3>Hóa đơn {data.invoice_number || `#${id}`}</h3><span className="helper">{data.seller_name || "Chưa xác định nhà cung cấp"}</span></div><Status value={data.approval_status}/></div>
        <div className="pill-row"><Status value={data.validation_status}/><Status value={data.lookup_status}/><span className="pill" title="Tỷ lệ đầy đủ của các trường dữ liệu chính; đây không phải độ chính xác OCR.">Trường đã có dữ liệu ·{Math.round((data.confidence_score ?? 0) * 100)}%</span></div>
        {isSafeHttpUrl(data.qr_url) && <p className="helper">Liên kết QR hóa đơn:<a href={data.qr_url} target="_blank" rel="noopener noreferrer">{data.qr_url}</a></p>}
        <div className="field-grid">{form && editableFields.map(([key, label]) => <label key={key}>{label}<input type={key === 'invoice_date' ? 'date' : ['subtotal', 'vat_rate', 'vat_amount', 'total_amount'].includes(key) ? 'number' : 'text'} step={['subtotal', 'vat_rate', 'vat_amount', 'total_amount'].includes(key) ? '0.01' : undefined} disabled={!canEdit} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/></label>)}</div>

        <div className="line-items-heading"><h3>Dòng hàng hóa/dịch vụ</h3>{canEdit && <button className="btn btn-muted btn-small" onClick={() => setForm(current => ({ ...current, items: [...current.items, { description: '', unit: '', quantity: '', unit_price: '', amount: '' }] }))}><Plus size={15}/>Thêm dòng hàng</button>}</div>
        {form?.items?.length ? <div className="line-items-scroll"><div className="line-item-table">
          <div className="line-item-row line-item-header"><span>Tên hàng hóa/dịch vụ</span><span>Số lượng</span><span>Đơn giá</span><span>Số tiền</span>{canEdit && <span/>}</div>
          {form.items.map((item, index) => <div className="line-item-row" key={index}>
            <input aria-label={`Dòng hàng ${index + 1} tên`} disabled={!canEdit} value={item.description} onChange={event => updateItem(index, 'description', event.target.value)} />
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} số lượng`} type="number" min="0" step="any" value={item.quantity} onChange={event => updateItem(index, 'quantity', event.target.value)} placeholder="—" /> : <span>{item.quantity === '' ? '—' : item.quantity}</span>}
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} đơn giá`} type="number" min="0" step="any" value={item.unit_price} onChange={event => updateItem(index, 'unit_price', event.target.value)} placeholder="—" /> : <span className="line-item-money">{moneyOrDash(item.unit_price)}</span>}
            {canEdit ? <input aria-label={`Dòng hàng ${index + 1} thành tiền`} type="number" min="0" step="any" value={item.amount} onChange={event => updateItem(index, 'amount', event.target.value)} placeholder="Bắt buộc" /> : <span className="line-item-money">{moneyOrDash(item.amount)}</span>}
            {canEdit && <button className="iconbtn" aria-label={`Xóa dòng hàng ${index + 1}`} onClick={() => setForm(current => ({ ...current, items: current.items.filter((_, row) => row !== index) }))}><Trash2 size={16}/></button>}
          </div>)}
        </div></div> : <div className="empty line-items-empty">API không trả về dòng hàng nào.</div>}
        {canEdit && <button className="btn btn-primary" onClick={save}><Save size={16}/> Lưu thay đổi và kiểm tra lại</button>}
        {data.warnings?.length > 0 && <div className="warning-box"><AlertTriangle size={18}/><div><strong>Kết quả kiểm tra ·{data.validation_status}</strong>{data.warnings.map((warning, index) => <p key={`${warning.rule}-${index}`}>{warning.rule ? `${warning.rule}: ` : ''}{warning.message}</p>)}</div></div>}
        {!data.warnings?.length && <p className="helper">Trạng thái kiểm tra hiện tại:{data.validation_status || '—'}</p>}
      </section>
    </div>

    <section className="panel action-panel">
      <div><h3>Quy trình phê duyệt</h3><p>Trạng thái kiểm tra, phê duyệt và tra cứu thuế được quản lý độc lập.</p></div>
      <div className="action-buttons">{canEdit && <button className="btn btn-primary" onClick={() => send(`/invoices/${id}/submit`)}><span>Gửi phê duyệt</span></button>}
        {isReviewer && data.approval_status === 'pending' && <><button className="btn btn-primary" onClick={() => send(`/invoices/${id}/approval`, { action: 'approved' })}>Phê duyệt</button><input className="reason" placeholder="Lý do từ chối (bắt buộc)" value={reject} onChange={event => setReject(event.target.value)}/><button className="btn btn-outline" onClick={() => send(`/invoices/${id}/approval`, { action: 'rejected', reason: reject })}>Từ chối</button></>}</div>
      {isReviewer && <div className="lookup"><h3>Tra cứu thuế bán thủ công</h3>
        {data.document_type === 'einvoice' ? <><p>Đối chiếu số hóa đơn, ký hiệu, ngày lập, nhà cung cấp, mã số thuế và tổng tiền ở trên với cổng tra cứu chính thức. Hệ thống không tự động thu thập dữ liệu từ cổng và không chứng nhận tính hợp pháp. Nếu cổng không khả dụng, hãy giữ nguyên trạng thái và thử lại sau.</p><div className="action-buttons"><a className="btn btn-muted" href="https://hoadondientu.gdt.gov.vn/" target="_blank" rel="noopener noreferrer">Mở cổng tra cứu thuế<ExternalLink size={15}/></a><select aria-label="Kết quả tra cứu thủ công" value={lookup} onChange={event => setLookup(event.target.value)}><option value="">Chọn kết quả sau khi đối chiếu</option><option value="verified">Đã xác minh</option><option value="mismatch">Không khớp</option><option value="not_found">Không tìm thấy</option></select><input aria-label="Ghi chú tra cứu" placeholder="Ghi chú đối chiếu (không bắt buộc)" value={lookupNote} onChange={event => setLookupNote(event.target.value)}/><button className="btn btn-primary" disabled={!lookup} onClick={() => send(`/invoices/${id}/lookup`, { result: lookup, note: lookupNote.trim() || null })}>Lưu kết quả tra cứu</button></div></> : data.document_type === 'bill' ? <p>Chứng từ này không thuộc diện tra cứu trên cổng thuế; kế toán tiếp tục kiểm tra thủ công.</p> : <p>Chưa xác định được loại chứng từ. Chưa thể thực hiện tra cứu; hãy kiểm tra chứng từ gốc và phân loại trước khi ghi nhận kết quả.</p>}
      </div>}
      <div className="history lookup-history"><strong>Lịch sử tra cứu thuế</strong>{lookupHistoryError ? <p className="error">{lookupHistoryError}</p> : lookupHistoryBusy ? <p>Đang tải lịch sử tra cứu thuế…</p> : lookupHistory?.length ? lookupHistory.map(entry => <p key={entry.id}><b>{approvalName(entry.result)}</b> · {entry.checked_by_name || `Người dùng #${entry.checked_by}`} · {formatLookupTimestamp(entry.checked_at)}{entry.note && ` · ${entry.note}`}</p>) : <p>Chưa có lịch sử tra cứu.</p>}</div>
      <div className="history"><strong>Lịch sử phê duyệt</strong>{data.history?.length ? data.history.map((entry, index) => <p key={index}>{workflowActionName(entry.action)} · {datefmt(entry.created_at)} {entry.reason && `· ${entry.reason}`}</p>) : <p>Chưa có lịch sử.</p>}</div>
      <div className="history correction-history"><strong>Lịch sử chỉnh sửa</strong>{correctionError ? <p className="error">{correctionError}</p> : corrections?.length ? corrections.map(entry => <p key={entry.id}><b>{correctionFieldName(entry.field_name)}</b>: {entry.old_value ?? '—'} → {entry.new_value ?? '—'} · {datefmt(entry.corrected_at)}</p>) : <p>Chưa ghi nhận chỉnh sửa nào.</p>}</div>
    </section>
    {message && <div className="toast" role="alert">{message}<button aria-label="Đóng thông báo" onClick={() => setMessage('')}>×</button></div>}
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

function workflowActionName(action) { return ({ submitted: 'Đã gửi phê duyệt', approved: 'Đã phê duyệt', rejected: 'Đã từ chối' })[action] || approvalName(action) || action; }
function correctionFieldName(field) { return ({ invoice_number: 'Số hóa đơn', invoice_symbol: 'Ký hiệu hóa đơn', invoice_date: 'Ngày lập', seller_name: 'Nhà cung cấp', seller_tax_code: 'Mã số thuế nhà cung cấp', buyer_name: 'Người mua', buyer_tax_code: 'Mã số thuế người mua', subtotal: 'Tiền trước thuế', vat_rate: 'Thuế suất VAT', vat_amount: 'Tiền thuế VAT', total_amount: 'Tổng tiền' })[field] || field; }
function PageTitle({ title, description, action }) { return <header className="pagehead"><div><small className="eyebrow">FINTECH OCR / KHÔNG GIAN LÀM VIỆC</small><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-action">{action}</div>}</header>; }
function Status({ value }) { const type = value === 'approved' || value === 'valid' || value === 'verified' || value === 'completed' ? 'pill-green' : value === 'rejected' || value === 'error' || value === 'mismatch' ? 'pill-red' : value === 'pending' || value === 'needs_review' ? 'pill-orange' : ''; return <span className={'pill '+type}>{approvalName(value) || value || '\u2014'}</span>; }
