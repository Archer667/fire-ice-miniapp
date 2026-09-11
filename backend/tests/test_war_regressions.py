"""Exercise real arrival/reconciliation functions against a deterministic in-memory DB."""
import copy
import types
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from test_castle_rules import load

def matches(row, query):
    for key, value in query.items():
        actual = row.get(key)
        if isinstance(value, dict):
            for op, target in value.items():
                if op == '$ne' and (actual == target or isinstance(actual, list) and target in actual): return False
                if op == '$exists' and (key in row) != target: return False
                if op == '$lte' and (actual is None or actual > target): return False
                if op == '$in' and actual not in target: return False
        elif actual != value: return False
    return True

class Cursor:
    def __init__(self, rows): self.rows = rows
    def __aiter__(self): self.it = iter(copy.deepcopy(self.rows)); return self
    async def __anext__(self):
        try: return next(self.it)
        except StopIteration: raise StopAsyncIteration
    def sort(self, key, direction): self.rows.sort(key=lambda x:x.get(key, datetime.min), reverse=direction<0); return self
    def limit(self, count): self.rows=self.rows[:count]; return self
    async def to_list(self, count): return copy.deepcopy(self.rows if count is None else self.rows[:count])

class Collection:
    def __init__(self, rows): self.rows=copy.deepcopy(rows)
    def find(self, query, *args): return Cursor([r for r in self.rows if matches(r, query)])
    async def find_one(self, query): return next((copy.deepcopy(r) for r in self.rows if matches(r, query)), None)
    async def update_one(self, query, update, upsert=False):
        for row in self.rows:
            if not matches(row, query): continue
            row.update(copy.deepcopy(update.get('$set', {})))
            for k,v in update.get('$push', {}).items(): row.setdefault(k, []).append(copy.deepcopy(v))
            for k,v in update.get('$addToSet', {}).items():
                if v not in row.setdefault(k, []): row[k].append(v)
            return types.SimpleNamespace(modified_count=1, matched_count=1)
        return types.SimpleNamespace(modified_count=0, matched_count=0)
    async def update_many(self, query, update):
        ids = [r['_id'] for r in self.rows if matches(r, query)]
        for oid in ids: await self.update_one({'_id':oid}, update)

class WarRegressions(unittest.IsolatedAsyncioTestCase):
    def setup_battle(self):
        clock=datetime(2026,9,10)
        def army(oid, owner, op, notified):
            return {'_id':oid,'tg_id':owner,'player_name':str(owner),'name':oid,'active':True,
                'op_type':op,'origin_castle':'home' if owner==1 else 'target','target_castle':'target',
                'arrival_at':clock-timedelta(minutes=1),'arrival_notified':notified,
                'troops':{'infantry':100},'men_committed':100,'equipment':{},'power':400}
        rows=[army('a',1,'attack',False),army('d',2,'defense',True),army('g',2,'garrison',True)]
        db=Collection(rows)
        ns={'campaigns':db, 'now':lambda:clock, 'ObjectId':lambda:'battle',
            'process_route_ambushes':AsyncMock(), 'detect_route_encounters':AsyncMock(),
            'repair_open_battle_rosters':AsyncMock(), 'owner_of_castle':AsyncMock(return_value={'tg_id':2,'name':'Defender'}),
            'players_are_friendly':AsyncMock(side_effect=lambda a,b:a==b),
            'send_system_message':AsyncMock(), 'notify_battle_admins':AsyncMock(),
            'OP_TYPES':{}, 'DIRECT_ATTACK_OP_TYPES':{'attack'}, 'DEFENSE_OP_TYPES':{'defense','garrison'},
            'defensive_infrastructure':lambda *a:[], 'infrastructure_summary':lambda x:'none',
            'roleplay_window_hours':lambda:6, 'campaign_power':lambda *a:400, '_building_levels':lambda *a:{}}
        load('routers/war.py', {'notify_arrivals','battle_army_snapshot'}, ns)
        return ns,db

    async def test_first_opponent_does_not_hide_second_defending_army(self):
        ns,db=self.setup_battle()
        await ns['notify_arrivals']()
        root=await db.find_one({'_id':'a'})
        self.assertEqual(set(root['battle_defender_army_ids']), {'d','g'})
        self.assertEqual(len(root['battle_defender_snapshot']),2)
        for oid in ('d','g'):
            row=await db.find_one({'_id':oid})
            self.assertTrue(row['engagement_locked'])
            self.assertEqual(row['battle_location'],'target')
        notices=[call.args[2] for call in ns['send_system_message'].await_args_list]
        self.assertTrue(any('200 نفر' in text for text in notices))

    async def test_repair_missing_locked_defender_is_idempotent(self):
        ns,db=self.setup_battle()
        await ns['notify_arrivals']()
        root=db.rows[0]
        root['battle_defender_army_ids'].remove('g')
        root['battle_defender_snapshot']=[a for a in root['battle_defender_snapshot'] if a['campaign_id']!='g']
        ns['queue_battle_roster']=AsyncMock()
        load('routers/war.py', {'repair_open_battle_rosters'}, ns)
        await ns['repair_open_battle_rosters']()
        await ns['repair_open_battle_rosters']()
        self.assertEqual(root['battle_defender_army_ids'].count('g'),1)
        ns['queue_battle_roster'].assert_awaited_once()

    def test_displayed_weapon_balance_can_be_spent_without_negative_balance(self):
        ns={};load('game.py',{'can_afford','pay'},ns)
        resources={'weapon_spear':52.8, 'men':100.8}
        cost={'weapon_spear':53, 'men':101}
        self.assertTrue(ns['can_afford'](resources,cost))
        ns['pay'](resources,cost)
        self.assertEqual(resources,{'weapon_spear':0,'men':0})
        self.assertFalse(ns['can_afford']({'weapon_spear':52.4},{'weapon_spear':53}))

if __name__=='__main__': unittest.main()
