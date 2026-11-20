import React,{useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {api,money,approvalName} from './api';
import {searchWorkspace,searchKindLabel} from './workspaceSearch';
export default function WorkspaceSearchPage(){
 const [params]=useSearchParams(),query=params.get('search')||'';
 const [result,setResult]=useState({rows:[],error:''}),[busy,setBusy]=useState(true);
 useEffect(()=>{let current=true;setBusy(true);searchWorkspace(api,query,250).then(data=>{if(current)setResult(data)}).catch(e=>{if(current)setResult({rows:[],error:e.message})}).finally(()=>{if(current)setBusy(false)});return ()=>{current=false}},[query]);
 return <><header className="pagehead"><div><h1>Kết quả tìm kiếm</h1><p>Kết quả cho “{query}” · Hồ sơ, xếp hạng, hóa đơn và lịch công tác</p></div></header>{result.error&&<p className="error" role="alert">{result.error}</p>}{busy?<p>Đang tìm kiếm...</p>:['Profiles','Ranking','Invoices','Schedule'].map(kind=><section className="panel workspace-search-group" key={kind}><h3>{searchKindLabel(kind)}</h3>{result.rows.filter(r=>r.kind===kind).map(item=><Link key={item.key} to={item.path} className="quick-search-result"><span><strong>{item.title}</strong><small>{item.subtitle}</small></span><span className="quick-search-meta"><strong>{kind==='Invoices'?money(item.amount):item.metric}</strong><small>{kind==='Invoices'?approvalName(item.detail):kind==='Schedule'?new Date(item.detail).toLocaleDateString('vi-VN'):item.detail}</small></span></Link>)}{!result.rows.some(r=>r.kind===kind)&&<p>Không có kết quả phù hợp.</p>}</section>)}</>;
}
