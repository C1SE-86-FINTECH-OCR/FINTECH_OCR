import React,{useLayoutEffect,useRef} from 'react';

// Fit the real rendered text to its card without hiding digits or rounding data.
export default function FittedFinancialValue({children,className='',...props}){
 const ref=useRef(null);
 useLayoutEffect(()=>{
  const element=ref.current;if(!element)return;
  let previousWidth=-1;
  const fit=()=>{
   const width=element.clientWidth;if(!width||width===previousWidth)return;
   previousWidth=width;element.style.fontSize='';
   const size=parseFloat(getComputedStyle(element).fontSize);
   if(element.scrollWidth>width)element.style.fontSize=`${size*width/element.scrollWidth*.98}px`;
  };
  fit();const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(fit);observer?.observe(element);
  return()=>observer?.disconnect();
 },[children]);
 return <strong {...props} ref={ref} className={`fitted-financial-value ${className}`} title={String(children??'')}>{children}</strong>;
}
