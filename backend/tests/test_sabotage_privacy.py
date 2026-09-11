import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from bson import ObjectId
from routers import admin as a

class SabotagePrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_outcome_and_cancellation_stay_private_even_with_public_request(self):
        for result in ['Cancelled at author request', 'Sabotage resolved']:
            role={'_id':ObjectId(),'tg_id':1,'player_name':'Author','category':'sabotage','target_tg_id':2,'target_player_name':'Target','admin_score':50}
            roles=MagicMock();roles.find_one=AsyncMock(return_value=role);roles.update_many=AsyncMock()
            players=MagicMock();players.find_one=AsyncMock(side_effect=lambda q,*args:{'tg_id':q['tg_id'],'name':str(q['tg_id'])})
            adjustments=AsyncMock(side_effect=lambda uid,res,pop:{'tg_id':uid,'resources':res,'popularity':pop})
            send=AsyncMock();public=AsyncMock(return_value=[{'tg_id':1},{'tg_id':2},{'tg_id':3}])
            with patch.object(a,'roleplays',roles),patch.object(a,'players',players),patch.object(a,'send_system_message',send),patch.object(a,'public_recipients',public),patch.object(a,'_apply_roleplay_player_adjustments',adjustments):
                body=a.RoleplayResultBody(result=result,visibility='all',other_lords=[2,3],target_resource_deltas={'gold':-10})
                response=await a.respond_roleplay(str(role['_id']),body,{'id':99})
                self.assertEqual(response['sent_to'],1)
                self.assertEqual([c.args[0] for c in send.await_args_list],[1])
                public.assert_not_awaited()
                self.assertTrue(any(c.args[0]==2 and c.args[1]=={'gold':-10} for c in adjustments.await_args_list))
