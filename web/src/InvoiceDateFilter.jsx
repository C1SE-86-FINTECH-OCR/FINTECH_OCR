import React from 'react';
import {CalendarDays, ChevronLeft, ChevronRight, X} from 'lucide-react';
import {invoiceDateRange} from './invoiceDateFilter.js';
import './invoiceDateFilter.css';

const modes = [['','Tất cả'],['month','Tháng'],['year','Năm'],['quarter','Quý']];
const pad = n => String(n).padStart(2,'0');
const dateValue = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const displayDate = value => value.split('-').reverse().join('/');

export default function InvoiceDateFilter({params, setParams}) {
  const requestedPeriod = params.get('period') || '';
  const period = modes.some(([mode])=>mode===requestedPeriod)?requestedPeriod:'';
  const value = params.get('date_value') || '';
  const quarter = params.get('quarter') || '1';
  const range = invoiceDateRange(period,value,quarter);
  const now = new Date();
  const year = Number(value.slice(0,4)) || now.getFullYear();
  const years = [...new Set([year,...Array.from({length:21},(_,i)=>now.getFullYear()+1-i)])].sort((a,b)=>b-a);
  function update(values) {
    setParams(current => {
      const next = new URLSearchParams(current);
      for (const [key, val] of Object.entries(values)) {
        if (val) next.set(key, String(val)); else next.delete(key);
      }
      return next;
    }, {replace: true});
  }
  function choose(mode) {
    update({period:mode, date_value:!mode?'':mode==='day'?dateValue(now):mode==='month'?dateValue(now).slice(0,7):String(now.getFullYear()), quarter:mode==='quarter'?String(Math.floor(now.getMonth()/3)+1):''});
  }
  function shift(direction) {
    if (!range.invoice_date_from) return;
    const [y,m,d] = range.invoice_date_from.split('-').map(Number);
    const next = new Date(y,m-1,d,12);
    if (period==='day') next.setDate(d+direction);
    if (period==='month') next.setMonth(m-1+direction);
    if (period==='quarter') next.setMonth(m-1+direction*3);
    if (period==='year') next.setFullYear(y+direction);
    if(next.getFullYear()<100 || next.getFullYear()>9999) return;
    update({date_value:period==='day'?dateValue(next):period==='month'?dateValue(next).slice(0,7):String(next.getFullYear()),quarter:period==='quarter'?String(Math.floor(next.getMonth()/3)+1):''});
  }
  const summary = !period?'Hiển thị hóa đơn trong mọi thời gian':range.invoice_date_from?range.invoice_date_from===range.invoice_date_to?`Ngày ${displayDate(range.invoice_date_from)}`:`${displayDate(range.invoice_date_from)} – ${displayDate(range.invoice_date_to)}`:'Chọn thời gian để lọc hóa đơn';
  return <section className="invoice-date-filter" aria-label="Lọc theo ngày hóa đơn">
    <div className="idf-heading"><span className="idf-label"><CalendarDays size={17}/> Ngày hóa đơn</span>
      <div className="idf-modes" role="group" aria-label="Kiểu lọc thời gian">
        {modes.map(([mode,label])=><button type="button" key={mode} aria-pressed={period===mode} className={period===mode?'is-selected':''} onClick={()=>choose(mode)}>{label}</button>)}
      </div>
      {period&&<button type="button" className="idf-clear" onClick={()=>choose('')}><X size={14}/> Xóa lọc</button>}
    </div>
    {period&&<div className="idf-controls">
      <button type="button" className="idf-arrow" aria-label="Khoảng thời gian trước" onClick={()=>shift(-1)} disabled={!range.invoice_date_from}><ChevronLeft size={18}/></button>
      {period==='month'&&<label className="idf-field"><span>Tháng</span><select value={value.slice(5,7)} onChange={e=>update({date_value:`${year}-${e.target.value}`})}>{Array.from({length:12},(_,i)=><option key={i} value={pad(i+1)}>Tháng {i+1}</option>)}</select></label>}
      {period==='quarter'&&<label className="idf-field"><span>Quý</span><select value={quarter} onChange={e=>update({quarter:e.target.value})}>{[1,2,3,4].map(q=><option key={q} value={q}>Quý {q} · Tháng {q*3-2}–{q*3}</option>)}</select></label>}
      {['month','quarter','year'].includes(period)&&<label className="idf-field"><span>Năm</span><select value={year} onChange={e=>update({date_value:period==='month'?`${e.target.value}-${value.slice(5,7)||pad(now.getMonth()+1)}`:e.target.value})}>{years.map(y=><option key={y} value={y}>{y}</option>)}</select></label>}
      <button type="button" className="idf-arrow" aria-label="Khoảng thời gian sau" onClick={()=>shift(1)} disabled={!range.invoice_date_from}><ChevronRight size={18}/></button>
      <button type="button" className="idf-current" onClick={()=>choose(period)}>{({day:'Hôm nay',month:'Tháng này',quarter:'Quý này',year:'Năm nay'})[period]}</button>
    </div>}
    <p className="idf-summary" role="status">{period&&<span className="idf-dot"/>}{summary}</p>
  </section>;
}
