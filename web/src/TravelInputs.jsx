import React,{useId,useRef,useState} from 'react';
import {CloudUpload,FileText,LoaderCircle,CheckCircle2,AlertTriangle} from 'lucide-react';
import {normalizeVndInput,formatTravelQuantity,parseTravelInput} from './travelView.js';

export function TravelDecimalInput({value,onChange,whole=false,min,...props}){
 const [text,setText]=useState(null),dirty=useRef(false);
 const display=value==null||value===''?'':formatTravelQuantity(value);
 function validate(raw){let canonical=parseTravelInput(raw);if(canonical==='')return '';
  if(whole){const [integer,fraction='']=canonical.split('.');if(/[1-9]/.test(fraction))throw new Error('VND phải là số nguyên đồng; không tự làm tròn phần lẻ.');canonical=integer;
   if(min!=null&&BigInt(canonical)<BigInt(min))throw new Error('Giá trị nhỏ hơn mức tối thiểu.');}
  return canonical;
 }
 return <input {...props} type="text" inputMode="decimal" autoComplete="off" value={text??display}
 onFocus={()=>{dirty.current=false;setText(display);}}
 onChange={e=>{dirty.current=true;setText(e.target.value);e.target.setCustomValidity('');try{onChange({target:{value:validate(e.target.value)}});}catch(error){e.target.setCustomValidity(error.message);}}}
 onBlur={e=>{if(!dirty.current){setText(null);return;}try{validate(e.target.value);setText(null);e.target.setCustomValidity('');}catch(error){e.target.setCustomValidity(error.message);e.target.reportValidity();}}}/>;
}
export function VndInput({value,...props}){
 let canonical=value;
 if(value!=null&&value!==''){try{canonical=normalizeVndInput(value);}catch{}}
 return <TravelDecimalInput {...props} whole value={canonical}/>;
}
export function fileSize(bytes){if(!Number.isFinite(bytes))return 'Chưa có dung lượng';return bytes<1024?`${bytes} B`:bytes<1048576?`${(bytes/1024).toFixed(0)} KB`:`${(bytes/1048576).toFixed(1)} MB`;}
export function TravelFileUpload({accept='.pdf,.png,.jpg,.jpeg',disabled=false,onUpload,label='Tải chứng từ',invoice=false}){
 const id=useId(),input=useRef(),depth=useRef(0),pending=useRef(false),[dragging,setDragging]=useState(false),[upload,setUpload]=useState(null),[error,setError]=useState('');
 const busy=upload?.status==='uploading';
 async function select(file){
  if(!file||disabled||pending.current)return;
  setError('');
  const ext='.'+file.name.split('.').pop().toLowerCase();
  if(!accept.split(',').includes(ext)||!file.size||file.size>20*1024*1024){setError('Chọn tệp đúng định dạng, không rỗng và tối đa 20 MB.');return;}
  pending.current=true;setUpload({name:file.name,size:file.size,status:'uploading'});
  try{await onUpload(file);setUpload({name:file.name,size:file.size,status:'done'});}catch(e){setError(e.message||'Không tải được tệp.');setUpload({name:file.name,size:file.size,status:'failed'});}finally{pending.current=false;if(input.current)input.current.value='';}
 }
 const open=()=>{if(!disabled&&!busy)input.current?.click();};
 return <div className="travel-upload-control">
 <input ref={input} id={id} type="file" accept={accept} hidden disabled={disabled||busy} aria-label={label} onChange={e=>select(e.target.files?.[0])}/>
 <div className={`travel-dropzone${dragging?' is-dragging':''}${disabled||busy?' is-disabled':''}`} role="button" tabIndex={disabled||busy?-1:0} aria-disabled={disabled||busy} aria-label={label} onClick={open} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}}}
 onDragEnter={e=>{e.preventDefault();if(!disabled&&!busy){depth.current++;setDragging(true);}}} onDragOver={e=>e.preventDefault()} onDragLeave={e=>{e.preventDefault();depth.current=Math.max(0,depth.current-1);if(!depth.current)setDragging(false);}} onDrop={e=>{e.preventDefault();depth.current=0;setDragging(false);const files=Array.from(e.dataTransfer.files||[]);if(files.length>1){setError('Vui lòng tải từng chứng từ để liên kết đúng khoản chi hoặc giao dịch.');return;}select(files[0]);}}>
 {busy?<LoaderCircle size={32} className="spin"/>:<CloudUpload size={36}/>}<strong>{busy?(invoice?'Đang tải và xử lý hóa đơn…':'Đang tải chứng từ…'):dragging?'Thả tệp để tải lên':label}</strong><span>Nhấn vào đây hoặc kéo thả tệp</span><small>{invoice?'PDF, JPG, PNG, XML':'PDF, JPG, PNG'} · Tối đa 20 MB/tệp</small>
 </div>
 {upload&&<div className={`travel-upload-file is-${upload.status}`} role="status"><FileText size={18}/><div><strong title={upload.name}>{upload.name}</strong><small>{fileSize(upload.size)}</small></div>{upload.status==='done'?<CheckCircle2 size={16}/>:upload.status==='failed'?<AlertTriangle size={16}/>:<LoaderCircle size={16} className="spin"/>}<span>{upload.status==='done'?'Đã tải lên':upload.status==='failed'?'Tải thất bại':'Đang xử lý'}</span></div>}
 {error&&<p className="error" role="alert">{error}</p>}
 </div>;
}
