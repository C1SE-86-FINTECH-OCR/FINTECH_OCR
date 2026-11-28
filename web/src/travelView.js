// Presentation policy mirrors the backend workflow; it never grants API rights.
export function normalizeVndInput(value){
 if(value==null||String(value).trim()==='')throw new Error('Vui lòng nhập số tiền VND.');
 let text=String(value).trim();
 if(/^\d{1,3}(?:\.\d{3})+(?:,0+)?$/.test(text))text=text.split(',')[0].replaceAll('.','');
 else if(/^\d+,0+$/.test(text))text=text.split(',')[0];
 else if(/^\d+\.0+$/.test(text))text=text.split('.')[0];
 if(!/^\d+$/.test(text))throw new Error('Nhập số nguyên đồng, ví dụ 10000000 hoặc 10.000.000; không nhập phần lẻ.');
 const result=BigInt(text).toString();
 if(result.length>16)throw new Error('Số tiền vượt giới hạn lưu trữ của hệ thống.');
 return result;
}
export function moneyCents(value){
 if(value==null||value==='')return null;
 const match=String(value).match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
 return match?(match[1]? -1n:1n)*(BigInt(match[2])*100n+BigInt((match[3]||'').padEnd(2,'0'))):null;
}
export function canonicalTravelNumber(value){
 if(value==null||String(value).trim()==='')return '';
 const text=String(value).trim();
 if(!/^-?\d+(?:[.,]\d+)?$/.test(text))throw new Error('Số không hợp lệ.');
 return text.replace(',','.');
}
export function parseTravelInput(value){
 const text=String(value??'').trim();
 if(text.includes(','))return canonicalTravelNumber(text.replaceAll('.',''));
 if(/^-?\d{1,3}(?:\.\d{3})+$/.test(text))return text.replaceAll('.','');
 return canonicalTravelNumber(text);
}
export function multiplyTravelDecimals(quantity,unitPrice){
 if(quantity==null||quantity===''||unitPrice==null||unitPrice==='')return null;
 const parts=value=>{const raw=canonicalTravelNumber(value);const [whole,fraction='']=raw.split('.');return {integer:BigInt(whole+fraction),scale:fraction.length};};
 const a=parts(quantity),b=parts(unitPrice),product=a.integer*b.integer,scale=a.scale+b.scale;
 const negative=product<0n,raw=(negative?-product:product).toString().padStart(scale+1,'0');
 const result=scale?raw.slice(0,-scale)+'.'+raw.slice(-scale):raw;
 return (negative?'-':'')+result.replace(/(\.\d*?)0+$/,'$1').replace(/\.$/,'');
}
export function formatTravelQuantity(value){
 if(value==null||value==='')return '—';
 const match=String(value).match(/^(-?)(\d+)(?:[.,](\d+))?$/);
 if(!match)return 'Chưa xác định';
 const fraction=(match[3]||'').replace(/0+$/,'');
 return (match[1]||'')+BigInt(match[2]).toLocaleString('vi-VN')+(fraction?','+fraction:'');
}
export function invoiceLinkState(invoice){
 if(!invoice)return {state:'loading',label:'Đang tải thông tin hóa đơn',canLink:false,reasons:[]};
 const extraction=invoice.extraction_state?.status;
 if(['pending','queued','processing','running'].includes(extraction))return {state:'processing',label:'Đang xử lý OCR',canLink:false,reasons:['Chờ OCR hoàn tất trước khi liên kết.']};
 if(invoice.validation_status==='error'||['failed','error'].includes(extraction)||invoice.ocr?.used_pipeline==='none')return {state:'failed',label:'Trích xuất thất bại',canLink:false,reasons:['Tệp gốc vẫn được giữ. Mở Chi tiết hóa đơn để kiểm tra lỗi và dữ liệu.']};
 const reasons=[];
 const currencyObservation=invoice.ocr?.currency_observation;
 if(currencyObservation?.state==='conflicting'||currencyObservation?.state==='observed'&&currencyObservation.code!==invoice.currency)reasons.push('Đơn vị tiền tệ chưa thống nhất với bằng chứng OCR.');
 if(!['bill','einvoice'].includes(invoice.document_type))reasons.push('Chứng từ chưa được xác định là hóa đơn hoặc khoản chi.');
 if(!invoice.currency)reasons.push('Chưa xác định đơn vị tiền tệ.');
 else if(invoice.currency!=='VND')reasons.push('Chi phí chưa phải VND; không tự quy đổi ngoại tệ.');
 if(invoice.total_amount==null||invoice.total_amount==='')reasons.push('Chưa trích xuất được tổng thanh toán.');
 else if(moneyCents(invoice.total_amount)==null||moneyCents(invoice.total_amount)<0n)reasons.push('Tổng thanh toán không hợp lệ.');
 if(!invoice.invoice_date)reasons.push('Chưa xác định ngày lập hóa đơn.');
 return {state:reasons.length||invoice.validation_status==='needs_review'?'review':'ready',label:reasons.length||invoice.validation_status==='needs_review'?'Cần kiểm tra dữ liệu':'Đã có dữ liệu để liên kết',canLink:reasons.length===0,reasons};
}
export function invoiceOptionLabel(invoice){
 const name=invoice.invoice_number||invoice.filename||'Chưa có số hóa đơn';
 return `#${invoice.id} · ${name.length>43?name.slice(0,40)+'…':name}${invoice.total_amount==null?' · Chưa có tổng tiền':''}`;
}
export function positiveRemainder(required,paid){const a=moneyCents(required),b=moneyCents(paid);return a!=null&&b!=null&&a>b;}
export function travelViewState(c,user){
 const t=c.totals||{},status=c.status,employee=user.role==='employee'&&user.id===c.owner_id,accountant=user.role==='accountant'&&user.id!==c.owner_id;
 const editExpenses=employee&&['received','settlement_returned'].includes(status);
 const refundDue=status==='settlement_approved'&&positiveRemainder(t.refund_required,t.refund_paid);
 const kinds=[];
 if(employee&&refundDue&&moneyCents(t.refund_declaration_available)>0n)kinds.push('return_declaration');
 if(accountant&&['advance_approved','disbursed','received'].includes(status)&&positiveRemainder(t.approved,t.issued))kinds.push('disbursement');
 if(accountant&&status==='settlement_approved'){
  if(refundDue)kinds.push('refund');
  if(positiveRemainder(t.supplement_required,t.supplement_paid))kinds.push('supplement');
 }
 const transactions=c.transactions||[],expenses=c.expenses||[];
 const evidenceTargets=[];
 if(editExpenses){
  evidenceTargets.push({value:'',label:'Toàn hồ sơ'});
  expenses.forEach(e=>evidenceTargets.push({value:'expense_id='+e.id,label:`Khoản chi: ${e.description}`}));
  transactions.forEach(tx=>evidenceTargets.push({value:'transaction_id='+tx.id,label:`Giao dịch: ${tx.reference}`}));
 }else if(employee&&refundDue){
  transactions.filter(tx=>tx.kind==='return_declaration'&&tx.actor_id===user.id).forEach(tx=>evidenceTargets.push({value:'transaction_id='+tx.id,label:`Hoàn ứng: ${tx.reference}`}));
 }else if(accountant&&['disbursed','received','settlement_approved'].includes(status)){
  const allowed=status==='settlement_approved'?['refund','supplement']:['disbursement'];
  transactions.filter(tx=>tx.actor_id===user.id&&allowed.includes(tx.kind)).forEach(tx=>evidenceTargets.push({value:'transaction_id='+tx.id,label:`Giao dịch: ${tx.reference}`}));
 }
 const canReceive=employee&&status==='disbursed';
 const moneyKeys=['requested'];
 if(t.approved!=null)moneyKeys.push('approved');
 if(transactions.some(tx=>tx.kind==='disbursement'))moneyKeys.push(status==='disbursed'?'issued':'received');
 if(expenses.length)moneyKeys.push('declared');
 if(['settlement_reviewed','settlement_approved','closed'].includes(status)&&t.accepted_proposed!=null)moneyKeys.push(t.accepted!=null?'accepted':'accepted_proposed');
 if(['settlement_approved','closed'].includes(status))moneyKeys.push('remaining');
 const descriptions={
  advance_draft:'Hoàn thiện đề nghị và gửi Admin phê duyệt.',advance_submitted:'Đề nghị đã gửi. Đang chờ Admin phê duyệt kinh phí.',
  advance_returned:'Admin yêu cầu bổ sung. Chỉnh sửa đề nghị và gửi lại.',advance_rejected:'Đề nghị đã bị từ chối. Xem lý do trước khi chỉnh sửa và gửi lại.',
  advance_approved:'Kinh phí đã được duyệt. Đang chờ Kế toán ghi nhận cấp tiền.',disbursed:'Kế toán đã ghi nhận cấp tiền. Chỉ xác nhận khi bạn đã thực tế nhận tiền.',
  received:'Bạn đã xác nhận nhận tiền. Khai báo khoản chi, liên kết hóa đơn và bổ sung chứng từ trước khi gửi quyết toán.',
  settlement_submitted:'Hồ sơ đã gửi Kế toán kiểm tra. Các khoản chi và chứng từ đang được khóa chỉnh sửa.',
  settlement_returned:'Hồ sơ được trả về. Bổ sung khoản chi hoặc chứng từ theo yêu cầu rồi gửi lại.',settlement_reviewed:'Kế toán đã kiểm tra. Đang chờ Admin phê duyệt cuối cùng; hồ sơ được khóa chỉnh sửa.',
  settlement_approved:refundDue?'Quyết toán đã được duyệt. Khai báo hoàn ứng nếu đã chuyển tiền và đính kèm bằng chứng để Kế toán đối chiếu.':positiveRemainder(t.supplement_required,t.supplement_paid)?'Quyết toán đã được duyệt. Đang chờ Kế toán thanh toán bổ sung.':'Các nghĩa vụ tiền đã được đối chiếu. Đang chờ Kế toán xác nhận đóng hồ sơ.',
  settlement_rejected:'Quyết toán đã bị từ chối. Xem lý do; hồ sơ chỉ được chỉnh sửa khi Admin trả về bổ sung.',closed:'Hồ sơ đã quyết toán. Chỉ xem dữ liệu, chứng từ và lịch sử.'};
 const roleHints=accountant?{advance_approved:'Ghi nhận số tiền thực tế đã cấp, không vượt kinh phí được Admin duyệt.',disbursed:'Theo dõi xác nhận nhận tiền và bổ sung chứng từ cấp tiền của bạn.',settlement_submitted:'Kiểm tra từng khoản chi và bằng chứng, sau đó chuyển Admin hoặc trả về bổ sung.',settlement_approved:'Đối chiếu hoàn ứng/thanh toán bổ sung. Chỉ đóng hồ sơ khi không còn chênh lệch.'}:user.role==='admin'?{advance_submitted:'Xem đề nghị và lịch công tác, sau đó duyệt, từ chối hoặc yêu cầu bổ sung.',settlement_reviewed:'Xem kết quả kiểm tra của Kế toán trước khi phê duyệt quyết toán.'}:{};
 return {employee,accountant,editExpenses,refundDue,kinds,evidenceTargets,canReceive,moneyKeys:[...new Set(moneyKeys)],
  showExpenses:expenses.length>0||editExpenses,showTransactions:transactions.length>0||kinds.length>0,
  guidance:roleHints[status]||descriptions[status]||'Theo dõi trạng thái hồ sơ.',
  legacyFractional:['requested','approved','issued','received'].some(k=>{const n=moneyCents(t[k]);return n!=null&&n%100n!==0n;})};
}
export function travelStages(c){
 const active={advance_draft:0,advance_submitted:1,advance_returned:0,advance_rejected:0,advance_approved:2,disbursed:3,received:4,settlement_returned:4,settlement_submitted:5,settlement_reviewed:6,settlement_approved:7,settlement_rejected:6,closed:8}[c.status]??0;
 return ['Đề nghị','Duyệt tạm ứng','Cấp tiền','Nhận tiền','Khai chi phí','Kế toán kiểm tra','Admin duyệt','Đối chiếu và đóng'].map((label,index)=>({label,state:index<active?'done':index===active?(c.status.endsWith('_rejected')?'rejected':'active'):'pending'}));
}
