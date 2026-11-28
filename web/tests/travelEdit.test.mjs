import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
import {formatTravelQuantity,canonicalTravelNumber,parseTravelInput,multiplyTravelDecimals} from '../src/travelView.js';
const require=createRequire(import.meta.url),Module=require('node:module'),{buildSync}=require('esbuild');
globalThis.localStorage={getItem:()=>null};
function harness(){
 const slots=[];let cursor=0;const calls=[];
 const state=initial=>{const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],v=>{slots[i]=typeof v==='function'?v(slots[i]):v;}];};
 const react={createElement:(type,props,...children)=>({type,props:{...props,children:children.flat(Infinity)}}),Fragment:'fragment',forwardRef:f=>f,memo:f=>f,useState:state,useRef:initial=>state(()=>({current:initial}))[0],useEffect:()=>{},useCallback:f=>f,useId:()=> 'isolated'};
 const bundle=buildSync({stdin:{contents:"export * from './TravelPage.jsx';export {TravelDecimalInput,VndInput} from './TravelInputs.jsx';",resolveDir:path.resolve('src'),sourcefile:'travel-test.jsx',loader:'jsx'},bundle:true,write:false,platform:'node',format:'cjs',external:['react','recharts','react-router-dom','./api'],loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
 const m=new Module(path.resolve('travel-edit-test.cjs'));m.filename=path.resolve('travel-edit-test.cjs');m.paths=Module._nodeModulePaths(process.cwd());const original=m.require.bind(m);
 m.require=name=>name==='react'?react:name==='./api'?{api:async(url,options)=>{calls.push({url,...options});return {id:7};}}:original(name);
 m._compile(bundle.outputFiles[0].text,m.filename);
 return {components:m.exports,calls,render:(component,props)=>{cursor=0;return component(props);}};
}
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of node.props?.children||[]){const found=find(child,predicate);if(found)return found;}return null;}
const expense={id:9,invoice_id:null,description:'Fixture',category:'travel',occurred_on:'2026-11-28',quantity:'4.0000',unit_price:'50000.0000',amount:'200000.00',purpose:'Fixture only',no_invoice_reason:'Fixture'};
test('Vietnamese display preserves meaningful decimals and exact input strings',()=>{
 for(const [raw,expected] of [['4,0000','4'],['4.0000','4'],['50000,0000','50.000'],['200000.00','200.000'],['4.1250','4,125'],['0.01','0,01']])assert.equal(formatTravelQuantity(raw),expected);
 assert.equal(parseTravelInput('50.000,1250'),'50000.1250');assert.equal(parseTravelInput('4,0000'),'4.0000');assert.equal(canonicalTravelNumber('50000.0000'),'50000.0000');
});
test('Open, cancel and save expense events preserve untouched original numeric values',async()=>{
 const h=harness();let opened=0,cancelled=0,saved=0;
 const actions=h.render(h.components.ExpenseActions,{c:{id:7},expense,onEdit:()=>opened++,onSaved:()=>{}});
 find(actions,n=>n.props.title==='Sửa khoản chi').props.onClick();assert.equal(opened,1);
 const formHarness=harness(),props={c:{id:7,expenses:[expense]},expense,onSaved:()=>saved++,onCancel:()=>cancelled++};
 let tree=formHarness.render(formHarness.components.ExpenseForm,props);
 find(tree,n=>n.type==='button'&&n.props.type==='button').props.onClick();assert.equal(cancelled,1);assert.equal(formHarness.calls.length,0);
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 assert.equal(saved,1);assert.equal(cancelled,2);assert.equal(formHarness.calls[0].method,'PUT');
 for(const key of ['quantity','unit_price','amount'])assert.equal(formHarness.calls[0].body[key],expense[key]);
});
test('Editing quantities sends exact decimal strings without binary rounding',async()=>{
 const h=harness(),props={c:{id:7,expenses:[expense]},expense,onSaved(){},onCancel(){}};
 let tree=h.render(h.components.ExpenseForm,props);
 find(tree,n=>n.props.value===expense.quantity&&typeof n.type==='function').props.onChange({target:{value:'2.5000'}});
 tree=h.render(h.components.ExpenseForm,props);
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 assert.equal(h.calls[0].body.quantity,'2.5000');assert.equal(h.calls[0].body.unit_price,'50000.0000');assert.equal(h.calls[0].body.amount,'125000');
 // Total follows quantity edits; arithmetic uses exact decimal strings.
});
test('Legacy fractional amount is not rounded by opening and saving',async()=>{
 const h=harness(),original={...expense,quantity:null,unit_price:null,amount:'0.01'};
 const tree=h.render(h.components.ExpenseForm,{c:{id:7,expenses:[original]},expense:original,onSaved(){},onCancel(){}});
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 assert.equal(h.calls[0].body.amount,'0.01');assert.equal(h.calls[0].body.quantity,null);
});
test('Focus and blur keep formatted values without rewriting untouched API decimals',()=>{
 for(const [raw,display] of [['4.0000','4'],['50000.0000','50.000'],['200000.00','200.000'],['0.01','0,01']]){
  const h=harness(),changes=[],props={value:raw,onChange:e=>changes.push(e.target.value)};
  let input=h.render(h.components.TravelDecimalInput,props);assert.equal(input.props.value,display);
  input.props.onFocus();input=h.render(h.components.TravelDecimalInput,props);assert.equal(input.props.value,display);
  input.props.onBlur({target:{value:display}});input=h.render(h.components.TravelDecimalInput,props);assert.equal(input.props.value,display);assert.deepEqual(changes,[]);
 }
});
test('Whole VND keeps comma zero decimals distinct from thousand grouping',()=>{
 for(const [typed,expected] of [['10,000','10'],['10.000','10000'],['10.000.000','10000000']]){
  const h=harness(),changes=[],input=h.render(h.components.TravelDecimalInput,{whole:true,value:'10',onChange:e=>changes.push(e.target.value)});
  input.props.onChange({target:{value:typed,setCustomValidity(){}}});assert.deepEqual(changes,[expected]);
 }
});
test('Five units at 50000 updates total to 250000 and survives reopening',async()=>{
 const h=harness(),props={c:{id:7,expenses:[expense]},expense,onSaved(){},onCancel(){}};
 let tree=h.render(h.components.ExpenseForm,props);
 find(tree,n=>n.props.value===expense.quantity&&typeof n.type==='function').props.onChange({target:{value:'5'}});
 tree=h.render(h.components.ExpenseForm,props);
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 const saved=h.calls[0].body;assert.equal(saved.amount,'250000');assert.equal(saved.unit_price,'50000.0000');
 const reopened=harness();tree=reopened.render(reopened.components.ExpenseForm,{...props,expense:{...expense,...saved}});
 assert.ok(find(tree,n=>n.props.value==='250000'));
 assert.equal(multiplyTravelDecimals('0.1','0.2'),'0.02');assert.equal(multiplyTravelDecimals('0','50000'),'0');assert.equal(multiplyTravelDecimals('4.1250','50000'),'206250');
});
