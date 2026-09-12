"""Accepted peace membership in explicit groups; no transitive alliances."""
async def peace_partners(collection, uid):
    kinds=['non_aggression','full_alliance']
    direct=await collection.find({'status':'accepted','type':{'$in':kinds},'$or':[{'from_id':uid},{'to_id':uid}]}).to_list(None)
    groups={r['group_id'] for r in direct if r.get('group_id')}
    rows=direct+(await collection.find({'status':'accepted','type':{'$in':kinds},'group_id':{'$in':list(groups)}}).to_list(None) if groups else [])
    out={}
    for r in rows:
        for member in (r['from_id'],r['to_id']):
            if member!=uid and (member not in out or r['type']=='full_alliance'):
                out[member]=r
    return out
