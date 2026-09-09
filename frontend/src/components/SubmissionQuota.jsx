import { useEffect, useState } from 'react';
import { api } from '../api.js';
export default function SubmissionQuota({kind, refreshKey = 0}) {
  const [value,setValue]=useState(null);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{let active=true;const load=()=>api.submissionLimits().then(r=>{if(active){setValue(r);setFailed(false);}}).catch(()=>{if(active)setFailed(true);});load();const t=setInterval(load,15000);return()=>{active=false;clearInterval(t);};},[kind, refreshKey]);
  if(!value)return <p className="page-sub">{failed ? 'دریافت سهمیه ناموفق بود؛ تلاش دوباره در چند ثانیه…' : 'در حال دریافت سهمیهٔ هفتگی…'}</p>;
  return <p className="page-sub">{kind==='roleplays'?'رول خرابکاری، آزاد، اقتصادی و دیپلماسی: سهمیهٔ مشترک':'درخواست پروژه'} · مصرف‌شده این هفته: {value[kind+'_used'].toLocaleString('fa-IR')} از {value[kind].toLocaleString('fa-IR')} · باقی‌مانده: {Math.max(0,value[kind]-value[kind+'_used']).toLocaleString('fa-IR')} · آغاز هفته: دوشنبه به وقت بازی</p>;
}
