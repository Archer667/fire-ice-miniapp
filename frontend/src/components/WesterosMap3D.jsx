import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api.js';
import { MAP_IMAGE } from '../mapCoords.js';
import { gameNow } from '../gameClock.js';
import { REGIONS_STATIC, PACT_COLORS, ALLIANCE_TYPES, castleLabel } from '../gamedata.js';
import { Keep, Swords } from './Icons.jsx';
import { haptic } from '../telegram.js';
import './WesterosMap3D.css';
const REGION_COLORS={north:'#ffffff',iron:'#172b50',river:'#677442',west:'#d6ad36',reach:'#6fae52',vale:'#b7def2',storm:'#92979d',dorne:'#e57932',crown:'#b82d32'};

export default function WesterosMap3D({ data, meCastle, meCastles, onSelectTarget, pickLabel='انتخاب به‌عنوان مقصد', routePath, fallback }) {
  const frame=useRef(null), [ready,setReady]=useState(false), [failed,setFailed]=useState(false), [live,setLive]=useState(data), [selection,setSelection]=useState(null), [army,setArmy]=useState(null), [pins,setPins]=useState('all'), [region,setRegion]=useState(null), [colorMode,setColorMode]=useState('region'), [armies,setArmies]=useState(true), [tick,setTick]=useState(gameNow()), [borders,setBorders]=useState(false);
  const latest=useRef(null);
  const popupRef=useRef(null);
  useEffect(()=>{if(selection||army)popupRef.current?.scrollIntoView({block:'nearest',behavior:'smooth'})},[selection,army]);
  useEffect(()=>setLive(data),[data]);
  useEffect(()=>{let active=true,busy=false;const refresh=async()=>{if(document.hidden||busy)return;busy=true;try{const result=await api.map();if(active)setLive(result)}catch{/* Keep the last authenticated response. */}finally{busy=false}};const timer=setInterval(refresh,20000);const clock=setInterval(()=>{if(!document.hidden)setTick(gameNow())},1000);document.addEventListener('visibilitychange',refresh);return()=>{active=false;clearInterval(timer);clearInterval(clock);document.removeEventListener('visibilitychange',refresh)}},[]);
  const own=useMemo(()=>new Set(meCastles?.length?meCastles:meCastle?[meCastle]:[]),[meCastle,meCastles]);
  const castles=useMemo(()=>(live?.regions||[]).flatMap(r=>r.castles.map(c=>({...c,region:r.id,mine:own.has(c.name)}))),[live,own]);
  const state=useMemo(()=>({castles,campaigns:live?.campaigns||[],effects:live?.effects||[],routePath:routePath||[],filters:{pins,region},colorMode,regionColors:REGION_COLORS,pactColors:PACT_COLORS,showArmies:armies,showBorders:borders,now:tick}),[castles,live,routePath,pins,region,colorMode,armies,borders,tick]);latest.current=state;
  const send=message=>frame.current?.contentWindow?.postMessage(message,location.origin);
  useEffect(()=>{const receive=event=>{if(event.origin!==location.origin||event.source!==frame.current?.contentWindow)return;const message=event.data;if(message?.type==='valyria-map-ready'){setReady(true);send({type:'valyria-map-state',state:latest.current})}if(message?.type==='valyria-map-castle'){haptic();setSelection(message.name);setArmy(null)}if(message?.type==='valyria-map-army'){haptic();setArmy(message.id);setSelection(null)}if(message?.type==='valyria-map-error')setFailed(true)};window.addEventListener('message',receive);return()=>window.removeEventListener('message',receive)},[]);
  useEffect(()=>{if(ready)send({type:'valyria-map-state',state})},[ready,state]);
  const castle=castles.find(c=>c.name===selection), campaign=(live?.campaigns||[]).find(c=>c.id===army), mine=castles.find(c=>c.mine);
  if(failed)return <div><p className="pi-stats">نمای سه‌بعدی در این دستگاه اجرا نشد؛ نقشهٔ معمولی فعال است.</p>{fallback}</div>;
  return <div className="mapview">
    <div className="map-region-tabs"><button className={`map-region-tab ${!region?'on':''}`} onClick={()=>{setRegion(null);send({type:'valyria-map-fit'})}}>همهٔ نقشه</button>{(live?.regions||[]).map(r=><button key={r.id} className={`map-region-tab ${region===r.id?'on':''}`} onClick={()=>{setRegion(r.id);const c=castles.find(c=>c.region===r.id);if(c)send({type:'valyria-map-focus',name:c.name})}}>{REGIONS_STATIC[r.id]?.name||r.name}</button>)}</div>
    <div className="map-region-tabs map-pin-filter">{[['all','همه'],['mine','قلعه‌های من'],['owned','صاحب‌دار'],['empty','خالی'],['port','بندر']].map(([id,name])=><button key={id} className={`map-region-tab ${pins===id?'on':''}`} onClick={()=>setPins(id)}>{name}</button>)}<button className={`map-region-tab ${armies?'on':''}`} role="switch" aria-checked={armies} onClick={()=>setArmies(!armies)}><Swords s={11}/> لشکرها</button><button className={`map-region-tab ${borders?'on':''}`} role="switch" aria-checked={borders} onClick={()=>setBorders(!borders)}>محدودهٔ اقلیم‌ها</button></div>
    <div className="mapview-frame map3d-frame"><iframe ref={frame} src="/westeros/hybrid-v2/index.html" title="نقشهٔ سه‌بعدی وستروس" className="map3d-view" />
      <button className="map3d-minimap" title="نقشهٔ راهنما؛ انتخاب قلعهٔ نزدیک" aria-label="نقشهٔ راهنما" onClick={e=>{const box=e.currentTarget.getBoundingClientRect(),x=(e.clientX-box.left)/box.width*100,y=(e.clientY-box.top)/box.height*100;const near=(live?.regions||[]).flatMap(r=>r.castles.filter(c=>r.coords?.[c.name]).map(c=>({name:c.name,xy:r.coords[c.name]}))).sort((a,b)=>Math.hypot(a.xy[0]-x,a.xy[1]-y)-Math.hypot(b.xy[0]-x,b.xy[1]-y))[0];if(near){setRegion(null);setPins('all');send({type:'valyria-map-focus',name:near.name})}}}><img src={MAP_IMAGE} alt="نمای کلی وستروس" draggable={false}/></button>
      {mine&&<button className="map-my-castle" aria-label="پرش به قلعهٔ خودم" onClick={()=>{setRegion(null);setPins('all');send({type:'valyria-map-focus',name:mine.name});setSelection(mine.name)}}><Keep s={14}/></button>}
    </div>
      {(castle||campaign)&&<div ref={popupRef} className="map3d-popup" role="dialog" aria-label="اطلاعات نقشه"><button className="map3d-close" aria-label="بستن" onClick={()=>{setSelection(null);setArmy(null)}}>×</button>
        {castle&&<><div className="pi-name">{castleLabel(castle.name)}{castle.port?' ⚓':''}{castle.mine&&<span className="pi-mine">قلعهٔ خودت</span>}</div><div className="pi-owner">خاندان: {castle.house||'—'}</div><div className="pi-owner">اقلیم: {REGIONS_STATIC[castle.region]?.name||'—'}</div>{castle.owner?<><div className="pi-owner">صاحب: {castle.owner.name}{castle.owner.title?` · ${castle.owner.title}`:''}</div><div className="pi-stats">امتیاز: {(castle.owner.points??0).toLocaleString('fa-IR')}{castle.owner.overlord_name?` · بالادستی: ${castle.owner.overlord_name}`:''}</div><div className="pi-owner">اقلیم مالک: {REGIONS_STATIC[castle.owner.region]?.name||'—'} · پیمان: {ALLIANCE_TYPES[castle.owner.pact]?.name||'بدون پیمان'}</div></>:<div className="pi-owner">بدون لرد — خالی</div>}{(live?.effects||[]).some(e=>e.castle===castle.name)&&<div className="pi-stats">⚔️ نبرد یا محاصرهٔ فعال</div>}{onSelectTarget&&<button className="btn ghost pi-pick" onClick={()=>onSelectTarget(castle)}>{pickLabel}</button>}</>}
        {campaign&&<><div className="pi-name">{campaign.name||'لشکر در حرکت'}</div><div className="pi-owner">فرمانده: {campaign.mine?'تو':campaign.player_name||'نامشخص'}</div><div className="pi-stats">از {castleLabel(campaign.from)} به {castleLabel(campaign.to)}</div></>}
      </div>}
    <div className="map-legend">{(live?.regions||[]).map(r=><span key={r.id} className="map-legend-item"><span className="map-legend-dot" style={{background:REGION_COLORS[r.id]}}/>{REGIONS_STATIC[r.id]?.name||r.name}</span>)}<span className="map-legend-item"><span className="map-legend-dot" style={{background:'#858b85',opacity:.5}}/>بدون مالک</span><button className="map-legend-toggle" onClick={()=>setColorMode(colorMode==='region'?'pact':'region')}>رنگ‌بندی: {colorMode==='region'?'اقلیم مالک':'پیمان'}</button></div>
  </div>;
}

