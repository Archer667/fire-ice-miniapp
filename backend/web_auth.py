"""Browser accounts, real-time sessions and recovery; no Telegram identity accepted."""
import asyncio
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from db import db

router = APIRouter(prefix='/api/web-auth', tags=['web accounts'])
accounts, sessions, attempts = db.web_accounts, db.web_sessions, db.web_auth_attempts
COOKIE = 'valyria_session'
SECURE_COOKIE = os.getenv('WEB_COOKIE_SECURE', 'true').lower() == 'true'
SESSION_DAYS = 14
PASSWORD_MIN = 12
hash_slots = asyncio.Semaphore(2)

def real_now(): return datetime.now(timezone.utc)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def account_name(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_]{3,32}', value):
        raise HTTPException(400, 'نام کاربری باید ۳ تا ۳۲ حرف انگلیسی، عدد یا زیرخط باشد')
    return value

def check_password(value):
    if len(value) < PASSWORD_MIN or len(value) > 128:
        raise HTTPException(400, 'رمز عبور باید بین ۱۲ تا ۱۲۸ نویسه باشد')

def password_hash(value, salt=None):
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, dklen=64, maxmem=64*1024*1024)
    return f'scrypt$32768$8$3${salt}${key.hex()}'

def password_matches(value, stored):
    try:
        method,n,r,p,salt,key = stored.split('$')
        if (method,n,r,p) != ('scrypt','32768','8','3'): return False
        return hmac.compare_digest(password_hash(value, salt).split('$')[-1], key)
    except (ValueError, TypeError): return False

async def hash_password(value):
    async with hash_slots: return await asyncio.to_thread(password_hash, value)

async def verify_password(value, stored):
    async with hash_slots: return await asyncio.to_thread(password_matches, value, stored)

def origin_guard(request):
    origin = request.headers.get('origin', '')
    allowed = os.getenv('PUBLIC_APP_ORIGIN', '').rstrip('/') or str(request.base_url).rstrip('/')
    if request.headers.get('x-valyria-client') != 'web' or origin != allowed:
        raise HTTPException(403, 'درخواست از نشانی معتبر بازی ارسال نشده است')

async def rate_limit(request, kind, username='', limit=20, minutes=15):
    stamp = real_now()
    address = request.client.host if request.client else 'unknown'
    for identity, maximum in [(address, limit), (f'user:{username}', 10 if kind=='login' else limit)]:
        if identity == 'user:': continue
        key = digest(f'{kind}:{identity}:{int(stamp.timestamp())//(minutes*60)}')
        row = await attempts.find_one_and_update({'_id': key}, {'$inc': {'count':1}, '$setOnInsert': {'expires_at':stamp+timedelta(minutes=minutes*2)}}, upsert=True, return_document=ReturnDocument.AFTER)
        if row['count'] > maximum: raise HTTPException(429, 'تعداد تلاش‌ها زیاد است؛ کمی بعد دوباره امتحان کنید')

async def ensure_indexes():
    from config import DB_NAME
    from urllib.parse import urlsplit
    origin=os.getenv('PUBLIC_APP_ORIGIN','').rstrip('/')
    local=urlsplit(origin).hostname in ('localhost','127.0.0.1','::1')
    if DB_NAME=='fire_ice': raise RuntimeError('Web edition must use its own database, not fire_ice')
    if not SECURE_COOKIE and not local: raise RuntimeError('Insecure cookies are permitted only on a loopback preview')
    if origin and not origin.startswith('https://') and not local: raise RuntimeError('Public web app requires an HTTPS origin')
    await accounts.create_index('username', unique=True)
    await accounts.create_index('uid', unique=True)
    await sessions.create_index('expires_at', expireAfterSeconds=0)
    await sessions.create_index('uid')
    await attempts.create_index('expires_at', expireAfterSeconds=0)
    await db.messages.create_index([('to_id',1),('from_id',1),('created_at',-1)])

def account_view(row): return {'id':row['uid'], 'username':row['username']}

async def new_account(username, password):
    check_password(password)
    code = secrets.token_urlsafe(24)
    counter = await db.web_counters.find_one_and_update({'_id':'accounts'}, {'$inc':{'value':1}}, upsert=True, return_document=ReturnDocument.AFTER)
    row = {'uid':1_000_000_000_000+counter['value'], 'username':username, 'password_hash':await hash_password(password), 'recovery_hash':digest(code), 'auth_version':1, 'created_at':real_now(), 'disabled':False}
    try: await accounts.insert_one(row)
    except DuplicateKeyError: raise HTTPException(409, 'این نام کاربری قابل استفاده نیست')
    return row, code

async def start_session(row, response):
    token,csrf = secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    await sessions.insert_one({'_id':digest(token), 'uid':row['uid'], 'auth_version':row['auth_version'], 'csrf':csrf, 'created_at':real_now(), 'expires_at':real_now()+timedelta(days=SESSION_DAYS)})
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS*86400, secure=SECURE_COOKIE, httponly=True, samesite='strict', path='/')
    response.headers['Cache-Control']='no-store'
    return {'account':account_view(row), 'csrf':csrf}

async def identity(request, mutation=None):
    cached = getattr(request.state, 'web_identity', None)
    if cached: return cached
    raw = request.cookies.get(COOKIE, '')
    if len(raw)<32 or len(raw)>128: raise HTTPException(401, 'برای ادامه وارد حساب شوید')
    session = await sessions.find_one({'_id':digest(raw), 'expires_at':{'$gt':real_now()}})
    if not session: raise HTTPException(401, 'نشست منقضی شده؛ دوباره وارد شوید')
    row = await accounts.find_one({'uid':session['uid'], 'disabled':False, 'auth_version':session['auth_version']})
    if not row: raise HTTPException(401, 'نشست معتبر نیست؛ دوباره وارد شوید')
    if mutation is None: mutation = request.method not in ('GET','HEAD','OPTIONS')
    if mutation:
        origin_guard(request)
        if not hmac.compare_digest(request.headers.get('x-valyria-csrf',''), session['csrf']):
            raise HTTPException(403, 'اعتبار درخواست منقضی شده؛ صفحه را تازه کنید')
    value={'id':row['uid'], 'first_name':row['username'], 'username':row['username'], '_web_account':row, '_web_session':session}
    request.state.web_identity=value
    return value

class Credentials(BaseModel):
    username: str = Field(min_length=3,max_length=32)
    password: str = Field(min_length=1,max_length=128)

class Recovery(Credentials):
    recovery_code: str = Field(min_length=20,max_length=128)

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=12,max_length=128)

@router.get('/config')
async def public_config(response: Response):
    response.headers['Cache-Control']='no-store'
    return {'name':'Valyria Web App', 'mode':'web', 'password_min':PASSWORD_MIN}

@router.post('/register')
async def register(body: Credentials, request: Request, response: Response):
    origin_guard(request)
    name=account_name(body.username)
    await rate_limit(request,'register',limit=5,minutes=60)
    from control_settings import feature_enabled
    if not feature_enabled('registration'): raise HTTPException(503,'ثبت‌نام در حال حاضر بسته است')
    row,code=await new_account(name,body.password)
    await db.web_auth_events.insert_one({'uid':row['uid'],'event':'registered','at':real_now()})
    return {**await start_session(row,response),'recovery_code':code}

@router.post('/login')
async def login(body: Credentials, request: Request, response: Response):
    origin_guard(request)
    name=account_name(body.username)
    await rate_limit(request,'login',name,limit=30)
    row=await accounts.find_one({'username':name,'disabled':False})
    # Unknown names incur the same password KDF cost.
    valid=await verify_password(body.password, row['password_hash'] if row else 'scrypt$32768$8$3$'+'0'*32+'$'+'0'*128)
    if not row or not valid: raise HTTPException(401,'نام کاربری یا رمز عبور نادرست است')
    await db.web_auth_events.insert_one({'uid':row['uid'],'event':'login','at':real_now()})
    return await start_session(row,response)

@router.get('/session')
async def current_session(request: Request, response: Response):
    user=await identity(request)
    response.headers['Cache-Control']='no-store'
    return {'account':account_view(user['_web_account']),'csrf':user['_web_session']['csrf']}

@router.post('/logout')
async def logout(request: Request, response: Response):
    user=await identity(request)
    await sessions.delete_one({'_id':user['_web_session']['_id']})
    response.delete_cookie(COOKIE,path='/',secure=SECURE_COOKIE,httponly=True,samesite='strict')
    response.headers['Cache-Control']='no-store'
    return {'ok':True}

@router.post('/password')
async def change_password(body: PasswordChange, request: Request, response: Response):
    user=await identity(request);row=user['_web_account']
    await rate_limit(request,'password',str(user['id']),limit=10)
    if not await verify_password(body.current_password,row['password_hash']): raise HTTPException(400,'رمز فعلی نادرست است')
    code=secrets.token_urlsafe(24)
    changed=await accounts.find_one_and_update({'uid':row['uid'],'auth_version':row['auth_version']},{'$set':{'password_hash':await hash_password(body.new_password),'recovery_hash':digest(code)},'$inc':{'auth_version':1}},return_document=ReturnDocument.AFTER)
    if not changed: raise HTTPException(409,'حساب تغییر کرده است؛ دوباره وارد شوید')
    await sessions.delete_many({'uid':row['uid'],'auth_version':{'$lte':row['auth_version']}})
    await db.web_auth_events.insert_one({'uid':row['uid'],'event':'password_changed','at':real_now()})
    return {**await start_session(changed,response),'recovery_code':code}

@router.post('/recover')
async def recover(body: Recovery, request: Request, response: Response):
    origin_guard(request);name=account_name(body.username);check_password(body.password)
    await rate_limit(request,'recover',name,limit=5)
    row=await accounts.find_one({'username':name,'disabled':False})
    if not row or not hmac.compare_digest(row.get('recovery_hash',''),digest(body.recovery_code.strip())):
        raise HTTPException(400,'اطلاعات بازیابی معتبر نیست')
    code=secrets.token_urlsafe(24)
    changed=await accounts.find_one_and_update({'uid':row['uid'],'auth_version':row['auth_version'],'recovery_hash':row['recovery_hash']},{'$set':{'password_hash':await hash_password(body.password),'recovery_hash':digest(code)},'$inc':{'auth_version':1}},return_document=ReturnDocument.AFTER)
    if not changed: raise HTTPException(409,'این کد قبلاً استفاده شده است')
    await sessions.delete_many({'uid':row['uid'],'auth_version':{'$lte':row['auth_version']}})
    await db.web_auth_events.insert_one({'uid':row['uid'],'event':'recovered','at':real_now()})
    return {**await start_session(changed,response),'recovery_code':code}

async def admin_cli(action):
    import getpass
    await ensure_indexes()
    username=account_name(input('Username: '));password=getpass.getpass('New password (12+ characters): ');check_password(password)
    if password!=getpass.getpass('Repeat password: '): raise ValueError('Passwords do not match')
    row=await accounts.find_one({'username':username})
    if action=='bootstrap-admin':
        if await db.admin_roles.find_one({'role':'owner'}): raise ValueError('An owner already exists; bootstrap is closed')
        if row and not await verify_password(password,row['password_hash']): raise ValueError('Existing account password does not match')
        if not row: row,code=await new_account(username,password);print('Save recovery code:',code)
        await db.admin_roles.update_one({'tg_id':row['uid']},{'$set':{'role':'owner','name':username}},upsert=True)
        print('Owner account created. Sign in on the web app.')
    elif action=='reset-password':
        if not row: raise ValueError('Account not found')
        code=secrets.token_urlsafe(24)
        await accounts.update_one({'uid':row['uid']},{'$set':{'password_hash':await hash_password(password),'recovery_hash':digest(code)},'$inc':{'auth_version':1}})
        await sessions.delete_many({'uid':row['uid']})
        await db.web_auth_events.insert_one({'uid':row['uid'],'event':'server_password_reset','at':real_now()})
        print('Password reset. Save recovery code:',code)
    else: raise ValueError('Use bootstrap-admin or reset-password')

if __name__=='__main__':
    import sys
    asyncio.run(admin_cli(sys.argv[1] if len(sys.argv)>1 else 'bootstrap-admin'))
