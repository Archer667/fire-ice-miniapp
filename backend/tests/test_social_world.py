"""Real escrow journal + wallets and private location access, no live database."""
import copy
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from fastapi import HTTPException
from pydantic import ValidationError
import social_world as s
import family
import project_engine as wallet
import character_travel as travel
from tests.test_institution_bank import get, put

def values(row,path):
    if not path:return [row]
    if isinstance(row,list):return [v for item in row for v in values(item,path)]
    if not isinstance(row,dict) or path[0] not in row:return []
    return values(row[path[0]],path[1:])

def matches(row,q):
    for k,v in q.items():
        if k=='$or':
            if not any(matches(row,x) for x in v):return False
            continue
        if k=='$and':
            if not all(matches(row,x) for x in v):return False
            continue
        found=values(row,k.split('.'));a=found[0] if found else None
        if isinstance(v,dict):
            for op,b in v.items():
                if op=='$exists' and bool(found)!=b:return False
                if op=='$ne' and a==b:return False
                if op=='$in' and not any(x in b for x in found):return False
                if op=='$gte' and (a is None or a<b):return False
                if op=='$gt' and (a is None or a<=b):return False
                if op=='$lt' and (a is None or a>=b):return False
                if op=='$lte' and (a is None or a>b):return False
        elif not (v is None and not found) and v not in found:return False
    return True

class Cursor:
    def __init__(self,rows):self.rows=copy.deepcopy(rows)
    def sort(self,key,direction=None):
        for k,d in reversed(key if isinstance(key,list) else [(key,direction)]):
            self.rows.sort(key=lambda r:(get(r,k) is not None,get(r,k)),reverse=d<0)
        return self
    def limit(self,n):self.rows=self.rows[:n];return self
    def __aiter__(self):self.it=iter(self.rows);return self
    async def __anext__(self):
        try:return next(self.it)
        except StopIteration:raise StopAsyncIteration

class Collection:
    def __init__(self):self.rows=[]
    def find(self,q):return Cursor([r for r in self.rows if matches(r,q)])
    async def find_one(self,q,*projection):return next((copy.deepcopy(r) for r in self.rows if matches(r,q)),None)
    async def count_documents(self,q):return sum(matches(r,q) for r in self.rows)
    async def insert_one(self,r):
        if r.get('_id') and any(x.get('_id')==r['_id'] for x in self.rows):raise AssertionError('duplicate id')
        self.rows.append(copy.deepcopy(r))
    async def update_one(self,q,u,upsert=False):
        r=next((r for r in self.rows if matches(r,q)),None);insert=False
        if r is None and upsert:r={k:v for k,v in q.items() if not isinstance(v,dict)};self.rows.append(r);insert=True
        if r is None:return SimpleNamespace(matched_count=0)
        for op,fields in u.items():
            if op=='$setOnInsert' and not insert:continue
            for k,v in fields.items():
                if op=='$addToSet':put(r,k,list(dict.fromkeys((get(r,k) or [])+[v])))
                else:put(r,k,(get(r,k) or 0)+v if op=='$inc' else v)
        return SimpleNamespace(matched_count=1)
    async def create_index(self,*a,**kw):pass

class Database:
    def __init__(self):self.collections={}
    def __getitem__(self,k):return self.collections.setdefault(k,Collection())
    def __getattr__(self,k):return self[k]

class WorldTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db=Database();self.clock=datetime(2026,10,21,12)
        self.db.players.rows=[{'_id':str(i),'tg_id':i,'name':f'Lord {i}','created_at':self.clock,'castle':chr(64+i),'region':'north','resources':{'gold':1000}} for i in (1,2,3)]
        for mod in (s,family,travel):self.enterContext(patch.object(mod,'db',self.db))
        for mod in (s,family,travel,wallet):self.enterContext(patch.object(mod,'players',self.db.players))
        for field in ('contracts','entries','articles'):self.enterContext(patch.object(s,field,self.db[{'contracts':'world_contracts','entries':'castle_life','articles':'world_news'}[field]]))
        self.enterContext(patch.object(family,'operations',self.db.family_operations))
        for name in ('locations','trips','places','captures'):self.enterContext(patch.object(travel,name,self.db['character_'+{'locations':'locations','trips':'trips','places':'places','captures':'captures'}[name]]))
        self.enterContext(patch.object(travel,'campaigns',self.db.campaigns))
        self.enterContext(patch.object(travel,'TRAVEL_GRAPH',{'A':{},'B':{},'C':{}}))
        self.enterContext(patch.object(travel,'tick',AsyncMock()))
        self.enterContext(patch('auth.get_admin_role',AsyncMock(return_value=None)))
        self.enterContext(patch.object(s,'notify_admins',AsyncMock()))
        self.enterContext(patch('text_limits.game_settings',self.db.game_settings))
        for mod in (s,family,travel):self.enterContext(patch.object(mod,'now',side_effect=lambda:self.clock))
        self.enterContext(patch.object(s.game_clock,'paused',return_value=False))
        self.enterContext(patch.object(wallet,'apply_production',side_effect=lambda p:p))
        self.enterContext(patch.object(wallet,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
    def draft(self,**kw):return s.ContractDraft(**{'request_id':uuid4(),'title':'عهدنامهٔ آزمایشی','description':'شرح کامل انجام قرارداد و شرایط تحویل','place':'AA','reward':200,'duration_days':3,**kw})
    async def row(self,ident):return await s.contracts.find_one({'_id':ident})
    async def action(self,ident,action,uid=1,**kw):
        row=await self.row(ident)
        return await s.act_contract(ident,s.ContractAction(action=action,version=row['version'],**kw),uid,self.db.players.rows[uid-1])
    async def created(self):return (await s.create_contract(self.draft(),{'id':1}))['id']
    async def assigned(self):
        ident=await self.created();await self.action(ident,'apply',2,message='برای انجام این کار آماده‌ام')
        await self.action(ident,'assign',applicant=family.key(self.db.players.rows[1]));return ident
    async def submitted(self):
        ident=await self.assigned();await self.action(ident,'submit',2,message='گزارش کامل انجام مأموریت و تحویل کار');return ident
    async def test_escrow_lifecycle_and_repeated_approval_never_pay_twice(self):
        ident=await self.submitted();self.assertEqual(self.db.players.rows[0]['resources']['gold'],800)
        row=await self.row(ident);body=s.ContractAction(action='approve',version=row['version'])
        await s.act_contract(ident,body,1,self.db.players.rows[0])
        with self.assertRaises(HTTPException):await s.act_contract(ident,body,1,self.db.players.rows[0])
        await family.recover();self.assertEqual(self.db.players.rows[1]['resources']['gold'],1200);self.assertEqual((await self.row(ident))['escrow'],0)
    async def test_duplicate_creation_same_payload_only_one_debit(self):
        body=self.draft();r=await s.create_contract(body,{'id':1});await s.create_contract(body,{'id':1})
        self.assertEqual(len(s.contracts.rows),1);self.assertEqual(self.db.players.rows[0]['resources']['gold'],800)
        with self.assertRaises(HTTPException):await s.create_contract(body.model_copy(update={'reward':250}),{'id':1})
        with self.assertRaises(HTTPException):await s.create_contract(body,{'id':2})
    async def test_insufficient_gold_makes_no_contract_or_balance_change(self):
        with self.assertRaises(HTTPException):await s.create_contract(self.draft(reward=2000),{'id':1})
        self.assertEqual(s.contracts.rows,[]);self.assertEqual(self.db.players.rows[0]['resources']['gold'],1000)
    async def test_crash_after_debit_recovers_without_charging_again(self):
        body=self.draft();original=family.wallet_once
        async def crash(*args,**kw):await original(*args,**kw);raise RuntimeError('after debit')
        with patch.object(family,'wallet_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await s.create_contract(body,{'id':1})
        await family.recover();await s.create_contract(body,{'id':1})
        self.assertEqual(self.db.players.rows[0]['resources']['gold'],800);self.assertEqual(len(s.contracts.rows),1)
    async def test_crash_after_payout_recovers_without_paying_again(self):
        ident=await self.submitted();original=family.wallet_once
        async def crash(*args,**kw):await original(*args,**kw);raise RuntimeError('after credit')
        with patch.object(family,'wallet_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await self.action(ident,'approve')
        await family.recover();await family.recover()
        self.assertEqual(self.db.players.rows[1]['resources']['gold'],1200);self.assertEqual((await self.row(ident))['status'],'completed')
    async def test_open_cancel_refunds_once_and_self_application_blocked(self):
        ident=await self.created()
        with self.assertRaises(HTTPException):await self.action(ident,'apply',message='خودم')
        await self.action(ident,'cancel');await family.recover()
        self.assertEqual(self.db.players.rows[0]['resources']['gold'],1000)
    async def test_active_owner_cannot_take_escrow_back_without_judgment(self):
        ident=await self.assigned()
        for action in ('cancel','refund','approve'):
            with self.assertRaises(HTTPException):await self.action(ident,action,message='توضیح')
        await self.action(ident,'dispute',message='بر سر نتیجه اختلاف داریم')
        row=await self.row(ident)
        await s.act_contract(ident,s.ContractAction(action='refund',version=row['version'],message='لغو با داوری و استرداد کامل'),99,management=True)
        self.assertEqual(self.db.players.rows[0]['resources']['gold'],1000)
    async def test_outsider_cannot_assign_submit_or_review(self):
        ident=await self.submitted()
        for action in ('assign','submit','approve','dispute','return','refund','cancel'):
            with self.assertRaises(HTTPException):await self.action(ident,action,3,message='تلاش غیرمجاز')
    async def test_dead_worker_closes_contract_not_paid_to_replacement(self):
        ident=await self.assigned();self.db.players.rows[1]['created_at']+=timedelta(seconds=1)
        await s.tick();self.assertEqual((await self.row(ident))['status'],'cancelled');self.assertEqual(self.db.players.rows[0]['resources']['gold'],1000)
    async def test_pause_and_deadlines_use_only_game_time(self):
        ident=await self.created();self.clock+=timedelta(days=4)
        with patch.object(s.game_clock,'paused',return_value=True):await s.tick()
        self.assertEqual((await self.row(ident))['status'],'open')
        await s.tick();self.assertEqual((await self.row(ident))['status'],'expired');self.assertEqual(self.db.players.rows[0]['resources']['gold'],1000)
        ident=await self.assigned();self.clock+=timedelta(days=4);await s.tick()
        self.assertEqual((await self.row(ident))['status'],'disputed');self.assertEqual(self.db.players.rows[0]['resources']['gold'],800)
    async def test_private_applications_and_result_are_not_public(self):
        ident=await self.submitted();row=await self.row(ident);row['review_note']='private'
        other=s.contract_view(row,family.key(self.db.players.rows[2]));self.assertEqual(other['applicants'],[])
        for field in ('result','review_note','owner_key','worker_key'):self.assertNotIn(field,other)
        mine=s.contract_view(row,family.key(self.db.players.rows[1]));self.assertIn('result',mine);self.assertEqual(len(mine['applicants']),1)
    async def test_word_limits_apply_before_reservation(self):
        self.db.game_settings.rows=[{'_id':'weekly_submission_limits','request_words':2}]
        with self.assertRaises(HTTPException):await self.created()
        self.assertEqual(self.db.players.rows[0]['resources']['gold'],1000)
    async def test_limits_disabled_settings_and_strict_reward(self):
        self.db.game_settings.rows=[{'_id':'social_world','enabled':False}]
        with self.assertRaises(HTTPException):await self.created()
        for reward in (-1,0,1.2,True):
            with self.assertRaises(ValidationError):self.draft(reward=reward)
    async def test_landless_character_can_post(self):
        self.db.players.rows[0].update(castle=None,landless=True)
        ident=await self.created();self.assertEqual((await self.row(ident))['status'],'open')
    async def test_castle_roster_private_to_current_residents_and_hosts(self):
        await travel.state(self.db.players.rows[0]);await travel.state(self.db.players.rows[1])
        with self.assertRaises(HTTPException):await s.castle_view('A',{'id':2})
        self.assertEqual(len((await s.castle_view('A',{'id':1}))['residents']),1)
        self.db.character_locations.rows[1]['place']='A'
        self.assertEqual(len((await s.castle_view('A',{'id':2}))['residents']),2)
        self.db.character_locations.rows[1]['trip']='trip'
        with self.assertRaises(HTTPException):await s.castle_view('A',{'id':2})
    async def entry(self,kind='notice',uid=1,**kw):
        return await s.entry_create(s.EntryDraft(request_id=uuid4(),place='A',kind=kind,title='اعلامیهٔ نمونه',body='شرح برنامهٔ تالار بزرگ',**kw),{'id':uid})
    async def test_guest_cannot_publish_host_notice_and_meeting_is_private(self):
        for p in self.db.players.rows:await travel.state(p)
        await travel.locations.update_one({'_id':family.key(self.db.players.rows[1])},{'$set':{'place':'A'}})
        with self.assertRaises(HTTPException):await self.entry(uid=2)
        await self.entry('meeting',2,target_key=family.key(self.db.players.rows[0]))
        await travel.locations.update_one({'_id':family.key(self.db.players.rows[2])},{'$set':{'place':'A'}})
        self.assertEqual((await s.castle_view('A',{'id':3}))['entries'],[])
        self.assertEqual(len((await s.castle_view('A',{'id':1}))['entries']),1)
    async def test_meeting_response_only_target_and_departure_invalidates(self):
        for p in self.db.players.rows:await travel.state(p)
        await travel.locations.update_one({'_id':family.key(self.db.players.rows[1])},{'$set':{'place':'A'}})
        r=await self.entry('meeting',2,target_key=family.key(self.db.players.rows[0]))
        body=s.EntryAction(version=1,action='accept')
        with self.assertRaises(HTTPException):await s.entry_action(r['id'],body,{'id':2})
        await travel.locations.update_one({'_id':family.key(self.db.players.rows[1])},{'$set':{'place':'B'}})
        with self.assertRaises(HTTPException):await s.entry_action(r['id'],body,{'id':1})
    async def test_event_attendance_requires_present_free_character_and_version(self):
        for p in self.db.players.rows:await travel.state(p)
        r=await self.entry('event');body=s.EntryAction(version=1,action='join')
        with self.assertRaises(HTTPException):await s.entry_action(r['id'],body,{'id':2})
        await s.entry_action(r['id'],body,{'id':1})
        with self.assertRaises(HTTPException):await s.entry_action(r['id'],body,{'id':1})
        self.assertEqual((await s.entries.find_one({'_id':r['id']}))['attendees'],[family.key(self.db.players.rows[0])])
    async def test_news_drafts_not_public_only_approved_news_visible(self):
        body=s.NewsDraft(request_id=uuid4(),title='خبر تازهٔ بندر',body='بازگشایی بندر و رونق بازار',source='خبرنگار بندر',image='port')
        r=await s.submit_news(body,{'id':1});self.assertEqual((await s.news_list('',{'id':2}))['articles'],[])
        await s.review_news(r['id'],s.NewsReview(version=1,action='publish',title=body.title,body=body.body,source=body.source,category='realm',image='port',issue=4),{'id':99})
        public=(await s.news_list('',{'id':2}))['articles'];self.assertEqual(public[0]['issue'],4)
        self.assertNotIn('author_key',public[0]);self.assertNotIn('reviewer',public[0])
        await s.review_news(r['id'],s.NewsReview(version=2,action='unpublish'),{'id':99});self.assertEqual((await s.news_list('',{'id':2}))['articles'],[])
    async def test_full_admin_guard_rejects_other_roles(self):
        with patch.object(s,'get_full_admin',AsyncMock(side_effect=HTTPException(403,'denied'))):
            with self.assertRaises(HTTPException):await s.admin({'id':2})
    async def test_http_routes_require_player_or_full_admin_and_validate_input(self):
        import httpx
        from fastapi import FastAPI
        app=FastAPI();app.include_router(s.router);app.include_router(s.news_router)
        app.dependency_overrides[s.get_user]=lambda:{'id':1}
        with patch.object(s,'get_full_admin',AsyncMock(side_effect=HTTPException(403,'denied'))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                self.assertEqual((await client.get('/api/admin/social/contracts')).status_code,403)
                self.assertEqual((await client.get('/api/admin/social/news')).status_code,403)
                self.assertEqual((await client.post('/api/contracts',json={'reward':-5})).status_code,422)
                result=await client.post('/api/contracts',json=self.draft().model_dump(mode='json'))
                self.assertEqual(result.status_code,200)
                self.assertNotIn('character_created_at',result.text)
                listing=await client.get('/api/contracts');self.assertEqual(listing.status_code,200)
        telegram=FastAPI();telegram.include_router(s.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=telegram),base_url='http://test') as client:
            self.assertEqual((await client.get('/api/newspaper')).status_code,404)
    async def test_pagination_is_chronological_not_random_uuid_order(self):
        ids=[]
        for i in range(3):
            self.clock+=timedelta(seconds=1);ids.append(await self.created())
        first=await s.board(2,'',False,{'id':1})
        self.assertEqual([r['id'] for r in first['contracts']],[ids[2],ids[1]])
        second=await s.board(2,first['next'],False,{'id':1})
        self.assertEqual([r['id'] for r in second['contracts']],[ids[0]])
    async def test_actual_auth_allows_landless_social_writes_but_not_territory(self):
        import auth
        from starlette.requests import Request
        from pathlib import Path
        self.db.players.rows[0].update(castle=None,landless=True)
        self.enterContext(patch.object(auth,'players',self.db.players))
        if Path(auth.__file__).with_name('web_auth.py').exists():
            self.enterContext(patch('web_auth.identity',AsyncMock(return_value={'id':1})))
        else:self.enterContext(patch.object(auth,'DEV_MODE',True))
        for path in ('/api/contracts','/api/contracts/c:1/action','/api/castle-life','/api/castle-life/e1/action'):
            request=Request({'type':'http','method':'POST','path':path,'headers':[]})
            self.assertEqual((await auth.get_user(request=request,x_dev_user='1:test'))['id'],1)
        request=Request({'type':'http','method':'POST','path':'/api/buildings/upgrade','headers':[]})
        with self.assertRaises(HTTPException):await auth.get_user(request=request,x_dev_user='1:test')
    async def test_character_end_and_moderation_preserve_audit(self):
        ident=await self.assigned();await self.action(ident,'dispute',message='توضیح اختلاف قرارداد')
        self.assertGreaterEqual(len(self.db.social_audit.rows),3)
        for p in self.db.players.rows:await travel.state(p)
        entry=await self.entry();await s.admin_remove(entry['id'],s.RemoveEntry(reason='محتوای نامناسب'),{'id':99})
        removed=await s.entries.find_one({'_id':entry['id']});self.assertTrue(removed['removed']);self.assertEqual(removed['removed_by'],99)

if __name__=='__main__':unittest.main()
