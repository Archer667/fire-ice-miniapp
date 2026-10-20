import {useEffect,useId,useState} from 'react';
import {req} from '../api.js';
import {countWords, trimWords} from '../textLimits.js';
const defaults={roleplay_words:1000,scenario_words:1000,request_words:1000};
let current=null,pending=null;
const listeners=new Set();
async function refresh(){
 if(pending)return pending;
 pending=req('/api/text-limits').then(data=>{current=data;listeners.forEach(fn=>fn(data));return data}).finally(()=>{pending=null});
 return pending;
}
export default function LimitedText({limitKind='scenario_words',value='',onChange,...props}){
 const [limits,setLimits]=useState(current),[error,setError]=useState(false),id=useId();
 useEffect(()=>{listeners.add(setLimits);const load=()=>refresh().then(()=>setError(false)).catch(()=>setError(true));load();window.addEventListener('focus',load);window.addEventListener('text-limits-changed',load);const timer=setInterval(()=>{if(!document.hidden)load()},30000);return()=>{listeners.delete(setLimits);clearInterval(timer);window.removeEventListener('focus',load);window.removeEventListener('text-limits-changed',load)}},[]);
 const maximum=(limits||defaults)[limitKind],used=countWords(value);
 return <><span id={id} style={{display:'block',textAlign:'left',fontSize:12,color:used>maximum?'var(--danger)':'var(--gold)',margin:'7px 0'}} dir="ltr">{used.toLocaleString('fa-IR')} / {maximum.toLocaleString('fa-IR')}</span><textarea {...props} value={value} disabled={props.disabled||!limits} aria-describedby={id} onChange={event=>{const field=event.target,position=field.selectionStart,text=trimWords(field.value,maximum);field.value=text;onChange?.(event);if(document.activeElement===field)field.setSelectionRange(Math.min(position,text.length),Math.min(position,text.length))}}/>{error&&!limits&&<span role="alert">سقف متن دریافت نشد؛ اتصال را بررسی کن و دوباره صفحه را باز کن.</span>}</>;
}
