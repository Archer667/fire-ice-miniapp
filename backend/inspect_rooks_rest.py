"""Read-only diagnosis: distinguish castle dossiers from nearby road encounters."""
import asyncio,json
from db import campaigns,client

def normalized(value):
    return ''.join((value or '').casefold().split()).replace('\u200c','').replace("'",'').replace('’','')
async def inspect():
    fields={'name':1,'player_name':1,'tg_id':1,'battle_is_root':1,'battle_open':1,
            'battle_location':1,'target_castle':1,'engagement_campaign_id':1,'battle_root_campaign_id':1,
            'battle_started_at':1,'battle_contact':1,'stationed_edge':1,'combat_resolved_at':1,
            'battle_cancelled_at':1,'battle_attacker_army_ids':1,'battle_defender_army_ids':1}
    result=[]
    async for row in campaigns.find({'battle_open':True},fields):
        label=normalized(row.get('battle_location') or row.get('target_castle'))
        if 'rooksrest' in label or ('روک' in label and 'رست' in label):result.append(row)
    print(json.dumps({'open_cases':result,'count':len(result)},ensure_ascii=False,default=str,indent=2))
    client.close()
if __name__=='__main__':asyncio.run(inspect())
