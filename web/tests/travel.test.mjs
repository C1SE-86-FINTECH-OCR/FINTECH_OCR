import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
const require=createRequire(import.meta.url),React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{MemoryRouter}=require('react-router-dom'),Module=require('node:module'),{buildSync}=require('esbuild');
globalThis.localStorage={getItem:()=>null};
function load(file){const bundle=buildSync({entryPoints:[path.resolve(file)],bundle:true,write:false,platform:'node',format:'cjs',external:['react','recharts','react-router-dom'],loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});const m=new Module(path.resolve('travel-render.cjs'));m.filename=path.resolve('travel-render.cjs');m.paths=Module._nodeModulePaths(process.cwd());m._compile(bundle.outputFiles[0].text,m.filename);return m.exports;}
const Travel=load('src/TravelPage.jsx'),Schedule=load('src/SchedulePage.jsx').default;
const render=(component,user,url='/travel')=>renderToStaticMarkup(React.createElement(MemoryRouter,{initialEntries:[url]},React.createElement(component,{user})));
test('Travel page retains shared design classes and truthful loading for each role',()=>{
 for(const role of ['employee','accountant','admin']){const html=render(Travel.default,{id:3,role});assert.ok(html.includes('pagehead'));assert.ok(html.includes('panel'));assert.ok(html.includes('Đang tải hồ sơ'));assert.ok(!html.includes('NaN'));assert.equal(html.includes('Đề nghị tạm ứng</button>'),role==='employee');}
});
test('Existing main Admin schedule creation remains available',()=>{
 for(const role of ['employee','accountant','admin']){const html=render(Schedule,{id:3,role},'/schedule');assert.equal(html.includes('Phân công công tác'),role==='admin');}
});
test('Advance creation supports existing schedule link without showing simulated money',()=>{
 const html=render(Travel.default,{id:3,role:'employee'},'/travel?schedule=12');assert.ok(html.includes('Lưu nháp đề nghị'));assert.ok(html.includes('Mục đích sử dụng'));assert.ok(!html.includes('value="10.000.000"'));assert.ok(!html.includes('value="10000000"'));
});
