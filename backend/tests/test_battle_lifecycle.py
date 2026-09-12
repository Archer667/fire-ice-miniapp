import unittest
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,patch
from bson import ObjectId
from routers import war,admin
class Cursor:
 def __init__(self,rows):self.rows=rows
 def __aiter__(self):self.it=iter(self.rows);return self
 async def __anext__(self):
  try:return next(self.it)
  except StopIteration:raise StopAsyncIteration
 async def to_list(self,n):return self.rows
class DB:
 def __init__(self,rows):self.rows=rows
 def match(self,row,q):
  for k,v in q.items():
   if k=='$or':
    if not any(self.match(row,x) for x in v):return False
   elif isinstance(v,dict):
    for op,val in v.items():
     x=row.get(k)
     if op=='$exists' and (k in row)!=val:return False
     if op=='$ne' and x==val:return False
     if op=='$in' and x not in val:return False
     if op=='$lte' and (x is None or x>val):return False
   elif row.get(k)!=v:return False
  return True
 def find(self,q,*args):return Cursor([r for r in self.rows if self.match(r,q)])
 async def find_one(self,q):return next((r for r in self.rows if self.match(r,q)),None)
 async def update_one(self,q,u):return await self.update_many(q,u)
 async def update_many(self,q,u):
  for r in self.rows:
   if self.match(r,q):
    r.update(u.get('$set',{}))
    for k in u.get('$unset',{}):r.pop(k,None)
class LifecycleTests(unittest.IsolatedAsyncioTestCase):
 async def test_closed_root_releases_member_and_waiting_fallback(self):
  at=datetime(2026,9,12);rid=ObjectId();aid=ObjectId()
  root={'_id':rid,'battle_open':False,'combat_resolved_at':at}
  army={'_id':aid,'active':True,'op_type':'attack','arrival_at':at-timedelta(days=1),'engagement_locked':True,'battle_root_campaign_id':str(rid)}
  db=DB([root,army])
  with patch.object(war,'campaigns',db),patch.object(war,'now',return_value=at):
   fixed=await war.repair_stale_engagement_lock(army)
   self.assertFalse(fixed['engagement_locked']);self.assertFalse(war.campaign_waiting_for_result(fixed))
 async def test_closure_releases_all_members(self):
  for cancelled in (True,False):
   rid=ObjectId();aid=ObjectId();bid=ObjectId();root={'_id':rid,'battle_attacker_army_ids':[str(aid)],'battle_defender_army_ids':[str(bid)]}
   rows=[root,{'_id':aid,'engagement_locked':True},{'_id':bid,'engagement_locked':True}];db=DB(rows)
   with patch.object(admin,'campaigns',db):await admin._close_battle_state(root,str(rid),cancelled=cancelled)
   self.assertTrue(all(not r['engagement_locked'] and not r['battle_open'] for r in rows))
 async def test_peaceful_unfiled_attack_released(self):
  row={'_id':ObjectId(),'tg_id':1,'active':True,'op_type':'attack','target_castle':'T','arrival_at':datetime(2020,1,1)};db=DB([row])
  with patch.object(war,'campaigns',db),patch.object(war,'owner_of_castle',AsyncMock(return_value={'tg_id':2})),patch.object(war,'players_are_friendly',AsyncMock(return_value=True)):
   await war.reconcile_battle_locks()
  self.assertIn('battle_cancelled_at',row)
 async def test_partial_pact_does_not_close_group_battle(self):
  rid=ObjectId();aid=ObjectId();did=ObjectId()
  root={'_id':rid,'tg_id':1,'active':True,'battle_open':True,'battle_is_root':True,'battle_attacker_army_ids':[str(rid),str(aid)],'battle_defender_army_ids':[str(did)],'battle_defender_tg_id':3}
  rows=[root,{'_id':aid,'tg_id':2,'active':True},{'_id':did,'tg_id':3,'active':True}];db=DB(rows)
  async def friendly(a,b):return a==1
  with patch.object(war,'campaigns',db),patch.object(war,'players_are_friendly',AsyncMock(side_effect=friendly)),patch.object(admin,'_dismiss_battle_record',AsyncMock()) as close:
   await war.reconcile_battle_locks();close.assert_not_awaited()

 async def test_full_peace_closes_group_once(self):
  rid=ObjectId();did=ObjectId()
  root={'_id':rid,'tg_id':1,'active':True,'battle_open':True,'battle_attacker_army_ids':[str(rid)],'battle_defender_army_ids':[str(did)],'battle_defender_tg_id':2}
  db=DB([root,{'_id':did,'tg_id':2,'active':True}])
  with patch.object(war,'campaigns',db),patch.object(war,'players_are_friendly',AsyncMock(return_value=True)),patch.object(admin,'_dismiss_battle_record',AsyncMock()) as close:
   await war.reconcile_battle_locks();close.assert_awaited_once()
