import copy
import unittest
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,patch
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError
from tests.test_institution_bank import Collection
import institution_bank as bank
import institution_finance as money
import institution_services as service
import institution_mercenaries as merc

class Database:
    def __init__(self):self.collections={}
    def __getitem__(self,name):return self.collections.setdefault(name,Collection(name=name))
    def __getattr__(self,name):return self[name]

class ServicesTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch("text_limits.game_settings",Collection()))
        self.at=datetime(2026,10,11,12);self.clock=self.at;self.db=Database()
        self.people=Collection([{'tg_id':uid,'name':'Player '+str(uid),'created_at':self.at,'castle':'Castle '+str(uid),'region':'north','resources':{'gold':1000,'wood':500,'food':500,'men':100}} for uid in (1,2,3,4)],name='players')
        self.db.collections['players']=self.people
        self.cfg={k:{**service.DEFAULTS,'enabled':True,'managers':[bank.member(self.people.rows[0]),bank.member(self.people.rows[2])]} for k in service.KINDS}
        for module in (money,service,merc):self.enterContext(patch.object(module,'db',self.db))
        for module,key,value in [(money,'players',self.people),(money,'operations',self.db.institution_transfers),(money,'treasuries',self.db.institution_service_treasuries),(service,'cases',self.db.institution_service_cases),(merc,'offers',self.db.institution_mercenary_offers),(merc,'contracts',self.db.institution_mercenary_contracts),(merc,'campaigns',self.db.campaigns),(merc,'players',self.people),(bank,'players',self.people),(bank,'messages',self.db.messages)]:self.enterContext(patch.object(module,key,value))
        self.enterContext(patch.object(service,'settings',new=AsyncMock(side_effect=lambda k:copy.deepcopy(self.cfg[k]))))
        self.enterContext(patch.object(bank,'get_admin_role',new=AsyncMock(return_value=None)))
        self.enterContext(patch.object(money,'apply_production',side_effect=lambda p:p));self.enterContext(patch.object(money,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
        self.enterContext(patch.object(service,'notify_admins',new=AsyncMock()))
        self.enterContext(patch.object(service,'now',side_effect=lambda:self.clock));self.enterContext(patch.object(merc,'now',side_effect=lambda:self.clock));self.enterContext(patch.object(money.game_clock,'now',side_effect=lambda:self.clock));self.enterContext(patch.object(money.game_clock,'real_now',side_effect=lambda:self.clock))
        self.enterContext(patch.object(merc,'food_rate',return_value=10))
    def body(self,**values):return service.Request(**{'request_id':str(uuid4()),'kind':'craft','title':'سفارش تازه','description':'شرح کامل سفارش ساخت مواد و منابع مورد نیاز برای آزمون','resources':{'gold':100,'wood':50},**values})
    async def balance(self,uid):return (await self.people.find_one({'tg_id':uid}))['resources']
    async def requested(self,k='alchemists',uid=2):return await service.request(k,self.body(kind=service.KINDS[k][0]),{'id':uid})
    async def working(self,k='alchemists',uid=2,assignee=1):
        r=await self.requested(k,uid);return await service.accept(k,r['id'],service.Revision(version=r['version']),{'id':assignee})
    async def submitted(self,k='alchemists',uid=2,assignee=1):
        r=await self.working(k,uid,assignee);return await service.submit(k,r['id'],service.Submission(version=r['version'],scenario='سناریوی کامل و دقیق انجام سفارش توسط عضو مسئول نهاد',proposal='محصول آماده برای تصمیم ادمین'),{'id':assignee})
    async def test_crafting_reserves_all_and_burns_inputs_only_after_approval(self):
        r=await self.submitted();self.assertEqual((await self.balance(2))['gold'],900);self.assertEqual((await self.balance(1))['gold'],1000)
        await service.review('alchemists',r['id'],service.Review(version=r['version'],action='approve',result='محصول توسط ادمین تحویل خواهد شد'),{'id':99})
        self.assertEqual((await self.balance(1))['gold'],1100);self.assertEqual((await self.balance(1))['wood'],500)
        with self.assertRaises(HTTPException):await service.review('alchemists',r['id'],service.Review(version=r['version'],action='approve',result='تکرار تصمیم'),{'id':99})
    async def test_rejection_refunds_exactly_once(self):
        r=await self.working();await service.reject('alchemists',r['id'],service.Decision(version=r['version'],reason='مواد مناسب نیست'),{'id':1});await money.recover()
        self.assertEqual((await self.balance(2))['gold'],1000);self.assertEqual((await self.balance(2))['wood'],500)
        with self.assertRaises(HTTPException):await service.reject('alchemists',r['id'],service.Decision(version=r['version'],reason='رد دوباره'),{'id':1})
    async def test_watch_payment_delivers_money_and_resources(self):
        r=await self.submitted('watch');await service.review('watch',r['id'],service.Review(version=r['version'],action='approve',result='مأموریت آن‌سوی دیوار تأیید شد'),{'id':99})
        self.assertEqual((await self.balance(1))['wood'],550)
    async def test_faceless_identity_hidden_in_dashboard_and_member_notification(self):
        r=await self.requested('faceless');view=await service.dashboard('faceless',1,{'id':1})
        self.assertNotIn('requester',view['cases'][0]);self.assertNotIn('request_key',view['cases'][0]);self.assertFalse(view['cases'][0]['mine'])
        self.assertNotIn('Player 2',str(self.db.messages.rows));admin=await service.admin_dashboard('faceless',1,{'id':99});self.assertEqual(admin['cases'][0]['requester']['tg_id'],2)
        self.assertEqual((await service.dashboard('faceless',1,{'id':4}))['cases'],[])
    async def test_only_assigned_member_can_submit_or_reject(self):
        r=await self.working()
        with self.assertRaises(HTTPException):await service.submit('alchemists',r['id'],service.Submission(version=r['version'],scenario='سناریوی جعلی توسط فرد دیگری که عضو این نهاد است',proposal='پیشنهاد جعلی'),{'id':3})
        with self.assertRaises(HTTPException):await service.reject('alchemists',r['id'],service.Decision(version=r['version'],reason='رد توسط دیگری'),{'id':3})
    async def test_insufficient_negative_and_unknown_resources_never_debit(self):
        for resources in ({'wood':501},{'wood':-1},{'unknown':1}):
            with self.assertRaises(HTTPException):await service.request('alchemists',self.body(resources=resources),{'id':2})
        with self.assertRaises(ValidationError):self.body(resources={'gold':True})
        self.assertEqual((await self.balance(2))['gold'],1000);self.assertEqual(self.db.institution_transfers.rows,[])
    async def test_repeated_request_same_payload_once_changed_payload_rejected(self):
        body=self.body();r=await service.request('alchemists',body,{'id':2});again=await service.request('alchemists',body,{'id':2});self.assertEqual(r['id'],again['id']);self.assertEqual((await self.balance(2))['gold'],900)
        with self.assertRaises(HTTPException):await service.request('alchemists',self.body(request_id=body.request_id,resources={'gold':20}),{'id':2})
    async def test_restart_after_debit_before_case_creation(self):
        body=self.body();original=money.leg_once
        async def crash(*args):await original(*args);raise RuntimeError('crash after debit')
        with patch.object(money,'leg_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await service.request('alchemists',body,{'id':2})
        self.assertEqual(self.db.institution_service_cases.rows,[]);await money.recover()
        r=await service.request('alchemists',body,{'id':2});self.assertEqual(r['status'],'requested');self.assertEqual((await self.balance(2))['gold'],900)
    async def test_faceless_two_per_seven_game_days_and_revision_no_extra_slot(self):
        r=await self.submitted('faceless');back=await service.review('faceless',r['id'],service.Review(version=r['version'],action='return',result='سناریو تکمیل شود'),{'id':99})
        await service.submit('faceless',r['id'],service.Submission(version=back['version'],scenario='سناریوی تکمیل‌شده با تمام جزئیات مربوط به مأموریت',proposal='نتیجهٔ اصلاح شده'),{'id':1})
        await self.submitted('faceless',uid=4);third=await self.working('faceless')
        with self.assertRaises(HTTPException):await service.submit('faceless',third['id'],service.Submission(version=third['version'],scenario='سناریوی کامل مأموریت سوم در همین هفتهٔ بازی',proposal='نتیجهٔ سوم'),{'id':1})
        self.clock+=timedelta(days=7)
        await service.submit('faceless',third['id'],service.Submission(version=third['version'],scenario='سناریوی کامل مأموریت سوم پس از گذشت هفت روز بازی',proposal='نتیجهٔ سوم'),{'id':1})
    async def test_reset_character_cannot_see_prior_cases(self):
        await self.requested();self.people.rows[1]['created_at']+=timedelta(days=1)
        self.assertEqual((await service.dashboard('alchemists',1,{'id':2}))['cases'],[])
    async def test_faith_donation_split_conserves_every_resource_and_withdraw_cooldown(self):
        body=service.Donation(request_id=str(uuid4()),resources={'gold':101,'wood':51});await service.donate(body,{'id':2});await service.donate(body,{'id':2})
        shares=[a['resources'] for a in self.db.institution_faith_accounts.rows];self.assertEqual(sum(s['gold'] for s in shares),101);self.assertEqual(sum(s['wood'] for s in shares),51)
        withdraw=service.Withdrawal(request_id=str(uuid4()));await service.withdraw(withdraw,{'id':1});await service.withdraw(withdraw,{'id':1})
        self.assertEqual((await self.balance(1))['gold'],1051)
        await service.donate(service.Donation(request_id=str(uuid4()),resources={'gold':20}),{'id':2})
        with self.assertRaises(HTTPException):await service.withdraw(service.Withdrawal(request_id=str(uuid4())),{'id':1})
        self.clock+=timedelta(hours=24);await service.withdraw(service.Withdrawal(request_id=str(uuid4())),{'id':1})
        self.assertEqual((await self.balance(1))['gold'],1061)
    async def test_faith_restart_between_two_credits(self):
        body=service.Donation(request_id=str(uuid4()),resources={'gold':101});original=money.leg_once;counter=0
        async def crash(*args):
            nonlocal counter
            await original(*args);counter+=1
            if counter==2:raise RuntimeError('crash after treasury credit')
        with patch.object(money,'leg_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await service.donate(body,{'id':2})
        await money.recover();await service.donate(body,{'id':2})
        self.assertEqual((await self.balance(2))['gold'],899);self.assertEqual((await money.treasuries.find_one({'_id':'faith'}))['resources']['gold'],101)
    async def test_faith_service_payment_enters_shared_treasury_and_equal_entitlements(self):
        r=await self.submitted('faith');await service.review('faith',r['id'],service.Review(version=r['version'],action='approve',result='میانجی‌گری تأیید شد'),{'id':99})
        self.assertEqual((await self.balance(1))['gold'],1000)
        self.assertEqual((await money.treasuries.find_one({'_id':'faith'}))['resources']['gold'],100)
        self.assertEqual([x['resources']['gold'] for x in self.db.institution_faith_accounts.rows],[50,50])
    async def test_disabled_service_and_self_order_do_not_touch_balance(self):
        self.cfg['alchemists']['enabled']=False
        with self.assertRaises(HTTPException):await self.requested()
        self.cfg['alchemists']['enabled']=True
        with self.assertRaises(HTTPException):await self.requested(uid=1)
        self.assertEqual(self.db.institution_transfers.rows,[])
    async def listing(self):return await merc.create(merc.Listing(request_id=str(uuid4()),name='مزدوران طلا',description='نیروهای مزدوری با قرارداد مشخص',troops={'infantry':100},equipment={},price=100,duration_hours=24),{'id':1})
    async def hired(self):
        row=await self.listing();await merc.review(row['id'],merc.Approval(version=row['version'],approved=True,result='ترکیب تأیید شد'),{'id':99});row=merc.public(await merc.offers.find_one({'_id':ObjectId(row['id'])}))
        return await merc.buy(row['id'],merc.Purchase(request_id=str(uuid4()),version=row['version'],castle='Castle 2'),{'id':2})
    async def test_mercenary_purchase_requires_approval_and_owned_destination(self):
        row=await self.listing()
        with self.assertRaises(HTTPException):await merc.buy(row['id'],merc.Purchase(request_id=str(uuid4()),version=row['version'],castle='Castle 2'),{'id':2})
        await merc.review(row['id'],merc.Approval(version=row['version'],approved=True,result='تأیید برای فروش'),{'id':99});row=merc.public(await merc.offers.find_one({'_id':ObjectId(row['id'])}))
        with self.assertRaises(HTTPException):await merc.buy(row['id'],merc.Purchase(request_id=str(uuid4()),version=row['version'],castle='Castle 4'),{'id':2})
        body=merc.Purchase(request_id=str(uuid4()),version=row['version'],castle='Castle 2');r=await merc.buy(row['id'],body,{'id':2});again=await merc.buy(row['id'],body,{'id':2});self.assertEqual(r['id'],again['id']);self.assertEqual(len(self.db.campaigns.rows),1);self.assertEqual((await self.balance(2))['gold'],900)
        with self.assertRaises(HTTPException):await merc.buy(row['id'],merc.Purchase(request_id=str(uuid4()),version=row['version'],castle='Castle 4'),{'id':4})
    async def test_mercenary_return_only_survivors_and_waits_for_battle(self):
        contract=await self.hired();army=self.db.campaigns.rows[0];army['troops']['infantry']=63;army['engagement_locked']=True;self.clock+=timedelta(hours=24)
        import routers.war as war
        with patch.object(war,'repair_stale_engagement_lock',new=AsyncMock(side_effect=lambda a:a)),patch.object(war,'campaign_waiting_for_result',return_value=False):
            await merc.tick();self.assertEqual(self.db.institution_mercenary_contracts.rows[0]['status'],'waiting_return');self.assertTrue(army['active'])
            army['engagement_locked']=False;await merc.tick();await merc.tick()
        self.assertFalse(army['active']);self.assertEqual(self.db.institution_mercenary_offers.rows[0]['troops']['infantry'],63)
    async def test_mercenary_restart_after_payment_does_not_duplicate_army(self):
        row=await self.listing();await merc.review(row['id'],merc.Approval(version=row['version'],approved=True,result='تأیید برای فروش'),{'id':99});row=merc.public(await merc.offers.find_one({'_id':ObjectId(row['id'])}));body=merc.Purchase(request_id=str(uuid4()),version=row['version'],castle='Castle 2');original=money.leg_once
        async def crash(*args):await original(*args);raise RuntimeError('crash after buyer payment')
        with patch.object(money,'leg_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await merc.buy(row['id'],body,{'id':2})
        await money.recover();await merc.buy(row['id'],body,{'id':2});self.assertEqual(len(self.db.campaigns.rows),1);self.assertEqual((await self.balance(2))['gold'],900);self.assertEqual((await self.balance(1))['gold'],1100)
    async def test_army_scenario_only_current_buyer(self):
        contract=await self.hired()
        with self.assertRaises(HTTPException):await merc.scenario(contract['id'],self.body(),{'id':4})
        r=await merc.scenario(contract['id'],self.body(),{'id':2});self.assertEqual(r['assigned_id'],1);self.assertEqual(r['status'],'working')

if __name__=='__main__':unittest.main()
