import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
const require=createRequire(import.meta.url),{buildSync}=require('esbuild'),Module=require('node:module'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
globalThis.localStorage={getItem:()=>null};
function load(file){const bundle=buildSync({entryPoints:[path.resolve(file)],bundle:true,write:false,platform:'node',format:'cjs',external:['react','recharts'],loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});const compiled=new Module(path.resolve('sla-render.cjs'));compiled.filename=path.resolve('sla-render.cjs');compiled.paths=Module._nodeModulePaths(process.cwd());compiled._compile(bundle.outputFiles[0].text,compiled.filename);return compiled.exports;}
const {SLABadge,SLAOverview}=load('src/ApprovalSLA.jsx'),FinancePage=load('src/FinancePage.jsx').default;
test('Only Employee finance filters receive the right-aligned action layout',()=>{
 for(const role of ['employee','accountant','admin']){const html=renderToStaticMarkup(React.createElement(FinancePage,{user:{role}}));assert.equal(html.includes('finance-filter-employee'),role==='employee');}
});
test('SLA badges distinguish deadline, final decision and missing processing evidence',()=>{
 const sample={submitted_at:'2026-11-23T03:00:00Z',due_at:'2026-11-26T03:00:00Z',remaining_working_seconds:86400,overdue_seconds:0};
 for(const [status,label] of Object.entries({in_time:'Trong hạn',due_soon:'Sắp đến hạn',overdue:'Quá hạn',approved:'Đã phê duyệt',rejected:'Đã từ chối',unknown:'Thiếu lịch sử xử lý'})){
  const html=renderToStaticMarkup(React.createElement(SLABadge,{sla:{...sample,status,...['approved','rejected'].includes(status)?{processed_at:'2026-11-25T03:00:00Z'}:{},...status==='overdue'?{overdue_seconds:3600}:{}}}));assert.ok(html.includes(label));assert.ok(!html.includes('NaN'));assert.ok(html.includes('26/11/26'));if(status==='unknown')assert.ok(!html.includes('Còn '));
 }
});
test('SLA loading and absent deadline are explicit for all three roles',()=>{
 for(const role of ['employee','accountant','admin']){assert.ok(renderToStaticMarkup(React.createElement(SLAOverview,{user:{role}})).includes('Đang tải thời hạn'));}
 assert.ok(renderToStaticMarkup(React.createElement(SLABadge,{})).includes('Chưa có hạn được ghi nhận'));
});
