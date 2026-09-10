"""Contract tests of real rule functions; external DB dependencies are mocked."""
import ast
import copy
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
class Rejected(Exception):
    def __init__(self, status, message): self.status = status

def load(path, names, ns):
    nodes = [n for n in ast.parse((ROOT/path).read_text(encoding='utf-8')).body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert len(nodes) == len(names)
    for node in nodes: node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), ns)
    return ns

class CastleRules(unittest.IsolatedAsyncioTestCase):
    def test_senior_lord_and_lady_display(self):
        ns={'RANK_LABEL_FA':{'warden':'والی','king':'پادشاه/ملکه'}}
        f=load('routers/leaderboard.py', {'display_rank'}, ns)['display_rank']
        self.assertEqual(f('overlord',{'gender':'lady'}),'لیدی ارشد')
        self.assertEqual(f('overlord',{'gender':'lord'}),'لرد ارشد')
        self.assertEqual(f('overlord',{}),'لرد ارشد')
        self.assertEqual(f('warden',{'gender':'lady'}),'والی')
        self.assertIsNone(f(None,{}))

    def test_harbor_preserves_upgrades_and_other_buildings(self):
        ns={'deepcopy': copy.deepcopy}
        load('game.py', {'normalize_building_state'}, ns)
        load('castle_defaults.py', {'harbor_default'}, ns)
        f=ns['harbor_default']
        self.assertEqual(f({})['port']['level'], 1)
        old={'port': {'level': 4, 'upgrade_to': 5, 'ready_at': 'later'}, 'wall': {'level': 3}}
        self.assertEqual(f(old), old)
        pending=f({'port': {'level':0, 'upgrade_to':1, 'ready_at':'later'}})
        self.assertEqual(pending['port']['level'],1)
        self.assertIsNone(pending['port']['ready_at'])
        self.assertEqual(f(f({})), f({}))

    def test_loot_conserves_resources_and_rejects_before_mutation(self):
        ns={'HTTPException':Rejected,'effective_caps':lambda p:{'gold':100, 'weapon_sword':100}, 'production_fields':lambda p: {'resources':p['resources']}}
        f=load('naval_loot.py', {'loot_changes'},ns)['loot_changes']
        a={'tg_id':1,'resources':{'gold':70,'weapon_sword':20}}
        b={'tg_id':2,'resources':{'gold':10,'weapon_sword':5}}
        for invalid in ({'gold':5,'weapon_sword':21}, {'gold':-1}, {'men':1}, {'gold':True}, {'gold':1.2}, {}):
            before=copy.deepcopy((a,b))
            with self.assertRaises(Rejected): f(a,b,invalid,{'gold','weapon_sword'})
            self.assertEqual((a,b),before)
        changes=f(a,b,{'gold':30,'weapon_sword':4},{'gold','weapon_sword'})
        self.assertEqual(a['resources']['gold']+b['resources']['gold'],80)
        self.assertEqual(b['resources'],{'gold':40,'weapon_sword':9})
        self.assertEqual(len(changes),2)
        b['resources']['gold']=99
        with self.assertRaises(Rejected): f(a,b,{'gold':2},{'gold'})

    async def test_any_active_player_can_hold_high_office_and_revoke(self):
        hierarchy=types.SimpleNamespace(update_one=AsyncMock())
        players=types.SimpleNamespace(find_one=AsyncMock(return_value={'tg_id':7, 'castle':'X'}))
        h={'king':7, 'warden_north':None,'warden_south':None,'overlords':{'north':7}}
        ns={'Depends':lambda x:None,'admin_user':None,'WardenBody':object,'KingBody':object,'HTTPException':Rejected,
            'WARDEN_GROUPS':{'north':{},'south':{}},'players':players,'hierarchy':hierarchy,
            'get_hierarchy_doc':AsyncMock(return_value=h),'HIERARCHY_ID':'main'}
        load('routers/titles.py',{'set_warden','set_king'},ns)
        await ns['set_warden'](types.SimpleNamespace(group='south',tg_id=7))
        change=hierarchy.update_one.call_args.args[1]['$set']
        self.assertEqual(change,{'warden_south':7,'king':None,'overlords.north':None})
        await ns['set_king'](types.SimpleNamespace(tg_id=99))
        self.assertEqual(hierarchy.update_one.call_args.args[1]['$set']['king'],99)
        await ns['set_king'](types.SimpleNamespace(tg_id=None))
        self.assertIsNone(hierarchy.update_one.call_args.args[1]['$set']['king'])
        await ns['set_warden'](types.SimpleNamespace(group='north',tg_id=None))
        self.assertIsNone(hierarchy.update_one.call_args.args[1]['$set']['warden_north'])
        players.find_one.return_value=None
        with self.assertRaises(Rejected): await ns['set_king'](types.SimpleNamespace(tg_id=999))

    async def test_recruitment_open_battle_or_arrived_attack_blocks(self):
        find=AsyncMock()
        ns={'campaigns':types.SimpleNamespace(find_one=find),'owned_castles':lambda p:['home','second'],
            'now':lambda:100,'ATTACK_OP_TYPES':{'attack','siege','naval_raid'},'HTTPException':Rejected}
        f=load('routers/war.py', {'ensure_recruitment_allowed'},ns)['ensure_recruitment_allowed']
        for rows in (({},None),(None,{})):
            find.side_effect=[{'_id':'battle'} if x == {} else None for x in rows]
            with self.assertRaises(Rejected): await f({'tg_id':1})
        find.side_effect=[None,None]
        await f({'tg_id':1})
        query=find.call_args.args[0]
        self.assertEqual(query['target_castle']['$in'],['home','second'])
        self.assertEqual(query['arrival_at'],{'$lte':100})

if __name__ == '__main__': unittest.main()
