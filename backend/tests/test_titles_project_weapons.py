import os, unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException

class TitlesWeaponsTests(unittest.IsolatedAsyncioTestCase):
    async def test_office_transitions_and_weapon_settlement(self):
        if os.environ.get('DB_NAME') != 'valyria_titles_weapons_test':
            self.skipTest('Disposable database required')
        from db import db, client
        import ranks
        from routers import titles as t, projects as p
        import project_engine as e
        from game_data import WEAPON_NAMES
        clock = [datetime(2026, 9, 9, 12)]
        await client.drop_database('valyria_titles_weapons_test')
        try:
            for uid in [101,102,103]:
                await db.players.insert_one({'tg_id':uid,'name':f'Player {uid}','castle':'Winterfell','region':'north',
                    'created_at':clock[0],'last_tick':clock[0],'resources':{'gold':10000,**{k:1000 for k in WEAPON_NAMES}},'buildings':{}})
            await db.hierarchy.insert_one({'_id':'main','overlords':{'north':101},'treasury_gold':500,'king_salary_rate':25})
            await t.set_warden(t.WardenBody(group='north',tg_id=101),{'id':999})
            h=await ranks.get_hierarchy_doc()
            self.assertIsNone(h['overlords']['north']);self.assertEqual(h['warden_north'],101)
            self.assertEqual(ranks.title_bonus_and_rank(101,h)[1],'warden')
            await t.set_warden(t.WardenBody(group='north',tg_id=101),{'id':999})
            with self.assertRaises(HTTPException):await t.set_overlord(t.OverlordBody(region='north',tg_id=101),{'id':999})
            await t.set_overlord(t.OverlordBody(region='north',tg_id=102),{'id':999})
            self.assertEqual((await ranks.my_tribute_role(101))[1],{102})
            await t.set_king(t.KingBody(tg_id=101),{'id':999})
            h=await ranks.get_hierarchy_doc()
            self.assertIsNone(h['warden_north']);self.assertEqual(h['king'],101)
            self.assertEqual(ranks.title_bonus_and_rank(101,h)[1],'king')
            self.assertEqual(h['treasury_gold'],500);self.assertEqual(h['king_salary_rate'],25)
            await t.set_king(t.KingBody(tg_id=101),{'id':999})
            with self.assertRaises(HTTPException):await t.set_warden(t.WardenBody(group='north',tg_id=101),{'id':999})
            with self.assertRaises(HTTPException):await t.set_king(t.KingBody(tg_id=103),{'id':999})
            await t.set_warden(t.WardenBody(group='north',tg_id=102),{'id':999})
            await t.set_overlord(t.OverlordBody(region='north',tg_id=103),{'id':999})
            h=await ranks.get_hierarchy_doc()
            self.assertEqual([ranks.title_bonus_and_rank(uid,h)[1] for uid in [101,102,103]],['king','warden','overlord'])
            # Upgrade pre-existing overlapping offices without changing highest bonuses.
            await db.hierarchy.update_one({'_id':'main'},{'$set':{'overlords.north':101,'overlords.vale':102,'warden_south':101}})
            before=await ranks.get_hierarchy_doc()
            await ranks.migrate_exclusive_titles();await ranks.migrate_exclusive_titles()
            after=await ranks.get_hierarchy_doc()
            self.assertIsNone(after['overlords']['north']);self.assertIsNone(after['overlords']['vale']);self.assertIsNone(after['warden_south'])
            self.assertEqual([ranks.title_bonus_and_rank(uid,before) for uid in [101,102]],[ranks.title_bonus_and_rank(uid,after) for uid in [101,102]])
            self.assertEqual(await db.admin_activity.count_documents({'_id':'exclusive-titles-v1','status':200}),1)
            await db.game_settings.insert_one({'_id':'weekly_submission_limits','roleplays':3,'projects':100})
            with patch.object(e,'now',lambda:clock[0]),patch.object(p,'now',lambda:clock[0]),patch.object(e,'apply_production',lambda x:x),patch.object(e.telegram_bot,'push'):
                def proposal():return p.Proposal(request_id=str(uuid4()),name='Weapon forge',goal='Forge weapons for the realm',description='Build workshops to forge all five types of weapons',
                    budget={k:100 for k in WEAPON_NAMES},period_return={k:20 for k in WEAPON_NAMES},total_shares=10,owner_shares=2,period_hours=24,period_count=2,accepted_terms=True)
                async def stock(uid):return (await db.players.find_one({'tg_id':uid}))['resources']
                body=proposal();created=await p.submit(body,{'id':101});await p.submit(body,{'id':101})
                resources=await stock(101);self.assertTrue(all(resources[k]==980 for k in WEAPON_NAMES))
                self.assertTrue(all(created['share_cost'][k]==10 for k in WEAPON_NAMES))
                await p.approve(created['id'],p.Approval(publish_at=(clock[0]+timedelta(hours=1)).replace(tzinfo=timezone.utc),funding_hours=24,max_shares_per_player=None,reason='Approved'),{'id':999})
                clock[0]+=timedelta(hours=1)
                purchase=p.Purchase(request_id=str(uuid4()),shares=8)
                await p.buy(created['id'],purchase,{'id':102});await p.buy(created['id'],purchase,{'id':102})
                resources=await stock(102);self.assertTrue(all(resources[k]==920 for k in WEAPON_NAMES))
                clock[0]+=timedelta(hours=49)
                result=await e.tick_project(await db.projects.find_one({'_id':created['id']}))
                self.assertEqual(result['status'],'completed')
                await e.tick_project(result)
                resources=await stock(102);self.assertTrue(all(resources[k]==952 for k in WEAPON_NAMES))
                self.assertTrue(all(e.public_project(result,102)['my_net'][k]==-48 for k in WEAPON_NAMES))
                self.assertIn(WEAPON_NAMES['weapon_archer'],e.announcement(result))
                resources=await stock(101)
                rejected=await p.submit(proposal(),{'id':101})
                await p.reject(rejected['id'],p.Decision(reason='Rejected'),{'id':999})
                self.assertEqual(await stock(101),resources)
                await db.players.update_one({'tg_id':101},{'$set':{'resources.weapon_hcav':0}})
                with self.assertRaises(HTTPException):await p.submit(proposal(),{'id':101})
        finally:
            await client.drop_database('valyria_titles_weapons_test')
