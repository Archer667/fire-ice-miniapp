import copy
import unittest
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from uuid import uuid4
from fastapi import HTTPException
from bson import ObjectId
from tests.test_institution_bank import Collection
import institution_bank as bank
import institution_citadel as c

class CitadelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch("text_limits.game_settings",Collection()))
        self.at=datetime(2026,10,11,12)
        self.people=Collection([{'tg_id':uid,'name':f'Player {uid}','created_at':self.at,'castle':'Castle','region':'north'} for uid in (1,2,3)])
        self.cases=Collection();self.messages=Collection();self.audit=Collection()
        self.cfg={**c.DEFAULTS,'enabled':True,'managers':[bank.member(self.people.rows[0])]}
        self.enterContext(patch.object(c,'settings',new=AsyncMock(side_effect=lambda:copy.deepcopy(self.cfg))))
        self.enterContext(patch.object(c,'cases',self.cases));self.enterContext(patch.object(c,'db',SimpleNamespace(institution_audit=self.audit)))
        self.enterContext(patch.object(c,'notify_admins',new=AsyncMock()))
        self.enterContext(patch.object(bank,'players',self.people));self.enterContext(patch.object(bank,'messages',self.messages))
        self.enterContext(patch.object(bank,'get_admin_role',new=AsyncMock(return_value=None)))
        self.enterContext(patch.object(c,'now',return_value=self.at));self.enterContext(patch.object(c.game_clock,'now',return_value=self.at));self.enterContext(patch.object(c.game_clock,'real_now',return_value=self.at+timedelta(days=10)))
    def body(self,**kw):return c.Request(**{'request_id':str(uuid4()),'kind':'research','title':'پژوهش تازه','description':'تحقیق دربارهٔ راه‌های ساخت پل و افزایش ایمنی بندر',**kw})
    async def requested(self):return await c.request(self.body(),{'id':2})
    async def working(self):
        r=await self.requested();return await c.start(r['id'],c.Start(version=r['version'],duration_hours=24),{'id':1})
    async def submitted(self):
        r=await self.working();return await c.submit(r['id'],c.Submission(version=r['version'],scenario='شرح آزمایش‌ها و مراحل پژوهش استادان سیتادل برای این پروژه',proposal='پیشنهاد بهبود طراحی پل برای افزایش ایمنی'),{'id':1})
    async def test_research_lifecycle_and_stale_review(self):
        r=await self.submitted();done=await c.review(r['id'],c.Review(version=r['version'],action='approve',result='پژوهش موفق و نتیجه ثبت شد'),{'id':99})
        self.assertEqual(done['status'],'resolved')
        with self.assertRaises(HTTPException):await c.review(r['id'],c.Review(version=r['version'],action='approve',result='تکرار تأیید'),{'id':99})
    async def test_healing_request_private_and_cancellable(self):
        r=await c.request(self.body(kind='healing'),{'id':2})
        other=await c.dashboard(1,{'id':3});self.assertEqual(other['cases'],[])
        with self.assertRaises(HTTPException):await c.cancel(r['id'],c.Revision(version=r['version']),{'id':3})
        cancelled=await c.cancel(r['id'],c.Revision(version=r['version']),{'id':2});self.assertEqual(cancelled['status'],'cancelled')
    async def test_non_manager_cannot_start_or_submit(self):
        r=await self.requested()
        with self.assertRaises(HTTPException):await c.start(r['id'],c.Start(version=r['version'],duration_hours=24),{'id':3})
        r=await self.working()
        with self.assertRaises(HTTPException):await c.submit(r['id'],c.Submission(version=r['version'],scenario='سناریوی آزمایشی بلند برای ارسال پرونده به داوری',proposal='نتیجهٔ پیشنهادی آزمایشی'),{'id':3})
    async def test_repeat_request_once_and_payload_cannot_change(self):
        body=self.body();r=await c.request(body,{'id':2});again=await c.request(body,{'id':2});self.assertEqual(r['id'],again['id']);self.assertEqual(len(self.cases.rows),1)
        with self.assertRaises(HTTPException):await c.request(self.body(request_id=body.request_id,title='عنوان متفاوت'),{'id':2})
    async def test_limits_disabled_services_and_trimmed_text(self):
        self.cfg['max_open_per_player']=1;await self.requested()
        with self.assertRaises(HTTPException):await self.requested()
        self.cfg['max_open_per_player']=3;self.cfg['healing_enabled']=False
        with self.assertRaises(HTTPException):await c.request(self.body(kind='healing'),{'id':3})
        with self.assertRaises(HTTPException):await c.request(self.body(description=' '*25),{'id':3})
    async def test_new_manager_can_continue_existing_case(self):
        r=await self.working();self.cfg['managers']=[bank.member(self.people.rows[2])]
        with self.assertRaises(HTTPException):await c.manager({'id':1})
        updated=await c.submit(r['id'],c.Submission(version=r['version'],scenario='سناریوی کامل پژوهش توسط مدیر تازهٔ منصوب‌شدهٔ سیتادل',proposal='نتیجهٔ پیشنهادی کامل پژوهش'),{'id':3});self.assertEqual(updated['status'],'submitted')
    async def test_return_allows_revised_scenario(self):
        r=await self.submitted();back=await c.review(r['id'],c.Review(version=r['version'],action='return',result='جزئیات آزمایش بیشتر لازم است'),{'id':99})
        self.assertEqual(back['status'],'working')
        updated=await c.submit(back['id'],c.Submission(version=back['version'],scenario='سناریوی تازه با شرح کامل آزمایش‌های تکمیلی و منابع پژوهش',proposal='پیشنهاد تازهٔ نتیجهٔ آزمایش‌ها'),{'id':1});self.assertEqual(updated['status'],'submitted')
    async def test_requester_reset_not_assigned_to_new_character(self):
        r=await self.requested();await self.people.update_one({'tg_id':2},{'$set':{'created_at':self.at+timedelta(days=1)}})
        self.assertEqual((await c.dashboard(1,{'id':2}))['cases'],[])
        with self.assertRaises(HTTPException):await c.start(r['id'],c.Start(version=r['version'],duration_hours=24),{'id':1})
    async def test_ordinary_player_and_limited_admin_cannot_review(self):
        import auth
        for role in (None,'limited'):
            with patch.object(auth,'get_admin_role',new=AsyncMock(return_value=role)):
                with self.assertRaises(HTTPException):await c.admin({'id':3})
    async def test_pause_deadline_and_duration_limit(self):
        r=await self.working()
        with patch.object(c.game_clock,'paused',return_value=True):
            row=c.public(await self.cases.find_one({'_id':ObjectId(r['id'])}));self.assertTrue(row['deadline']['paused']);self.assertEqual(row['deadline']['remaining_seconds'],86400)
        r=await self.requested();self.cfg['max_duration_hours']=12
        with self.assertRaises(HTTPException):await c.start(r['id'],c.Start(version=r['version'],duration_hours=24),{'id':1})
