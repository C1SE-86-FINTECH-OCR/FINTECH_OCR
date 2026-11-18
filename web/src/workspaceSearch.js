export const searchKindLabel=kind=>({Profiles:'Hồ sơ nhân viên',Ranking:'Xếp hạng',Invoices:'Hóa đơn',Schedule:'Lịch công tác'})[kind]||kind;
export function normalizeWorkspaceText(value){
 return String(value??'').toLowerCase().replaceAll('đ','d').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().replace(/\s+/g,' ');
}
export function matchesWorkspaceText(query,...fields){
 const text=normalizeWorkspaceText(fields.join(' '));
 return normalizeWorkspaceText(query).split(' ').every(word=>text.includes(word));
}
export function rankingSearchResults(rows,query){
 const allRanking=['ranking','bang xep hang','nhan vien di nhieu nhat','di cong tac nhieu nhat'].includes(normalizeWorkspaceText(query));
 return rows.map((r,index)=>({...r,rank:index+1})).filter(r=>allRanking||matchesWorkspaceText(query,r.full_name)).map(r=>({key:'ranking-'+r.user_id,kind:'Ranking',title:r.full_name,subtitle:'Chuyến công tác hoàn thành · Toàn thời gian',metric:r.completed+' chuyến hoàn thành',detail:'#'+r.rank+' trong bảng xếp hạng',path:'/ranking?period=all#ranking-'+r.user_id}));
}
export async function searchWorkspace(get,query,limit=5){
 const requests=await Promise.allSettled([
  get('/invoices?'+new URLSearchParams({search:query,limit:String(limit)})),
  get('/ranking?period=all'),get('/schedules'),get('/directory/profiles?'+new URLSearchParams({search:query,limit:String(limit)}))
 ]);
 const data=index=>requests[index].status==='fulfilled'&&Array.isArray(requests[index].value)?requests[index].value:[];
 const rankings=rankingSearchResults(data(1),query).slice(0,limit);
 const invoices=data(0).map(r=>({key:'invoice-'+r.id,kind:'Invoices',title:r.invoice_number||'#'+r.id,subtitle:r.seller_name||'Chưa xác định nhà cung cấp',amount:r.total_amount,detail:r.approval_status,path:'/invoices/'+r.id}));
 const schedules=data(2).filter(r=>matchesWorkspaceText(query,r.title,r.destination,r.employee_name)).slice(0,limit).map(r=>({key:'schedule-'+r.id,kind:'Schedule',title:r.title,subtitle:r.employee_name+' · '+r.destination,metric:({planned:'Đã lên kế hoạch',in_progress:'Đang thực hiện',completed:'Hoàn thành',cancelled:'Đã hủy'})[r.status]||r.status,detail:r.starts_at,path:'/schedule#schedule-'+r.id}));
 const profiles=data(3).map(r=>({key:'profile-'+r.id,kind:'Profiles',title:r.full_name,subtitle:r.email||'Hồ sơ nhân viên',metric:r.completed_trips+' chuyến hoàn thành',detail:r.rank?'#'+r.rank+' trong bảng xếp hạng':'Chưa có thứ hạng',path:'/people/'+r.id}));
 const names=['Invoices','Ranking','Schedule','Profiles'];
 return {rows:[...profiles,...rankings,...invoices,...schedules],error:requests.map((r,i)=>r.status==='rejected'?searchKindLabel(names[i])+': '+r.reason.message:'').filter(Boolean).join(' / ')};
}
