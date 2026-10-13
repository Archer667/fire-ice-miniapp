import unittest
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from bson import ObjectId
import encounter_runtime as engine
from tests.test_battle_lifecycle import DB

class Memory(DB):
    async def update_many(self,q,update):
        for row in self.rows:
            if not self.match(row,q):continue
            row.update(update.get('$set',{}))
            for k in update.get('$unset',{}):row.pop(k,None)
            for k,v in update.get('$push',{}).items():row.setdefault(k,[]).append(v)
            for k,v in update.get('$addToSet',{}).items():
                if v not in row.setdefault(k,[]):row[k].append(v)

class CastleRegistryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.at=datetime(2026,10,12)
        self.root={'_id':ObjectId(),'tg_id':1,'battle_is_root':True,'battle_open':True,'battle_location':'روکزرست','engagement_campaign_id':'existing','battle_started_at':self.at,'battle_participant_tg_ids':[1,2]}
        self.first={'_id':ObjectId(),'tg_id':3,'player_name':'Third','active':True,'target_castle':'روکزرست','troops':{'infantry':10}}
        self.second={'_id':ObjectId(),'tg_id':4,'player_name':'Fourth','active':True,'target_castle':'روکزرست','troops':{'infantry':20}}
        self.db=Memory([self.root,self.first,self.second]);self.w=SimpleNamespace(campaigns=self.db,choose_battle_side=AsyncMock(return_value='independent'),battle_army_snapshot=lambda a:{'campaign_id':str(a['_id']),'tg_id':a['tg_id'],'troops':a['troops']})
        self.enterContext(patch.object(engine,'announce',new=AsyncMock()))
    async def test_unlocked_pair_joins_existing_case_instead_of_starting_second(self):
        await engine.start(self.w,self.first,self.second,{'kind':'castle','castle':'روکزرست'},self.at+timedelta(minutes=5))
        self.assertEqual(sum(r.get('battle_open',False) for r in self.db.rows),1)
        for army in (self.first,self.second):
            self.assertEqual(army['engagement_campaign_id'],'existing');self.assertFalse(army['battle_is_root']);self.assertTrue(army['engagement_locked'])
        self.assertEqual(set(self.root['battle_attacker_army_ids']),{str(self.first['_id']),str(self.second['_id'])})
        self.assertEqual(self.first['troops']['infantry'],10);self.assertEqual(self.second['troops']['infantry'],20)
    async def test_pair_neutral_to_old_parties_still_retains_its_own_hostility_in_one_case(self):
        self.w.choose_battle_side.return_value=None
        await engine.start(self.w,self.first,self.second,{'kind':'castle','castle':'روکزرست'},self.at)
        self.assertEqual([j['side'] for j in self.root['battle_joins']],['independent','independent'])
    async def test_replaying_join_does_not_duplicate_roster(self):
        point={'kind':'castle','castle':'روکزرست'}
        await engine.join(self.w,self.root,self.first,point,self.at);await engine.join(self.w,self.root,self.first,point,self.at)
        self.assertEqual(len(self.root['battle_attacker_army_ids']),1)
    async def test_closed_case_and_road_contact_are_not_reused(self):
        self.root['combat_resolved_at']=self.at
        self.assertIsNone(await engine.open_castle_battle(self.w,'روکزرست'))
        self.root.pop('combat_resolved_at');self.root['battle_contact']={'kind':'edge','a':'روکزرست','b':'Other','position':.5}
        self.assertIsNone(await engine.open_castle_battle(self.w,'روکزرست'))
    async def test_legacy_root_with_target_only_is_reused(self):
        self.root.pop('battle_is_root');self.root.pop('battle_location');self.root['target_castle']='روکزرست'
        self.assertEqual((await engine.open_castle_battle(self.w,'روکزرست'))['_id'],self.root['_id'])
    async def test_oldest_root_selected_deterministically_when_duplicates_already_exist(self):
        other={**self.root,'_id':ObjectId(),'battle_started_at':self.at-timedelta(hours=1)};self.db.rows.append(other)
        self.assertEqual((await engine.open_castle_battle(self.w,'روکزرست'))['_id'],other['_id'])

if __name__=='__main__':unittest.main()
