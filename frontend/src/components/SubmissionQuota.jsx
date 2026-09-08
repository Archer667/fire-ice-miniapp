import { useEffect, useState } from 'react';
import { api } from '../api.js';
export default function SubmissionQuota({kind}) {
  const [value,setValue]=useState(null);
  useEffect(()=>{let active=true;const load=()=>api.submissionLimits().then(r=>{if(active)setValue(r);}).catch(()=>{});load();const t=setInterval(load,15000);return()=>{active=false;clearInterval(t);};},[]);
  if(!value)return null;
  return <p className="page-sub">{kind==='roleplays'?'رول خرابکاری، آزاد، اقتصادی و دیپلماسی: سهمیهٔ مشترک':'درخواست پروژه'} · این هفته {value[kind+'_used'].toLocaleString('fa-IR')} از {value[kind].toLocaleString('fa-IR')} · آغاز هفته: دوشنبه به وقت بازی</p>;
}
