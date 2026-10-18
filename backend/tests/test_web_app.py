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
