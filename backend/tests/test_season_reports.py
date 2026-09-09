import os, unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

class SeasonReportsTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_epoch_reports_and_access(self):
        if os.environ.get('DB_NAME') != 'valyria_season_reports_test':
            self.skipTest('Disposable database required')
        from db import db, client
        import season_clock as sc
        import system_reports as sr
        import httpx
        from fastapi import FastAPI
        from auth import get_user
        clock = datetime(2026, 9, 9, 12)
        await client.drop_database('valyria_season_reports_test')
        try:
            with patch.object(sc.game_clock, 'now', return_value=clock), patch('admin_notifications._admin_ids', AsyncMock(return_value={999})):
                await db.players.insert_many([
                    {'tg_id': 999, 'created_at': clock-timedelta(days=50)},
                    {'tg_id': 1, 'created_at': clock-timedelta(days=10), 'season_started_at': clock-timedelta(days=3)},
                    {'tg_id': 2, 'created_at': clock-timedelta(hours=8)}])
                self.assertEqual((await sc.season_day())['day'], 4)
                await db.players.delete_many({})
                self.assertEqual((await sc.season_day())['day'], 4)
                await sc.start_season(clock)
                self.assertEqual((await sc.season_day())['day'], 1)
                await sc.start_season(clock-timedelta(days=35))
                self.assertEqual((await sc.season_day())['day'], 30)
                await sc.start_season(clock-timedelta(days=3))
                from routers import players as pr
                from starlette.requests import Request
                from fastapi import BackgroundTasks
                from config import STARTING_RESOURCES
                for uid, age in [(1, 10), (2, 0)]:
                    await db.players.insert_one({'tg_id':uid,'name':str(uid),'created_at':clock-timedelta(days=age), 'last_tick':clock,
                        'castle':'Winterfell','region':'north','is_port':False,'resources':dict(STARTING_RESOURCES),'buildings':{},'stats':{}})
                with patch.object(pr,'get_admin_role',AsyncMock(return_value=None)), patch.object(pr,'scored_players',AsyncMock(return_value=[])), patch.object(pr,'apply_campaign_upkeep',AsyncMock(side_effect=lambda uid,r:r)):
                    days=[]
                    for uid in [1,2]:
                        result=await pr.me(Request({'type':'http','headers':[]}),BackgroundTasks(),{'id':uid})
                        days.append(result['day'])
                        self.assertIn('gold',result['daily_production'])
                    self.assertEqual(days,[4,4])
            await db.caravans.insert_one({'tg_id':1,'player_name':'Sender','target_tg_id':2,'target_name':'Receiver',
                'created_at':clock,'arrival_at':clock,'resources':{'wood':47},'route_path':['A','B'],'active':True})
            result=await sr.report('caravans',{'id':999})
            for text in ['Sender','Receiver','47','A ← B','در راه']:
                self.assertIn(text,result['text'])
            app=FastAPI();app.include_router(sr.router)
            identity={'id':999}
            app.dependency_overrides[get_user]=lambda:identity
            await db.admin_roles.insert_one({'tg_id':999,'role':'full'})
            with patch('telegram_bot.send_report_document',AsyncMock()) as send:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                    r=await c.post('/api/admin/reports/caravans/telegram',json={'chat_id':2})
                    self.assertEqual(r.status_code,200,r.text)
                    self.assertEqual(send.call_args.args[0],999)
                    await db.admin_roles.update_one({'tg_id':999},{'$set':{'role':'limited'}})
                    r=await c.post('/api/admin/reports/caravans/telegram')
                    self.assertEqual(r.status_code,403)
                    r=await c.post('/api/admin/reports/blacklist/telegram')
                    self.assertEqual(r.status_code,200,r.text)
                    identity={'id':2}
                    r=await c.get('/api/admin/reports/caravans')
                    self.assertEqual(r.status_code,403)
                    r=await c.post('/api/admin/reports/blacklist/telegram')
                    self.assertEqual(r.status_code,403)
        finally:
            await client.drop_database('valyria_season_reports_test')
