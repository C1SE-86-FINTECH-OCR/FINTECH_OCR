import InvoiceVerificationReport from './InvoiceVerificationReport.jsx';
import React, { useState, useEffect, useRef } from 'react';
import { api } from './api';
import { Building2, CheckCircle2, AlertTriangle, CircleHelp, RefreshCw, ExternalLink } from 'lucide-react';
import './taxVerification.css';

const labels = {tax_code:'Mã số thuế',name:'Tên doanh nghiệp',address:'Địa chỉ',operating_status:'Tình trạng hoạt động',tax_department:'Cơ quan thuế'};
const states = {found:'Đã tìm thấy doanh nghiệp',not_found:'Chưa tìm thấy trên nguồn tra cứu',unavailable:'Tra cứu tạm thời không khả dụng',invalid_or_missing_tax_code:'Chưa có MST hợp lệ'};
const comparisonLabels={match:'Trùng khớp',partial_match:'Khớp một phần',mismatch:'Sai lệch',needs_review:'Cần đối chiếu',insufficient_data:'Chưa đủ dữ liệu',unconfirmed:'Chưa đủ dữ liệu'};
export default function TaxVerificationCard({ result, llmStatus }) {
  const [updated,setUpdated]=useState(null), [busy,setBusy]=useState(false), [error,setError]=useState('');
  const scope=useRef(0),locked=useRef(false);
  useEffect(()=>{
    scope.current+=1;locked.current=false;setUpdated(null);setBusy(false);setError('');
    return ()=>{scope.current+=1;};
  },[result.message_id]);
  const data=updated || result;
  async function refresh(){
    if(locked.current)return;
    locked.current=true;
    const ticket=scope.current;
    setBusy(true);setError('');
    try {const next=await api(`/chatbot/tax-verifications/${data.message_id}/refresh`,{method:'POST'});if(ticket===scope.current)setUpdated(next);}
    catch(e){if(ticket===scope.current)setError(e.message);}finally{if(ticket===scope.current){locked.current=false;setBusy(false);}}
  }
  return <section className="tax-card" aria-label="Kết quả tra cứu thuế">
    <header><strong><Building2 size={20}/> Đối chiếu thông tin thuế</strong><span className={`tax-status tax-status-${data.status==='found'?'found':'review'}`}>{data.status==='found'?<CheckCircle2 size={15}/>:<CircleHelp size={15}/>} {states[data.status] || 'Chưa xác minh'}</span></header>
    <small>{updated ? 'Đã tra cứu lại · Nhận xét tại máy' : llmStatus==='completed' ? 'AI đã đối chiếu dữ kiện nguồn' : llmStatus==='unavailable' ? 'AI tạm thời không khả dụng · Giữ kết quả tra cứu' : 'Nhận xét tại máy'}</small>
    <div className={`tax-comparison tax-comparison-${data.overall_comparison || 'insufficient_data'}`}><strong>Đối chiếu tổng thể: {comparisonLabels[data.overall_comparison] || 'Chưa đủ dữ liệu'}</strong></div>
    {data.comparison_note && <p className="tax-notice">{data.comparison_note}</p>}
    {data.verification_report && <InvoiceVerificationReport report={data.verification_report}/>}
    <dl>{[['MST',data.tax_code],['Doanh nghiệp',data.registered_name],['Địa chỉ',data.registered_address],['Tình trạng hoạt động',data.operating_status],['Cơ quan thuế',data.tax_department]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value || 'Chưa có dữ liệu'}</dd></div>)}</dl>
    <div className="tax-table-scroll"><table><thead><tr><th>Trường</th><th>Trên chứng từ</th><th>Nguồn tra cứu</th><th>Đối chiếu</th></tr></thead><tbody>{data.comparisons?.map(row=><tr key={row.field}><td data-label="Trường">{labels[row.field]}</td><td data-label="Trên chứng từ">{row.observed || 'Chưa có dữ liệu'}</td><td data-label="Nguồn tra cứu">{row.registered || 'Chưa có'}</td><td data-label="Đối chiếu"><span className={`tax-comparison tax-comparison-${row.status}`}>{comparisonLabels[row.status] || 'Chưa đủ dữ liệu'}</span></td></tr>)}</tbody></table></div>
    <small>Nguồn: {data.source}{data.supplementary_source ? ' + '+data.supplementary_source : ''} · {data.checked_at ? new Date(data.checked_at).toLocaleString('vi-VN') : 'Chưa có thời điểm tra cứu'}{data.cached?' · Bộ nhớ đệm':''}</small>
    <p className="tax-notice"><AlertTriangle size={16}/>{data.document_kind==='invoice'?'Chưa xác minh tính hợp pháp của hóa đơn. MST tồn tại không chứng minh hóa đơn hợp pháp.':data.document_kind==='tax_registration'?'Giấy chứng nhận đăng ký thuế: kết quả chỉ đối chiếu thông tin người nộp thuế, không phải xác minh hóa đơn.':'Đây là đối chiếu thông tin doanh nghiệp; chưa đủ căn cứ áp dụng kết luận xác minh hóa đơn.'}</p>
    <footer>{data.document_kind==='invoice' && <a href="https://hoadondientu.gdt.gov.vn/" target="_blank" rel="noopener noreferrer"><ExternalLink size={14}/> Cổng tra cứu hóa đơn</a>}{data.message_id && <button type="button" onClick={refresh} disabled={busy}><RefreshCw size={14} className={busy?'spin':''}/>{busy?'Đang tra cứu…':'Tra cứu lại'}</button>}</footer>
    {error && <p role="alert">{error}</p>}
  </section>;
}
