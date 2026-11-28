import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
import {normalizeVndInput,moneyCents,travelViewState,travelStages,formatTravelQuantity,invoiceLinkState,invoiceOptionLabel} from '../src/travelView.js';
test('Invoice linking preserves zero and separates missing, processing and conflicting data',()=>{
 const invoice={id:48,filename:'a'.repeat(100),document_type:'einvoice',currency:'VND',total_amount:0,invoice_date:'2026-11-28',validation_status:'needs_review'};
 assert.equal(invoiceLinkState(invoice).canLink,true);
 for(const change of [{total_amount:null},{currency:null},{document_type:'other'},{extraction_state:{status:'processing'}},{extraction_state:{status:'failed'}},{ocr:{currency_observation:{state:'observed',code:'USD'}}}])assert.equal(invoiceLinkState({...invoice,...change}).canLink,false);
 assert.equal(formatTravelQuantity('4.0000'),'4');assert.equal(formatTravelQuantity('10.0000'),'10');assert.equal(formatTravelQuantity('4.2500'),'4,25');assert.equal(formatTravelQuantity('0'),'0');
 assert.ok(invoiceOptionLabel(invoice).length<80);
});
const require=createRequire(import.meta.url),React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),Module=require('node:module'),{buildSync}=require('esbuild');
globalThis.localStorage={getItem:()=>null};
function load(file){const bundle=buildSync({entryPoints:[path.resolve(file)],bundle:true,write:false,platform:'node',format:'cjs',external:['react','recharts','react-router-dom'],loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});const m=new Module(path.resolve('travel-ux.cjs'));m.filename=path.resolve('travel-ux.cjs');m.paths=Module._nodeModulePaths(process.cwd());m._compile(bundle.outputFiles[0].text,m.filename);return m.exports;}
const View=load('src/TravelDetailView.jsx').default,Inputs=load('src/TravelInputs.jsx'),{format}=load('src/FinancePage.jsx');
const users={employee:{id:3,role:'employee'},accountant:{id:2,role:'accountant'},admin:{id:1,role:'admin'}};
function fixture(status,extra={}){return {id:1,owner_id:3,status,schedule:{title:'Isolated UX fixture',destination:'Test',starts_at:'2026-11-01T00:00:00Z',ends_at:'2026-11-02T00:00:00Z'},employee_name:'Employee test',purpose:'Unit fixture',transactions:[],expenses:[],evidence:[],history:[],sla_history:[],totals:{requested:'10000000.00',approved:'10000000.00',issued:'10000000.00',received:'10000000.00',declared:'7500000.00',refund_required:'2500000.00',refund_paid:'0.00',refund_declaration_available:'2500000.00',supplement_required:'0.00',supplement_paid:'0.00',remaining:'2500000.00'},...extra};}
function render(c,role){const marker=t=>React.createElement('div',null,t);return renderToStaticMarkup(React.createElement(View,{c,user:users[role],fmt:v=>v==null?'Chưa xác định':format(v)+' đ',stamp:v=>v||'—',Status:({value})=>marker(value),actions:{},txLabels:{disbursement:'Đã cấp tiền'},categoryLabels:{},onBack(){},onReload(){},actionControls:null,expenseEditor:marker('EXPENSE_EDITOR'),transactionForm:marker('TRANSACTION_EDITOR'),evidenceForm:marker('EVIDENCE_EDITOR'),renderExpenseActions:()=>marker('EDIT_EXPENSE'),renderExpenseReview:()=>marker('REVIEW_EXPENSE'),renderReceive:()=>marker('CONFIRM_RECEIVE'),renderEvidence:()=>marker('SAVED_EVIDENCE')}));}
test('Whole VND input stays exact and accepts Vietnamese grouping',()=>{
 for(const raw of ['10000000','10.000.000','10000000.00','10.000.000,00'])assert.equal(normalizeVndInput(raw),'10000000');
 assert.equal(normalizeVndInput('0'),'0');assert.equal(moneyCents('0.01'),1n);assert.equal(moneyCents(null),null);
 for(const raw of ['0.01','0,01','','abc','10.000.000,01','10000000000000000'])assert.throws(()=>normalizeVndInput(raw));
 assert.equal(format('0.01'),'0,01');
});
test('Employee waiting stages have neither evidence uploader nor expense editor',()=>{
 for(const state of ['advance_draft','advance_submitted','advance_approved','disbursed','settlement_submitted','settlement_reviewed','settlement_rejected']){
  const c=fixture(state),v=travelViewState(c,users.employee),html=render(c,'employee');
  assert.equal(v.editExpenses,false,state);assert.equal(v.evidenceTargets.length,0,state);assert.equal(v.kinds.length,0,state);
  for(const marker of ['EVIDENCE_EDITOR','EXPENSE_EDITOR','TRANSACTION_EDITOR'])assert.ok(!html.includes(marker),state+': '+marker);
 }
 assert.ok(render(fixture('advance_approved'),'employee').includes('Đang chờ Kế toán'));
});
test('Receipt confirmation and editing open only in their actual workflow stage',()=>{
 const tx={id:1,kind:'disbursement',actor_id:2,reference:'fixture',amount:'10000000',paid_on:'2026-11-01',received_at:null};
 const issued=fixture('disbursed',{transactions:[tx]});assert.ok(render(issued,'employee').includes('CONFIRM_RECEIVE'));
 for(const state of ['received','settlement_returned']){
  const c=fixture(state,{transactions:[{...tx,received_at:'2026-11-02'}]}),html=render(c,'employee');assert.ok(html.includes('EXPENSE_EDITOR'));assert.ok(html.includes('EVIDENCE_EDITOR'));assert.ok(!html.includes('CONFIRM_RECEIVE'));
 }
});
test('Approved settlements expose only outstanding permitted transactions and proof targets',()=>{
 const c=fixture('settlement_approved');assert.deepEqual(travelViewState(c,users.employee).kinds,['return_declaration']);assert.equal(travelViewState(c,users.employee).evidenceTargets.length,0);
 assert.deepEqual(travelViewState(c,users.accountant).kinds,['refund']);
 const claim={id:5,kind:'return_declaration',actor_id:3,reference:'claim-fixture'};
 c.transactions=[claim];c.totals.refund_declaration_available='0.00';
 const pending=travelViewState(c,users.employee);assert.deepEqual(pending.kinds,[]);assert.deepEqual(pending.evidenceTargets.map(x=>x.value),['transaction_id=5']);
 c.totals.refund_paid='2500000.00';assert.deepEqual(travelViewState(c,users.employee).evidenceTargets,[]);
 c.totals.refund_required='0.00';c.totals.refund_paid='0.00';c.totals.supplement_required='2000000.00';
 assert.deepEqual(travelViewState(c,users.employee).kinds,[]);assert.deepEqual(travelViewState(c,users.accountant).kinds,['supplement']);
});
test('Closed records stay read-only for all roles; timeline and named history remain visible',()=>{
 const c=fixture('closed',{expenses:[{id:1,description:'Test expense',amount:'7500000',accepted:'7500000',review_status:'accepted'}],evidence:[{id:1}],history:[{id:1,action:'transaction_recorded',actor_id:2,actor_name:'Kế toán kiểm thử',actor_role:'accountant',actor_role_source:'event',created_at:'2026-11-02'}]});
 for(const role of Object.keys(users)){
  const html=render(c,role),v=travelViewState(c,users[role]);assert.deepEqual(v.kinds,[]);assert.deepEqual(v.evidenceTargets,[]);assert.equal(v.editExpenses,false);
  for(const marker of ['EVIDENCE_EDITOR','EXPENSE_EDITOR','TRANSACTION_EDITOR','EDIT_EXPENSE','REVIEW_EXPENSE'])assert.ok(!html.includes(marker),role+': '+marker);
  assert.ok(html.includes('Kế toán kiểm thử'));assert.ok(html.includes('SAVED_EVIDENCE'));assert.ok(!html.includes('Người thực hiện #'));
 }
 assert.equal(travelStages(c).filter(s=>s.state==='done').length,8);
});
test('Legacy fractional money is shown unchanged with an explicit notice',()=>{
 const c=fixture('disbursed');c.totals.requested=c.totals.approved='0.01';assert.ok(render(c,'employee').includes('0,01 đ'));assert.ok(render(c,'employee').includes('giữ nguyên số liệu gốc'));
});
test('Professional upload has hidden native input, keyboard entry and actual size labels',()=>{
 const html=renderToStaticMarkup(React.createElement(Inputs.TravelFileUpload,{onUpload:async()=>{},label:'Đính kèm chứng từ'}));
 assert.ok(html.includes('hidden=""'));assert.ok(html.includes('role="button"'));assert.ok(html.includes('tabindex="0"'));assert.ok(html.includes('20 MB'));assert.ok(!html.includes('Chọn tệp'));
 assert.equal(Inputs.fileSize(1048576),'1.0 MB');
});
