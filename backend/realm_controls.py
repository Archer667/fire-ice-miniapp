"""One rule source for council, influence and the player trade network."""
from fastapi import HTTPException
from pydantic import BaseModel, Field, StrictBool, StrictInt, create_model
from db import db

DEFAULTS = {
 'council_enabled':True,'trade_network_enabled':True,'contract_fees_enabled':False,
 'proposal_cost':10,'support_cost':2,'voting_hours':48,'quorum_percent':30,
 'market_fee_percent':2,'cross_region_tariff_percent':3,
 'influence_start':20,'influence_cap':1000000,'reward_vote':1,'reward_trade':1,
 'reward_trade_max':3,'reward_trade_step':5000,'reward_supply':2,'reward_tribute':1,
 'reward_pact_proposer':3,'reward_pact_receiver':2,
 'max_open_proposals':5,'max_open_orders':20,'max_open_contracts':10,
 'max_order_quantity':1000000000,'max_trade_value':1000000000000,
 'max_contract_deliveries':30,'max_contract_interval':720,'contract_grace_hours':24,
}
BOUNDS={'voting_hours':(1,720),'quorum_percent':(0,100),'market_fee_percent':(0,50),
 'cross_region_tariff_percent':(0,50),'influence_cap':(1,1000000000),
 'reward_trade_step':(1,1000000000),'reward_trade_max':(0,1000),
 'max_open_proposals':(0,1000),'max_open_orders':(0,1000),'max_open_contracts':(0,1000),
 'max_order_quantity':(1,1000000000),'max_trade_value':(1,1000000000000),
 'max_contract_deliveries':(1,30),'max_contract_interval':(1,720),'contract_grace_hours':(0,720)}

async def rules():
 row=await db.game_settings.find_one({'_id':'realm_rules'}) or {}
 return {k:row.get(k,v) for k,v in DEFAULTS.items()}

fields={}
for key,value in DEFAULTS.items():
 if isinstance(value,bool):fields[key]=(StrictBool,value)
 else:
  low,high=BOUNDS.get(key,(0,1000000));fields[key]=(StrictInt,Field(default=value,ge=low,le=high))
RulesSchema=create_model('RealmRulesSchema',**fields)

async def require_enabled(key):
 cfg=await rules()
 if not cfg[key]:raise HTTPException(503,'ثبت و اجرای اقدام تازه در این بخش فعلاً متوقف است؛ لغو و بازپرداخت همچنان قابل پیگیری است')
 return cfg

def reward_for(source,requested,cfg):
 if requested<=0:return requested
 if source.startswith('vote:'):return cfg['reward_vote']
 if source.startswith('buy-order:'):return min(cfg['reward_trade_max'],requested*cfg['reward_trade'])
 if source.startswith('supply:'):return cfg['reward_supply']
 if source.startswith('tribute:'):return cfg['reward_tribute']
 if source.startswith('pact:'):return cfg['reward_pact_proposer' if source.endswith(':from') else 'reward_pact_receiver']
 return requested
