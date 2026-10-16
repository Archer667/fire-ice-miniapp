import unittest,base64,io
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from bson import ObjectId
from fastapi import HTTPException
from PIL import Image
from routers import admin,war
import admin_formations as f
import daily_schedule as ds
from tests.test_player_death import Collection

class Formations(unittest.IsolatedAsyncioTestCase):
    async def test_move_all_members_preserves_group(self):
        gid=ObjectId();rows=[{'_id':ObjectId(),'tg_id':uid,'active':True} for uid in (1,2,3)]
        group={'_id':gid,'army_ids':[a['_id'] for a in rows],'leader_tg_id':1}
        move=AsyncMock(return_value={'ok':True})
        with patch.object(f,'groups',SimpleNamespace(find_one=AsyncMock(return_value=group))),patch.object(f,'members',AsyncMock(return_value=rows)),patch.object(war,'all_castle_names_and_ports',AsyncMock(return_value=({'C'},set()))),patch.object(admin,'_relocate_campaign',move),patch.object(f,'set_members',AsyncMock()) as split:
            result=await f.operate(str(gid),f.Action(action='relocate',destination='C'),{'id':9})
        self.assertEqual(result['affected'],3);self.assertEqual(move.await_count,3);split.assert_not_awaited()
        self.assertTrue(all(call.kwargs['allow_group'] for call in move.call_args_list))
    async def test_battle_confirmation_validates_whole_group_before_any_move(self):
        with patch.object(f,'groups',SimpleNamespace(find_one=AsyncMock(return_value={'_id':ObjectId()}))),patch.object(f,'members',AsyncMock(return_value=[{'engagement_locked':False},{'engagement_locked':True}])),patch.object(admin,'_relocate_campaign',AsyncMock()) as move:
            with self.assertRaises(HTTPException):await f.operate(str(ObjectId()),f.Action(action='relocate',destination='C'),{'id':9})
        move.assert_not_awaited()
    async def test_stay_closure_does_not_return_armies_or_move_departed_root(self):
        rid,aid,bid=ObjectId(),ObjectId(),ObjectId();at=datetime(2026,10,16)
        root={'_id':rid,'tg_id':1,'active':True,'engagement_campaign_id':str(rid),'battle_left_at':at-timedelta(minutes=1),'target_castle':'C','battle_location':'B','battle_attacker_army_ids':[str(aid)],'battle_defender_army_ids':[str(bid)]}
        rows=[root,{'_id':aid,'tg_id':2,'active':True,'engagement_campaign_id':str(rid),'origin_castle':'A','target_castle':'B'}, {'_id':bid,'tg_id':3,'active':True,'engagement_campaign_id':str(rid),'origin_castle':'D','target_castle':'B'}]
        store=Collection(rows)
        with patch.object(admin,'campaigns',store),patch.object(admin,'now',return_value=at),patch.object(admin,'_plan_battle_return',AsyncMock()) as returning:
            await admin._close_battle_state(root,str(rid),cancelled=True,stay=True)
        returning.assert_not_awaited()
        self.assertEqual(store.rows[0]['target_castle'],'C')
        for army in store.rows[1:]:
            self.assertEqual(army['target_castle'],'B');self.assertEqual(army['origin_castle'],'B');self.assertFalse(army['engagement_locked']);self.assertEqual(army['op_type'],'garrison')
    async def test_stay_at_road_contact_preserves_fraction(self):
        rid=ObjectId();point={'kind':'edge','a':'A','b':'B','position':.37,'base_minutes':30}
        root={'_id':rid,'active':True,'target_castle':'مسیر A — B','battle_contact':point,'engagement_campaign_id':str(rid)}
        store=Collection([root])
        with patch.object(admin,'campaigns',store):await admin._close_battle_state(root,str(rid),cancelled=True,stay=True)
        self.assertEqual(store.rows[0]['stationed_edge']['position'],.37)
        self.assertEqual(store.rows[0]['travel_minutes'],0)
    async def test_last_defending_army_exit_closes_case_even_if_castle_still_owned(self):
        rid,aid,did=ObjectId(),ObjectId(),ObjectId()
        root={'_id':rid,'tg_id':1,'active':False,'battle_is_root':True,'battle_open':True,'engagement_campaign_id':str(rid),'battle_location':'B','battle_defender_tg_id':2,'battle_attacker_army_ids':[str(aid)],'battle_defender_army_ids':[str(did)]}
        attacker={'_id':aid,'tg_id':1,'active':True,'engagement_campaign_id':str(rid),'target_castle':'B'}
        defender={'_id':did,'tg_id':2,'active':True,'engagement_campaign_id':str(rid),'target_castle':'B'}
        store=Collection([root,attacker,defender]);dismiss=AsyncMock()
        with patch.object(admin,'campaigns',store),patch.object(war,'campaigns',store),patch.object(war,'players_are_friendly',AsyncMock(return_value=False)),patch.object(admin,'owner_of_castle',AsyncMock(return_value={'tg_id':2})),patch.object(admin,'_dismiss_battle_record',dismiss):
            result=await admin._remove_campaign_from_battle(defender,'انتقال')
        self.assertTrue(result['battle_closed']);self.assertTrue(dismiss.call_args.kwargs['stay'])
    async def test_last_allied_defender_exit_also_closes_empty_defending_side(self):
        rid,aid,did=ObjectId(),ObjectId(),ObjectId()
        root={'_id':rid,'tg_id':1,'active':False,'battle_is_root':True,'battle_open':True,'engagement_campaign_id':str(rid),'battle_location':'B','battle_defender_tg_id':2,'battle_attacker_army_ids':[str(aid)],'battle_defender_army_ids':[str(did)]}
        attacker={'_id':aid,'tg_id':1,'active':True,'engagement_campaign_id':str(rid),'target_castle':'B'}
        defender={'_id':did,'tg_id':3,'active':True,'engagement_campaign_id':str(rid),'target_castle':'B'}
        store=Collection([root,attacker,defender]);dismiss=AsyncMock()
        with patch.object(admin,'campaigns',store),patch.object(war,'campaigns',store),patch.object(war,'players_are_friendly',AsyncMock(return_value=False)),patch.object(admin,'owner_of_castle',AsyncMock(return_value={'tg_id':2})),patch.object(admin,'_dismiss_battle_record',dismiss):
            result=await admin._remove_campaign_from_battle(defender,'انتقال')
        self.assertTrue(result['battle_closed']);self.assertTrue(dismiss.call_args.kwargs['stay'])

class Scheduling(unittest.IsolatedAsyncioTestCase):
    def test_local_slot_is_converted_to_game_utc(self):
        current=datetime(2026,10,16,12)
        self.assertEqual(ds.next_slot(current,'18:00'),datetime(2026,10,16,14,30))
        self.assertEqual(ds.next_slot(current,'10:00'),datetime(2026,10,17,6,30))
    async def test_paused_clock_never_executes(self):
        callback=AsyncMock()
        with patch.object(ds.game_clock,'paused',return_value=True):await ds.run('food',callback)
        callback.assert_not_awaited()
    async def test_daily_slot_runs_only_when_due(self):
        at=datetime(2026,10,16,12);store=SimpleNamespace(find_one=AsyncMock(return_value={'enabled':True,'next_at':at+timedelta(minutes=1),'clock':'18:00'}),update_one=AsyncMock());callback=AsyncMock()
        with patch.object(ds,'db',SimpleNamespace(daily_schedules=store)),patch.object(ds.game_clock,'paused',return_value=False),patch.object(ds.game_clock,'now',return_value=at):
            await ds.run('food',callback);callback.assert_not_awaited()
            store.find_one.return_value['next_at']=at-timedelta(days=3)
            await ds.run('food',callback)
        callback.assert_awaited_once();self.assertGreater(store.update_one.call_args.args[1]['$set']['next_at'],at)
    async def test_failed_processing_does_not_advance_next_slot(self):
        at=datetime(2026,10,16,12);store=SimpleNamespace(find_one=AsyncMock(return_value={'enabled':True,'next_at':at,'clock':'18:00'}),update_one=AsyncMock())
        with patch.object(ds,'db',SimpleNamespace(daily_schedules=store)),patch.object(ds.game_clock,'paused',return_value=False),patch.object(ds.game_clock,'now',return_value=at):
            with self.assertRaises(RuntimeError):await ds.run('food',AsyncMock(side_effect=RuntimeError('retry')))
        store.update_one.assert_not_awaited()

class ProfileFlags(unittest.IsolatedAsyncioTestCase):
    def flag(self):
        raw=io.BytesIO();Image.new('RGB',(16,16),'gold').save(raw,format='PNG');return 'data:image/png;base64,'+base64.b64encode(raw.getvalue()).decode()
    async def test_flag_is_returned_and_editable(self):
        flag=self.flag();store=SimpleNamespace(find_one=AsyncMock(return_value={'name':'Lord','flag_image':flag}),update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        with patch.object(admin,'players',store):
            self.assertEqual((await admin.admin_get_player_profile(1,{}))['flag_image'],flag)
            await admin.admin_edit_player_profile(1,admin.EditPlayerProfileBody(name='Lord',backstory='x'*45,flag_image=flag),{'id':9})
        change=store.update_one.call_args.args[1]['$set'];self.assertEqual(change['flag_image'],flag);self.assertTrue(change['flag_map_image'].startswith('data:image/webp'))
    async def test_omitted_flag_is_preserved_and_invalid_file_is_rejected(self):
        store=SimpleNamespace(find_one=AsyncMock(return_value={}),update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        with patch.object(admin,'players',store):
            await admin.admin_edit_player_profile(1,admin.EditPlayerProfileBody(name='Lord',backstory='x'*45),{'id':9})
            self.assertNotIn('flag_image',store.update_one.call_args.args[1]['$set'])
            store.update_one.reset_mock()
            with self.assertRaises(HTTPException):await admin.admin_edit_player_profile(1,admin.EditPlayerProfileBody(name='Lord',backstory='x'*45,flag_image='bad'),{'id':9})
            store.update_one.assert_not_awaited()
