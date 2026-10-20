"""Approval of a character without granting any castle ownership."""
from uuid import uuid4
from fastapi import HTTPException
from db import players
from game import now
from game_data import REGIONS
from character_access import status
from character_travel import destination
from family import key, commit, recover, change

async def approve(uid, region, place, actor, expected_key=''):
    await recover()
    p = await players.find_one({'tg_id': uid})
    if not p: raise HTTPException(404, 'درخواست ثبت‌نام پیدا نشد')
    if status(p) != 'pending': raise HTTPException(409, 'این درخواست دیگر در انتظار تأیید نیست؛ فهرست را تازه کن')
    if expected_key and expected_key != key(p): raise HTTPException(409, 'کاراکتر تغییر کرده؛ فهرست را تازه کن')
    if p.get('castle') or p.get('castle_buildings'): raise HTTPException(409, 'برای این کاراکتر مالکیت قلعه ثبت شده است')
    if region not in REGIONS: raise HTTPException(400, 'اقلیم معتبر انتخاب کن')
    if not place.strip(): raise HTTPException(400, 'محل اقامت اولیه را انتخاب کن')
    await destination(place)
    character = key(p)
    location = {'tg_id':uid,'name':p['name'],'place':place,'previous':None,'trip':None,'captive':None}
    fields = {'region':region,'castle':None,'castle_buildings':{},'buildings':{},'is_port':False,
              'landless':True,'pending':False,'approved_at':now(),'approved_by':actor,'last_tick':now()}
    await commit({'_id':'character-admission:'+str(uuid4()),'complete':False,'changes':[
        {'collection':'character_locations','query':{'_id':character},'update':{'$set':location},'upsert':True},
        change('players',{'tg_id':uid,'created_at':p['created_at'],'castle':None,'is_dead':{'$ne':True},'registration_reset':{'$ne':True}},fields),
    ],'notices':[{'event':'character-approved:'+character,'recipients':[uid],
        'text':f"درخواست کاراکترت تأیید شد. محل اقامت: {place}. بدون مالکیت قلعه می‌توانی سفر و امور شخصی را دنبال کنی."}]})
    return {'ok':True,'landless':True,'place':place}
