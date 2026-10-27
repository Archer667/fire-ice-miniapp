import { useRef } from 'react';
import { api } from '../api.js';
import './espionage.css';

export const spyLabels = {pending:'در انتظار داوری',active:'فعال',risk_review:'بررسی خطر دستگیری',suspended:'تعلیق‌شده',closed:'جمع‌شده',captured:'دستگیرشده',failed:'نفوذ ناموفق',returned:'نیاز به اصلاح',rejected:'ردشده',delivered:'پاسخ رسیده',delivery_failed:'پیام نرسیده',cancelled:'بسته‌شده'};
export const fa = n => Number(n || 0).toLocaleString('fa-IR');
export const spyDate = s => s ? new Date(s.endsWith('Z') || /[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z').toLocaleString('fa-IR',{dateStyle:'short',timeStyle:'short'}) : '—';
export function SpyStatus({status}) { return <span className={`spy-status spy-${status}`}>{spyLabels[status] || status}</span>; }
export function useSpyCommand() {
  const attempts = useRef(new Map());
  return async (path,data={}) => {
    const key=path+JSON.stringify(data);
    let id=attempts.current.get(key);
    if(!id) { id=crypto.randomUUID(); attempts.current.set(key,id); }
    let result;
    try { result=await api.spy(path,{...data,request_id:id}); }
    catch(error) { if(error.status>=400&&error.status<500)attempts.current.delete(key); throw error; }
    attempts.current.delete(key);
    return result;
  };
}
export function SpyEmpty({children}) { return <div className="card spy-empty">{children}</div>; }
