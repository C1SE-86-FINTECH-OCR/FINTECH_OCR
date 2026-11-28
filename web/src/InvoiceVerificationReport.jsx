import RiskAssessmentCard from './RiskAssessmentCard.jsx';
import {BudgetSummary} from './FinancePage.jsx';
import React, {useEffect,useState} from 'react';
import {api} from './api';
import './taxVerification.css';
function confidenceLabel(field){
 if(field.status==='low')return 'Cần kiểm tra theo chính sách confidence đã duyệt';
 if(field.ocr_word_scores?.length)return 'Điểm từ OCR: '+field.ocr_word_scores.join(', ');
 return 'Chưa đánh giá';
}
const labels={exact:'Trùng file chính xác',suspected:'Nghi ngờ trùng',not_detected:'Chưa phát hiện trùng',consistent:'Nhất quán',mismatch:'Sai lệch',needs_review:'Cần kiểm tra',insufficient_data:'Chưa đủ dữ liệu',not_applicable:'Không áp dụng',unavailable:'Chưa kiểm tra được'};
export function InvoiceVerificationPanel({invoiceId}){
 const [open,setOpen]=useState(false);
 return <details onToggle={event=>setOpen(event.currentTarget.open)}><summary>Báo cáo kiểm tra hóa đơn</summary>{open&&<InvoiceVerificationReport invoiceId={invoiceId}/>}</details>;
}
export default function InvoiceVerificationReport({invoiceId,report,revision,canAssess=false}){
 const [loaded,setLoaded]=useState(null),[error,setError]=useState('');
 const [saving,setSaving]=useState(false);
 const [riskHistory,setRiskHistory]=useState([]);
 useEffect(()=>{let active=true;setRiskHistory([]);if(invoiceId&&canAssess)api(`/invoices/${invoiceId}/risk-assessments`).then(rows=>{if(active)setRiskHistory(rows)}).catch(()=>{});return()=>{active=false}},[invoiceId,canAssess]);
 async function assess(){if(saving)return;setSaving(true);setError('');try{setLoaded(await api(`/invoices/${invoiceId}/risk-assessments`,{method:'POST'}));setRiskHistory(await api(`/invoices/${invoiceId}/risk-assessments`));}catch{setError('Không lưu hoặc tải lại được đánh giá; kiểm tra lịch sử trước khi thử lại.');}finally{setSaving(false);}}
 useEffect(()=>{let active=true;setLoaded(null);setError('');if(invoiceId)api(`/invoices/${invoiceId}/verification-report`).then(data=>{if(active)setLoaded(data)}).catch(()=>{if(active)setError('Chưa tải được báo cáo kiểm tra.')});return()=>{active=false}},[invoiceId,revision]);
 const data=loaded||report;
 if(!data)return error?<p role="status">{error}</p>:null;
 return <section className="tax-card" aria-label="Báo cáo kiểm tra hóa đơn"><header><strong>Báo cáo kiểm tra hóa đơn</strong></header>
 <RiskAssessmentCard risk={data.risk}/>
 {data.expense_category&&<p>Danh mục đề xuất: <strong>{data.expense_category.category}</strong> · {data.expense_category.reason}</p>}
 {data.budget?.budgets?.map(b=><BudgetSummary key={b.id} budget={b}/>)}
 {data.budget?.status==='reviewer_required'&&<small>Ngân sách được kiểm tra bởi người có thẩm quyền trước khi phê duyệt.</small>}
 {canAssess&&invoiceId&&<button type="button" className="btn btn-outline" disabled={saving} onClick={assess}>{saving?'Đang lưu…':'Đánh giá lại và lưu lịch sử rủi ro'}</button>}
 {canAssess&&<details><summary>Lịch sử đánh giá rủi ro ({riskHistory.length})</summary>{riskHistory.map((snapshot,index)=><p key={index}>{snapshot.generated_at?new Date(snapshot.generated_at).toLocaleString('vi-VN'):'Chưa có thời điểm'} · {snapshot.assessment_origin==='review'?`Người đánh giá #${snapshot.reviewed_by}`:'Đánh giá khi upload'} · {snapshot.score==null?'Chưa đủ dữ liệu':`${snapshot.score}/100 điểm quy tắc`}</p>)}</details>}
 {error&&<p role="alert">{error}</p>}
 <p>Tra cứu thuế: <strong>{data.tax?.status==='found'?'Đã tìm thấy doanh nghiệp':data.tax?.status==='not_found'?'Chưa tìm thấy trên nguồn tra cứu':data.tax?.status==='unavailable'?'Nguồn tra cứu chưa khả dụng':'Chưa đủ dữ liệu'}</strong>{data.tax?.registered_name?' · '+data.tax.registered_name:''}</p>
 <p>Trùng lặp: <strong>{labels[data.duplicates?.status]||'Chưa đánh giá'}</strong></p>
 {data.duplicates?.coverage_incomplete&&<small>Phạm vi tìm kiếm bị giới hạn; chưa kết luận đã kiểm tra toàn bộ dữ liệu.</small>}
 {data.duplicates?.matches?.map(m=><p key={m.invoice_id?`invoice-${m.invoice_id}`:`chat-${m.chat_message_id}`}><a href={m.invoice_id?`/invoices/${m.invoice_id}`:`/chat?conversation=${m.conversation_id}`}>{m.invoice_id?`Hóa đơn #${m.invoice_id}`:`Cuộc trò chuyện #${m.conversation_id}`}</a> · {m.reasons.map(reason=>({identical_file_sha256:'Nội dung file giống hệt',matching_invoice_identity_and_total:'Trùng thông tin định danh và tổng tiền',similar_visual_dhash_advisory:'Hình ảnh tương tự, cần đối chiếu'})[reason]||reason).join('; ')}</p>)}
 <p>Số học: <strong>{labels[data.financial?.status]||'Chưa đánh giá'}</strong></p>
 <details><summary>Chi tiết kiểm tra số liệu</summary>{data.financial?.checks?.map((c,i)=><p key={i}>{c.line_no?`Dòng ${c.line_no}: `:''}{c.message||'Số lượng × đơn giá so với thành tiền'} · {labels[c.status]||c.status}{c.difference!=null?` · Chênh lệch ${c.difference}`:''}</p>)}</details>
 <details><summary>Bằng chứng độ tin cậy từng trường</summary><small>Không có điểm accuracy hoặc ngưỡng confidence được phê duyệt. Điểm từ OCR không phải xác suất trường đúng.</small>{Object.entries(data.confidence?.fields||{}).map(([key,field])=><p key={key}>{({seller_name:'Nhà cung cấp',seller_tax_code:'MST',invoice_number:'Số hóa đơn',invoice_date:'Ngày lập',vat_amount:'VAT',total_amount:'Tổng tiền'})[key]||key}: {confidenceLabel(field)}</p>)}</details>
 <small>Kết quả hỗ trợ rà soát, không xác minh tính hợp pháp và không tự phê duyệt hóa đơn.</small></section>
}
