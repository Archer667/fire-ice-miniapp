"""Optional daily execution slots on the paused game clock, with real ETA display."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from db import db
import game_clock

TASKS={'food':'مصرف غلات','rebellions':'محبوبیت، مالیات و احتمال شورش'}

def next_slot(current,clock):
    hour,minute=map(int,clock.split(':'))
    local=current.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Tehran'))
    target=local.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if target<=local:target+=timedelta(days=1)
    return target.astimezone(timezone.utc).replace(tzinfo=None)

async def run(task,callback,scheduled_callback=None):
    if game_clock.paused():return
    cfg=await db.daily_schedules.find_one({'_id':task}) or {}
    if cfg.get('enabled') and game_clock.now()<cfg['next_at']:return
    await (scheduled_callback if cfg.get('enabled') and scheduled_callback else callback)()
    if cfg.get('enabled'):
        await db.daily_schedules.update_one({'_id':task},{'$set':{
            'last_game_at':game_clock.now(),'last_real_at':game_clock.real_now(),
            'next_at':next_slot(game_clock.now(),cfg['clock'])}})

async def view():
    from time_management import deadline_view,iso
    result=[]
    for task,name in TASKS.items():
        row=await db.daily_schedules.find_one({'_id':task}) or {}
        due=row.get('next_at')
        if not row.get('enabled'):
            if task=='rebellions':due=game_clock.now().replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
            else:
                epoch=await db.game_settings.find_one({'_id':'food_settlement_v1'}) or {}
                dues=[]
                async for sample in db.players.find({'castle':{'$nin':[None,'']},'is_dead':{'$ne':True}},{'food_settled_at':1,'created_at':1}):
                    anchor=sample.get('food_settled_at') or max(epoch.get('started_at',game_clock.now()),sample.get('created_at',game_clock.now()))
                    dues.append(anchor+timedelta(days=1))
                due=min(dues) if dues else None
        last_real=row.get('last_real_at')
        if not last_real:
            table,field=('food_settlements','processed_real_at') if task=='food' else ('rebellion_checks','processed_real_at')
            event=await db[table].find_one({field:{'$exists':True}},sort=[(field,-1)]) or {}
            last_real=event.get(field)
        result.append({'task':task,'name':name,'enabled':bool(row.get('enabled')),'clock':row.get('clock','00:00'),
            'next':deadline_view(due) if due else None,'last_real_at':iso(last_real),
            'mode':('روزانه در ساعت تعیین‌شدهٔ ساعت بازی، با نمایش تهران' if row.get('enabled') else
                    'هر بازیکن پس از تکمیل ۲۴ ساعت بازی از آخرین تسویه' if task=='food' else 'اولین بررسی هر روز بازی؛ کنترل مهلت رول پیوسته است')})
    return result
