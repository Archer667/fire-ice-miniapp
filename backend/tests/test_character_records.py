import os
import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime
from db import db, client
from character_records import retire, blacklist, archives, vacant_buildings, swap_castles, death_text
from routers.characters import RetireBody

class TextTests(unittest.TestCase):
    def test_optional_edited_narrative(self):
        p={'name':'Test','backstory':'original','gender':'lady'}
        text=death_text(p,'reason','edited')
        self.assertIn('edited',text)
        self.assertNotIn('original',text)
        self.assertNotIn('روایت کاراکتر',death_text(p,'reason','  '))
        self.assertTrue(text.endswith('داستان این کاراکتر به پایان رسید.'))

class Integration(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_blacklist_castles_archive_and_swap(self):
        if os.environ.get('DB_NAME') != 'valyria_character_test':
            self.skipTest('Requires isolated valyria_character_test database')
        await client.drop_database('valyria_character_test')
        try:
            from game_data import REGIONS
            region=next(k for k,r in REGIONS.items() if len(r['castles'])>=3)
            a,b,c=REGIONS[region]['castles'][:3]
            def person(uid,castle,level):
                return {'tg_id':uid,'name':f'Player {uid}','castle':castle,'region':region,
                        'resources':{'gold':123,'wood':12,'food':100,'men':50}, 'buildings':{'farm':{'level':level}},
                        'castle_buildings':{},'troops':{},'created_at':datetime.utcnow(),'last_tick':datetime.utcnow(),
                        'stats':{},'points':100,'backstory':'original story'}
            p=person(1,a,3);p['castle_buildings']={b:{'farm':{'level':2}}}
            await db.players.insert_many([p,person(2,c,1)])
            # No player messages are sent during tests.
            with patch('routers.ravens.send_system_message',AsyncMock()):
                await retire(1,RetireBody(action='death',reason='reason',narrative='edited',blacklisted=True),999)
            self.assertIsNotNone(await blacklist.find_one({'_id':1}))
            self.assertEqual((await vacant_buildings(a))['farm']['level'],3)
            self.assertEqual((await vacant_buildings(b))['farm']['level'],2)
            current=await db.players.find_one({'tg_id':1})
            self.assertTrue(current['registration_reset'])
            self.assertIsNone(current['castle'])
            self.assertEqual(current['backstory'],'original story')
            self.assertEqual(await archives.count_documents({'tg_id':1}),1)
            from routers.leaderboard import with_dead_players
            dead_rows=await with_dead_players([])
            self.assertEqual(len(dead_rows),1)
            self.assertTrue(dead_rows[0]['player']['is_dead'])
            notice=await db.character_announcements.find_one({})
            self.assertIn('edited',notice['text'])
            self.assertTrue(notice['ready'])
            # New character replacing the account does not replace the archived death.
            await db.players.replace_one({'tg_id':1},person(1,a,3))
            self.assertEqual(await archives.count_documents({'tg_id':1}),1)
            await swap_castles(1,a,2,c)
            first=await db.players.find_one({'tg_id':1});second=await db.players.find_one({'tg_id':2})
            self.assertEqual(first['castle'],c);self.assertEqual(second['castle'],a)
            self.assertEqual(first['buildings']['farm']['level'],1)
            self.assertEqual(second['buildings']['farm']['level'],3)
            self.assertEqual(first.get('stats',{}).get('attack_wins',0),0)
            self.assertEqual(first.get('stats',{}).get('castles_captured',0),0)
            from routers.admin import _add_castle, AddCastleBody, _admin_remove_castle
            await _add_castle(2, AddCastleBody(castle=b, mode='normal'))
            recipient=await db.players.find_one({'tg_id':2})
            self.assertEqual(recipient['castle_buildings'][b]['farm']['level'],2)
            self.assertEqual(recipient.get('stats',{}).get('castles_captured',0),0)
            await _admin_remove_castle(2,b,{})
            await _add_castle(2,AddCastleBody(castle=b,mode='conquest'))
            recipient=await db.players.find_one({'tg_id':2})
            self.assertEqual(recipient['stats']['castles_captured'],1)
            self.assertEqual(recipient['stats']['attack_wins'],1)
            from routers.admin import _clear_season_history
            await _clear_season_history()
            self.assertIsNotNone(await blacklist.find_one({'_id':1}))
            from routers.admin import reset_season, reset_game, ResetGameBody
            await reset_season(ResetGameBody(confirm='NEWSEASON'),{'id':999})
            self.assertIsNotNone(await blacklist.find_one({'_id':1}))
            await reset_game(ResetGameBody(confirm='RESET'),{'id':999})
            self.assertIsNotNone(await blacklist.find_one({'_id':1}))
            pending=person(1,None,0);pending['region']=None
            await db.players.insert_one(pending)
            await db.admin_roles.insert_one({'tg_id':777,'role':'limited'})
            import httpx
            from fastapi import FastAPI
            from auth import get_user
            from routers import characters, admin
            app=FastAPI();app.include_router(characters.router);app.include_router(admin.router)
            app.dependency_overrides[get_user]=lambda:{'id':777}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as http:
                rows=(await http.get('/api/admin/players/pending')).json()
                self.assertTrue(rows[0]['blacklisted'])
                self.assertEqual((await http.get('/api/admin/blacklist')).status_code,200)
                self.assertEqual((await http.post('/api/admin/characters/1/retire',json={'action':'delete'})).status_code,403)
        finally:
            await client.drop_database('valyria_character_test')
