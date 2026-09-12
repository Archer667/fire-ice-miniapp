"""Minute snapshots for rolling 24-hour rank comparisons, isolated by season/week."""
import asyncio,hashlib,logging
from datetime import datetime,timedelta
from db import db,game_settings
history=db.rank_history

def player_key(p):
    return hashlib.sha256((str(p['tg_id'])+':'+str(p.get('created_at'))).encode()).hexdigest()

async def scope(kind):
    from ranks import current_week_start
    season=await game_settings.find_one({'_id':'season_clock'}) or {}
    return str(season.get('started_at','initial'))+(':'+str(current_week_start()) if kind=='weekly' else '')

def movement(prior,key,rank):
    if prior is None:return {'state':'pending','delta':None}
    old=prior.get(key)
    if old is None:return {'state':'new','delta':None}
    return {'state':'known','delta':old-rank}

async def baseline(kind):
    cutoff=datetime.utcnow()-timedelta(hours=24)
    row=await history.find_one({'kind':kind,'scope':await scope(kind),'at':{'$lte':cutoff}},sort=[('at',-1)])
    return row['ranks'] if row and cutoff-row['at']<=timedelta(minutes=5) else None

async def capture():
    from routers.leaderboard import _without_admins,with_dead_players
    from ranks import scored_players,weekly_scored_players
    from game_data import REGIONS
    live=await _without_admins(await scored_players())
    total=await _without_admins(await with_dead_players(list(live)))
    weekly=await _without_admins(await with_dead_players(await weekly_scored_players(),weekly=True))
    sums={rid:0 for rid in REGIONS}
    for row in live:
        rid=row['player'].get('region')
        if rid in sums:sums[rid]+=row['score']
    ordered=sorted(sums,key=lambda rid:sums[rid],reverse=True)
    tables={'lords':{player_key(r['player']):i+1 for i,r in enumerate(total)},
            'weekly':{player_key(r['player']):i+1 for i,r in enumerate(weekly)},
            'regions':{rid:i+1 for i,rid in enumerate(ordered)}}
    at=datetime.utcnow().replace(second=0,microsecond=0)
    for kind,ranks in tables.items():
        epoch=await scope(kind)
        await history.update_one({'kind':kind,'scope':epoch,'at':at},{'$setOnInsert':{'ranks':ranks}},upsert=True)
    await history.delete_many({'at':{'$lt':at-timedelta(days=3)}})

async def watcher():
    from project_engine import game_state_lock
    import game_clock
    await history.create_index([('kind',1),('scope',1),('at',-1)],unique=True)
    while True:
        try:
            async with game_state_lock:
                await game_clock.load()
                await capture()
        except Exception:logging.getLogger(__name__).exception('rank snapshot failed')
        await asyncio.sleep(60)
