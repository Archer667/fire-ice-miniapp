"""Loan lifecycle and crash recovery without touching a running database."""
import copy
import unittest
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError
import institution_bank as b

def get(row,key):
    for part in key.split('.'):
        if isinstance(row,list):
            try:row=row[int(part)]
            except (IndexError,ValueError):return None
        elif isinstance(row,dict):row=row.get(part)
        else:return None
    return row
def match(row,q):
    for k,v in q.items():
        if k=='$or':
            if not any(match(row,x) for x in v):return False
            continue
        a=get(row,k)
        if isinstance(v,dict):
            for op,x in v.items():
                if op=='$ne' and a==x:return False
                if op=='$gte' and (a is None or a<x):return False
                if op=='$in' and a not in x:return False
        elif a!=v:return False
    return True
def put(row,key,v):
    bits=key.split('.')
    for part in bits[:-1]:row=row[int(part)] if isinstance(row,list) else row.setdefault(part,{})
    if isinstance(row,list):row[int(bits[-1])]=copy.deepcopy(v)
    else:row[bits[-1]]=copy.deepcopy(v)
class Cursor:
    def __init__(self,rows):self.rows=copy.deepcopy(rows)
    def sort(self,*a):return self
    def skip(self,n):self.rows=self.rows[n:];return self
    def limit(self,n):self.rows=self.rows[:n];return self
    def __aiter__(self):self.it=iter(self.rows);return self
    async def __anext__(self):
        try:return next(self.it)
        except StopIteration:raise StopAsyncIteration
class Collection:
    def __init__(self,rows=()):self.rows=copy.deepcopy(list(rows))
    def find(self,q):return Cursor([r for r in self.rows if match(r,q)])
    async def find_one(self,q):return next((copy.deepcopy(r) for r in self.rows if match(r,q)),None)
    async def insert_one(self,r):self.rows.append(copy.deepcopy(r));return SimpleNamespace(inserted_id=r.get('_id'))
    async def count_documents(self,q):return sum(match(r,q) for r in self.rows)
    async def update_one(self,q,update,upsert=False):
        r=next((r for r in self.rows if match(r,q)),None);insert=False
        if r is None and upsert:r={k:v for k,v in q.items() if not isinstance(v,dict)};self.rows.append(r);insert=True
        if r is None:return SimpleNamespace(matched_count=0)
        for op,fields in update.items():
            if op=='$setOnInsert' and not insert:continue
            for key,v in fields.items():put(r,key,(get(r,key) or 0)+v if op=='$inc' else v)
        return SimpleNamespace(matched_count=1)

class BankTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.at=datetime(2026,10,10,12);self.clock=self.at
        self.people=Collection([{'tg_id':uid,'name':f'Player {uid}','created_at':self.at,'castle':'Castle','region':'north','resources':{'gold':1000}} for uid in (1,2,3,4)])
        self.treasury=Collection([{'_id':'iron-bank','gold':5000}]);self.loans=Collection();self.ops=Collection();self.messages=Collection();self.audit=Collection()
        self.cfg={**b.DEFAULTS,'enabled':True,'managers':[b.member(self.people.rows[0])]}
        self.enterContext(patch.object(b,'settings',new=AsyncMock(side_effect=lambda:copy.deepcopy(self.cfg))))
        for key,v in [('players',self.people),('bank',self.treasury),('loans',self.loans),('operations',self.ops),('messages',self.messages)]:self.enterContext(patch.object(b,key,v))
        self.enterContext(patch.object(b,'db',SimpleNamespace(institution_audit=self.audit)))
        self.enterContext(patch.object(b,'get_admin_role',new=AsyncMock(return_value=None)))
        self.enterContext(patch.object(b,'apply_production',side_effect=lambda p:p))
        self.enterContext(patch.object(b,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
        self.enterContext(patch.object(b,'now',side_effect=lambda:self.clock))
        self.enterContext(patch.object(b.game_clock,'now',side_effect=lambda:self.clock))
        self.enterContext(patch.object(b.game_clock,'real_now',side_effect=lambda:self.clock+timedelta(days=10)))
        self.enterContext(patch.object(b.game_clock,'paused',return_value=False))
    async def request(self,uid=2):return await b.request_loan(b.RequestLoan(request_id=str(uuid4()),amount=600,purpose='ساخت بندر تازه'),{'id':uid})
    async def offered(self):
        loan=await self.request();return await b.offer(loan['id'],b.Offer(principal=600,interest_percent=10,installment_count=3,interval_hours=24,guarantor_id=3),{'id':1})
    async def active(self):
        loan=await self.offered()
        for uid in (2,3):await b.accept(loan['id'],b.Acceptance(version=loan['version'],accepted=True),{'id':uid})
        return await self.loans.find_one({'_id':ObjectId(loan['id'])})
    async def balance(self,uid):return (await self.people.find_one({'tg_id':uid}))['resources']['gold']
    async def test_manager_cannot_borrow_and_unauthorized_cannot_offer(self):
        with self.assertRaises(HTTPException):await self.request(1)
        loan=await self.request()
        with self.assertRaises(HTTPException):await b.offer(loan['id'],b.Offer(principal=100,interest_percent=0,installment_count=1,interval_hours=24,guarantor_id=3),{'id':4})
        self.cfg['managers'].append(b.member(self.people.rows[1]))
        with self.assertRaises(HTTPException):await b.offer(loan['id'],b.Offer(principal=100,interest_percent=0,installment_count=1,interval_hours=24,guarantor_id=3),{'id':1})
    async def test_two_consents_and_exact_once_disbursement(self):
        l=await self.offered();v=b.Acceptance(version=l['version'],accepted=True)
        await b.accept(l['id'],v,{'id':2});self.assertEqual(await self.balance(2),1000)
        await b.accept(l['id'],v,{'id':3});await b.accept(l['id'],v,{'id':3});await b.recover()
        self.assertEqual(await self.balance(2),1600);self.assertEqual((await b.treasury())['gold'],4400)
    async def test_offer_change_invalidates_old_consents(self):
        l=await self.offered();await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':2})
        fresh=await b.offer(l['id'],b.Offer(principal=300,interest_percent=0,installment_count=3,interval_hours=24,guarantor_id=3),{'id':1})
        self.assertFalse(fresh['borrower_accepted'])
        with self.assertRaises(HTTPException):await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':3})
    async def test_self_guarantor_and_nonparticipant_rejected(self):
        l=await self.request()
        with self.assertRaises(HTTPException):await b.offer(l['id'],b.Offer(principal=100,interest_percent=0,installment_count=1,interval_hours=24,guarantor_id=2),{'id':1})
        l=await self.offered()
        with self.assertRaises(HTTPException):await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':4})
    async def test_insufficient_bank_never_credits_borrower(self):
        l=await self.offered();self.treasury.rows[0]['gold']=100
        await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':2})
        with self.assertRaises(HTTPException):await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':3})
        self.assertEqual(await self.balance(2),1000);self.assertEqual(len(self.ops.rows),0)
        self.treasury.rows[0]['gold']=1000
        await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':3})
        self.assertEqual(await self.balance(2),1600)
    async def test_restart_after_intent_before_state_and_after_bank_debit(self):
        l=await self.offered();await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':2})
        original=self.loans.update_one
        async def crash(q,u,**kw):
            if u.get('$set',{}).get('status')=='disbursing':raise RuntimeError('crash after journal')
            return await original(q,u,**kw)
        with patch.object(self.loans,'update_one',side_effect=crash):
            with self.assertRaises(RuntimeError):await b.accept(l['id'],b.Acceptance(version=l['version'],accepted=True),{'id':3})
        bank_once=b.bank_once
        async def debit_crash(*args):await bank_once(*args);raise RuntimeError('crash after debit')
        with patch.object(b,'bank_once',side_effect=debit_crash):
            with self.assertRaises(RuntimeError):await b.recover()
        await b.recover();await b.recover()
        self.assertEqual(await self.balance(2),1600);self.assertEqual((await b.treasury())['gold'],4400)
        self.assertEqual((await self.loans.find_one({'_id':ObjectId(l['id'])}))['status'],'active')
    async def test_manual_duplicate_never_pays_next_installment(self):
        l=await self.active();await b.pay_next(str(l['_id']),b.Payment(number=1),{'id':2})
        with self.assertRaises(HTTPException):await b.pay_next(str(l['_id']),b.Payment(number=1),{'id':2})
        self.assertEqual(await self.balance(2),1380);self.assertEqual((await b.treasury())['gold'],4620)
    async def test_repayment_recovery_after_player_debit(self):
        l=await self.active();original=b.player_once
        async def crash(*args):await original(*args);raise RuntimeError('crash after payer debit')
        with patch.object(b,'player_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await b.pay_installment(l,0,l['borrower'])
        await b.recover();await b.recover();await b.pay_installment(l,0,l['borrower'])
        self.assertEqual(await self.balance(2),1380);self.assertEqual((await b.treasury())['gold'],4620)
    async def test_guarantor_only_charged_after_grace_and_pause_stops_due_processing(self):
        l=await self.active();await self.people.update_one({'tg_id':2},{'$set':{'resources.gold':0}})
        self.clock+=timedelta(hours=24);await b.tick();self.assertEqual(await self.balance(3),1000)
        self.clock+=timedelta(hours=24)
        with patch.object(b.game_clock,'paused',return_value=True):await b.tick()
        self.assertEqual(await self.balance(3),1000)
        await b.tick();await b.tick();self.assertEqual(await self.balance(3),780)
        self.assertTrue((await self.loans.find_one({'_id':l['_id']}))['installments'][0]['paid'])
    async def test_reset_character_never_inherits_debt_or_credit(self):
        l=await self.active();await self.people.update_one({'tg_id':2},{'$set':{'created_at':self.at+timedelta(days=1)}})
        with self.assertRaises(HTTPException):await b.player_once(l['borrower'],-220,'reset-payment')
        with self.assertRaises(HTTPException):await b.player_once(l['borrower'],220,'reset-credit')
        self.assertEqual(await self.balance(2),1600)
    async def test_manager_replacement_retains_existing_contracts(self):
        l=await self.active();self.cfg['managers']=[b.member(self.people.rows[3])]
        with self.assertRaises(HTTPException):await b.manager({'id':1})
        await b.pay_installment(l,0,l['borrower']);self.assertEqual(await self.balance(2),1380)
    async def test_failed_treasury_debit_has_no_later_side_effect_and_uuid_payload_bound(self):
        key=str(uuid4())
        with self.assertRaises(HTTPException):await b.change_treasury(b.TreasuryChange(request_id=key,amount=-6000,reason='اصلاح خزانه'),{'id':999})
        self.assertEqual(len(self.ops.rows),0);self.treasury.rows[0]['gold']=10000;await b.recover();self.assertEqual((await b.treasury())['gold'],10000)
        await b.change_treasury(b.TreasuryChange(request_id=key,amount=100,reason='اصلاح خزانه'),{'id':999})
        await b.change_treasury(b.TreasuryChange(request_id=key,amount=100,reason='اصلاح خزانه'),{'id':999})
        with self.assertRaises(HTTPException):await b.change_treasury(b.TreasuryChange(request_id=key,amount=200,reason='اصلاح خزانه'),{'id':999})
        self.assertEqual((await b.treasury())['gold'],10100)
    async def test_writeoff_stops_future_debits(self):
        l=await self.active();await b.writeoff(str(l['_id']),b.Decision(reason='بخشودگی ادمین'),{'id':999});self.clock+=timedelta(days=10);await b.tick()
        self.assertEqual(await self.balance(2),1600)
    async def test_all_installments_settle_once_even_when_bank_closed(self):
        l=await self.active();self.cfg['enabled']=False;self.clock+=timedelta(days=4)
        await b.tick();await b.tick()
        self.assertEqual(await self.balance(2),940);self.assertEqual((await b.treasury())['gold'],5060)
        self.assertEqual((await self.loans.find_one({'_id':l['_id']}))['status'],'repaid')
    async def test_admin_dependency_rejects_regular_and_limited_roles(self):
        import auth
        for role in (None,'limited'):
            with patch.object(auth,'get_admin_role',new=AsyncMock(return_value=role)):
                with self.assertRaises(HTTPException):await b.admin({'id':4})
        with patch.object(auth,'get_admin_role',new=AsyncMock(return_value='full')):
            self.assertEqual((await b.admin({'id':999}))['id'],999)
    async def test_journal_without_debit_aborts_instead_of_charging_new_character(self):
        l=await self.active()
        op={'_id':f"{l['_id']}:repay:0:2",'loan_id':l['_id'],'kind':'repay','index':0,'payer':l['borrower'],'amount':220,'at':self.clock,'complete':False,'text':'قسط','recipients':[]}
        await self.ops.insert_one(op)
        await self.people.update_one({'tg_id':2},{'$set':{'created_at':self.at+timedelta(days=1)}})
        await b.recover();self.assertTrue((await self.ops.find_one({'_id':op['_id']}))['aborted'])
        await b.pay_installment(l,0,l['guarantor']);self.assertEqual(await self.balance(3),780);self.assertEqual(await self.balance(2),1600)
    async def test_pending_money_operation_prevents_writeoff(self):
        l=await self.active()
        await self.ops.insert_one({'_id':'pending','loan_id':l['_id'],'complete':False})
        with self.assertRaises(HTTPException):await b.writeoff(str(l['_id']),b.Decision(reason='بخشودگی ادمین'),{'id':999})
    async def test_privacy_and_exact_rounding(self):
        await self.active();d=await b.dashboard(1,{'id':4});self.assertEqual(d['loans'],[]);self.assertIsNone(d['treasury'])
        parts=b.schedule(101,15,3,24,self.at);self.assertEqual(sum(i['amount'] for i in parts),117);self.assertEqual(len(parts),3)
    def test_strict_integer_and_boolean_terms(self):
        with self.assertRaises(ValidationError):b.Offer(principal=1.2,interest_percent=0,installment_count=1,interval_hours=24)
        with self.assertRaises(ValidationError):b.Acceptance(version='x',accepted='false')

if __name__=='__main__':unittest.main()
