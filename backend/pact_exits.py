"""Pact exits share compensation and use durable family wallet intents."""
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException
from db import alliances, players
from game import now, apply_production
from family import operations, finish, commit, change
from project_engine import member_for

async def recover_exits():
    async for op in operations.find({'kind':'pact_exit','complete':False}):
        await finish(op)

async def exit_pact(alliance_id, departing=None, forced=False, actor=None):
    await recover_exits()
    if not ObjectId.is_valid(alliance_id):
        raise HTTPException(400,'شناسهٔ پیمان نامعتبر است')
    a=await alliances.find_one({'_id':ObjectId(alliance_id)})
    if not a or a['status'] != 'accepted':
        raise HTTPException(409,'این پیمان دیگر برقرار نیست')
    query={'group_id':a['group_id']} if a.get('group_id') else {'_id':a['_id']}
    rows=await alliances.find(query).to_list(None)
    if any(r.get('marriage_id') for r in rows):
        raise HTTPException(409,'پیمان ازدواج از بخش خانواده و با قواعد فسخ مدیریت می‌شود')
    accepted=[r for r in rows if r['status']=='accepted']
    ids={r[k] for r in accepted for k in ('from_id','to_id')}
    if departing is not None and departing not in ids:
        raise HTTPException(403,'این بازیکن عضو پذیرفته‌شدهٔ پیمان نیست')
    dissolve=departing is None or departing==a['from_id']
    removed=accepted if dissolve else [r for r in accepted if departing in (r['from_id'],r['to_id'])]
    penalty=max(0,int(next((r.get('penalty_gold',0) for r in removed if departing==r['to_id']),a.get('penalty_gold',0)))) if departing is not None else 0
    people={p['tg_id']:p async for p in players.find({'tg_id':{'$in':list(ids)}})}
    payer=people.get(departing)
    if departing is not None and not payer:
        raise HTTPException(409,'حساب پرداخت‌کننده پیدا نشد')
    if payer and not forced and apply_production(payer).get('resources',{}).get('gold',0)<penalty:
        raise HTTPException(400,f'برای خروج {penalty:,} سکه غرامت لازم داری')
    beneficiaries=sorted(ids-{departing}) if departing is not None else []
    if penalty and any(uid not in people for uid in beneficiaries):
        raise HTTPException(409,'حساب یکی از اعضا پیدا نشد؛ ابتدا وضعیت عضویت را بررسی کن')
    wallets=[]; shares={}
    if penalty:
        wallets.append({'member':member_for(payer,0),'cost':{'gold':-penalty}})
        q,remainder=divmod(penalty,len(beneficiaries))
        for i,uid in enumerate(beneficiaries):
            amount=q+(i<remainder);shares[uid]=amount
            wallets.append({'member':member_for(people[uid],0),'cost':{'gold':amount}})
    changes=[]
    removed_ids=[r['_id'] for r in removed]
    for r in removed:
        changes.append(change('alliances',{'_id':r['_id']},{'status':'dissolved' if dissolve else 'left',
            'ended_at':now(),'left_by':departing,'admin_actor':actor,'exit_penalty':penalty}))
    for uid in ids:
        count=await alliances.count_documents({'status':'accepted','_id':{'$nin':removed_ids},'$or':[{'from_id':uid},{'to_id':uid}]})
        if uid in people: changes.append(change('players',{'tg_id':uid},{'alliance_count':count}))
    for r in rows:
        if r['status']=='pending' and (dissolve or departing in (r['from_id'],r['to_id'])):
            changes.append(change('alliances',{'_id':r['_id']},{'status':'cancelled','ended_at':now()}))
            proposer=await players.find_one({'tg_id':r['from_id']})
            if proposer and r.get('wine_cost'):
                wallets.append({'member':member_for(proposer,0),'cost':{'wine':r['wine_cost']}})
    event=str(uuid4())
    label=(payer or {}).get('name','مدیریت')
    text=f"📜 {a.get('name') or 'پیمان'}\n"+(f"{label} از پیمان خارج شد." if departing is not None else 'پیمان توسط مدیریت منحل شد.')
    text+='\nکل گروه منحل شد.' if dissolve else '\nعضویت سایر اعضا برقرار است.'
    text+=f'\nغرامت کل: {penalty:,} سکه.'
    notices=[{'event':event+':'+str(uid),'recipients':[uid],'text':text+(f'\nسهم تو از غرامت: {shares[uid]:,} سکه.' if uid in shares else '')} for uid in ids]
    await commit({'_id':event,'kind':'pact_exit','complete':False,'wallets':wallets,'changes':changes,'notices':notices})
    from family import flush_notices
    await flush_notices()
    return {'ok':True,'penalty_paid':penalty,'dissolved':dissolve,'compensation':shares}
