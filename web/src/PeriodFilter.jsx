import React from 'react';
import {currentPeriod, shiftPeriod, validPeriod} from './periodFilters.js';

export default function PeriodFilter({value, onChange}) {
  const {period, year, month} = value;
  const change = partial => onChange({...value, ...partial});
  const bounded = ['month','quarter','year'].includes(period);
  const label = period === 'month' ? `Tháng ${month}/${year}` :
    period === 'quarter' ? `Quý ${Math.ceil(month / 3)}/${year}` : `Năm ${year}`;
  return <div className="filters">
    <select aria-label="Kỳ thống kê" value={period} onChange={e => change({period: e.target.value})}>
      <option value="month">Theo tháng</option>
      <option value="quarter">Theo quý</option>
      <option value="year">Theo năm</option>
      <option value="custom">Khoảng thời gian</option>
      <option value="all">Toàn thời gian</option>
    </select>
    {bounded && <>
      <button type="button" className="btn btn-outline" aria-label="Kỳ trước"
        disabled={!validPeriod(shiftPeriod(value, -1))} onClick={() => onChange(shiftPeriod(value, -1))}>‹</button>
      <strong aria-live="polite">{label}</strong>
      <input type="number" aria-label="Năm" min="1" max="9999" value={year} onChange={e=>change({year:e.target.value})}/>
      {period==='month'&&<select aria-label="Tháng" value={month} onChange={e=>change({month:e.target.value})}>
        {Array.from({length:12},(_,i)=><option key={i+1} value={i+1}>Tháng {i+1}</option>)}
      </select>}
      {period==='quarter'&&<select aria-label="Quý" value={Math.ceil(month/3)} onChange={e=>change({month:(Number(e.target.value)-1)*3+1})}>
        {[1,2,3,4].map(q=><option key={q} value={q}>Quý {q}</option>)}
      </select>}
      <button type="button" className="btn btn-outline" aria-label="Kỳ sau"
        disabled={!validPeriod(shiftPeriod(value, 1))} onClick={() => onChange(shiftPeriod(value, 1))}>›</button>
    </>}
    {period === 'custom' && <>
      <label>Từ ngày <input type="date" value={value.date_from} onChange={e => change({date_from: e.target.value})}/></label>
      <label>Đến ngày <input type="date" value={value.date_to} onChange={e => change({date_to: e.target.value})}/></label>
      {!validPeriod(value) && <span role="alert">Chọn khoảng ngày hợp lệ.</span>}
    </>}
    <button type="button" className="btn btn-outline" onClick={() => onChange({...currentPeriod(), period: bounded ? period : 'month'})}>Hiện tại</button>
  </div>;
}
