import unittest, os
from datetime import timedelta
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
class SystemTests(unittest.IsolatedAsyncioTestCase):
    async def test_limits_reports_and_pagination(self):
        assert os.environ['DB_NAME']=='valyria_character_test' and os.environ['DEV_MODE']=='true'
        from db import db,client
        from game import now
        import system_reports as sr
        await client.drop_database('valyria_character_test')
        try:
            for i,category in enumerate(['sabotage','economy','other']):
                await db.roleplays.insert_one({'_id':str(i),'tg_id':11,'category':category,'created_at':now()})
            self.assertEqual(await sr.usage(11,'roleplays'),3)
            with self.assertRaises(HTTPException): await sr.check_quota(11,'roleplays')
            await db.roleplays.delete_many({})
            with self.assertRaises(HTTPException): await sr.check_quota(11,'roleplays')
            await sr.save_limits(sr.LimitsBody(roleplays=4,projects=1),{'id':999})
            await sr.check_quota(11,'roleplays')
            await sr.consume(11,'projects','one');await sr.consume(11,'projects','one')
            self.assertEqual(await sr.usage(11,'projects'),1)
            with self.assertRaises(HTTPException): await sr.check_quota(11,'projects')
            with patch.object(sr,'current_week_start',return_value=now()+timedelta(days=7)):
                self.assertEqual(await sr.usage(11,'projects'),0)
            from routers import leaderboard as lb
            rows=[{'player':{'tg_id':i,'name':str(i),'castle':'A','region':'north'},'score':124-i,'rank_label':None} for i in range(123)]
            with patch.object(lb,'scored_players',AsyncMock(return_value=rows)),patch.object(lb,'with_dead_players',AsyncMock(side_effect=lambda r:r)),patch.object(lb,'_without_admins',AsyncMock(side_effect=lambda r:r)):
                first=await lb.leaderboard({'id':1},page=1);second=await lb.leaderboard({'id':1},page=2);last=await lb.leaderboard({'id':1},page=3)
                self.assertEqual([len(x['items']) for x in [first,second,last]],[50,50,23]);self.assertEqual(second['items'][0]['rank'],51);self.assertEqual(last['items'][-1]['rank'],123)
            buyer={'tg_id':11,'name':'Buyer'}
            for source in ['players','westeros','black']:
                key=await sr.market_start(buyer,source,'wood',8,12,{'seller_tg_id':12,'seller_name':'Seller'} if source=='players' else None)
                await sr.market_done(key)
            report=await sr.report('market',{'id':999})
            self.assertIn('96',report['text']);self.assertIn('Buyer',report['text']);self.assertIn('Seller',report['text'])
            # Real middleware: admin settings are audited; player has no access.
            import main,httpx
            await db.admin_roles.insert_one({'tg_id':999,'role':'owner'})
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as c:
                response=await c.post('/api/admin/submission-limits',headers={'X-Dev-User':'999:Admin'},json={'roleplays':3,'projects':1})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(await db.admin_activity.count_documents({'actor_id':999,'status':200}),1)
                from config import STARTING_RESOURCES
                await db.players.insert_many([{'tg_id':uid,'name':name,'resources':{**STARTING_RESOURCES,'gold':1000},'created_at':now(),'last_tick':now(),'castle':'Winterfell','region':'north','buildings':{},'castle_buildings':{},'popularity':50,'tax_rate':10} for uid,name in [(11,'Buyer'),(12,'Seller')]])
                denied=await c.post('/api/roleplay/send',headers={'X-Dev-User':'11:Buyer'},json={'category':'diplomacy','text':'A valid diplomatic roleplay'})
                self.assertEqual(denied.status_code,429,denied.text)
                listing=await db.player_market_listings.insert_one({'seller_tg_id':12,'seller_name':'Seller','resource':'wood','qty':20,'price':10,'created_at':now()})
                purchase=await c.post('/api/market/players/buy',headers={'X-Dev-User':'11:Buyer'},json={'listing_id':str(listing.inserted_id),'qty':5})
                self.assertEqual(purchase.status_code,200,purchase.text)
                trade=await db.market_history.find_one({'buyer_id':11,'qty':5,'status':'completed'})
                self.assertEqual(trade['total'],50);self.assertEqual(trade['seller_id'],12)
                change=await c.post('/api/admin/players/11/resources',headers={'X-Dev-User':'999:Admin'},json={'resources':{'gold':700}})
                self.assertEqual(change.status_code,200,change.text)
                audit=await db.admin_activity.find_one({'path':'/api/admin/players/11/resources','status':200})
                self.assertEqual(audit['changes'][0]['after']['resources']['gold'],700)
                forbidden=await c.get('/api/admin/reports/market',headers={'X-Dev-User':'11:Player'})
                self.assertEqual(forbidden.status_code,403)
        finally: await client.drop_database('valyria_character_test')
