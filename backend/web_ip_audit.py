"""Owner-only view of successful browser logins that shared an IP address."""
import ipaddress
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request

from auth import get_user, get_owner
from db import db

router = APIRouter(tags=['web ip audit'])
RETENTION_DAYS = 90


def now():
    return datetime.now(timezone.utc)


def _normal_ip(value):
    try:
        parsed = ipaddress.ip_address((value or '').strip())
        if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
            parsed = parsed.ipv4_mapped
        return str(parsed)
    except ValueError:
        return None


def request_ip(request: Request):
    """Trust proxy forwarding only when the direct peer is local/private."""
    peer = _normal_ip(request.client.host if request.client else '')
    try:
        trusted_proxy = not peer or ipaddress.ip_address(peer).is_private or ipaddress.ip_address(peer).is_loopback
    except ValueError:
        trusted_proxy = False
    if trusted_proxy:
        forwarded = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
        candidate = _normal_ip(forwarded)
        if candidate:
            return candidate
    return peer


async def ensure_indexes():
    await db.web_ip_observations.create_index([('uid', 1), ('ip', 1)], unique=True)
    await db.web_ip_observations.create_index([('ip', 1), ('last_seen', -1)])
    await db.web_ip_observations.create_index('expires_at', expireAfterSeconds=0)


async def record(request: Request, uid: int, username: str, event: str):
    address = request_ip(request)
    if not address:
        return
    stamp = now()
    await db.web_ip_observations.update_one(
        {'uid': uid, 'ip': address},
        {
            '$set': {'username': username, 'last_seen': stamp, 'last_event': event,
                     'expires_at': stamp + timedelta(days=RETENTION_DAYS)},
            '$setOnInsert': {'first_seen': stamp},
            '$inc': {'count': 1},
        },
        upsert=True,
    )


def iso(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace('+00:00', 'Z')


@router.get('/api/admin/web-ip-audit')
async def shared_ips(
    days: int = Query(default=30, ge=1, le=90),
    min_accounts: int = Query(default=2, ge=2, le=20),
    user=Depends(get_user),
):
    await get_owner(user)
    cutoff = now() - timedelta(days=days)
    rows = [row async for row in db.web_ip_observations.find(
        {'last_seen': {'$gte': cutoff}}, {'_id': 0}
    ).sort('last_seen', -1).limit(10000)]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['ip']].append(row)
    shared = []
    for address, observations in grouped.items():
        unique = {row['uid']: row for row in observations}
        if len(unique) < min_accounts:
            continue
        accounts = []
        for uid, row in unique.items():
            player = await db.players.find_one({'tg_id': uid}, {'name': 1, 'castle': 1, 'is_dead': 1, 'registration_reset': 1}) or {}
            accounts.append({
                'uid': uid,
                'username': row.get('username') or str(uid),
                'player_name': player.get('name'),
                'castle': player.get('castle'),
                'is_dead': bool(player.get('is_dead')),
                'registration_reset': bool(player.get('registration_reset')),
                'first_seen': iso(row.get('first_seen')),
                'last_seen': iso(row.get('last_seen')),
                'count': int(row.get('count', 0)),
                'last_event': row.get('last_event', 'login'),
                'active_sessions': await db.web_sessions.count_documents({'uid': uid, 'expires_at': {'$gt': now()}}),
            })
        accounts.sort(key=lambda item: item['last_seen'] or '', reverse=True)
        shared.append({
            'ip': address,
            'account_count': len(accounts),
            'total_logins': sum(item['count'] for item in accounts),
            'first_seen': min((item['first_seen'] for item in accounts if item['first_seen']), default=None),
            'last_seen': max((item['last_seen'] for item in accounts if item['last_seen']), default=None),
            'accounts': accounts,
        })
    shared.sort(key=lambda item: (item['account_count'], item['last_seen'] or ''), reverse=True)
    return {
        'days': days,
        'retention_days': RETENTION_DAYS,
        'generated_at': iso(now()),
        'total_shared_ips': len(shared),
        'rows': shared,
        'notice': 'اشتراک IP به‌تنهایی نشانهٔ تخلف نیست؛ اینترنت خانوادگی، سازمانی، اپراتور موبایل و VPN می‌توانند IP مشترک ایجاد کنند.',
    }
