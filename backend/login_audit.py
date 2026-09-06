"""Short-lived, authenticated login observations; never an account-ban signal."""
import hashlib
import hmac
import ipaddress
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError
from db import db
from config import OWNER_ID
import telegram_bot

logger = logging.getLogger(__name__)


def verified_ip(headers, secret, clock=None):
    if not secret:
        return None
    stamp = headers.get('x-login-time', '')
    address = headers.get('x-login-ip', '')
    try:
        if abs((time.time() if clock is None else clock) - int(stamp)) > 60:
            return None
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return None
    except ValueError:
        return None
    payload = '\n'.join([stamp, address, headers.get('authorization', '')])
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    signature = headers.get('x-login-signature', '')
    if len(signature) != 64 or any(c not in '0123456789abcdef' for c in signature):
        return None
    if not hmac.compare_digest(expected, signature):
        return None
    return str(ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip)


async def ensure_indexes():
    await db.login_observations.create_index('expires_at', expireAfterSeconds=0)
    await db.login_observations.create_index([('ip', 1), ('last_seen', 1)])
    await db.login_alerts.create_index('expires_at', expireAfterSeconds=0)


async def record_login(user, address):
    if not address or not OWNER_ID:
        return
    try:
        now = datetime.now(timezone.utc)
        player = await db.players.find_one({'tg_id': user['id']}, {'name': 1})
        if not player:
            return
        uid = user['id']
        await db.login_observations.update_one(
            {'_id': f'{uid}:{address}'}, {'$set': {
                'tg_id': uid, 'name': player.get('name', str(uid)), 'ip': address,
                'last_seen': now, 'expires_at': now + timedelta(days=7),
            }}, upsert=True)
        peers = db.login_observations.find({
            'ip': address, 'tg_id': {'$ne': uid},
            'last_seen': {'$gte': now - timedelta(hours=24)},
        })
        async for peer in peers:
            pair = ':'.join(map(str, sorted([uid, peer['tg_id']])))
            # Atomic claim across concurrent workers; one notification per pair / 24h.
            try:
                claim = await db.login_alerts.update_one(
                    {'_id': pair, 'last_sent': {'$lte': now - timedelta(hours=24)}},
                    {'$set': {'last_sent': now, 'ip': address, 'expires_at': now + timedelta(days=7)}},
                    upsert=True)
            except DuplicateKeyError:
                continue
            if claim.modified_count or claim.upserted_id:
                telegram_bot.push(OWNER_ID,
                    '🔎 هشدار ورود از IP مشترک\n'
                    f"بازیکن اول: {player.get('name', uid)} ({uid})\n"
                    f"بازیکن دوم: {peer['name']} ({peer['tg_id']})\n"
                    f"IP مشترک: {address}\n"
                    f"زمان تشخیص: {now:%Y-%m-%d %H:%M} UTC\n"
                    'هر دو حساب در ۲۴ ساعت اخیر از یک IP وارد شده‌اند.\n'
                    'این هشدار اثبات چنداکانتی نیست؛ اینترنت یا VPN مشترک هم می‌تواند علت باشد.')
    except Exception:
        # Telemetry must never prevent entry; do not log IPs or auth headers.
        logger.warning('Login audit failed')


def request_ip(request):
    return verified_ip(request.headers, os.getenv('LOGIN_AUDIT_SECRET', ''))
