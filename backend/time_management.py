"""Clock diagnostics and explicit timer corrections; real UTC is never rewritten."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth import get_user, get_full_admin
from db import db, game_settings
import game_clock
from game import normalize_datetime
from season_clock import season_day

router = APIRouter(prefix='/api/admin/time', tags=['time management'])

async def admin(user=Depends(get_user)):
    return await get_full_admin(user)

def iso(value):
    value = normalize_datetime(value)
    return value.isoformat() + 'Z' if value else None

def deadline_view(value):
    value = normalize_datetime(value)
    remaining = (value - game_clock.now()).total_seconds() if value else 0
    return {'internal_at': iso(value), 'display_at': iso(game_clock.real_now() + timedelta(seconds=remaining)) if value else None,
            'remaining_seconds': remaining, 'paused': game_clock.paused(),
            'estimated': game_clock.paused(), 'clock': 'game'}

async def display_zone():
    row = await game_settings.find_one({'_id': 'time_display'}) or {}
    return row.get('timezone', 'Asia/Tehran')

# Active deadlines only; settled events are never silently replayed.
SOURCES = {
    'rebellions': ('شورش', {'status': {'$in': ['awaiting_roleplay', 'roleplay_submitted', 'expired']}}, {'deadline': 'game'}),
    'campaigns': ('لشکرکشی', {'active': True}, {'arrival_at': 'game'}),
    'caravans': ('کاروان', {'active': True, 'arrival_notified': {'$ne': True}}, {'arrival_at': 'game'}),
    'spy_missions': ('جاسوسی', {'resolved':{'$ne':True}}, {'arrival_at': 'game'}),
    'projects': ('پروژه', {'status': {'$in': ['scheduled', 'funding', 'active']}}, {'publish_at': 'real', 'funding_deadline': 'game', 'next_payout_at': 'game'}),
    'family_marriages': ('مهلت ازدواج', {'status': {'$in':['proposed','accepted']}}, {'expires_at':'game'}),
    'family_children': ('بلوغ فرزندان', {'status':'alive', 'adult_notified':{'$ne':True}}, {'adult_at':'game'}),
    'tributes': ('مهلت خراج', {'status':'pending'}, {'due_at':'game'}),
    'black_market_listings': ('انقضای بازار سیاه', {'qty':{'$gt':0}}, {'expires_at':'game'}),
    'item_grants': ('اعتبار آیتم‌های موقت', {'expires_at':{'$type':'date'}}, {'expires_at':'game'}),
    'players': ('ساخت، تولید و کول‌داون بازیکنان', {}, {'next_production':'game', 'next_feast':'game', 'next_daily_boundary':'game'}),
}

@router.get('')
async def overview(user=Depends(admin)):
    await game_clock.load()
    zone = await display_zone()
    season = await game_settings.find_one({'_id': 'season_clock'}) or {}
    from control_settings import get as rule
    from config import FEAST_COOLDOWN_HOURS, RUMOR_COOLDOWN_HOURS
    return {**game_clock.status(), 'real_now': iso(game_clock.real_now()), 'offset_seconds': game_clock._state.get('offset_seconds', 0),
            'timezone': zone, 'storage_timezone': 'UTC', 'calendar': await season_day(), 'season_started_at': iso(season.get('started_at')),
            'sources': [{'key': key, 'name': item[0], 'fields': item[2]} for key,item in SOURCES.items()],
            'workers': {key:game_clock.timing(key) for key in game_clock.TIMING_DEFAULTS}, 'durations': [
                {'name':'فرصت رول شورش', 'value':rule('war.roleplay_hours',6), 'unit':'ساعت بازی', 'edit':'قوانین و نرخ‌ها / جنگ'},
                {'name':'ضیافت', 'value':rule('diplomacy.feast_cooldown_hours',FEAST_COOLDOWN_HOURS), 'unit':'ساعت بازی', 'edit':'قوانین و نرخ‌ها / دیپلماسی'},
                {'name':'شایعه', 'value':rule('tweets.cooldown_hours',RUMOR_COOLDOWN_HOURS), 'unit':'ساعت بازی', 'edit':'قوانین و نرخ‌ها / شایعه'},
                {'name':'گزارش نبرد', 'value':rule('war.report_visible_hours',24), 'unit':'ساعت بازی', 'edit':'قوانین و نرخ‌ها / جنگ'},
                {'name':'فرصت لغو حرکت', 'value':rule('war.cancel_grace_minutes',5), 'unit':'دقیقه بازی', 'edit':'قوانین و نرخ‌ها / جنگ'},
                {'name':'رسیدگی لشکر، شورش، اعلان و مصرف', 'value':game_clock.timing('arrival_poll_seconds'), 'unit':'ثانیه واقعی', 'edit':'چرخهٔ سرور'},
                {'name':'رسیدگی پروژه', 'value':game_clock.timing('project_poll_seconds'), 'unit':'ثانیه واقعی', 'edit':'چرخهٔ سرور'},
                {'name':'رسیدگی بازار', 'value':game_clock.timing('market_poll_seconds'), 'unit':'ثانیه واقعی', 'edit':'چرخهٔ سرور'},
                {'name':'هشدار نزدیک‌شدن مهلت ادمین', 'value':game_clock.timing('deadline_warning_hours'), 'unit':'ساعت بازی', 'edit':'چرخهٔ اعلان'},
            ],
            'domains': [
                {'name':'ساعت واقعی', 'use':'ورود، امنیت، گزارش فعالیت ادمین و تاریخ انتشار پروژه', 'pause':False},
                {'name':'ساعت محاسبات بازی', 'use':'حرکت لشکر، کاروان، جاسوسی، ساخت، مصرف، تولید، شورش و مهلت‌های بازی', 'pause':True},
                {'name':'تقویم فصل بازی', 'use':'روز فصل و رنگ و آب‌وهوای نقشه؛ از آغاز فصل و ساعت بازی', 'pause':True},
                {'name':'تاریخ نمایشی', 'use':'تبدیل به شمسی و منطقهٔ زمانی؛ مبنای محاسبه نیست', 'pause':False},
                {'name':'زمان‌بندی رسیدگی سرور', 'use':'بررسی دوره‌ای رخدادها؛ رسیدن مهلت با اجرای بررسی یکی نیست', 'pause':False},
            ]}

@router.get('/timers')
async def timers(kind: str = 'rebellions', page: int = 1, user=Depends(admin)):
    if kind not in SOURCES or page < 1 or page > 10000:
        raise HTTPException(400, 'نوع زمان یا صفحه نامعتبر است')
    label, query, fields = SOURCES[kind]
    collection = db[kind]
    projection = {k: 1 for k in (*fields, 'player_name', 'name', 'status', 'tg_id', 'target_castle', 'castle', 'arrival_notified', 'engagement_locked')}
    if kind == 'players':
        projection.update({'buildings':1, 'last_tick':1, 'last_feast':1})
    out = []
    async for row in collection.find(query, projection).sort('_id', -1).skip((page-1)*25).limit(25):
        row_fields = dict(fields)
        if kind == 'players':
            from control_settings import get as rule
            if row.get('last_tick'):
                row['next_production'] = normalize_datetime(row['last_tick']) + timedelta(days=1)
            if row.get('last_feast'):
                row['next_feast'] = normalize_datetime(row['last_feast']) + timedelta(hours=float(rule('diplomacy.feast_cooldown_hours',24)))
            row['next_daily_boundary'] = game_clock.now().replace(hour=0,minute=0,second=0,microsecond=0) + timedelta(days=1)
            for key,building in (row.get('buildings') or {}).items():
                if isinstance(building,dict) and building.get('ready_at'):
                    field = 'buildings.'+key+'.ready_at'
                    row[field] = building['ready_at']
                    row_fields[field] = 'game'
        for field, clock in row_fields.items():
            stamp = row.get(field)
            if isinstance(stamp, str):
                try:
                    stamp = normalize_datetime(stamp)
                except (ValueError,TypeError):
                    continue
            if not isinstance(stamp, datetime):
                continue
            if kind == 'projects' and row.get('status') == 'scheduled' and field == 'funding_deadline':
                clock = 'real'
            view = deadline_view(stamp) if clock == 'game' else {'internal_at':iso(stamp), 'display_at':iso(stamp), 'remaining_seconds':(stamp-game_clock.real_now()).total_seconds(), 'paused':False, 'estimated':False, 'clock':'real'}
            out.append({'id':str(row['_id']), 'kind':kind, 'field':field, 'name':row.get('player_name') or row.get('name') or str(row.get('tg_id','')), 'location':row.get('target_castle') or row.get('castle'), 'status':row.get('status'), **view,
                        'editable':kind == 'rebellions' and field == 'deadline' and row.get('status') in ('awaiting_roleplay','expired')})
    return {'rows':out, 'page':page, 'total':await collection.count_documents(query)}

class DisplaySettings(BaseModel):
    timezone: str = Field(max_length=80)

@router.put('/display')
async def save_display(body: DisplaySettings, user=Depends(admin)):
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(400, 'منطقهٔ زمانی معتبر نیست') from None
    await game_settings.update_one({'_id':'time_display'}, {'$set':{'timezone':body.timezone, 'changed_by':user['id'], 'changed_at':game_clock.real_now()}}, upsert=True)
    return {'ok':True}

class WorkerSettings(BaseModel):
    arrival_poll_seconds: int = Field(ge=10,le=300)
    project_poll_seconds: int = Field(ge=5,le=300)
    market_poll_seconds: int = Field(ge=60,le=3600)
    deadline_warning_hours: float = Field(ge=0,le=168)

@router.put('/workers')
async def save_workers(body: WorkerSettings, user=Depends(admin)):
    # The API middleware already owns game_state_lock across this handler.
    await game_settings.update_one({'_id':'game_clock'}, {'$set':{'timing':body.model_dump(), 'timing_changed_by':user['id'], 'timing_changed_at':game_clock.real_now()}}, upsert=True)
    await game_clock.load()
    return {'ok':True}

class SeasonSettings(BaseModel):
    day: int = Field(ge=1, le=30)
    reason: str = Field(min_length=3, max_length=500)

@router.put('/season')
async def correct_season(body: SeasonSettings, user=Depends(admin)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل اصلاح را بنویس')
    # The API middleware already owns game_state_lock across this handler.
    start = game_clock.now() - timedelta(days=body.day-1)
    await game_settings.update_one({'_id':'season_clock'}, {'$set':{'started_at':start, 'changed_by':user['id'], 'reason':body.reason, 'changed_at':game_clock.real_now()}}, upsert=True)
    return await season_day()

class TimerCorrection(BaseModel):
    remaining_minutes: int = Field(ge=1, le=43200)
    expected_internal_at: datetime
    reason: str = Field(min_length=3, max_length=500)

@router.put('/rebellions/{timer_id}')
async def correct_rebellion(timer_id: str, body: TimerCorrection, user=Depends(admin)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل اصلاح را بنویس')
    try:
        oid = ObjectId(timer_id)
    except Exception:
        raise HTTPException(400, 'شناسه نامعتبر است') from None
    # The API middleware already owns game_state_lock across this handler.
    old = normalize_datetime(body.expected_internal_at)
    stamp = game_clock.now() + timedelta(minutes=body.remaining_minutes)
    result = await db.rebellions.update_one({'_id':oid, 'deadline':old, 'status':{'$in':['awaiting_roleplay','expired']}},
        {'$set':{'deadline':stamp, 'status':'awaiting_roleplay'}, '$push':{'time_corrections':{'old':old, 'new':stamp, 'reason':body.reason, 'actor':user['id'], 'at':game_clock.real_now()}}})
    if not result.matched_count:
        raise HTTPException(409, 'مهلت یا وضعیت تغییر کرده؛ فهرست را تازه کن. رول ارسال‌شده یا پروندهٔ تمام‌شده بازنویسی نمی‌شود')
    return {'ok':True, **deadline_view(stamp)}
