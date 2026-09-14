import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from routers import rebellions as r, ravens

class RebellionBroadcastTests(unittest.IsolatedAsyncioTestCase):
 async def test_resolve_broadcasts_public_result_only(self):
  row={'_id':ObjectId(),'tg_id':1,'castle':'ریورران','player_name':'تالی'}
  people=MagicMock();people.find_one=AsyncMock(return_value={'tg_id':1,'name':'تالی','gender':'lady','popularity':35,'resources':{'gold':100}});people.update_one=AsyncMock()
  records=MagicMock();records.find_one=AsyncMock(return_value=row);records.update_one=AsyncMock()
  audience=AsyncMock(return_value=[{'tg_id':1,'name':'تالی'},{'tg_id':2,'name':'بازیکن'},{'tg_id':99,'name':'ادمین'}]);send=AsyncMock()
  with patch.object(r,'players',people),patch.object(r,'rebellions',records),patch.object(r,'public_recipients',audience),patch.object(r,'send_system_message',send):
   await r.resolve(str(row['_id']),r.ResolveBody(result='مردم آرام شدند.',outcome='negotiated',gold_delta=-10),{'id':99})
  self.assertEqual([c.args[0] for c in send.await_args_list],[1,2,99])
  for c in send.await_args_list:
   self.assertIn('ریورران',c.args[2]);self.assertIn('لیدی تالی',c.args[2]);self.assertIn('شورش با مذاکره پایان یافت',c.args[2]);self.assertNotIn('gold',c.args[2]);self.assertEqual(c.kwargs['kind'],'rebellion_result')
 async def test_result_always_uses_raven_and_bot(self):
  messages=MagicMock();messages.insert_one=AsyncMock();push=MagicMock()
  with patch.object(ravens,'notification_route',return_value={'raven':False,'bot':False}),patch.object(ravens,'normalize_player_names',AsyncMock(side_effect=lambda s:s)),patch.object(ravens,'messages',messages),patch.object(ravens.telegram_bot,'push',push):
   await ravens.send_system_message(99,'ادمین','نتیجه شورش',kind='rebellion_result')
  messages.insert_one.assert_awaited_once();push.assert_called_once()
  self.assertIn('نتیجه شورش',push.call_args.args[1])
