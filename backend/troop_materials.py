from game_data import NAVAL_TROOPS

def snapshot(troops):
    return {tid:{r:float(NAVAL_TROOPS[tid].get(r+'_cost',0)) for r in ('wood','iron')} for tid,n in troops.items() if n>0 and tid in NAVAL_TROOPS}

def refund(army, troops=None):
    result={}
    for tid,cost in army.get('naval_material_costs',{}).items():
        for resource,amount in cost.items():
            result[resource]=result.get(resource,0)+amount*max(0,(troops if troops is not None else army.get('troops',{})).get(tid,0))
    return result
