import React,{useCallback,useEffect,useRef,useState} from 'react';
import {ExternalLink,RefreshCw,FileText,LoaderCircle,AlertTriangle,CheckCircle2} from 'lucide-react';
import {api,datefmt} from './api';
import {invoiceLinkState} from './travelView.js';
import {aiProcessingState} from './ocrRuntimeInfo.js';
import TaxVerificationCard from './TaxVerificationCard.jsx';

export default function TravelInvoicePreview({invoiceId,onInvoiceChange,fmt}){
 const[data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[tax,setTax]=useState(null),[taxBusy,setTaxBusy]=useState(false),[taxError,setTaxError]=useState(''),[preview,setPreview]=useState({loading:true}),scope=useRef(0),request=useRef(0);
 const load=useCallback(async()=>{const ticket=++request.current;setLoading(true);setError('');onInvoiceChange(null);try{const next=await api('/invoices/'+invoiceId);if(ticket!==request.current)return;setData(next);setTax(null);setTaxError('');onInvoiceChange(next);}catch(e){if(ticket===request.current){setData(null);setError(e.message);}}finally{if(ticket===request.current)setLoading(false);}},[invoiceId,onInvoiceChange]);
 useEffect(()=>{scope.current++;setData(null);setPreview({loading:true});load();return()=>{scope.current++;request.current++;};},[load]);
 useEffect(()=>{if(!data)return;let active=true,url='';setPreview({loading:true});const xml=String(data.filename||'').toLowerCase().endsWith('.xml');
  api(`/invoices/${data.id}/${xml?'file':'thumbnail'}`,{raw:true}).then(async response=>{
   if(xml){const text=await response.text();if(active)setPreview({text:text.slice(0,4000),truncated:text.length>4000});}
   else if((response.headers.get('content-type')||'').startsWith('image/')){url=URL.createObjectURL(await response.blob());if(active)setPreview({url});else URL.revokeObjectURL(url);}
   else if(active)setPreview({error:'Chưa có ảnh xem trước; mở trang Chi tiết để xem chứng từ đầy đủ.'});
  }).catch(e=>{if(active)setPreview({error:e.message});});return()=>{active=false;if(url)URL.revokeObjectURL(url);};
 },[data?.id,data?.filename]);
 if(error)return <div className="travel-invoice-preview travel-wide"><p className="error" role="alert">Không đọc được hóa đơn: {error}</p><button type="button" className="btn btn-outline btn-small" onClick={load}>Tải lại</button></div>;
 if(!data)return <div className="travel-invoice-preview travel-wide" role="status"><LoaderCircle size={16} className="spin"/> Đang tải thông tin hóa đơn…</div>;
 const state=invoiceLinkState(data),ai=aiProcessingState(data.ocr),storedTax=data.ocr?.tax_verification;
 const taxResult=tax||(storedTax&&String(storedTax.tax_code||'').replace(/\D/g,'')===String(data.seller_tax_code||'').replace(/\D/g,'')?storedTax:null);
 const extraction=({completed:'Đã xử lý',failed:'Xử lý thất bại',pending:'Đang chờ xử lý',processing:'Đang xử lý',running:'Đang xử lý',not_available:'Chưa có lần trích xuất được ghi nhận'})[data.extraction_state?.status]||'Chưa có trạng thái trích xuất';
 async function refreshTax(){if(taxBusy||!data.seller_tax_code)return;const ticket=scope.current;setTaxBusy(true);setTaxError('');try{const next=await api(`/invoices/${data.id}/tax-verification`);if(ticket===scope.current)setTax(next);}catch(e){if(ticket===scope.current)setTaxError(e.message);}finally{if(ticket===scope.current)setTaxBusy(false);}}
 return <section className="travel-invoice-preview travel-wide" aria-label="Hóa đơn đang lựa chọn" aria-busy={loading}>
  <div className="panel-heading"><div><strong title={data.filename}>Hóa đơn #{data.id} · {data.invoice_number||'Chưa có số hóa đơn'}</strong><small className="travel-selected-filename" title={data.filename}>{data.filename}</small></div><div className="travel-actions"><a className="btn btn-outline btn-small" href={'/invoices/'+data.id} target="_blank" rel="noopener noreferrer"><ExternalLink size={14}/> Xem chi tiết hóa đơn</a><button type="button" className="iconbtn" disabled={loading} title="Nạp lại sau khi kiểm tra hoặc bổ sung dữ liệu" aria-label="Nạp lại dữ liệu hóa đơn" onClick={load}><RefreshCw size={15} className={loading?'spin':''}/></button></div></div>
  <div className={`travel-invoice-readiness is-${state.state}`} role="status">{state.state==='ready'?<CheckCircle2 size={16}/>:state.state==='processing'?<LoaderCircle size={16} className="spin"/>:<AlertTriangle size={16}/>}<div><strong>{state.label}</strong>{state.reasons.length>0&&<ul>{state.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul>}{state.state==='review'&&<p>Mở Chi tiết hóa đơn để đối chiếu hoặc bổ sung dữ liệu theo quyền hiện có, sau đó nạp lại. Không tự tạo dữ liệu còn thiếu.</p>}</div></div>
  <div className="travel-invoice-snapshot"><div className="travel-document-thumbnail">{preview.loading?<span role="status">Đang tải chứng từ…</span>:preview.url?<a href={'/invoices/'+data.id} target="_blank" rel="noopener noreferrer" title="Xem chứng từ đầy đủ"><img src={preview.url} alt={'Xem trước chứng từ hóa đơn #'+data.id}/></a>:preview.text?<><pre>{preview.text}</pre>{preview.truncated&&<small>Xem trước 4.000 ký tự đầu; trang Chi tiết giữ toàn bộ XML.</small>}</>:<p><FileText size={20}/>{preview.error||'Chưa có ảnh xem trước.'}</p>}</div>
  <dl>{[['Doanh nghiệp',data.seller_name||'Chưa trích xuất'],['MST người bán',data.seller_tax_code||'Chưa trích xuất'],['Ngày lập',data.invoice_date?datefmt(data.invoice_date):'Chưa trích xuất'],['Tổng thanh toán',fmt(data.total_amount)],['VAT',fmt(data.vat_amount)],['Đơn vị tiền tệ',data.currency||'Chưa xác định'],['Trích xuất',extraction],['Hỗ trợ AI',ai?.label||'Không ghi nhận AI tham gia']].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></div>
  {taxResult?<details className="travel-tax-preview"><summary>Đối chiếu thuế · {taxResult.status==='found'?'Đã tìm thấy doanh nghiệp':taxResult.status==='unavailable'?'Nguồn tra cứu chưa khả dụng':'Cần kiểm tra'}</summary><TaxVerificationCard key={data.id} result={taxResult}/></details>:<p className="travel-muted">Chưa có kết quả tra cứu thuế được ghi nhận cho hóa đơn này.</p>}
  {data.seller_tax_code&&<button type="button" className="textbtn" disabled={taxBusy} onClick={refreshTax}><RefreshCw size={13} className={taxBusy?'spin':''}/> {taxBusy?'Đang tra cứu MST…':'Tra cứu lại MST bằng nguồn hiện có'}</button>}{taxError&&<p className="error" role="alert">{taxError}</p>}
  <small className="travel-muted">Tra cứu MST không thay thế xác minh tính pháp lý của hóa đơn. Chỉ các trường có dữ liệu hợp lệ mới được dùng khi liên kết khoản chi.</small>
 </section>;
}
