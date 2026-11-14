export const ROOT = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
let token = localStorage.getItem('fintech_token');
export const authStore = {get:()=>token,set:(next)=>{token=next; if(next)localStorage.setItem('fintech_token',next);else localStorage.removeItem('fintech_token')}};
export async function api(path,{method='GET',body,headers={},raw=false}={}) {
 const h={...(token?{Authorization:`Bearer ${token}`}:{}) ,...headers};
 if(body && !(body instanceof FormData))h['Content-Type']='application/json';
 let response;
 try { response=await fetch(ROOT+path,{method,headers:h,body:body?(body instanceof FormData?body:JSON.stringify(body)):undefined}); }
 catch{ throw new Error('Không kết nối được backend. Hãy kiểm tra http://localhost:8000/health');}
 if(!response.ok){let json;try{json=await response.json()}catch{};const msg=typeof json?.detail==='string'?json.detail:Array.isArray(json?.detail)?json.detail.map(x=>x.msg).join('; '):`HTTP ${response.status}`;throw new Error(msg)}
 return raw?response:response.status===204?null:response.json();
}
export const money = n => `${Number(n||0).toLocaleString('vi-VN',{maximumFractionDigits:0})} đ`;
export const datefmt = s => s?new Date(s).toLocaleDateString('vi-VN'):'—';
export const roleName = x => ({admin:'Admin',accountant:'Accountant',employee:'Employee'})[x]||x;
export const approvalName = s => ({draft:'Nháp',pending:'Chờ duyệt',approved:'Đã duyệt',rejected:'Từ chối'})[s]||s;
