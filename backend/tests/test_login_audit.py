import asyncio
import hashlib
import hmac
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import login_audit as audit


class SignatureTests(unittest.TestCase):
    def headers(self, ip='8.8.8.8'):
        headers = {'x-login-ip': ip, 'x-login-time': '1000', 'authorization': 'tma sample'}
        headers['x-login-signature'] = hmac.new(b'test', f'1000\n{ip}\ntma sample'.encode(), hashlib.sha256).hexdigest()
        return headers

    def test_signature_and_expiry(self):
        headers = self.headers()
        self.assertEqual(audit.verified_ip(headers, 'test', 1010), '8.8.8.8')
        self.assertIsNone(audit.verified_ip(headers, 'test', 1100))
        self.assertIsNone(audit.verified_ip(headers, '', 1010))
        headers['authorization'] = 'tma another-account'
        self.assertIsNone(audit.verified_ip(headers, 'test', 1010))

    def test_untrusted_and_private_ips(self):
        self.assertIsNone(audit.verified_ip({'x-forwarded-for': '8.8.8.8'}, 'test', 1010))
        for ip in ['127.0.0.1', '10.0.0.1', '8.8.8.8, 1.1.1.1', 'invalid']:
            self.assertIsNone(audit.verified_ip(self.headers(ip), 'test', 1010))
        self.assertEqual(audit.verified_ip(self.headers('::ffff:8.8.8.8'), 'test', 1010), '8.8.8.8')


class LoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.environ.get('DB_NAME') != 'valyria_login_test':
            self.skipTest('Requires isolated valyria_login_test database')
        # Motor binds to a loop; create a fresh client for each isolated test.
        from motor.motor_asyncio import AsyncIOMotorClient
        self.client = AsyncIOMotorClient(os.environ['MONGODB_URI'])
        self.db_patch = patch.object(audit, 'db', self.client.valyria_login_test)
        self.db_patch.start()
        await self.client.drop_database('valyria_login_test')
        await audit.ensure_indexes()
        await audit.db.players.insert_many([{'tg_id': i, 'name': f'Player {i}', 'castle':'Castle', 'region':'north', 'created_at':datetime(2026,9,1)} for i in [1, 2, 3]])

    async def asyncTearDown(self):
        if hasattr(self, 'client'):
            await self.client.drop_database('valyria_login_test')
            self.client.close()
            self.db_patch.stop()

    async def test_pairs_deduplication_and_retention(self):
        with patch.object(audit, 'OWNER_ID', 999), patch.object(audit.telegram_bot, 'push') as send:
            await audit.record_login({'id': 1}, '8.8.8.8')
            await audit.record_login({'id': 1}, '8.8.8.8')
            self.assertEqual(send.call_count, 0)
            await asyncio.gather(*(audit.record_login({'id': 2}, '8.8.8.8') for _ in range(3)))
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args.args[0], 999)
            self.assertIn('Player 1', send.call_args.args[1])
            self.assertIn('Player 2', send.call_args.args[1])
            await audit.record_login({'id': 3}, '1.1.1.1')
            self.assertEqual(send.call_count, 1)
            old = datetime.now(timezone.utc) - timedelta(hours=25)
            await audit.db.login_observations.update_many({}, {'$set': {'last_seen': old}})
            await audit.record_login({'id': 3}, '8.8.8.8')
            self.assertEqual(send.call_count, 1)
            indexes = await audit.db.login_observations.index_information()
            self.assertEqual(indexes['expires_at_1']['expireAfterSeconds'], 0)

    async def test_retired_and_recreated_characters_do_not_match_old_logins(self):
        with patch.object(audit, 'OWNER_ID', 999), patch.object(audit.telegram_bot, 'push') as send:
            await audit.record_login({'id': 1}, '8.8.8.8')
            await audit.db.players.update_one({'tg_id':1},{'$set':{'is_dead':True}})
            await audit.record_login({'id': 2}, '8.8.8.8')
            self.assertEqual(send.call_count,0)
            await audit.db.players.update_one({'tg_id':1},{'$set':{'is_dead':False,'registration_reset':True,'castle':None}})
            await audit.record_login({'id': 1}, '1.1.1.1')
            self.assertIsNone(await audit.db.login_observations.find_one({'tg_id':1,'ip':'1.1.1.1'}))
            await audit.db.players.update_one({'tg_id':1},{'$set':{'registration_reset':False,'castle':'New Castle','created_at':datetime(2026,9,8),'name':'New Character'}})
            await audit.record_login({'id': 2}, '8.8.8.8')
            self.assertEqual(send.call_count,0)
            await audit.record_login({'id': 1}, '8.8.8.8')
            self.assertEqual(send.call_count,1)
            self.assertIn('New Character',send.call_args.args[1])

if __name__ == '__main__':
    unittest.main()
