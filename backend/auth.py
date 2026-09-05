"""احراز هویت Telegram Mini App — اعتبارسنجی initData با HMAC"""
import hashlib, hmac, json, time
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException, Request
from config import BOT_TOKEN, DEV_MODE, ADMIN_IDS, OWNER_ID
from db import admin_roles, players

def _validate_init_data(init_data: str) -> dict:
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "hash موجود نیست")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        raise HTTPException(401, "initData نامعتبر است")

    # حداکثر عمر ۲۴ ساعت
    if time.time() - int(parsed.get("auth_date", 0)) > 86400:
        raise HTTPException(401, "نشست منقضی شده — دوباره باز کن")

    return json.loads(parsed.get("user", "{}"))

async def get_user(
    request: Request = None,
    authorization: str = Header(default=""),
    x_dev_user: str = Header(default=""),
) -> dict:
    """کاربر تأییدشدهٔ تلگرام. در DEV_MODE هدر X-Dev-User (id:name) پذیرفته می‌شود."""
    if DEV_MODE and x_dev_user:
        uid, _, name = x_dev_user.partition(":")
        user = {"id": int(uid), "first_name": name or "Dev"}
    else:
        if not authorization.startswith("tma "):
            raise HTTPException(401, "توکن تلگرام ارسال نشده")
        user = _validate_init_data(authorization[4:])
    if request and request.url.path != "/api/players/me":
        dead = await players.find_one({"tg_id": user["id"], "is_dead": True}, {"_id": 1})
        if dead and not await get_admin_role(user):
            raise HTTPException(403, "کشته شد — تا حذف خاندان توسط ادمین امکان بازی نداری", headers={"X-Player-Dead": "1"})
    return user

async def get_admin_role(user: dict) -> str | None:
    """owner = ادمین اصلی، full = ادمین کامل، limited = ادمین اجرایی.

    OWNER_ID همیشه ادمین اصلیِ غیرقابل‌حذف است، اما ادمین اصلی می‌تواند همین نقش را
    از داخل پنل به افراد دیگری هم بدهد. ADMIN_IDS برای سازگاری با دیپلوی‌های قدیمی
    همچنان ادمین کامل محسوب می‌شود.
    """
    if OWNER_ID is not None and user["id"] == OWNER_ID:
        return "owner"
    if user["id"] in ADMIN_IDS:
        return "full"
    doc = await admin_roles.find_one({"tg_id": user["id"]})
    role = doc.get("role") if doc else None
    return role if role in ("owner", "full", "limited") else None

async def get_admin(user: dict) -> dict:
    """هر سه سطح ادمین — برای کارهای اجرایی مشترک."""
    role = await get_admin_role(user)
    if not role:
        raise HTTPException(403, "دسترسی ادمین نداری")
    user["admin_role"] = role
    return user

async def get_full_admin(user: dict) -> dict:
    """ادمین اصلی یا کامل — برای تنظیمات و ابزارهای حساس بازی."""
    role = await get_admin_role(user)
    if role not in ("owner", "full"):
        raise HTTPException(403, "این بخش فقط برای ادمین اصلی یا کامل است")
    user["admin_role"] = role
    return user

async def get_owner(user: dict) -> dict:
    """هر ادمین اصلی؛ OWNER_ID یا کسی که نقش owner را از پنل گرفته است."""
    role = await get_admin_role(user)
    if role != "owner":
        raise HTTPException(403, "این بخش فقط برای ادمین اصلی است")
    user["admin_role"] = "owner"
    return user
