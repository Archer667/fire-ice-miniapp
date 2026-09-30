import {useState} from 'react';
import {api} from '../api.js';

export default function PassageConsent({armyId,status,refresh,toast}) {
 const [busy,setBusy]=useState(false);
 if(!status)return null;
 const vote=async()=>{setBusy(true);try{const r=await api.passageConsent(armyId,!status.agreed);await refresh();toast(r.closed?'همه موافقت کردند؛ نبرد بسته شد و مسیر ادامه پیدا کرد.':status.agreed?'موافقتت پس گرفته شد.':'موافقت ثبت شد؛ منتظر سایر طرف‌ها هستیم.')}catch(e){toast(e.message)}finally{setBusy(false)}};
 return <div className="army-passage"><div style={{fontSize:11,color:'var(--mid)',marginBottom:6,lineHeight:1.8}}>موافقت با ادامهٔ مسیر: {status.agreed_count.toLocaleString('fa-IR')} از {status.required_count.toLocaleString('fa-IR')} طرف. تا موافقت همه، نبرد باز می‌ماند.</div>{status.can_vote&&<button className="btn ghost army-action" disabled={busy} onClick={vote}>{busy?'…':status.agreed?'پس گرفتن موافقت':'ادامهٔ مسیر و انصراف از نبرد'}</button>}</div>;
}
