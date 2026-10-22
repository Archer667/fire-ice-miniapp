"""Private, season-scoped statistics and real-hour asset samples.

Samples are observations, never interpolated balances. Every caller holds the
single-worker game_state_lock. These audit collections survive world resets.
"""
import asyncio
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import html
import logging
from pathlib import Path
import secrets
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from auth import get_user, get_full_admin
from db import db, players, game_settings
from game import now, apply_production, owned_castles, normalize_building_state
import game_clock
from season_clock import season_day
from season_branding import read_branding
from game_data import COMMON_TROOPS, NAVAL_TROOPS, SIEGE_EQUIPMENT, BUILDINGS, TRADE_GOOD_NAMES, WEAPON_NAMES, REGIONS

router=APIRouter(prefix='/api')
snapshots=db.analytics_hourly
events=db.analytics_events
seasons=db.analytics_seasons
files=db.analytics_files
yearbooks=db.analytics_yearbooks
UTC=timezone.utc
TEHRAN=ZoneInfo('Asia/Tehran')
ORNAMENT='꧁─꩜༺᪥༻꩜─꧂'
RESOURCE_NAMES={'gold':'سکه','food':'غلات','wood':'چوب','stone':'سنگ','iron':'آهن','men':'مردم / نیروی انسانی','wine':'شراب',**WEAPON_NAMES,**TRADE_GOOD_NAMES}
FEEDS={
    'roleplays':['tg_id','player_name','category','admin_score','scored_at','created_at','resolved_at','resolved','admin_adjustments','admin_generated'],
    'campaigns':['tg_id','player_name','op_type','name','created_at','men_committed','combat_resolved_at','medal_outcome_battle_id','winner_tg_ids','loser_tg_ids','engagement_campaign_id','battle_is_root','medal_outcome_recorded'],
    'market_history':['buyer_id','buyer_name','seller_id','seller_name','qty','resource','total','status','game_at'],
    'caravans':['tg_id','player_name','target_tg_id','target_name','created_at','resources','arrival_notified','delivery_failed'],
    'spy_missions':['tg_id','player_name','created_at','success','resolved'],
    'projects':['owner_id','owner_name','created_at','status'],
}

def real_now():return datetime.now(UTC).replace(tzinfo=None)
def instant(value):
    if isinstance(value,datetime):return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    return None
def season_id(epoch):return hashlib.sha256(epoch.isoformat().encode()).hexdigest()[:24]
def character_key(p):return str(p['tg_id'])+':'+str(p.get('created_at'))
def numbers(value):
    return {str(k):float(v) for k,v in (value or {}).items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
def counts(value):return {k:int(v) for k,v in numbers(value).items() if v>0}
def unit_name(unit):
    if unit in COMMON_TROOPS:return COMMON_TROOPS[unit]['name']
    if unit in NAVAL_TROOPS:return NAVAL_TROOPS[unit]['name']
    if unit in SIEGE_EQUIPMENT:return SIEGE_EQUIPMENT[unit]['name']
    for region in REGIONS.values():
        special=region.get('special_troop',{})
        if isinstance(special,dict) and special.get('id')==unit:return special.get('name',unit)
    return RESOURCE_NAMES.get(unit,unit)

async def full(user=Depends(get_user)):return await get_full_admin(user)

async def current_season():
    clock=await game_settings.find_one({'_id':'season_clock'}) or {}
    if not instant(clock.get('started_at')):
        await season_day();clock=await game_settings.find_one({'_id':'season_clock'}) or {}
    epoch=instant(clock.get('started_at'))
    if not epoch:return None
    ident=season_id(epoch);branding=await read_branding()
    old=await seasons.find_one({'_id':ident})
    if not old:
        old={'_id':ident,'epoch':epoch,'end':epoch+timedelta(days=30),'title':branding['title'],'first_observed_real':real_now(),'first_observed_game':now()}
        await seasons.update_one({'_id':ident},{'$setOnInsert':old},upsert=True)
    # The live title may change without advancing the season clock.
    if old['title']!=branding['title']:
        await seasons.update_one({'_id':ident},{'$set':{'title':branding['title']}});old['title']=branding['title']
    return old

async def admin_ids():
    from config import ADMIN_IDS, OWNER_ID
    ids=set(ADMIN_IDS)
    if OWNER_ID is not None:ids.add(OWNER_ID)
    async for row in db.admin_roles.find({}, {'tg_id':1}):ids.add(row['tg_id'])
    return ids

async def archive_sources(season):
    """Retain compact facts before operational source cleanup; no private prose."""
    for source,fields in FEEDS.items():
        timefield='game_at' if source=='market_history' else 'created_at'
        async for row in db[source].find({timefield:{'$gte':season['epoch'],'$lt':season['end']}}, {**{k:1 for k in fields}}):
            await archive_row(source,row,season)

async def archive_row(source,row,season=None):
    if not row or source not in FEEDS:return
    timefield='game_at' if source=='market_history' else 'created_at'
    if not instant(row.get(timefield)):return
    season=season or await current_season()
    if not season or not in_window(row[timefield],season):return
    ident=f"{season['_id']}:{source}:{row['_id']}"
    payload={k:row[k] for k in FEEDS[source] if k in row}
    if source=='roleplays':
        old=await events.find_one({'_id':ident}) or {}
        old=old.get('data',{})
        for timing,fields in [('scored_at',['admin_score','scored_at']),('resolved_at',['resolved','resolved_at','admin_adjustments'])]:
            if instant(payload.get(timing)) and not in_window(payload[timing],season):
                for field in fields:
                    payload.pop(field,None)
                    if field in old:payload[field]=old[field]
    await events.update_one({'_id':ident},{'$set':{'season':season['_id'],'source':source,'source_id':str(row['_id']),'data':payload,'observed_real':real_now()}},upsert=True)

def army_view(c):
    troops=counts(c.get('troops'));equipment=counts(c.get('equipment'))
    return {'id':str(c['_id']),'name':c.get('name') or 'لشکر بدون نام','origin':c.get('origin_castle'),'destination':c.get('target_castle'),
            'operation':c.get('op_type'),'troops':troops,'equipment':equipment,'group':str(c.get('merge_group_id') or ''),
            'mercenary':bool(c.get('mercenary_contract_id')),'battle':bool(c.get('engagement_locked')),
            'men':sum(v for k,v in troops.items() if k not in NAVAL_TROOPS),'ships':sum(troops.get(k,0) for k in NAVAL_TROOPS)}

async def asset_state(p,armies,templates):
    calculated=apply_production(deepcopy(p))
    active_armies=[army_view(c) for c in armies]
    reserve=counts(p.get('troops'));equipment=counts(p.get('equipment'))
    troop_totals=dict(reserve);equipment_totals=dict(equipment)
    for army in active_armies:
        for k,v in army['troops'].items():troop_totals[k]=troop_totals.get(k,0)+v
        for k,v in army['equipment'].items():equipment_totals[k]=equipment_totals.get(k,0)+v
    from item_effects import character_matches, instant as item_instant
    inventory=[]
    async for grant in db.item_grants.find({'tg_id':p['tg_id']}):
        expiry=item_instant(grant['expires_at']) if grant.get('expires_at') else None
        if not character_matches(grant,p) or (expiry and now()>=expiry):continue
        template=templates.get(str(grant.get('item_id')), {})
        inventory.append({'id':str(grant['_id']),'name':template.get('name','آیتم ثبت‌شده'),'escrow':bool(grant.get('store_listing_id'))})
    buildings={}
    for castle in owned_castles(p):
        state=p.get('castle_buildings',{}).get(castle) if castle!=p.get('castle') else p.get('buildings',{})
        if not state:state=p.get('castle_buildings',{}).get(castle,{})
        buildings[castle]={bid:normalize_building_state(raw)['level'] for bid,raw in (state or {}).items()}
    escrow=[]
    async for contract in db.world_contracts.find({'owner.tg_id':p['tg_id'],'escrow':{'$gt':0}}):
        if contract.get('owner',{}).get('character_created_at')==p.get('created_at'):escrow.append({'name':contract.get('title','عهدنامه'),'gold':contract['escrow']})
    return {'resources':numbers(calculated.get('resources')),'stored_resources':numbers(p.get('resources')),'reserve_troops':reserve,'reserve_equipment':equipment,
            'troops':troop_totals,'equipment':equipment_totals,'armies':active_armies,'castles':owned_castles(p),'buildings':buildings,'items':inventory,'contract_escrow':escrow,
            'men':sum(v for k,v in troop_totals.items() if k not in NAVAL_TROOPS),'ships':sum(troop_totals.get(k,0) for k in NAVAL_TROOPS),
            'army_count':len(active_armies),'points':float(calculated.get('points',0) or 0),'stats':numbers(calculated.get('stats')),
            'dead':bool(p.get('is_dead')),'retired':bool(p.get('registration_reset'))}

async def capture(force=False):
    season=await current_season()
    if not season:return
    at=real_now();hour=at.replace(minute=0,second=0,microsecond=0)
    runid=season['_id']+':'+hour.isoformat()
    completed=await db.analytics_runs.find_one({'_id':runid,'complete':True})
    if completed and not force:return
    await archive_sources(season)
    ids=await admin_ids();armies={}
    async for c in db.campaigns.find({'active':True}):armies.setdefault(c.get('tg_id'),[]).append(c)
    templates={str(t['_id']):t async for t in db.items.find({}, {'name':1})}
    projection={k:1 for k in ('tg_id','name','created_at','region','castle','landless','castle_buildings','buildings','resources','troops','equipment','last_tick','stats','points','is_dead','registration_reset','item_effects')}
    async for p in players.find({},projection):
        if p['tg_id'] in ids:continue
        if not p.get('created_at'):continue
        ident=runid+':'+str(p['tg_id'])
        # One observed state per account/hour. Manual exports never overwrite history.
        if await snapshots.find_one({'_id':ident}):continue
        sample={'_id':ident,'season':season['_id'],'uid':p['tg_id'],'name':p.get('name','بازیکن'),'character':character_key(p),'hour':hour,'captured_at':at,
                'game_at':now(),'paused':game_clock.paused(),'state':await asset_state(p,armies.get(p['tg_id'],[]),templates)}
        await snapshots.update_one({'_id':ident},{'$setOnInsert':sample},upsert=True)
    await db.analytics_runs.update_one({'_id':runid},{'$set':{'complete':True,'at':at,'game_at':now()}},upsert=True)
    await snapshots.delete_many({'captured_at':{'$lt':at-timedelta(days=35)}})

async def ensure_indexes():
    await snapshots.create_index([('uid',1),('captured_at',-1)])
    await snapshots.create_index([('season',1),('hour',-1)])
    await events.create_index([('season',1),('source',1)])
    await files.create_index('expires_at',expireAfterSeconds=0)
    await yearbooks.create_index('frozen_at')

async def watcher():
    from project_engine import game_state_lock
    while True:
        try:
            async with game_state_lock:
                await game_clock.load()
                await capture()
        except Exception:logging.getLogger(__name__).exception('analytics hourly capture failed')
        await asyncio.sleep(60)

def add_metric(table,uid,name,metric,value=1):
    if uid is None:return
    uid=str(uid);row=table.setdefault(uid,{'uid':uid,'name':name or uid,'metrics':{},'role_resources':{}})
    row['metrics'][metric]=row['metrics'].get(metric,0)+value
def in_window(value,season):
    value=instant(value)
    return bool(value and season['epoch']<=value<season['end'])

async def season_data(season):
    table={};daily=[{'day':i+1,'roles':0,'attacks':0,'trades':0} for i in range(30)];sources={}
    ids=await admin_ids();wins=set()
    async for event in events.find({'season':season['_id']}):
        source=event['source'];r=event['data'];sources[source]=sources.get(source,0)+1
        stamp=instant(r.get('game_at') if source=='market_history' else r.get('created_at'))
        day=min(29,max(0,(stamp-season['epoch']).days)) if stamp else None
        uid=r.get('tg_id',r.get('owner_id'));name=r.get('player_name') or r.get('owner_name')
        if uid in ids:continue
        if source=='roleplays' and not r.get('admin_generated'):
            add_metric(table,uid,name,'roles');daily[day]['roles']+=1
            if r.get('admin_score') is not None and in_window(r.get('scored_at'),season):add_metric(table,uid,name,'role_score',max(0,float(r['admin_score'])))
            if r.get('resolved') and in_window(r.get('resolved_at'),season):
                add_metric(table,uid,name,'resolved_roles')
                for adjustment in r.get('admin_adjustments',[]):
                    if adjustment.get('tg_id')!=uid:continue
                    for resource,amount in numbers(adjustment.get('resources')).items():
                        record=table[str(uid)]['role_resources'];record[resource]=record.get(resource,0)+amount
                        if resource=='gold':
                            add_metric(table,uid,name,'role_gold_gain',max(0,amount));add_metric(table,uid,name,'role_gold_net',amount)
        elif source=='campaigns':
            op=r.get('op_type','')
            if op in ('attack','siege','naval_raid'):
                add_metric(table,uid,name,'attacks');daily[day]['attacks']+=1
                add_metric(table,uid,name,'men_dispatched',r.get('men_committed',0) or 0)
            elif op in ('defend','support','naval_defend'):add_metric(table,uid,name,'defenses')
            battle=r.get('medal_outcome_battle_id') or r.get('engagement_campaign_id') or event['source_id']
            if r.get('medal_outcome_recorded') and in_window(r.get('combat_resolved_at'),season):
                for winner in set(r.get('winner_tg_ids') or []):
                    if winner not in ids and (battle,winner) not in wins:
                        wins.add((battle,winner));add_metric(table,winner,None,'battle_wins')
        elif source=='market_history' and r.get('status')=='completed':
            daily[day]['trades']+=1
            if r.get('buyer_id') not in ids:
                add_metric(table,r.get('buyer_id'),r.get('buyer_name'),'trades');add_metric(table,r.get('buyer_id'),r.get('buyer_name'),'market_buy_gold',r.get('total',0))
            if r.get('seller_id') not in ids:
                add_metric(table,r.get('seller_id'),r.get('seller_name'),'market_sell_gold',r.get('total',0))
        elif source=='caravans':add_metric(table,uid,name,'caravans')
        elif source=='spy_missions':
            add_metric(table,uid,name,'spy_missions')
            if r.get('resolved') and r.get('success'):add_metric(table,uid,name,'successful_spies')
        elif source=='projects' and r.get('status')!='invalid':add_metric(table,uid,name,'projects')
    # Current account names label records; no account/profile secrets enter exports.
    async for p in players.find({}, {'tg_id':1,'name':1}):
        if str(p['tg_id']) in table:table[str(p['tg_id'])]['name']=p.get('name',str(p['tg_id']))
    return {'players':table,'daily':daily,'sources':sources}

def esc(value):return html.escape(str(value),quote=True)
def num(value):
    v=float(value or 0)
    text=f'{v:,.2f}'.rstrip('0').rstrip('.') if v%1 else f'{int(v):,}'
    return text.translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
def stamp(value):
    value=instant(value)
    return value.replace(tzinfo=UTC).astimezone(TEHRAN).strftime('%Y/%m/%d · %H:%M') if value else '—'

CSS='''*{box-sizing:border-box}body{margin:0;background:#111512;color:#e9e1cf;font-family:ReportPeyda,Tahoma,sans-serif;line-height:1.9}main{max-width:1240px;margin:auto;padding:44px 28px 80px}header{text-align:center;border:1px solid #b99b5866;border-top:4px solid #ac3841;padding:42px 24px;background:radial-gradient(ellipse at top,#70502c55,transparent 75%),#1a2019}header small,.eyebrow{color:#bfa570;letter-spacing:2px;font-size:11px}h1{font-size:40px;line-height:1.5;margin:14px 0}h2{font-size:25px;color:#dfc48a;margin:30px 0 15px}h3{font-size:18px;margin:6px 0;color:#d9c499}p{margin:8px 0}.ornament{font:28px Georgia,serif;letter-spacing:5px;color:#d7b76e;margin:18px 0}.sub,.muted{color:#a8ad9e;font-size:12px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:24px 0}.stat,.panel{background:#1b211a;border:1px solid #a48b4c44;border-radius:8px;padding:20px}.stat b{display:block;font-size:32px;color:#e4c47e}.stat span{font-size:12px;color:#acb09d}.notice{border-right:3px solid #af7b4a;background:#b48e4b12;padding:17px 20px;font-size:13px;color:#c9bc9e;margin:20px 0}.rank-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.ranking{padding:24px;border:1px solid #9f854a55;background:linear-gradient(145deg,#29281c,#171d17);border-radius:8px}.winner{font-size:24px;color:#f0d392;margin:12px 0}.bar-row{display:grid;grid-template-columns:25px minmax(90px,1fr) 70px;gap:12px;align-items:center;font-size:12px;margin:12px 0}.track{height:5px;background:#53513b55;border-radius:3px;overflow:hidden;grid-column:2/4}.track i{display:block;height:100%;background:linear-gradient(90deg,#8d3039,#d0aa62)}table{width:100%;border-collapse:collapse;font-size:12px}th{color:#dfc48a;background:#c0a15b10;text-align:right}td,th{padding:11px 12px;border-bottom:1px solid #bc9d5c25;vertical-align:top}td.num{font-variant-numeric:tabular-nums;white-space:nowrap}.table-wrap{overflow:auto;border:1px solid #ab8d4933;border-radius:8px;margin:15px 0}details{margin:14px 0;background:#1a2019;border:1px solid #9f854a44;border-radius:7px;padding:16px}summary{cursor:pointer;color:#d8bd80;font-weight:bold;min-height:32px}.chip{display:inline-block;border:1px solid #b39b6044;border-radius:14px;padding:2px 9px;font-size:10px;color:#cebd94;margin:3px}.missing{color:#9c9d90}.delta.plus{color:#a9c79a}.delta.minus{color:#e49e98}.chart{display:flex;gap:5px;align-items:flex-end;min-height:165px;padding-top:25px}.day{flex:1;min-width:12px;text-align:center;font-size:9px;color:#aaa88e}.column{height:120px;display:flex;align-items:flex-end;justify-content:center;gap:2px}.column i{display:block;min-width:3px;width:32%;background:#ccb16b}.column i.red{background:#a7464a}footer{text-align:center;color:#a99b76;font-size:11px;padding:35px 0 0;border-top:1px solid #a48b4c55;margin-top:35px}.section-note{font-size:12px;color:#929b89}.identity{font-size:11px;color:#9ca48e}.wordmark{font:52px Georgia;color:#ddbe7d}.svg-line{display:block;width:140px;height:15px;margin:10px auto}.empty{text-align:center;color:#a8ad9e;padding:30px}.asset-lines{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;font-size:12px}.asset-lines div{border-bottom:1px dotted #a48b4c44;padding:7px}.asset-lines b{float:left;color:#e1cd9d}.group-label{color:#bca574;font-size:11px}.period{font-size:12px;color:#c5ba9d}a{color:#d7b76e}@media(max-width:750px){main{padding:20px 14px}header{padding:30px 15px}h1{font-size:28px}.grid{grid-template-columns:1fr 1fr}.rank-grid{grid-template-columns:1fr}.asset-lines{grid-template-columns:1fr}.chart{min-width:600px}.panel,.ranking{padding:16px}.table-wrap{max-width:100%}}@media print{body{background:white;color:#241e16}main{max-width:none;padding:0}header,.panel,.ranking,.stat,details{background:#fffdf5;color:#241e16;border-color:#cbb57d}h1,h2,h3,.winner,.stat b,summary{color:#674b23}.muted,.sub,.section-note,.identity{color:#655b48}.rank-grid{grid-template-columns:1fr 1fr}table{font-size:10px}th{color:#674b23}td,th{border-color:#ddd0af}.table-wrap{overflow:visible}details{break-inside:avoid}header{break-after:avoid}.notice{color:#5b4d32}.chip{color:#5b4d32}}
'''

def document(title,subtitle,body,at=None):
    font_css=''
    font=Path(__file__).with_name('report_assets')/'peyda-regular.woff2'
    if font.exists():font_css="@font-face{font-family:ReportPeyda;src:url(data:font/woff2;base64,"+base64.b64encode(font.read_bytes()).decode()+")}"
    return '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\';style-src \'unsafe-inline\';font-src data:;base-uri \'none\';form-action \'none\'"><title>'+esc(title)+'</title><style>'+font_css+CSS+'</style></head><body><main><header><div class="wordmark">V</div><small>VALYRIA · THE ROYAL ARCHIVES</small><div class="ornament">'+ORNAMENT+'</div><h1>'+esc(title)+'</h1><p class="sub">'+esc(subtitle)+'</p><svg class="svg-line" viewBox="0 0 140 15" aria-hidden="true"><path d="M0 8H57L70 1L83 8H140M57 8L70 14L83 8" fill="none" stroke="#b99b58"/></svg><p class="period">تهیهٔ سالنامه: '+stamp(at or real_now())+'</p></header>'+body+'<footer>'+ORNAMENT+'<p>والریا · سالنامهٔ فصل</p></footer></main></body></html>'

def table_html(headers,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'

METRICS=[('role_gold_gain','بیشترین سکهٔ دریافتی از نتایج رول','سکه'),('role_score','بیشترین امتیاز ثبت‌شدهٔ رول','امتیاز'),('attacks','بیشترین لشکرکشی تهاجمی','فرمان'),('battle_wins','بیشترین پیروزی ثبت‌شدهٔ نبرد','پیروزی'),('roles','فعال‌ترین نویسندگان رول','رول'),('men_dispatched','بیشترین اعزام نفرات در حمله‌ها','نفر ـ اعزام'),('market_buy_gold','بیشترین خرید بازار','سکه'),('market_sell_gold','بیشترین فروش بازار','سکه'),('caravans','بیشترین کاروان ارسالی','کاروان'),('spy_missions','بیشترین مأموریت جاسوسی','مأموریت'),('projects','بیشترین طرح پروژه','طرح'),('defenses','بیشترین استقرار دفاعی','فرمان')]

def render_season(season,data):
    people=list(data['players'].values());tot=lambda metric:sum(r['metrics'].get(metric,0) for r in people)
    elapsed=min(30,max(0,(now()-season['epoch']).days+1))
    body='<div class="grid">'+''.join('<div class="stat"><b>'+num(value)+'</b><span>'+esc(label)+'</span></div>' for label,value in [('بازیکن دارای سابقه',len(people)),('رول ثبت‌شده',tot('roles')),('فرمان تهاجمی',tot('attacks')),('روز تحت پوشش فعلی',elapsed)])+'</div>'
    body+='<div class="notice">بازهٔ فصل: روز ۱ تا ۳۰ شمارندهٔ بازی؛ از '+stamp(season['epoch'])+' تا پیش از '+stamp(season['end'])+'. '+('در گزارش میان‌فصل، روزهای آینده خالی نمایش داده می‌شوند.' if now()<season['end'] else 'این سالنامه مخصوص همین فصل است.')+'</div>'
    body+='<h2>نشان‌های فصل</h2><div class="rank-grid">'
    for metric,title,unit in METRICS:
        ranked=sorted((r for r in people if r['metrics'].get(metric,0)>0),key=lambda r:(-r['metrics'][metric],r['name']))[:5]
        body+='<section class="ranking"><span class="eyebrow">نشان افتخار</span><h3>'+esc(title)+'</h3>'
        if not ranked:body+='<p class="empty">برای این نشان رکوردی ثبت نشده است.</p>'
        else:
            maximum=ranked[0]['metrics'][metric]
            ties=sum(r['metrics'].get(metric,0)==maximum for r in people)
            body+='<div class="winner">'+esc(ranked[0]['name'])+('</div><span class="chip">رکورد مشترک با '+num(ties-1)+' نفر دیگر</span>' if ties>1 else '</div>')
            for i,r in enumerate(ranked):
                value=r['metrics'][metric];width=max(1,min(100,value/maximum*100))
                body+='<div class="bar-row"><span>'+num(i+1)+'</span><span>'+esc(r['name'])+'</span><b>'+num(value)+'</b><div class="track"><i style="width:'+str(round(width,2))+'%"></i></div></div>'
            body+='<p class="section-note">واحد: '+esc(unit)+'</p>'
        body+='</section>'
    body+='</div><h2>ضرب‌آهنگ سی روز</h2><p class="section-note">طلایی: رول‌ها · قرمز: فرمان‌های تهاجمی</p><div class="table-wrap panel"><div class="chart">'
    maximum=max([1]+[max(d['roles'],d['attacks']) for d in data['daily']])
    for d in data['daily']:
        body+='<div class="day" title="روز '+num(d['day'])+' · رول '+num(d['roles'])+' · حمله '+num(d['attacks'])+'"><div class="column"><i style="height:'+str(d['roles']/maximum*120)+'px"></i><i class="red" style="height:'+str(d['attacks']/maximum*120)+'px"></i></div>'+num(d['day'])+'</div>'
    body+='</div></div>'
    body+=table_html(['روز بازی','رول ثبت‌شده','فرمان تهاجمی','معاملهٔ تکمیل‌شده'],[[num(d['day']),num(d['roles']) if d['day']<=elapsed else 'هنوز نرسیده',num(d['attacks']) if d['day']<=elapsed else 'هنوز نرسیده',num(d['trades']) if d['day']<=elapsed else 'هنوز نرسیده'] for d in data['daily']])
    body+='<h2>دفتر عملکرد بازیکنان</h2>'
    for r in sorted(people,key=lambda r:(-r['metrics'].get('role_score',0),r['name'])):
        m=r['metrics'];body+='<details><summary>'+esc(r['name'])+' <span class="identity">شناسهٔ حساب '+esc(r['uid'])+'</span></summary>'
        body+='<div class="asset-lines">'+''.join('<div>'+esc(title)+'<b>'+num(m.get(k,0))+'</b></div>' for k,title,_ in METRICS)+'</div>'
        if r['role_resources']:
            body+='<h3>خالص تغییر منابع ناشی از نتیجهٔ رول</h3>'+table_html(['منبع','تغییر خالص ثبت‌شده'],[[esc(RESOURCE_NAMES.get(k,k)),num(v)] for k,v in r['role_resources'].items()])
        body+='</details>'
    return document(season['title']+' · سالنامهٔ فصل','روایت آماری رقابت، قلم و فرماندهی · روزهای ۱ تا ۳۰',body)

async def freeze_season(reason='manual'):
    """Store one immutable, reset-safe yearbook before operational data is removed."""
    season=await current_season()
    if not season:return None
    existing=await yearbooks.find_one({'_id':season['_id']})
    if existing:return existing
    await archive_sources(season)
    content=render_season(season,await season_data(season))
    encoded=content.encode('utf-8')
    row={'_id':season['_id'],'title':season['title'],'epoch':season['epoch'],'end':season['end'],
         'content':content,'sha256':hashlib.sha256(encoded).hexdigest(),'bytes':len(encoded),
         'frozen_at':real_now(),'frozen_game_at':now(),'reason':reason}
    await yearbooks.update_one({'_id':season['_id']},{'$setOnInsert':row},upsert=True)
    await seasons.update_one({'_id':season['_id']},{'$set':{'frozen_at':row['frozen_at'],'yearbook_sha256':row['sha256']}})
    return await yearbooks.find_one({'_id':season['_id']}) or row

def basket_html(values,labels=None):
    labels=labels or RESOURCE_NAMES
    return '<div class="asset-lines">'+''.join('<div>'+esc(labels.get(k,k))+'<b>'+num(v)+'</b></div>' for k,v in sorted(values.items()))+'</div>' if values else '<p class="muted">موردی ثبت نشده است.</p>'

def state_details(sample,previous=None):
    s=sample['state'];body='<p class="muted">نمونه‌برداری واقعی: '+stamp(sample['captured_at'])+' · ساعت داخلی بازی: '+stamp(sample['game_at'])+' · '+('بازی متوقف' if sample['paused'] else 'بازی در حال اجرا')+'</p>'
    body+='<h3>منابع محاسبه‌شده</h3>'+basket_html(s['resources'])
    if s.get('resources')!=s.get('stored_resources'):body+='<details><summary>موجودی ذخیره‌شده پیش از محاسبهٔ تولید</summary>'+basket_html(s['stored_resources'])+'</details>'
    if previous and previous['character']==sample['character']:
        delta={k:s['resources'].get(k,0)-previous['state']['resources'].get(k,0) for k in set(s['resources'])|set(previous['state']['resources'])}
        delta={k:v for k,v in delta.items() if abs(v)>.00001}
        body+='<h3>تغییر نسبت به نمونهٔ ساعتی قبل</h3>'+basket_html(delta)
    body+='<h3>نیروهای ذخیره و خارج از لشکر</h3>'+basket_html(s['reserve_troops'],{k:unit_name(k) for k in s['reserve_troops']})
    body+='<h3>ادوات ذخیره</h3>'+basket_html(s['reserve_equipment'],{k:unit_name(k) for k in s['reserve_equipment']})
    body+='<h3>لشکرها · تفکیک نیرو، کشتی و ادوات</h3>'
    for a in s['armies']:
        body+='<section class="panel"><h3>'+esc(a['name'])+'</h3><p class="muted">'+esc(a['id'])+' · '+esc(a.get('origin') or '—')+' ← '+esc(a.get('destination') or '—')+'</p>'
        if a.get('group'):body+='<p class="group-label">عضو لشکر مشترک · '+esc(a['group'])+'</p>'
        if a.get('mercenary'):body+='<span class="chip">نیروی قراردادی</span>'
        if a.get('battle'):body+='<span class="chip">درگیر نبرد</span>'
        body+=basket_html(a['troops'],{k:unit_name(k) for k in a['troops']})+basket_html(a['equipment'],{k:unit_name(k) for k in a['equipment']})+'</section>'
    if not s['armies']:body+='<p class="muted">لشکر فعال ثبت نشده است.</p>'
    body+='<h3>قلعه‌ها و سطح ساختمان‌ها</h3>'
    for castle,state in s['buildings'].items():body+='<details><summary>'+esc(castle)+'</summary>'+basket_html(state,{k:BUILDINGS.get(k,{}).get('name',k) for k in state})+'</details>'
    body+='<h3>آیتم‌ها</h3>'+(''.join('<span class="chip">'+esc(i['name'])+(' · در امانت فروشگاه' if i.get('escrow') else '')+'</span>' for i in s['items']) or '<p class="muted">آیتمی ثبت نشده است.</p>')
    if s.get('contract_escrow'):body+='<h3>پاداش‌های رزروشدهٔ عهدنامه</h3>'+table_html(['عهدنامه','سکهٔ رزروشده'],[[esc(r['name']),num(r['gold'])] for r in s['contract_escrow']])
    return body

def timeline_svg(observed,metric,color):
    values=[r['state']['resources'].get('gold',0) if metric=='gold' else r['state']['men'] for r in observed if r]
    if not values:return '<p class="empty">نمونه‌ای برای رسم نمودار ثبت نشده است.</p>'
    low=min(values);high=max(values);span=high-low or 1
    paths=[];segment=[];dots=[];last_character=None
    for i,r in enumerate(observed):
        if not r:
            if segment:paths.append(segment);segment=[]
            last_character=None;continue
        if last_character and last_character!=r['character'] and segment:paths.append(segment);segment=[]
        last_character=r['character'];value=r['state']['resources'].get('gold',0) if metric=='gold' else r['state']['men']
        x=50+i*34;y=135-(value-low)/span*110
        segment.append((x,y));dots.append((x,y))
    if segment:paths.append(segment)
    return '<svg viewBox="0 0 900 180" role="img" aria-label="روند ساعتی با فاصله در ساعت‌های فاقد داده" style="width:100%;height:auto"><path d="M45 25H855M45 80H855M45 135H855" stroke="#ae965333" fill="none"/>'+''.join('<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in points)+'" fill="none" stroke="'+color+'" stroke-width="3"/>' for points in paths)+''.join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="{color}"/>' for x,y in dots)+'<text x="885" y="28" fill="#bda879" font-size="12">'+num(high)+'</text><text x="885" y="140" fill="#bda879" font-size="12">'+num(low)+'</text>'+''.join('<text x="'+str(50+i*34)+'" y="165" fill="#a8ad9e" font-size="11" text-anchor="middle">'+num(24-i)+' ساعت پیش</text>' for i in (0,6,12,18))+'</svg>'

def render_hourly(uid,samples,at,current=None):
    slots=[at-timedelta(hours=24-i) for i in range(24)]
    name=current['name'] if current else samples[-1]['name'] if samples else str(uid)
    rows=[];previous=None;details='';known=0;observed=[]
    for index,slot in enumerate(slots):
        upper=slot+timedelta(hours=1)
        candidates=[r for r in samples if slot<=r['captured_at']<upper or (index==23 and r['captured_at']==at)]
        sample=max(candidates,key=lambda r:r['captured_at']) if candidates else None
        observed.append(sample)
        label=stamp(slot)+' ← '+stamp(upper)
        if not sample:
            rows.append([label,'<span class="missing">ثبت نشده</span>']+['—']*5);previous=None;continue
        known+=1;s=sample['state']
        change='—' if not previous or sample['character']!=previous['character'] else num(s['men']-previous['state']['men'])
        rows.append([label,esc(sample['name']),num(s['resources'].get('gold',0)),num(s['army_count']),num(s['men']),num(s['ships']),change])
        details+='<details><summary>'+label+' · '+esc(sample['name'])+' · '+num(s['men'])+' نفر / '+num(s['ships'])+' کشتی</summary>'+state_details(sample,previous)+'</details>'
        previous=sample
    body='<div class="grid">'+''.join('<div class="stat"><b>'+num(v)+'</b><span>'+esc(k)+'</span></div>' for k,v in [('بازهٔ ساعتی',24),('نمونهٔ موجود',known),('ساعت بدون سابقه',24-known),('لشکر فعال فعلی',current['state']['army_count'] if current else 0)])+'</div>'
    body+='<div class="notice">بازهٔ واقعی: '+stamp(at-timedelta(hours=24))+' تا '+stamp(at)+'، به وقت تهران و مستقل از توقف بازی. جدول شامل ۲۴ بازهٔ ساعتی اخیر است؛ زمان دقیق برداشت هر نمونه در جزئیات آمده است. ساعت‌های بدون سابقه تخمین زده نمی‌شوند.<br>نمونهٔ ساعتی، وضعیت مشاهده‌شده در آن ساعت است؛ تغییرات میان دو نمونه و علت تغییر از این جدول به‌تنهایی قابل استنتاج نیست. اختلاف ساعت‌های فاقد نمونه یا کاراکترهای متفاوت محاسبه نمی‌شود.</div>'
    body+='<h2>روند دارایی و نفرات</h2><div class="panel"><h3>سکهٔ قابل خرج</h3>'+timeline_svg(observed,'gold','#d3b46d')+'<h3>نفرات نظامی</h3>'+timeline_svg(observed,'men','#bd5a5d')+'<p class="section-note">خط نمودار از ساعت‌های بدون نمونه و مرز تغییر کاراکتر عبور نمی‌کند.</p></div>'
    body+='<h2>خط زمانی دارایی و نیرو</h2>'+table_html(['بازهٔ ساعت واقعی','کاراکتر','سکه','لشکر فعال','نفرات نظامی','کشتی‌ها','تغییر نفرات'],rows)
    if current:body+='<h2>وضعیت فعلی هنگام صدور گزارش</h2><section class="panel">'+state_details(current)+'</section>'
    body+='<h2>دفتر تفصیلی هر ساعت</h2>'+details+'<h2>تعریف شمارنده‌ها</h2><div class="panel"><p>نفرات نظامی برابر نیروهای ذخیرهٔ ثبت‌شده به‌علاوهٔ نفرات لشکرهای فعال متعلق به بازیکن است. کشتی‌ها جدا شمرده می‌شوند؛ مردمِ منابع، سرباز محسوب نمی‌شوند. لشکر مشترک از روی لشکرهای واقعی اعضا محاسبه می‌شود و مجموع گروه دوباره جمع زده نمی‌شود.</p><p>منابع محاسبه‌شده، تولید معوق را روی یک نسخهٔ خواندنی محاسبه می‌کنند؛ صدور گزارش دارایی واقعی را تغییر نمی‌دهد. موجودی ذخیره‌شده نیز در صورت تفاوت آمده است. سرمایه و بدهی نهادها جزو موجودی قابل خرج شخصی جمع زده نمی‌شوند.</p></div>'
    return document('دفتر ۲۴ ساعتهٔ '+name,'شناسهٔ بازیکن '+str(uid)+' · نمونه‌برداری مستقل از ساعت بازی',body,at)

async def issue_file(content,name,uid):
    at=real_now()
    if await files.count_documents({'author':uid,'created_at':{'$gte':at-timedelta(minutes=1)}})>=6:raise HTTPException(429,'تعداد درخواست گزارش زیاد است؛ یک دقیقه بعد تلاش کنید')
    if len(content.encode('utf-8'))>12_000_000:raise HTTPException(413,'حجم گزارش از سقف فایل بیشتر است؛ برای بررسی این پرونده با پشتیبانی فنی هماهنگ شود')
    token=secrets.token_urlsafe(32);filename='valyria-'+name+'-'+at.strftime('%Y%m%d-%H%M%S')+'.html'
    await files.insert_one({'_id':hashlib.sha256(token.encode()).hexdigest(),'author':uid,'content':content,'filename':filename,'created_at':at,'expires_at':at+timedelta(minutes=10)})
    return {'path':'/api/analytics-files/'+token,'filename':filename}

@router.get('/admin/analytics')
async def management(user=Depends(full)):
    current=await current_season()
    return {'current_season':current['_id'] if current else None,'seasons':[{'id':s['_id'],'title':s['title'],'epoch':s['epoch'],'end':s['end'],'archived':bool(s.get('frozen_at'))} async for s in seasons.find({}).sort('epoch',-1).limit(100)],
            'players':[{'id':p['tg_id'],'name':p.get('name',str(p['tg_id'])),'dead':bool(p.get('is_dead'))} async for p in players.find({'tg_id':{'$nin':list(await admin_ids())}},{'tg_id':1,'name':1,'is_dead':1}).sort('name',1)]}

class SeasonRequest(BaseModel):
    season:str=''

@router.post('/admin/analytics/season')
async def export_season(body:SeasonRequest,user=Depends(full)):
    await capture(force=True)
    archived=await yearbooks.find_one({'_id':body.season}) if body.season else None
    season=await seasons.find_one({'_id':body.season}) if body.season else await current_season()
    if not season and not archived:raise HTTPException(404,'سیزن ثبت‌شده‌ای وجود ندارد')
    if not archived:archived=await yearbooks.find_one({'_id':season['_id']})
    content=archived['content'] if archived else render_season(season,await season_data(season))
    return await issue_file(content,'season-'+(archived or season)['_id'],user['id'])

@router.post('/admin/analytics/players/{uid}/hourly')
async def export_hourly(uid:int,user=Depends(full)):
    if uid in await admin_ids():raise HTTPException(400,'یک بازیکن انتخاب کنید')
    await capture();at=real_now()
    samples=[r async for r in snapshots.find({'uid':uid,'captured_at':{'$gte':at-timedelta(hours=24),'$lte':at}}).sort('captured_at',1)]
    # Pick the last actually observed sample per hour across season resets.
    p=await players.find_one({'tg_id':uid});current=None
    if p:
        armies=[c async for c in db.campaigns.find({'tg_id':uid,'active':True})]
        templates={str(t['_id']):t async for t in db.items.find({}, {'name':1})}
        current={'name':p.get('name',str(uid)),'character':character_key(p),'captured_at':at,'game_at':now(),'paused':game_clock.paused(),'state':await asset_state(p,armies,templates)}
    if not p and not samples:raise HTTPException(404,'بازیکن یا سابقهٔ ۲۴ ساعته پیدا نشد')
    return await issue_file(render_hourly(uid,samples,at,current),'player-'+str(uid),user['id'])

@router.api_route('/analytics-files/{token}',methods=['GET','HEAD'])
async def download(token:str):
    if len(token)!=43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):raise HTTPException(404,'مهلت فایل تمام شده یا لینک معتبر نیست')
    row=await files.find_one({'_id':hashlib.sha256(token.encode()).hexdigest(),'expires_at':{'$gt':real_now()}})
    if not row:raise HTTPException(404,'مهلت فایل تمام شده یا لینک معتبر نیست')
    return Response(row['content'],media_type='text/html; charset=utf-8',headers={'Content-Disposition':'attachment; filename="'+row['filename']+'"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"sandbox; default-src 'none'; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'"})
