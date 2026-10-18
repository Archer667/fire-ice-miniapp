import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from fastapi import FastAPI, HTTPException, Request
import battle_report_files as report
from admin_permissions import war_roleplay_allowed

class BattleReportFiles(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store=SimpleNamespace(create_index=AsyncMock(), count_documents=AsyncMock(return_value=0),
                                   insert_one=AsyncMock(),find_one=AsyncMock(return_value=None))
        self.patch=patch.object(report,'reports',self.store);self.patch.start()
        self.addCleanup(self.patch.stop)
        async def identity(request: Request):
            role=request.headers.get('x-test-role')
            if not role:raise HTTPException(401)
            return {'id':9,'role':role}
        async def admin(user):
            if user['role'] not in ('full','war_roleplay'):raise HTTPException(403)
            return user
        self.admin=patch.object(report,'get_admin',admin);self.admin.start();self.addCleanup(self.admin.stop)
        app=FastAPI();app.include_router(report.router);app.dependency_overrides[report.get_user]=identity
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://test')
        self.addAsyncCleanup(self.client.aclose)

    async def test_non_admin_cannot_create_download(self):
        for headers,code in [({},401),({'x-test-role':'player'},403)]:
            result=await self.client.post('/api/admin/battle-reports',json={'title':'نبرد','text':'گزارش'},headers=headers)
            self.assertEqual(result.status_code,code)
        self.store.insert_one.assert_not_awaited()

    async def test_large_report_is_complete_and_escaped(self):
        body=('لشکر مدافع و مهاجم\n'*12000)+'<script>alert(1)</script>\nپایان کامل گزارش'
        created=await self.client.post('/api/admin/battle-reports',json={'title':'نبرد <img src=x>','text':body},headers={'x-test-role':'full'})
        self.assertEqual(created.status_code,200)
        ticket=created.json();token=ticket['path'].rsplit('/',1)[-1]
        row=self.store.insert_one.call_args.args[0]
        self.assertEqual(row['_id'],hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(row['text'],body);self.assertEqual(row['expires_at']-row['created_at'],timedelta(minutes=15))
        self.store.find_one.return_value=row
        result=await self.client.get(ticket['path'])
        self.assertEqual(result.status_code,200)
        self.assertIn('پایان کامل گزارش',result.text)
        self.assertIn('&lt;script&gt;',result.text);self.assertNotIn('<script>',result.text)
        self.assertNotIn('<img src=x>',result.text)
        self.assertEqual(result.headers['cache-control'],'no-store')
        self.assertIn('attachment;',result.headers['content-disposition'])
        self.assertEqual(result.headers['access-control-allow-origin'],'https://web.telegram.org')
        self.assertIn('sandbox',result.headers['content-security-policy'])

    async def test_unknown_and_expired_link_rejected_even_before_ttl_cleanup(self):
        result=await self.client.get('/api/battle-report-files/'+'A'*43)
        self.assertEqual(result.status_code,404)
        query=self.store.find_one.call_args.args[0]
        self.assertIn('$gt',query['expires_at'])
        self.assertIsInstance(query['expires_at']['$gt'],datetime)
        self.assertEqual((await self.client.get('/api/battle-report-files/invalid')).status_code,404)

    async def test_rate_limit_and_oversize_fail_without_truncation(self):
        self.store.count_documents.return_value=10
        result=await self.client.post('/api/admin/battle-reports',json={'title':'نبرد','text':'x'},headers={'x-test-role':'full'})
        self.assertEqual(result.status_code,429)
        self.store.insert_one.assert_not_awaited()
        self.store.count_documents.return_value=0
        result=await self.client.post('/api/admin/battle-reports',json={'title':'نبرد','text':'😀'*1_100_000},headers={'x-test-role':'full'})
        self.assertEqual(result.status_code,413)
        self.store.insert_one.assert_not_awaited()

    async def test_war_judge_can_export_and_head_is_supported(self):
        self.assertTrue(war_roleplay_allowed('POST','/api/admin/battle-reports'))
        result=await self.client.post('/api/admin/battle-reports',json={'title':'نبرد','text':'کامل'},headers={'x-test-role':'war_roleplay'})
        self.assertEqual(result.status_code,200)
        self.store.find_one.return_value=self.store.insert_one.call_args.args[0]
        head=await self.client.head(result.json()['path'])
        self.assertEqual(head.status_code,200);self.assertEqual(head.content,b'')
