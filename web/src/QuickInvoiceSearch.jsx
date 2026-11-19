import React,{useEffect,useRef,useState} from 'react';
import {useLocation,useNavigate} from 'react-router-dom';
import {Search,X,FileText,ArrowRight,RefreshCw,Trophy,CalendarDays,UserCircle} from 'lucide-react';
import {api,money,approvalName} from './api';
import {searchWorkspace,searchKindLabel} from './workspaceSearch';

export default function QuickInvoiceSearch(){
 const [query,setQuery]=useState(''),[open,setOpen]=useState(false),[selected,setSelected]=useState(-1);
 const [result,setResult]=useState({query:'',rows:[],error:''});
 const root=useRef(null),input=useRef(null),navigate=useNavigate(),location=useLocation();
 const term=query.trim(),busy=!!term&&result.query!==term;
 const rows=busy?[]:result.rows;
 useEffect(()=>{
   let current=true;
   if(!term){setResult({query:'',rows:[],error:''});return}
   const timer=setTimeout(()=>{
     searchWorkspace(api,term)
       .then(result=>{if(current)setResult({query:term,...result})})
       .catch(error=>{if(current)setResult({query:term,rows:[],error:error.message})});
   },300);
   return ()=>{current=false;clearTimeout(timer)};
 },[term]);
 useEffect(()=>{setOpen(false);setQuery('');setSelected(-1)},[location.pathname,location.search]);
 useEffect(()=>{
   const outside=e=>{if(!root.current?.contains(e.target))setOpen(false)};
   document.addEventListener('pointerdown',outside);
   return ()=>document.removeEventListener('pointerdown',outside);
 },[]);
 function viewAll(){if(term){setOpen(false);navigate('/search?'+new URLSearchParams({search:term}))}}
 function choose(item){setOpen(false);navigate(item.path)}
 function keydown(e){
   if(e.key==='Escape'){e.preventDefault();setOpen(false);setSelected(-1)}
   if(e.key==='ArrowDown'){e.preventDefault();setOpen(true);setSelected(i=>rows.length?Math.min(i+1,rows.length-1):-1)}
   if(e.key==='ArrowUp'){e.preventDefault();setSelected(i=>Math.max(-1,i-1))}
   if(e.key==='Enter'){e.preventDefault();if(open&&selected>=0&&rows[selected])choose(rows[selected]);else viewAll()}
 }
 return <div className="quick-search" ref={root} onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setOpen(false)}}>
   <div className="topsearch quick-search-field"><Search size={16}/><input ref={input} type="search" role="combobox" aria-label="Tìm hóa đơn, hồ sơ nhân viên, xếp hạng hoặc lịch công tác" aria-expanded={open&&!!term} aria-controls="quick-invoice-results" aria-autocomplete="list" aria-activedescendant={open&&selected>=0&&rows[selected]?'quick-invoice-'+rows[selected].key:undefined} placeholder="Tìm hóa đơn, nhân viên, lịch công tác..." value={query} onFocus={()=>setOpen(true)} onChange={e=>{setQuery(e.target.value);setOpen(true);setSelected(-1)}} onKeyDown={keydown}/>{query&&<button type="button" className="quick-search-clear" aria-label="Xóa từ khóa" onClick={()=>{setQuery('');setSelected(-1);input.current?.focus()}}><X size={14}/></button>}</div>
   {open&&term&&<div className="quick-search-panel"><div className="quick-search-caption">Kết quả trong hệ thống</div><div role="status" aria-live="polite">{busy?<p className="quick-search-feedback"><RefreshCw size={14} className="spin"/> Đang tìm kiếm...</p>:result.error?<p className="quick-search-feedback error">{result.error}</p>:!rows.length?<p className="quick-search-feedback">Không có kết quả phù hợp.</p>:null}</div><div id="quick-invoice-results" role="listbox" aria-label="Kết quả tìm kiếm trong hệ thống">{rows.map((item,index)=><button type="button" role="option" aria-selected={selected===index} id={'quick-invoice-'+item.key} className={'quick-search-result '+(selected===index?'selected':'')} key={item.key} onClick={()=>choose(item)}>{item.kind==='Profiles'?<UserCircle size={18}/>:item.kind==='Ranking'?<Trophy size={18}/>:item.kind==='Schedule'?<CalendarDays size={18}/>:<FileText size={18}/>}<span><small className="search-result-kind">{searchKindLabel(item.kind)}</small><strong>{item.title}</strong><small>{item.subtitle}</small></span><span className="quick-search-meta"><strong>{item.kind==='Invoices'?money(item.amount):item.metric}</strong><small>{item.kind==='Invoices'?approvalName(item.detail):item.kind==='Schedule'?new Date(item.detail).toLocaleDateString('vi-VN'):item.detail}</small></span></button>)}</div><button type="button" className="quick-search-all" onClick={viewAll}>Xem tất cả kết quả <ArrowRight size={14}/></button></div>}
 </div>;
}
