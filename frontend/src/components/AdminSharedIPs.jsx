import {useEffect,useMemo,useState} from 'react';
import {api} from '../api.js';

const number=value=>Number(value||0).toLocaleString('fa-IR');
const date=value=>value?new Date(value).toLocaleString('fa-IR',{timeZone:'Asia/Tehran'}):'ثبت نشده';
const eventName={registered:'ثبت‌نام',login:'ورود',password_changed:'تغییر رمز',recovered:'بازیابی حساب'};

export default function AdminSharedIPs({toast}){
  const [days,setDays]=useState(30),[data,setData]=useState(null),[query,setQuery]=useState(''),[loading,setLoading]=useState(false);
  const load=async()=>{setLoading(true);try{setData(await api.adminSharedIPs(days));}catch(error){toast(error.message);}finally{setLoading(false)}};
  useEffect(()=>{load()},[days]);
  const rows=useMemo(()=>{
    const needle=query.trim().toLocaleLowerCase('fa');
    if(!needle)return data?.rows||[];
    return (data?.rows||[]).filter(row=>row.ip.toLowerCase().includes(needle)||row.accounts.some(account=>
      [account.username,account.player_name,account.castle,String(account.uid)].some(value=>String(value||'').toLocaleLowerCase('fa').includes(needle))));
  },[data,query]);
  return <section className="admin-ip-audit">
    <div className="sect">آی‌پی‌های مشترک وب‌اپ</div>
    <div className="notice-guide"><strong>نشانه برای بررسی، نه حکم تخلف</strong><span>{data?.notice||'IP مشترک می‌تواند به‌دلیل اینترنت مشترک، اپراتور موبایل یا VPN باشد. نتیجه را کنار زمان ورود و فعالیت حساب‌ها بررسی کن.'}</span></div>
    <div className="card admin-ip-tools">
      <label className="f">بازهٔ بررسی<select value={days} onChange={event=>setDays(Number(event.target.value))}><option value={7}>۷ روز اخیر</option><option value={30}>۳۰ روز اخیر</option><option value={90}>۹۰ روز اخیر</option></select></label>
      <label className="f">جست‌وجو<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="IP، نام کاربری، نام کاراکتر، قلعه یا شناسه"/></label>
      <button className="btn ghost" disabled={loading} onClick={load}>{loading?'در حال دریافت…':'تازه‌کردن فهرست'}</button>
    </div>
    {data&&<div className="admin-ip-summary"><span><b>{number(data.total_shared_ips)}</b> IP مشترک</span><span><b>{number(rows.reduce((sum,row)=>sum+row.account_count,0))}</b> حساب در نتایج</span><span>نگهداری سوابق: {number(data.retention_days)} روز</span></div>}
    {loading&&!data&&<div className="loading">در حال بررسی ورودهای وب‌اپ…</div>}
    {!loading&&data&&!rows.length&&<div className="card empty">در این بازه IP مشترکی پیدا نشد.</div>}
    <div className="admin-ip-list">{rows.map(row=><details className="admin-ip-row" key={row.ip}>
      <summary><span className="admin-ip-address" dir="ltr">{row.ip}</span><span>{number(row.account_count)} حساب</span><small>آخرین مشاهده: {date(row.last_seen)}</small></summary>
      <div className="admin-ip-meta">از {date(row.first_seen)} تا {date(row.last_seen)} · مجموع {number(row.total_logins)} ورود موفق ثبت‌شده</div>
      <div className="admin-ip-accounts">{row.accounts.map(account=><article key={account.uid}>
        <header><strong>{account.player_name||'بدون کاراکتر'}</strong><span dir="ltr">@{account.username}</span></header>
        <p>شناسه حساب: <b dir="ltr">{account.uid}</b>{account.castle?` · قلعه: ${account.castle}`:''}</p>
        <p>اولین مشاهده: {date(account.first_seen)}<br/>آخرین مشاهده: {date(account.last_seen)}</p>
        <footer><span>{number(account.count)} رویداد ورود</span><span>{number(account.active_sessions)} نشست فعال</span><span>{eventName[account.last_event]||account.last_event}</span>{account.is_dead&&<span className="danger">کشته‌شده</span>}{account.registration_reset&&<span className="danger">کاراکتر حذف‌شده</span>}</footer>
      </article>)}</div>
    </details>)}</div>
  </section>;
}
