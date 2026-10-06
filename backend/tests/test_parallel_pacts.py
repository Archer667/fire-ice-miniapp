import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from routers import diplomacy as d

class ParallelPactTests(unittest.IsolatedAsyncioTestCase):
    async def test_spouses_can_accept_independent_full_group(self):
        invitation={'_id':'invite','from_id':1,'to_id':2,'from_name':'A','to_name':'B','type':'full_alliance','status':'pending','public':False,'group_id':'group','invited_via':'source'}
        alliances=SimpleNamespace(find_one=AsyncMock(side_effect=[invitation,{'status':'accepted'}]),update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        players=SimpleNamespace(find_one=AsyncMock(return_value={'tg_id':1,'castle':'Castle'}),find=MagicMock(return_value=SimpleNamespace(to_list=AsyncMock(return_value=[]))),update_one=AsyncMock())
        with patch('marriage_pacts.spouses',AsyncMock(return_value=True)),patch.object(d,'alliances',alliances),patch.object(d,'players',players),patch.object(d,'send_system_message',AsyncMock()),patch.object(d,'ObjectId',side_effect=lambda x:x),patch.object(d,'titled_name',side_effect=lambda p,**kw:kw['name']):
            result=await d.respond('invite',d.RespondBody(accept=True),{'id':2})
        self.assertTrue(result['ok'])
        self.assertEqual(alliances.update_one.call_args.args[1]['$set']['status'],'accepted')

    async def test_new_contract_does_not_check_unrelated_pair_contracts(self):
        for kind in ('trade','non_aggression','full_alliance'):
            with self.subTest(kind=kind),ExitStack() as stack:
                p={'tg_id':1,'name':'A','castle':'Castle','resources':{'wine':10000}}
                targets=[{'tg_id':2,'name':'B'}]
                players=SimpleNamespace(find_one=AsyncMock(return_value=p),find=MagicMock(return_value=SimpleNamespace(to_list=AsyncMock(return_value=targets))),update_one=AsyncMock())
                alliances=SimpleNamespace(find_one=AsyncMock(return_value={'status':'accepted','marriage_id':'marriage'}),insert_many=AsyncMock())
                for name,value in [('players',players),('alliances',alliances),('send_system_message',AsyncMock()),('apply_production',lambda p:p),('production_fields',lambda p:{}),('rule',lambda k,v:v),('can_afford',lambda r,c:True),('pay',lambda r,c:None),('titled_name',lambda p:p['name'])]:stack.enter_context(patch.object(d,name,value))
                result=await d.propose(d.ProposeBody(to_tg_ids=[2],type=kind,penalty_gold=100),{'id':1})
                self.assertEqual(result['sent_to'],1)
                alliances.find_one.assert_not_awaited()
                self.assertEqual(alliances.insert_many.call_args.args[0][0]['status'],'pending')

if __name__=='__main__':unittest.main()

