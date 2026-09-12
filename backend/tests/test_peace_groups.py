import os
import unittest
from unittest.mock import patch, AsyncMock
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from peace_pacts import peace_partners
from routers import war

class PeaceTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  assert 'valyria-project-test-db:27017' in os.environ['MONGODB_URI']
  self.client=AsyncIOMotorClient(os.environ['MONGODB_URI']);self.rows=self.client.peace_test.alliances
  await self.rows.delete_many({})
 async def asyncTearDown(self):self.client.close()
 async def edge(self,a,b,g,status='accepted',kind='full_alliance'):
  await self.rows.insert_one({'from_id':a,'to_id':b,'group_id':g,'status':status,'type':kind})
 async def test_members_blocked_pending_other_groups_and_trade_excluded(self):
  await self.edge(1,2,'g');await self.edge(1,3,'g');await self.edge(1,4,'g','pending')
  await self.edge(1,5,'other');await self.edge(2,6,'trade',kind='trade')
  self.assertEqual(set(await peace_partners(self.rows,2)),{1,3})
  with patch.object(war,'alliances',self.rows),patch.object(war,'owner_of_castle',AsyncMock(return_value={'tg_id':3})):
   for op in ('attack','siege','naval_raid'):
    with self.assertRaises(HTTPException):await war.reject_hostile_order_during_pact(2,'target',op)
   await war.reject_hostile_order_during_pact(2,'target','garrison')
 async def test_non_aggression_exit_removes_protection(self):
  await self.edge(1,2,'g',kind='non_aggression');await self.edge(1,3,'g',kind='non_aggression')
  self.assertIn(3,await peace_partners(self.rows,2))
  await self.rows.update_one({'to_id':3},{'$set':{'status':'left'}})
  self.assertNotIn(3,await peace_partners(self.rows,2))
