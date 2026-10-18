"""Short-lived, unguessable download links for administrator battle reports."""
import hashlib
import html
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from auth import get_user, get_admin
from db import db

router = APIRouter(prefix='/api')
reports = db.battle_report_files

class ReportBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2_000_000)

def render_report(title, text, created):
    stamp = created.astimezone(ZoneInfo('Asia/Tehran')).strftime('%Y-%m-%d %H:%M')
    return ('<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{html.escape(title)}</title><style>'
            '*{box-sizing:border-box}body{margin:0;background:#ece7dd;color:#30271e;font-family:Tahoma,Arial,sans-serif;line-height:2}'
            'main{max-width:900px;margin:30px auto;background:#fffdf8;border:1px solid #b99452;border-top:6px solid #8d2525;padding:35px}'
            'header{border-bottom:1px solid #c9ae78;margin-bottom:25px;padding-bottom:18px}h1{font-size:25px;margin:4px 0;color:#702424}'
            'small{color:#79613c}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:normal;font:inherit;font-size:15px;unicode-bidi:plaintext}'
            '@media(max-width:600px){main{margin:0;padding:22px 16px}h1{font-size:21px}}'
            '@media print{body{background:white}main{margin:0;border:0;padding:0;max-width:none}h1{break-after:avoid}}'
            '</style></head><body><main><header><small>والریا · گزارش کامل نبرد</small>'
            f'<h1>{html.escape(title)}</h1><small>تهیهٔ گزارش: <bdi>{stamp}</bdi> · به وقت تهران</small>'
            f'</header><article><pre>{html.escape(text)}</pre></article></main></body></html>')

@router.post('/admin/battle-reports')
async def create_report(body: ReportBody, user=Depends(get_user)):
    await get_admin(user)
    if len(body.text.encode('utf-8')) > 4_000_000:
        raise HTTPException(413, 'حجم گزارش بیش از چهار مگابایت است؛ گزارش ذخیره نشد')
    now = datetime.now(timezone.utc)
    if await reports.count_documents({'author':user['id'], 'created_at':{'$gte':now-timedelta(minutes=1)}}) >= 10:
        raise HTTPException(429, 'تعداد درخواست‌های دانلود زیاد است؛ یک دقیقه بعد دوباره تلاش کنید')
    await reports.create_index('expires_at', expireAfterSeconds=0)
    token = secrets.token_urlsafe(32)
    filename = 'valyria-battle-' + now.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.html'
    await reports.insert_one({'_id':hashlib.sha256(token.encode()).hexdigest(), 'author':user['id'],
                              'title':body.title, 'text':body.text, 'filename':filename,
                              'created_at':now, 'expires_at':now+timedelta(minutes=15)})
    return {'path':'/api/battle-report-files/'+token, 'filename':filename}

@router.api_route('/battle-report-files/{token}', methods=['GET','HEAD'])
async def download_report(token: str):
    # Possession of this 256-bit bearer link grants access only to this one report.
    if len(token) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):
        raise HTTPException(404, 'فایل گزارش پیدا نشد یا مهلت دانلود تمام شده است')
    row = await reports.find_one({'_id':hashlib.sha256(token.encode()).hexdigest(),
                                 'expires_at':{'$gt':datetime.now(timezone.utc)}})
    if not row:
        raise HTTPException(404, 'فایل گزارش پیدا نشد یا مهلت دانلود تمام شده است')
    return Response(render_report(row['title'],row['text'],row['created_at'].replace(tzinfo=timezone.utc)),
                    media_type='text/html; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="{row["filename"]}"',
                             'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
                             'Access-Control-Allow-Origin':'https://web.telegram.org',
                             'Referrer-Policy':'no-referrer',
                             'Content-Security-Policy':"sandbox; default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"})
