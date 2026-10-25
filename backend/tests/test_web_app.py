import os
os.environ['PUBLIC_APP_ORIGIN']='https://web.test'
os.environ['DB_NAME']='valyria_web_test'
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import httpx
try:
    from mongomock_motor import AsyncMongoMockClient
except ImportError:
    AsyncMongoMockClient=None

@unittest.skipUnless(AsyncMongoMockClient,'Install mongomock-motor for isolated web integration tests')
class BrowserAccounts(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with patch('motor.motor_asyncio.AsyncIOMotorClient',AsyncMongoMockClient):
            import main,web_auth,db,web_notifications
        cls.app,cls.auth,cls.db,cls.notices=main.app,web_auth,db.db,web_notifications

    async def asyncSetUp(self):
        for name in await self.db.list_collection_names(): await self.db[name].delete_many({})
        await self.auth.ensure_indexes()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://web.test',headers={'origin':'https://web.test','x-valyria-client':'web'})

    async def asyncTearDown(self): await self.client.aclose()

    async def signup(self,name='player_one'):
        response=await self.client.post('/api/web-auth/register',json={'username':name,'password':'correct horse valyria 72'})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.client.headers['x-valyria-csrf']=data['csrf'];return data

    async def test_registration_session_and_no_automatic_admin(self):
        data=await self.signup()
        self.assertGreater(data['account']['id'],10**12)
        self.assertNotIn('password',str(data));self.assertTrue(data['recovery_code'])
        self.assertEqual((await self.client.get('/api/web-auth/session')).json()['account'],data['account'])
        self.assertEqual((await self.client.get('/api/admin/admins')).status_code,403)
        me=await self.client.get('/api/players/me');self.assertEqual(me.status_code,200);self.assertFalse(me.json()['registered'])
        row=await self.auth.accounts.find_one({'username':'player_one'})
        self.assertNotEqual(row['password_hash'],'correct horse valyria 72')
        self.assertNotIn(data['recovery_code'],str(row))

    async def test_duplicate_username_and_case_normalization(self):
        await self.signup('Player_One')
        response=await self.client.post('/api/web-auth/register',json={'username':'player_one','password':'another sufficiently long password'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(await self.auth.accounts.count_documents({}),1)

    async def test_no_telegram_or_development_bypass(self):
        self.assertEqual((await self.client.get('/api/players/me',headers={'x-dev-user':'1:owner','authorization':'tma fake'})).status_code,401)
        self.assertEqual((await self.client.post('/api/telegram/webhook',json={})).status_code,404)
        self.assertEqual((await self.client.get('/api/web-auth/config')).json()['mode'],'web')

    async def test_csrf_and_origin_required(self):
        data=await self.signup()
        self.assertEqual((await self.client.post('/api/notifications/action',headers={'x-valyria-csrf':''},json={'action':'read_all'})).status_code,403)
        self.assertEqual((await self.client.post('/api/web-auth/logout',headers={'origin':'https://attacker.test'},json={})).status_code,403)
        self.assertEqual((await self.client.post('/api/web-auth/login',headers={'x-valyria-client':''},json={'username':'player_one','password':'correct horse valyria 72'})).status_code,403)
        self.assertEqual((await self.client.get('/api/web-auth/session')).status_code,200)

    async def test_login_logout_and_generic_wrong_password(self):
        await self.signup()
        self.assertEqual((await self.client.post('/api/web-auth/logout',json={})).status_code,200)
        self.assertEqual((await self.client.get('/api/web-auth/session')).status_code,401)
        bad=await self.client.post('/api/web-auth/login',json={'username':'player_one','password':'wrong'})
        unknown=await self.client.post('/api/web-auth/login',json={'username':'unknown','password':'wrong'})
        self.assertEqual(bad.status_code,401);self.assertEqual(bad.json(),unknown.json())
        ok=await self.client.post('/api/web-auth/login',json={'username':'player_one','password':'correct horse valyria 72'})
        self.assertEqual(ok.status_code,200)
        cookie=ok.headers['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=strict',cookie)

    async def test_owner_can_review_shared_successful_login_ips(self):
        self.client.headers['x-forwarded-for']='203.0.113.42'
        first=await self.signup('player_one')
        await self.client.post('/api/web-auth/logout')
        second=await self.signup('player_two')
        await self.db.admin_roles.insert_one({'tg_id':second['account']['id'],'role':'owner'})
        response=await self.client.get('/api/admin/web-ip-audit?days=7')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['total_shared_ips'],1)
        row=response.json()['rows'][0]
        self.assertEqual(row['ip'],'203.0.113.42')
        self.assertEqual({account['username'] for account in row['accounts']},{'player_one','player_two'})
        await self.db.admin_roles.update_one({'tg_id':second['account']['id']},{'$set':{'role':'full'}})
        self.assertEqual((await self.client.get('/api/admin/web-ip-audit')).status_code,403)

    async def test_sessions_expire_with_real_time_and_disabled_account(self):
        data=await self.signup()
        await self.auth.sessions.update_many({}, {'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
        self.assertEqual((await self.client.get('/api/web-auth/session')).status_code,401)
        await self.signup('player_two')
        await self.auth.accounts.update_one({'username':'player_two'},{'$set':{'disabled':True}})
        self.assertEqual((await self.client.get('/api/players/me')).status_code,401)

    async def test_recovery_rotates_code_and_revokes_old_sessions(self):
        data=await self.signup();old_cookie=self.client.cookies.get(self.auth.COOKIE)
        recovered=await self.client.post('/api/web-auth/recover',json={'username':'player_one','password':'a fresh very long password 123','recovery_code':data['recovery_code']})
        self.assertEqual(recovered.status_code,200,recovered.text);self.assertNotEqual(data['recovery_code'],recovered.json()['recovery_code'])
        reused=await self.client.post('/api/web-auth/recover',json={'username':'player_one','password':'another very long password','recovery_code':data['recovery_code']})
        self.assertEqual(reused.status_code,400)
        self.assertIsNone(await self.auth.sessions.find_one({'_id':self.auth.digest(old_cookie)}))

    async def test_password_change_requires_old_password(self):
        await self.signup()
        bad=await self.client.post('/api/web-auth/password',json={'current_password':'wrong','new_password':'new correct password 82'})
        self.assertEqual(bad.status_code,400)
        ok=await self.client.post('/api/web-auth/password',json={'current_password':'correct horse valyria 72','new_password':'new correct password 82'})
        self.assertEqual(ok.status_code,200,ok.text)
        self.assertEqual(await self.auth.sessions.count_documents({}),1)

    async def test_weak_password_and_rate_limit(self):
        self.assertEqual((await self.client.post('/api/web-auth/register',json={'username':'player_one','password':'short'})).status_code,400)
        for _ in range(5):
            response=await self.client.post('/api/web-auth/register',json={'username':'player_one','password':'short'})
        self.assertEqual(response.status_code,429)

    async def test_private_notifications_pagination_and_marking(self):
        data=await self.signup();uid=data['account']['id']
        from game import now
        rows=[{'from_id':0,'to_id':uid,'text':f'نبرد شماره {i}','kind':'battle','read':False,'created_at':now()} for i in range(35)]
        await self.db.messages.insert_many(rows)
        foreign=await self.db.messages.insert_one({'from_id':0,'to_id':99,'text':'private','read':False,'created_at':now()})
        response=await self.client.get('/api/notifications?kind=war')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['total'],35);self.assertEqual(len(response.json()['rows']),30)
        second=await self.client.get('/api/notifications?page=2');self.assertEqual(len(second.json()['rows']),5)
        result=await self.client.post('/api/notifications/action',json={'action':'read','ids':[str(foreign.inserted_id)]})
        self.assertEqual(result.json()['changed'],0)
        self.assertFalse((await self.db.messages.find_one({'_id':foreign.inserted_id}))['read'])
        await self.client.post('/api/notifications/action',json={'action':'read_all'})
        self.assertEqual((await self.client.get('/api/notifications')).json()['unread'],0)

    async def test_system_notice_persists_even_when_routes_are_disabled(self):
        data=await self.signup();uid=data['account']['id']
        from routers.ravens import send_system_message
        import telegram_bot
        with patch('routers.ravens.notification_route',return_value={'raven':False,'bot':False}):
            await send_system_message(uid,'بازیکن','نتیجهٔ نبرد',via_raven=False)
        self.assertEqual(await self.db.messages.count_documents({'to_id':uid}),1)
        await telegram_bot.push(uid,'<b>درخواست تازه</b>',parse_mode='HTML')
        response=await self.client.get('/api/notifications')
        self.assertEqual(response.json()['total'],2)
        self.assertTrue(any(row['text']=='درخواست تازه' for row in response.json()['rows']))
        row=response.json()['rows'][0]
        await self.client.post('/api/notifications/action',json={'action':'archive','ids':[row['id']]})
        self.assertEqual((await self.client.get('/api/notifications')).json()['total'],1)
        self.assertEqual((await self.client.get('/api/notifications?archived=true')).json()['total'],1)
        await self.client.post('/api/notifications/action',json={'action':'restore','ids':[row['id']]})
        self.assertEqual((await self.client.get('/api/notifications')).json()['total'],2)

    async def test_notification_read_during_pause(self):
        await self.signup()
        import game_clock
        with patch.object(game_clock,'paused',return_value=True):
            response=await self.client.post('/api/notifications/action',json={'action':'read_all'})
        self.assertEqual(response.status_code,200,response.text)

    async def test_battle_download_ticket_does_not_open_other_private_routes(self):
        data=await self.signup()
        payload={'title':'نبرد آزمایشی','text':'گزارش کامل\nپایان گزارش'}
        self.assertEqual((await self.client.post('/api/admin/battle-reports',json=payload)).status_code,403)
        await self.db.admin_roles.insert_one({'tg_id':data['account']['id'],'role':'full'})
        self.assertEqual((await self.client.post('/api/admin/battle-reports',json=payload,headers={'x-valyria-csrf':''})).status_code,403)
        response=await self.client.post('/api/admin/battle-reports',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://web.test') as anonymous:
            download=await anonymous.get(response.json()['path'])
            self.assertEqual(download.status_code,200,download.text)
            self.assertIn('پایان گزارش',download.text)
            self.assertEqual((await anonymous.get('/api/battle-report-files/'+'A'*43)).status_code,404)
            self.assertEqual((await anonymous.get('/api/admin/battles')).status_code,401)

    async def test_notification_filter_aliases_return_to_all_and_privacy(self):
        data=await self.signup();uid=data['account']['id']
        from game import now
        await self.db.messages.insert_many([
            {'from_id':0,'to_id':uid,'text':'The clash is settled','kind':'battle','read':False,'created_at':now()},
            {'from_id':0,'to_id':uid,'text':'بی چهره ها سفارش را پذیرفتند','kind':'general','read':False,'created_at':now()},
            {'from_id':0,'to_id':uid+1,'text':'private clash','kind':'battle','read':False,'created_at':now()},
        ])
        for url,total in [('/api/notifications',2),('/api/notifications?kind=war',1),('/api/notifications?kind=institution',1),('/api/notifications?kind=family',0),('/api/notifications?kind=',2),('/api/notifications?q=clash&kind=war',1)]:
            response=await self.client.get(url);self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['total'],total,url)

    async def test_word_limit_settings_require_full_admin_and_update_immediately(self):
        data=await self.signup();uid=data['account']['id']
        payload={'roleplays':3,'projects':1,'roleplay_words':45,'scenario_words':72,'request_words':80}
        self.assertEqual((await self.client.post('/api/admin/submission-limits',json=payload)).status_code,403)
        await self.db.admin_roles.insert_one({'tg_id':uid,'role':'full'})
        result=await self.client.post('/api/admin/submission-limits',json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual((await self.client.get('/api/text-limits')).json(),{'roleplay_words':45,'scenario_words':72,'request_words':80})
        self.assertEqual((await self.client.post('/api/admin/submission-limits',json={'roleplays':3,'projects':1})).status_code,200)
        self.assertEqual((await self.client.get('/api/text-limits')).json()['scenario_words'],72)

    async def test_social_features_real_browser_auth_landless_escrow_and_csrf(self):
        from uuid import uuid4
        from game import now
        import game_clock
        data=await self.signup();uid=data['account']['id'];at=now()
        await self.db.players.insert_one({'tg_id':uid,'name':'لیدی آلیس','created_at':at,'last_tick':at,'region':'north','castle':None,'landless':True,'resources':{'gold':1000},'buildings':{},'castle_buildings':{}})
        import family
        await self.db.character_locations.insert_one({'_id':family.key(await self.db.players.find_one({'tg_id':uid})),'tg_id':uid,'name':'لیدی آلیس','place':'وینترفل','trip':None,'captive':None})
        body={'request_id':str(uuid4()),'title':'تأمین چوب بندر','description':'تأمین چوب برای تعمیر اسکله و تحویل به بندر','kind':'trade','place':'بندر سفید','reward':100,'duration_days':3}
        self.assertEqual((await self.client.post('/api/contracts',json=body,headers={'x-valyria-csrf':''})).status_code,403)
        response=await self.client.post('/api/contracts',json=body);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual((await self.db.players.find_one({'tg_id':uid}))['resources']['gold'],900)
        repeat=await self.client.post('/api/contracts',json=body);self.assertEqual(repeat.status_code,200,repeat.text)
        self.assertEqual((await self.db.players.find_one({'tg_id':uid}))['resources']['gold'],900)
        self.assertEqual((await self.client.get('/api/castle-life')).status_code,200)
        with patch.object(game_clock,'paused',return_value=True):
            paused=await self.client.post('/api/contracts',json={**body,'request_id':str(uuid4())})
            self.assertEqual(paused.status_code,423,paused.text)
        news=await self.client.post('/api/newspaper',json={'request_id':str(uuid4()),'title':'خبری از بندر سفید','body':'کشتی‌های بازرگانی به بندر رسیده‌اند.','source':'خبرنگار بندر','image':'port'})
        self.assertEqual(news.status_code,200,news.text)
        self.assertEqual((await self.client.get('/api/newspaper')).json()['articles'],[])
        self.assertEqual((await self.client.post('/api/admin/social/news/'+news.json()['id']+'/review',json={'version':1,'action':'publish'})).status_code,403)

    async def test_analytics_full_admin_exports_and_scoped_private_download(self):
        data=await self.signup();uid=data['account']['id']
        from game import now
        target=1001;at=now()
        await self.db.players.insert_one({'tg_id':target,'name':'لرد آزمون','created_at':at,'last_tick':at,'region':'north','landless':True,'castle':None,'resources':{'gold':800,'men':300},'troops':{'infantry':30,'ship':2},'buildings':{},'castle_buildings':{},'points':100,'stats':{}})
        self.assertEqual((await self.client.get('/api/admin/analytics')).status_code,403)
        await self.db.admin_roles.insert_one({'tg_id':uid,'role':'limited'})
        self.assertEqual((await self.client.post('/api/admin/analytics/players/1001/hourly',json={})).status_code,403)
        await self.db.admin_roles.update_one({'tg_id':uid},{'$set':{'role':'full'}})
        metadata=await self.client.get('/api/admin/analytics');self.assertEqual(metadata.status_code,200,metadata.text)
        self.assertEqual(metadata.json()['players'][0]['id'],1001)
        self.assertEqual((await self.client.post('/api/admin/analytics/players/1001/hourly',json={},headers={'x-valyria-csrf':''})).status_code,403)
        tickets=[]
        for route,body in [('/api/admin/analytics/season',{}),('/api/admin/analytics/players/1001/hourly',{})]:
            result=await self.client.post(route,json=body);self.assertEqual(result.status_code,200,result.text);tickets.append(result.json())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://web.test') as anonymous:
            for ticket in tickets:
                result=await anonymous.get(ticket['path']);self.assertEqual(result.status_code,200,result.text)
                self.assertIn('꧁─꩜༺᪥༻꩜─꧂',result.text);self.assertIn('attachment',result.headers['content-disposition'])
            self.assertEqual((await anonymous.get('/api/admin/analytics')).status_code,401)
            self.assertEqual((await anonymous.get('/api/analytics-files/'+'a'*43)).status_code,404)
        self.assertEqual((await self.db.players.find_one({'tg_id':target}))['resources']['gold'],800)
        self.assertEqual(await self.db.analytics_hourly.count_documents({'uid':1001}),1)
