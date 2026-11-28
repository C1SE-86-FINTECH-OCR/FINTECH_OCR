import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{MemoryRouter}=require('react-router-dom'),Module=require('node:module'),{buildSync}=require('esbuild');
globalThis.localStorage={getItem:()=>null};
test('Authenticated dashboard renders recent invoices with and without SLA for all roles',()=>{
 const fixture=[{id:1,invoice_number:'TEST-RENDER',seller_name:'Render fixture',total_amount:0,approval_status:'pending',approval_sla:{status:'unknown'}},{id:2,invoice_number:'NO-SLA',total_amount:null,approval_status:'draft'}];
 let source=fs.readFileSync('src/App.jsx','utf8').replace("import InvoiceDetailPage from './InvoiceDetailPage';",'const InvoiceDetailPage=()=>null;');
 const begin=source.indexOf('function useLoad('),end=source.indexOf('const NotificationContext=',begin);
 assert.ok(begin>=0&&end>begin);
 source=source.slice(0,begin)+`function useLoad(path){return {data:path.startsWith('/invoices')?${JSON.stringify(fixture)}:path==='/schedules'?[]:{total_invoices:2,approved:0,pending:1,rejected:0},busy:false,error:null,reload(){}};}\n`+source.slice(end)+'\nexport {HomePage};';
 const output=buildSync({stdin:{contents:source,resolveDir:path.resolve('src'),sourcefile:'App.jsx',loader:'jsx'},bundle:true,write:false,platform:'node',format:'cjs',external:['react','react-router-dom','recharts'],loader:{'.css':'empty','.svg':'dataurl'},define:{'import.meta.env':'{}'}});
 const m=new Module(path.resolve('home-regression.cjs'));m.filename=path.resolve('home-regression.cjs');m.paths=Module._nodeModulePaths(process.cwd());m._compile(output.outputFiles[0].text,m.filename);
 for(const role of ['employee','accountant','admin']){
  const html=renderToStaticMarkup(React.createElement(MemoryRouter,null,React.createElement(m.exports.HomePage,{user:{id:3,full_name:'Render Fixture',role}})));
  assert.ok(html.includes('TEST-RENDER'));assert.ok(html.includes('NO-SLA'));assert.ok(html.includes('sla-unknown'));
 }
});
