import React from 'react';
import {ShieldAlert,AlertTriangle,CircleHelp,CheckCircle2} from 'lucide-react';
import './taxVerification.css';
const levels={low:'Thấp',medium:'Trung bình',high:'Cao',insufficient_data:'Chưa đủ dữ liệu'};
const recommendations={consider_approval:'Có thể xem xét phê duyệt',additional_review:'Cần kiểm tra thêm',priority_review:'Cần ưu tiên kiểm tra rủi ro'};
export default function RiskAssessmentCard({risk}){
 if(!risk)return null;
 if(risk.applicability==='not_applicable')return <section className="tax-card"><strong>Không áp dụng điểm rủi ro hóa đơn</strong><p>{risk.reason}</p></section>;
 const Icon=risk.level==='high'?ShieldAlert:risk.level==='medium'?AlertTriangle:risk.level==='low'?CheckCircle2:CircleHelp;
 return <section className="tax-card" aria-label="Đánh giá rủi ro và hỗ trợ phê duyệt"><header><strong><Icon size={20}/> Mức rủi ro: {levels[risk.level]||'Chưa đánh giá'}</strong><span className={`tax-status ${risk.level==='high'?'tax-comparison-mismatch':risk.level==='low'?'tax-status-found':'tax-status-review'}`}>{risk.score==null?'Chưa đủ căn cứ chấm điểm':`${risk.score}/100 điểm quy tắc`}</span></header>
 <p><strong>{recommendations[risk.recommendation]||'Cần kiểm tra thêm'}</strong></p>
 <small>Đây là dấu hiệu cần xem xét, không phải kết luận gian lận hoặc xác suất gian lận. Quyết định thuộc người có thẩm quyền.</small>
 {risk.generated_at&&<small>Thời điểm đánh giá: {new Date(risk.generated_at).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'})}. Hãy mở bằng chứng hiện tại trước khi quyết định.</small>}
 {risk.signals?.map(signal=><div key={signal.rule}><p><strong>+{signal.points} điểm</strong> · {signal.reason}</p><small>{signal.action}</small></div>)}
 {risk.missing_evidence?.length>0&&<p>Còn {risk.missing_evidence.length} nhóm bằng chứng chưa đủ; không được coi là rủi ro thấp.</p>}
 <details><summary>Chính sách và phạm vi đánh giá</summary><p>Phiên bản: {risk.policy?.version||'Chưa cấu hình'}. Điểm là tổng trọng số tín hiệu được kích hoạt, giới hạn 100. Ngưỡng trung bình: {risk.policy?.medium??'—'}; cao: {risk.policy?.high??'—'}.</p><p>Lịch sử chi tiêu: {risk.history?.sample_count??0} mẫu; {risk.history?.status==='evaluated'?'đã đánh giá theo trung vị và độ lệch tuyệt đối trung vị':'chưa đủ dữ liệu đánh giá'}.</p><p>{risk.document_tampering?.reason}</p></details>
 </section>;
}
