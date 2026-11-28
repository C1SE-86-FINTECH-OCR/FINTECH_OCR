import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
const require=createRequire(import.meta.url);
const {buildSync}=require('esbuild');
const Module=require('node:module');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
globalThis.localStorage={getItem:()=>null};
const bundled=buildSync({entryPoints:[path.resolve('src/FinancePage.jsx')],bundle:true,write:false,platform:'node',format:'cjs',external:['react','recharts'],loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
const compiled=new Module(path.resolve('quality-render.cjs'));compiled.filename=path.resolve('quality-render.cjs');compiled.paths=Module._nodeModulePaths(process.cwd());compiled._compile(bundled.outputFiles[0].text,compiled.filename);
const {format,FinancialAnalysisCard,BudgetSummary,summarizeFinance,financeChartType,default:FinancePage}=compiled.exports;
test('Exact Vietnamese financial display, zero/null and rounding',()=>{
 assert.equal(format('9999999999999999.99'),'9.999.999.999.999.999,99');assert.equal(format('0.005'),'0,01');assert.equal(format('-0.004'),'0');assert.equal(format(null),'Chưa xác định');assert.equal(format(0),'0');
});
test('Financial table and Excel action render; legacy missing VAT is not shown as zero',()=>{
 const data={scope:'own',filters:{group:'category'},rows:[{label:'office',currency:'VND',approved:'8470000.00',pending:'0',vat:'0',missing_vat:1,missing_amounts:0,count:1}],export_url:'/finance/chat-exports/1'};
 const html=renderToStaticMarkup(React.createElement(FinancialAnalysisCard,{data}));
 assert.ok(html.includes('8.470.000'));assert.ok(html.includes('Văn phòng phẩm'));assert.ok(html.includes('Chưa xác định'));assert.ok(html.includes('Xuất Excel'));assert.ok(html.includes('finance-chart'));assert.ok(!html.includes('[object Object]'));
});
test('Budget dates and missing balance remain readable',()=>{
 const html=renderToStaticMarkup(React.createElement(BudgetSummary,{budget:{id:1,starts_on:'2026-11-01',ends_on:'2026-11-30',category:'office',currency:'VND',limit:'1000',approved:'0',pending:'0',remaining:null,utilization_percent:null,missing_amounts:1,alerts:[]}}));
 assert.ok(html.includes('01/11/2026'));assert.ok(html.includes('Văn phòng phẩm'));assert.ok(html.includes('Chưa xác định'));
});
test('Declared light/dark text contrast meets 4.5:1 (static palette, not browser QA)',()=>{
 const luminance=hex=>{const rgb=hex.match(/\w\w/g).map(v=>parseInt(v,16)/255).map(c=>c<=0.04045?c/12.92:((c+0.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722};
 for(const [fg,bg] of [['172033','ffffff'],['eef2f7','172234'],['92400e','ffffff'],['fbbf24','172234']]){const a=luminance(fg),b=luminance(bg);assert.ok((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5)}
});
test('Finance page presentation totals retain exact decimals and separate currencies',()=>{
 const rows=[{currency:'VND',approved:'9999999999999999.99',pending:'0',vat:'0',count:1,missing_amounts:0,missing_vat:0},{currency:'VND',approved:'0.01',pending:'10.10',vat:null,count:2,missing_amounts:1,missing_vat:1},{currency:'USD',approved:'5.25',pending:'0.75',vat:'0',count:1}];
 const values=summarizeFinance(rows);
 assert.equal(values[0].approved,'10000000000000000.00');assert.equal(values[0].pending,'10.10');assert.equal(values[0].vat,null);assert.equal(values[0].count,3);assert.equal(values[0].missingAmounts,1);assert.equal(values[1].approved,'5.25');assert.equal(values[1].vat,'0.00');
 assert.equal(summarizeFinance([{currency:'VND',approved:null,pending:'0',vat:null,count:1}])[0].approved,null);
});
test('One period always renders a bar chart without manufacturing extra periods',()=>{
 assert.equal(financeChartType({chart:'line'},[{label:'2026-11'}]),'bar');assert.equal(financeChartType({chart:'pie'},[{label:'office'}]),'bar');assert.equal(financeChartType({chart:'line'},[{},{}]),'line');
});
test('Redesigned finance view uses existing panels/KPIs and preserves incomplete VAT',()=>{
 const data={scope:'own',filters:{group:'month',starts:'2026-11-01',ends:'2026-11-30'},chart:'line',rows:[{label:'2026-11',currency:'VND',count:2,approved:'8470000.00',pending:'0',vat:'0',missing_vat:1,missing_amounts:0}]};
 const html=renderToStaticMarkup(React.createElement(FinancialAnalysisCard,{data,pageView:true}));
 for(const text of ['kpi-grid','panel finance-chart-panel','finance-statistics-panel','8.470.000','Chưa đủ dữ liệu','Biểu đồ cột','Xuất Excel','01/11/2026'])assert.ok(html.includes(text),text);
 assert.ok(!html.includes('Biểu đồ đường'));assert.ok(html.includes('Thiếu dữ liệu'));
});
test('Finance empty/loading states and role-scoped budget management render distinctly',()=>{
 const loading=renderToStaticMarkup(React.createElement(FinancialAnalysisCard,{data:null,pageView:true,loading:true}));assert.ok(loading.includes('Đang tải dữ liệu'));assert.ok(loading.includes('aria-busy="true"'));
 const empty=renderToStaticMarkup(React.createElement(FinancialAnalysisCard,{data:{scope:'own',filters:{},rows:[]},pageView:true}));assert.ok(empty.includes('Chưa có khoản chi phù hợp'));assert.ok(empty.includes('disabled=""'));
 const employee=renderToStaticMarkup(React.createElement(FinancePage,{user:{role:'employee'}}));assert.ok(employee.includes('pagehead'));assert.ok(employee.includes('report-filters'));assert.ok(!employee.includes('Quản lý ngân sách'));assert.ok(!employee.includes('Nhân viên ID'));
 for(const role of ['accountant','admin']){const reviewer=renderToStaticMarkup(React.createElement(FinancePage,{user:{role}}));assert.ok(reviewer.includes('Quản lý ngân sách'));assert.ok(reviewer.includes('Thiết lập ngân sách'));assert.ok(reviewer.includes('Nhân viên ID'))}
});
