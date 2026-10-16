"""Administrative formation controls; constituent ownership remains unchanged."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user,get_full_admin,get_admin
from db import db,players,campaigns
from game import now
from army_groups import groups,members,oid,set_members,composition

router=APIRouter(prefix='/api/admin/army-groups')
async def full(user=Depends(get_user)):return await get_full_admin(user)
async def reader(user=Depends(get_user)):return await get_admin(user)

async def listings(leader_id=None):
    q={'active':True}
    if leader_id is not None:q['leader_tg_id']=leader_id
    out=[]
    async for g in groups.find(q):
        rows=await members(g)
        leader=await players.find_one({'tg_id':g['leader_tg_id']}) or {}
        out.append({'id':str(g['_id']),'name':g.get('name','لشکر مشترک'),'leader_id':g['leader_tg_id'],
            'leader_name':leader.get('name','فرمانده نامشخص'),'location':rows[0].get('target_castle') if rows else '',
            'in_battle':any(a.get('engagement_locked') or (a.get('engagement_campaign_id') and not a.get('battle_left_at')) for a in rows),'active':True,'is_group':True,
            'members':[{'id':str(a['_id']),'name':a.get('name','لشکر'),'player':a.get('player_name',''),
                'tg_id':a['tg_id'],'men':a.get('men_committed',0),'location':a.get('target_castle'),
                **composition([a])} for a in rows],**composition(rows)})
    return out

@router.get('')
async def list_groups(leader_id:int|None=None,user=Depends(reader)):
    return await listings(leader_id)

class Action(BaseModel):
    action:Literal['relocate','split','detach','disband','destroy']
    destination:str=''
    member_id:str=''
    confirm_battle_exit:bool=False

@router.post('/{group_id}')
async def operate(group_id:str,body:Action,user=Depends(full)):
    from routers import admin,war
    g=await groups.find_one({'_id':oid(group_id),'active':True})
    if not g:raise HTTPException(404,'لشکر مشترک فعال پیدا نشد')
    rows=await members(g)
    if not rows:raise HTTPException(409,'عضو فعالی باقی نمانده است')
    if body.action=='detach':
        aid=oid(body.member_id)
        if aid not in [a['_id'] for a in rows]:raise HTTPException(400,'لشکر عضو این گروه نیست')
        await set_members(g,[a['_id'] for a in rows if a['_id']!=aid])
        return {'ok':True}
    if body.action=='split':
        await set_members(g,[])
        return {'ok':True}
    if any(a.get('engagement_locked') or (a.get('engagement_campaign_id') and not a.get('battle_left_at')) for a in rows) and not body.confirm_battle_exit:
        raise HTTPException(409,'خروج تمام اعضای لشکر مشترک از نبرد را تأیید کنید')
    if body.action=='relocate':
        names,_=await war.all_castle_names_and_ports()
        if body.destination.strip() not in names:raise HTTPException(400,'مقصد در نقشه وجود ندارد')
        for a in rows:
            await admin._relocate_campaign(str(a['_id']),admin.RelocateCampaignBody(destination=body.destination,confirm_battle_exit=True),user,allow_group=True)
    else:
        if body.action=='disband' and any(a.get('mercenary_contract_id') for a in rows):
            raise HTTPException(409,'لشکر قراردادی باید از بخش قرارداد مزدوری تعیین تکلیف شود')
        # Splitting removes derived tags without moving or returning any troops.
        await set_members(g,[])
        for a in rows:
            if body.action=='disband':await admin.admin_disband_campaign(str(a['_id']),user)
            else:await admin.admin_destroy_campaign(str(a['_id']),user)
    return {'ok':True,'affected':len(rows)}
