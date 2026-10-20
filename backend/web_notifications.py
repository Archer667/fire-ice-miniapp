import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth import get_user
from db import db, messages
from game import now
from config import SYSTEM_SENDER_ID, SYSTEM_SENDER_NAME

router=APIRouter(prefix='/api/notifications',tags=['notifications'])

class PlainText(HTMLParser):
    def __init__(self): super().__init__();self.parts=[]
    def handle_data(self,data): self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag in ('br','p','div'): self.parts.append('\n')

async def persist_notice(uid,text,image=None,parse_mode=None):
    if not await db.web_accounts.find_one({'uid':uid},{'_id':1}): return
    if parse_mode=='HTML':
        parser=PlainText();parser.feed(text);text=''.join(parser.parts)
    await messages.insert_one({'from_id':SYSTEM_SENDER_ID,'from_name':SYSTEM_SENDER_NAME,'to_id':uid,'to_name':'','text':text[:8000],'kind':'general','read':False,'created_at':now(),'real_created_at':datetime.now(timezone.utc),**({'image_url':image} if image else {})})

@router.get('')
async def list_notices(page:int=1,kind:str='',unread:bool=False,archived:bool=False,q:str='',user=Depends(get_user)):
    if page<1 or page>10000 or len(q)>100 or len(kind)>40: raise HTTPException(400,'جست‌وجو معتبر نیست')
    query={'to_id':user['id'],'from_id':SYSTEM_SENDER_ID,'archived':True if archived else {'$ne':True}}
    if kind:
        patterns={'war':'نبرد|لشکر|محاصره|حمله','rebellion':'شورش','building':'ساختمان|ارتقا','trade':'تجارت|کاروان|بازار','diplomacy':'پیمان|اتحاد','family':'خانواده|فرزند|ازدواج','project':'پروژه','institution':'سیتادل|بانک|نهاد|کیمیا|گروهان|ایمان|نگهبان|بی‌چهره'}
        aliases={'war':['war','battle','campaign','siege','attack','army','ambush'],'building':['building','construction','upgrade'],'trade':['trade','market','caravan'],'family':['family','marriage','birth'],'institution':['institution','citadel','bank','alchemists','faceless','faith','watch','golden-company']}
        pattern=patterns.get(kind,re.escape(kind)).replace('بی‌چهره','بی[\u200c\\s]*چهره')
        query['$or']=[{'kind':{'$in':aliases.get(kind,[kind])}},{'text':{'$regex':pattern,'$options':'i'}}]
    if unread: query['read']={'$ne':True}
    if q.strip(): query['text']={'$regex':re.escape(q.strip()),'$options':'i'}
    rows=[]
    async for row in messages.find(query).sort('created_at',-1).skip((page-1)*30).limit(30):
        stamp=row.get('real_created_at') or row['created_at']
        rows.append({'id':str(row['_id']),'text':row['text'],'kind':row.get('kind','general'),'read':bool(row.get('read')),'image_url':row.get('image_url'),'at':stamp.isoformat(),'clock':'real' if row.get('real_created_at') else 'game'})
    return {'rows':rows,'page':page,'total':await messages.count_documents(query),'unread':await messages.count_documents({'to_id':user['id'],'from_id':SYSTEM_SENDER_ID,'read':False,'archived':{'$ne':True}})}

class NoticeAction(BaseModel):
    ids:list[str]=Field(default_factory=list,max_length=100)
    action:str='read'

@router.post('/action')
async def notice_action(body:NoticeAction,user=Depends(get_user)):
    if body.action not in ('read','read_all','archive','restore'): raise HTTPException(400,'عملیات معتبر نیست')
    query={'to_id':user['id'],'from_id':SYSTEM_SENDER_ID}
    if body.action!='read_all':
        identities=[]
        for value in body.ids:
            if len(value)>200: raise HTTPException(400,'شناسه معتبر نیست')
            identities.append(value)
            if ObjectId.is_valid(value): identities.append(ObjectId(value))
        query['_id']={'$in':identities}
    result=await messages.update_many(query,{'$set':{'read':True,**({'archived':body.action=='archive'} if body.action in ('archive','restore') else {})}})
    return {'ok':True,'changed':result.modified_count}
