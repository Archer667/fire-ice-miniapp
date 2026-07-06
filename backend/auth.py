"""احراز هویت Telegram Mini App — اعتبارسنجی initData با HMAC"""
import hashlib, hmac, json, time
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException
from config import BOT_TOKEN, DEV_MODE, ADMIN_IDS

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
    authorization: str = Header(default=""),
    x_dev_user: str = Header(default=""),
) -> dict:
    """کاربر تأییدشدهٔ تلگرام. در DEV_MODE هدر X-Dev-User (id:name) پذیرفته می‌شود."""
    if DEV_MODE and x_dev_user:
        uid, _, name = x_dev_user.partition(":")
        return {"id": int(uid), "first_name": name or "Dev"}
    if not authorization.startswith("tma "):
        raise HTTPException(401, "توکن تلگرام ارسال نشده")
    return _validate_init_data(authorization[4:])

async def get_admin(user: dict) -> dict:
    if user["id"] not in ADMIN_IDS:
        raise HTTPException(403, "دسترسی ادمین نداری")
    return user
