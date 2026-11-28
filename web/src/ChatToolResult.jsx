import React from 'react';
import InvoiceVerificationReport from './InvoiceVerificationReport.jsx';
export default function ChatToolResult({meta}){
 return <>{meta.invoice_id&&<a className="btn btn-outline" href={`/invoices/${meta.invoice_id}`}>Xem hóa đơn #{meta.invoice_id}</a>}{meta.verification_report&&<InvoiceVerificationReport report={meta.verification_report}/>}{meta.risk_invoices?.length>0&&<section className="tax-card"><h3>Hóa đơn cần kiểm tra rủi ro</h3>{meta.risk_invoices.map(row=><p key={row.invoice_id}><a href={`/invoices/${row.invoice_id}`}>Hóa đơn #{row.invoice_id}</a> · {row.score==null?'Chưa có điểm':`${row.score}/100`} · {row.signals?.map(signal=>signal.reason).join('; ')}</p>)}<small>Cảnh báo hỗ trợ kiểm tra, không phải kết luận gian lận.</small></section>}</>;
}
