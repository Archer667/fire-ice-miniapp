"""Dependency-free tests of display helpers; no production DB or bot access.

Load the real helper ASTs so this suite can also run during a network outage.
External persistence and castle lookups are replaced with controlled fixtures.
"""
import ast
import copy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]

def functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)

class DisplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_current_and_field_defenses(self):
        owner = {'castle': 'Home', 'buildings': {'wall': 8}, 'castle_buildings': {'Target': {'wall': 2, 'watchtower': 3}}}
        war = types.ModuleType('routers.war')
        namespace = {'BUILDINGS': {'wall': {'name': 'Wall', 'type': 'defense'}, 'watchtower': {'name': 'Tower', 'type': 'defense'}},
                     '_building_levels': lambda p,c: p['buildings'] if c == p['castle'] else p['castle_buildings'].get(c,{})}
        functions('routers/war.py', {'defensive_infrastructure'}, namespace)
        war.defensive_infrastructure = namespace['defensive_infrastructure']
        lookup = AsyncMock(return_value=owner)
        ns = {'owner_of_castle': lookup}
        functions('routers/admin.py', {'_admin_castle_defenses'}, ns)
        with patch.dict(sys.modules, {'routers.war': war}):
            current = await ns['_admin_castle_defenses']({'target_castle':'Target'})
            self.assertEqual([x['level'] for x in current['defense_infrastructure']], [2,3])
            self.assertEqual(current['defense_infrastructure_source'], 'current')
            old = await ns['_admin_castle_defenses']({'target_castle':'Target','battle_defense_infrastructure':[]})
            self.assertEqual(old['defense_infrastructure'], [])
            self.assertEqual(len(old['defense_infrastructure_current']), 2)
            self.assertEqual(old['defense_infrastructure_source'], 'snapshot')
            lookup.reset_mock()
            road = await ns['_admin_castle_defenses']({'target_castle':'Target','battle_location':'مسیر A — B'})
            self.assertEqual(road['defense_infrastructure_source'], 'field');lookup.assert_not_awaited()

    async def test_power_retained_and_missing_is_not_zero(self):
        class Identity(str):
            @staticmethod
            def is_valid(value): return len(value) == 24
        collection = types.SimpleNamespace(find_one=AsyncMock(return_value={'troops':{'infantry':100}, 'power':700}))
        import importlib.util
        spec = importlib.util.spec_from_file_location('test_game_data', ROOT / 'game_data.py')
        data = importlib.util.module_from_spec(spec); spec.loader.exec_module(data)
        owner = {'castle': 'home', 'castle_buildings': {'origin': {}}, 'buildings': {}}
        ns = {'campaigns':collection, 'ObjectId':Identity, 'SIEGE_EQUIPMENT':{'ram':{'siege_power':50}},
              'game_data':data, 'players':types.SimpleNamespace(find_one=AsyncMock(return_value=owner)),
              'building_levels_for':lambda p,c: {'barracks':2}, 'owned_castles':lambda p:['home','origin'],
              'control_settings':types.SimpleNamespace(get=lambda k,d:d)}
        functions('routers/admin.py', {'_admin_army_metrics'}, ns)
        f = ns['_admin_army_metrics']
        self.assertEqual((await f({'power':123,'troops':{},'equipment':{'ram':2}})), {'power':123,'equipment_power':100,'power_calculated':False})
        self.assertEqual((await f({'campaign_id':'a'*24,'troops':{'infantry':100}}))['power'],700)
        self.assertEqual((await f({'campaign_id':'a'*24,'troops':{'infantry':50}}))['power'], data.campaign_power({'infantry':50}, {}))
        self.assertEqual((await f({'troops':{}}))['power'],0)
        roster = {next(iter(data.COMMON_TROOPS)): 100, next(iter(data.NAVAL_TROOPS)): 2}
        army = {'tg_id':1, 'origin_castle':'origin', 'troops':roster, 'commander_present':True}
        result = await f(army)
        self.assertEqual(result['power'],round(data.campaign_power(roster, {'barracks':2})*1.1))
        self.assertTrue(result['power_calculated'])
        army['power_building_levels']={'port':3}
        army['commander_power_bonus_percent']=20
        self.assertEqual((await f(army))['power'], round(data.campaign_power(roster, {'port':3})*1.2))
        ns = {};functions('routers/war.py', {'battle_army_snapshot'}, ns)
        self.assertEqual(ns['battle_army_snapshot']({'power':321,'men_committed':100,'troops':{'infantry':100}})['power'],321)

    async def test_wine_migration_preserves_other_settings_and_later_edits(self):
        class Settings:
            def __init__(self): self.doc = {'_id':'control_center_v1','settings':{'economy':{'starting_resources':{'gold':777,'wine':30}}}}
            async def find_one(self,q): return copy.deepcopy(self.doc)
            async def update_one(self,q,update,upsert=False):
                if self.doc and q.get('initial_wine_60_applied') and self.doc.get('initial_wine_60_applied'): return
                if not self.doc:
                    if not upsert:return
                    self.doc={'_id':q['_id'],**update.get('$setOnInsert',{})}
                for key,value in update.get('$set',{}).items():
                    cursor=self.doc;parts=key.split('.')
                    for part in parts[:-1]:cursor=cursor.setdefault(part,{})
                    cursor[parts[-1]]=value
        settings=Settings();db=types.ModuleType('db');db.game_settings=settings
        ns={'DOC_ID':'control_center_v1'};functions('control_settings.py',{'migrate_initial_wine_60'},ns)
        with patch.dict(sys.modules,{'db':db}):
            await ns['migrate_initial_wine_60']()
            self.assertEqual(settings.doc['settings']['economy']['starting_resources'],{'gold':777,'wine':60})
            settings.doc['settings']['economy']['starting_resources']['wine']=90
            await ns['migrate_initial_wine_60']()
            self.assertEqual(settings.doc['settings']['economy']['starting_resources']['wine'],90)
            settings.doc=None;await ns['migrate_initial_wine_60']()
            self.assertEqual(settings.doc['settings']['economy']['starting_resources']['wine'],60)

if __name__ == '__main__': unittest.main()
