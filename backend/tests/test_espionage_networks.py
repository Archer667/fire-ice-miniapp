"""Intelligence contracts tested only against an isolated in-memory database."""
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient
from pydantic import ValidationError
import auth
import espionage_networks as spy
import family
import project_engine
from routers import admin as admin_routes, war


class EspionageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mem = AsyncMongoMockClient()['espionage_test']
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.clock = datetime(2026, 10, 1, 12)
        self.start = self.clock
        for module, key, value in [(spy,'db',self.mem),(spy,'players',self.mem.players),
                (spy,'networks',self.mem.espionage_networks),(spy,'questions',self.mem.espionage_questions),
                (spy,'audits',self.mem.espionage_audit),(spy,'outbox',self.mem.espionage_outbox),
                (family,'db',self.mem),(family,'operations',self.mem.family_operations),
                (project_engine,'players',self.mem.players),(auth,'admin_roles',self.mem.admin_roles)]:
            self.stack.enter_context(patch.object(module,key,value))
        self.stack.enter_context(patch.object(spy,'now',lambda:self.clock))
        self.stack.enter_context(patch.object(spy,'quota_window',self.window))
        self.stack.enter_context(patch.object(spy,'feature_enabled',lambda _:True))
        self.stack.enter_context(patch.object(spy,'rule',lambda *args:1000))
        self.stack.enter_context(patch.object(spy,'check_text',AsyncMock()))
        self.stack.enter_context(patch.object(spy,'spy_travel_minutes',lambda *args:1))
        self.stack.enter_context(patch.object(war,'owner_of_castle',self.owner))
        self.stack.enter_context(patch.object(project_engine,'apply_production',lambda p:p))
        self.stack.enter_context(patch.object(project_engine,'production_fields',lambda p:{'resources':p['resources']}))
        self.stack.enter_context(patch.object(auth,'ADMIN_IDS',set()))
        self.stack.enter_context(patch.object(auth,'OWNER_ID',999))
        await self.mem.game_settings.insert_one({'_id':'season_clock','started_at':self.start})
        await self.mem.players.insert_many([{'tg_id':uid,'name':f'Lord {uid}','castle':f'C{uid}',
            'region':'north','created_at':self.start-timedelta(days=1),'resources':{'gold':10000,'men':100}}
            for uid in range(1,7)])

    async def window(self):
        index=max(0,(self.clock-self.start).days)//7
        start=self.start+timedelta(days=index*7)
        return {'week_start':start,'week_end':start+timedelta(days=7),'week_number':index+1}

    async def owner(self,castle):
        return await self.mem.players.find_one({'castle':castle})

    async def deploy(self,target='C2',uid=1):
        return await spy.deploy(spy.Deployment(request_id=uuid4(),target_castle=target,scenario='رول کامل نفوذ و استقرار جاسوسی'),{'id':uid})

    async def active(self,target='C2',score=100):
        row=await self.deploy(target)
        self.clock+=timedelta(minutes=2)
        await spy.score_network(row['id'],spy.Score(request_id=uuid4(),score=score),{'id':999})
        return row['id']

    async def ask(self,nid,uid=1):
        return await spy.ask(nid,spy.Question(request_id=uuid4(),text='اطلاعات دروازه‌های قلعه را می‌خواهم'),{'id':uid})

    async def answer(self,qid,chance=100,**kw):
        return await spy.answer_question(qid,spy.Answer(request_id=uuid4(),text='پاسخ محرمانهٔ ادمین',chance=chance,**kw),{'id':999})

    async def manage(self,nid,action,**kw):
        return await spy.manage_network(nid,spy.NetworkAction(request_id=uuid4(),action=action,reason='تصمیم داوری پرونده',**kw),{'id':999})

    async def test_deploy_charges_gold_once_no_manpower(self):
        body=spy.Deployment(request_id=uuid4(),target_castle='C2',scenario='روش کامل نفوذ به قلعهٔ هدف')
        a=await spy.deploy(body,{'id':1}); b=await spy.deploy(body,{'id':1})
        self.assertEqual(a,b)
        p=await self.mem.players.find_one({'tg_id':1})
        self.assertEqual(p['resources'],{'gold':9000,'men':100})
        self.assertEqual(await spy.networks.count_documents({}),1)

    async def test_own_castle_and_duplicate_and_cap(self):
        with self.assertRaises(HTTPException):await self.deploy('C1')
        await self.deploy('C2')
        with self.assertRaises(HTTPException):await self.deploy('C2')
        await self.deploy('C3');await self.deploy('C4')
        with self.assertRaises(HTTPException):await self.deploy('C5')
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],7000)

    async def test_insufficient_funds_does_not_create_network(self):
        await self.mem.players.update_one({'tg_id':1},{'$set':{'resources.gold':1}})
        with self.assertRaises(HTTPException):await self.deploy()
        self.assertEqual(await spy.networks.count_documents({}),0)
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],1)

    async def test_crash_after_debit_recovers_without_double_charge(self):
        body=spy.Deployment(request_id=uuid4(),target_castle='C2',scenario='روش کامل نفوذ به قلعهٔ هدف')
        original=family.finish
        async def crash(op):
            w=op['wallets'][0]
            await family.wallet_once(w['member'],w['cost'],f"family:{op['_id']}:0",debit=True)
            raise RuntimeError('simulated process interruption')
        with patch.object(family,'finish',crash):
            with self.assertRaises(RuntimeError):await spy.deploy(body,{'id':1})
        await spy.deploy(body,{'id':1})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],9000)
        self.assertEqual(await spy.networks.count_documents({}),1)

    async def test_score_arrival_required_and_replay_does_not_reroll(self):
        n=await self.deploy(); body=spy.Score(request_id=uuid4(),score=80)
        with self.assertRaises(HTTPException):await spy.score_network(n['id'],body,{'id':999})
        self.clock+=timedelta(minutes=2)
        with patch.object(spy,'draw',return_value=70) as draw:
            a=await spy.score_network(n['id'],body,{'id':999})
            b=await spy.score_network(n['id'],body,{'id':999})
        self.assertEqual(a,b);draw.assert_called_once()
        with self.assertRaises(HTTPException):await spy.score_network(n['id'],spy.Score(request_id=uuid4(),score=100),{'id':999})

    async def test_quota_is_per_network_and_resets_after_seven_game_days(self):
        a=await self.active('C2'); b=await self.active('C3')
        for _ in range(3):await self.ask(a)
        with self.assertRaises(HTTPException) as e:await self.ask(a)
        self.assertEqual(e.exception.status_code,429)
        await self.ask(b)
        p=await self.mem.players.find_one({'tg_id':1});row=await spy.networks.find_one({'_id':spy.oid(a)})
        self.assertEqual((await spy.quota(row,p))['remaining'],0)
        # Advancing no game time, as during a pause, does not refill anything.
        self.assertEqual((await spy.quota(row,p))['remaining'],0)
        self.clock=self.start+timedelta(days=7)
        self.assertEqual((await spy.quota(row,p))['remaining'],3)
        await self.ask(a)

    async def test_new_question_requires_manual_chance_not_previous_score(self):
        n=await self.active();q=await self.ask(n)
        with self.assertRaises(HTTPException):
            await spy.answer_question(q['id'],spy.Answer(request_id=uuid4(),text='پاسخ بدون شانس'),{'id':999})
        result=await self.answer(q['id'],chance=0)
        self.assertEqual(result['status'],'delivery_failed')
        self.assertEqual(result['score'],0)
        self.assertEqual((await spy.questions.find_one({'_id':spy.oid(q['id'])}))['score'],100)

    async def test_failed_answer_hidden_and_risk_requires_admin_decision(self):
        n=await self.active();q=await self.ask(n);await self.answer(q['id'],chance=0)
        mine=await spy.my_questions({'id':1})
        self.assertEqual(mine[0]['answer'],'')
        for secret in ('score','roll','delivery_chance','deployment_scenario'):self.assertNotIn(secret,mine[0])
        self.assertEqual((await spy.mine({'id':1}))[0]['status'],'risk_review')
        with self.assertRaises(HTTPException):await self.ask(n)
        with self.assertRaises(HTTPException):await spy.recall(n,spy.Request(request_id=uuid4()),{'id':1})
        await self.manage(n,'resume');await self.ask(n)

    async def test_new_chance_can_deliver_even_when_prior_score_would_fail(self):
        with patch.object(spy,'draw',return_value=1):n=await self.active(score=20)
        q=await self.ask(n)
        with patch.object(spy,'draw',return_value=90):result=await self.answer(q['id'],chance=95)
        self.assertEqual(result['status'],'delivered')
        self.assertEqual(result['score'],95)
        self.assertEqual((await spy.questions.find_one({'_id':spy.oid(q['id'])}))['score'],20)

    async def test_other_player_cannot_read_edit_or_use_network(self):
        n=await self.active();q=await self.ask(n)
        self.assertEqual(await spy.my_questions({'id':2}),[])
        self.assertEqual(await spy.mine({'id':2}),[])
        with self.assertRaises(HTTPException):await self.ask(n,uid=2)
        with self.assertRaises(HTTPException):await spy.recall(n,spy.Request(request_id=uuid4()),{'id':2})
        await spy.answer_question(q['id'],spy.Answer(request_id=uuid4(),action='return',reason='متن کامل‌تر لازم است'),{'id':999})
        with self.assertRaises(HTTPException):await spy.edit_question(q['id'],spy.Question(request_id=uuid4(),text='دسترسی به سؤال دیگری'),{'id':2})

    async def test_successful_answer_replay_and_private_notification(self):
        n=await self.active();q=await self.ask(n)
        body=spy.Answer(request_id=uuid4(),text='اطلاعات محرمانه',chance=100)
        with patch.object(spy,'draw',return_value=50) as draw:
            await spy.answer_question(q['id'],body,{'id':999});await spy.answer_question(q['id'],body,{'id':999})
        draw.assert_called_once()
        self.assertEqual((await spy.my_questions({'id':1}))[0]['answer'],'اطلاعات محرمانه')
        async for note in spy.outbox.find({}):self.assertNotIn('اطلاعات محرمانه',note['text'])

    async def test_rejected_refunds_returned_edits_keep_same_quota(self):
        n=await self.active();a=await self.ask(n);b=await self.ask(n)
        await spy.answer_question(a['id'],spy.Answer(request_id=uuid4(),action='reject',reason='سؤال خارج از موضوع'),{'id':999})
        await spy.answer_question(b['id'],spy.Answer(request_id=uuid4(),action='return',reason='سؤال را دقیق‌تر بنویس'),{'id':999})
        before=await spy.questions.find_one({'_id':spy.oid(b['id'])})
        await spy.edit_question(b['id'],spy.Question(request_id=uuid4(),text='اصلاح دقیق سؤال دربارهٔ دروازه'),{'id':1})
        after=await spy.questions.find_one({'_id':before['_id']})
        self.assertEqual(before['created_at'],after['created_at'])
        row=await spy.networks.find_one({'_id':spy.oid(n)});p=await self.mem.players.find_one({'tg_id':1})
        self.assertEqual((await spy.quota(row,p))['used'],1)

    async def test_capture_cancels_pending_questions_without_revealing_sender(self):
        n=await self.active();q=await self.ask(n);await self.manage(n,'capture')
        self.assertEqual((await spy.questions.find_one({'_id':spy.oid(q['id'])}))['status'],'cancelled')
        target=await spy.outbox.find_one({'recipient':2})
        self.assertNotIn('Lord 1',target['text'])
        with self.assertRaises(HTTPException):await self.ask(n)

    async def test_forced_delivery_keeps_failed_roll_and_records_reason(self):
        n=await self.active();q=await self.ask(n)
        with patch.object(spy,'draw',return_value=90):await self.answer(q['id'],chance=1)
        with patch.object(spy,'draw',side_effect=AssertionError('must not reroll')):
            await spy.answer_question(q['id'],spy.Answer(request_id=uuid4(),action='force_deliver',reason='تصحیح اشتباه داوری'),{'id':999})
        row=await spy.questions.find_one({'_id':spy.oid(q['id'])})
        self.assertEqual(row['roll'],90);self.assertEqual(row['delivery_chance'],1);self.assertTrue(row['forced'])
        self.assertEqual((await spy.my_questions({'id':1}))[0]['answer'],'پاسخ محرمانهٔ ادمین')
        self.assertEqual((await spy.mine({'id':1}))[0]['status'],'risk_review')

    async def test_target_owner_change_blocks_until_rebind(self):
        n=await self.active()
        await self.mem.players.update_one({'tg_id':2},{'$set':{'castle':'old'}})
        await self.mem.players.update_one({'tg_id':3},{'$set':{'castle':'C2'}})
        with self.assertRaises(HTTPException):await self.ask(n)
        await self.manage(n,'resume');await self.ask(n)

    async def test_new_character_and_new_season_cannot_inherit_network(self):
        n=await self.active()
        await self.mem.players.update_one({'tg_id':1},{'$set':{'created_at':self.clock}})
        self.assertEqual(await spy.mine({'id':1}),[])
        with self.assertRaises(HTTPException):await self.ask(n)
        await self.mem.players.update_one({'tg_id':1},{'$set':{'created_at':self.start-timedelta(days=1)}})
        await self.mem.game_settings.update_one({'_id':'season_clock'},{'$set':{'started_at':self.clock}})
        self.assertEqual(await spy.mine({'id':1}),[])
        with self.assertRaises(HTTPException):await self.ask(n)

    async def test_landless_can_manage_existing_not_deploy(self):
        n=await self.active()
        await self.mem.players.update_one({'tg_id':1},{'$set':{'castle':None,'landless':True}})
        await self.ask(n)
        with self.assertRaises(HTTPException):await self.deploy('C3')

    async def test_admin_question_includes_original_narrative_and_score(self):
        n=await self.active();await self.ask(n)
        result=await spy.admin_questions('', '', 0, {'id':999})
        row=result['rows'][0]
        self.assertEqual(row['deployment_scenario'],'رول کامل نفوذ و استقرار جاسوسی')
        self.assertEqual(row['deployment_score'],100)
        self.assertIsNone(row['delivery_chance'])

    def test_yearbook_feed_keeps_statistics_without_secret_text(self):
        from season_analytics import FEEDS
        fields=FEEDS['espionage_networks']
        self.assertIn('deployment_score',fields)
        for secret in ('scenario','answer','text','target_castle'):
            self.assertNotIn(secret,fields)

    async def test_admin_adjustments_and_player_limits(self):
        n=await self.active()
        for _ in range(3):await self.ask(n)
        await self.manage(n,'quota_delta',delta=1);await self.ask(n)
        await self.manage(n,'quota_reset')
        p=await self.mem.players.find_one({'tg_id':1});row=await spy.networks.find_one({'_id':spy.oid(n)})
        self.assertEqual((await spy.quota(row,p))['remaining'],3)
        await spy.save_player_limits(1,spy.PlayerLimits(request_id=uuid4(),max_networks=4,reason='افزایش ظرفیت کاراکتر'),{'id':999})
        self.assertEqual((await spy.settings(p))['max_networks'],4)

    async def test_legacy_conversion_no_second_debit_no_autoreport(self):
        original=await self.mem.spy_missions.insert_one({'tg_id':1,'player_name':'Lord 1','origin_castle':'C1',
            'target_castle':'C2','scenario':'رول قبلی جاسوسی','created_at':self.start,'resolved':False,'report':{'secret':999}})
        body=spy.Request(request_id=uuid4())
        await spy.convert_legacy(str(original.inserted_id),body,{'id':999})
        await spy.convert_legacy(str(original.inserted_id),body,{'id':999})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],10000)
        self.assertNotIn('report',(await spy.mine({'id':1}))[0])

    async def test_changed_payload_cannot_reuse_request_id(self):
        body=spy.Deployment(request_id=uuid4(),target_castle='C2',scenario='روش کامل نفوذ به قلعهٔ هدف')
        await spy.deploy(body,{'id':1})
        with self.assertRaises(HTTPException):await spy.deploy(body.model_copy(update={'target_castle':'C3'}),{'id':1})

    async def test_admin_roles_and_legacy_score_restrictions(self):
        for role in ('limited','war_roleplay'):
            await self.mem.admin_roles.update_one({'tg_id':100},{'$set':{'role':role}},upsert=True)
            with self.assertRaises(HTTPException):await spy.full_admin({'id':100})
            self.assertEqual(admin_routes._admin_notification_scope(role)['$and'][1],{'kind':{'$ne':'espionage'}})
        for role in ('full','owner'):
            await self.mem.admin_roles.update_one({'tg_id':100},{'$set':{'role':role}},upsert=True)
            self.assertEqual((await spy.full_admin({'id':100}))['admin_role'],role)
        with self.assertRaises(HTTPException) as e:await admin_routes.score_spy('unused',admin_routes.SpyScoreBody(score=90),{'id':999})
        self.assertEqual(e.exception.status_code,410)

    async def test_blank_questions_and_noninteger_chance_rejected(self):
        n=await self.active()
        with self.assertRaises(HTTPException):await spy.ask(n,spy.Question(request_id=uuid4(),text='   '),{'id':1})
        for invalid in (-1,101,True,50.1,'50'):
            with self.assertRaises(ValidationError):spy.Answer(request_id=uuid4(),chance=invalid)

    async def test_failure_of_initial_infiltration_has_no_automatic_data(self):
        n=await self.deploy();self.clock+=timedelta(minutes=2)
        await spy.score_network(n['id'],spy.Score(request_id=uuid4(),score=0),{'id':999})
        row=(await spy.mine({'id':1}))[0]
        self.assertEqual(row['status'],'failed')
        for secret in ('report','resources','military','score','deployment_roll'):self.assertNotIn(secret,row)

    async def test_notifications_are_deduplicated_and_admin_only(self):
        await self.deploy()
        with patch('admin_notifications.notify_admins',new_callable=AsyncMock) as notify, patch('telegram_bot.push',new_callable=AsyncMock):
            await spy.flush_notifications();await spy.flush_notifications()
        notify.assert_awaited_once()
        self.assertEqual(notify.call_args.kwargs['audience_roles'],('owner','full'))
        self.assertEqual(await self.mem.messages.count_documents({'to_id':1}),1)

    async def test_http_cannot_spoof_admin_actor(self):
        app=FastAPI();app.include_router(spy.router)
        async def user():return {'id':1}
        app.dependency_overrides[spy.get_user]=user
        with TestClient(app) as client:
            result=client.get('/api/espionage/admin/settings')
            self.assertEqual(result.status_code,403)
            result=client.post('/api/espionage/admin/questions/'+str(uuid4()),json={'request_id':str(uuid4()),'chance':100,'text':'answer','admin':{'id':999}})
            self.assertEqual(result.status_code,403)
