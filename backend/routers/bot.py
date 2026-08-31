from fastapi import APIRouter, Header, Request
from config import MINI_APP_URL
import telegram_bot
from db import players

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

WELCOME_TEXT = (
    "🏰 به «والریا : سیزن اول» خوش آمدی!\n\n"
    "با دکمهٔ پایین وارد بازی شو — اسم و جنسیتت را بده، بعد صبر کن تا ادمین خاندان و "
    "قلعه‌ات را دستی مشخص کند."
)

@router.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")):
    """تلگرام آپدیت‌ها را اینجا پوش می‌کند (بعد از register_webhook در استارتاپ).
    فعلاً فقط /start را جواب می‌دهد — همیشه 200 برمی‌گردانیم چون تلگرام منتظر جواب
    سریع است و خطا دادن باعث می‌شود دوباره و دوباره retry کند"""
    if telegram_bot.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != telegram_bot.WEBHOOK_SECRET:
        return {"ok": True}

    update = await request.json()
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    sender = message.get("from") or {}

    # برای بازیکن‌های قدیمی هم هر پیام تازه به بات، username فعلی را بی‌سروصدا
    # در پرونده‌شان به‌روز می‌کند؛ هیچ کاری داخل اپ از آن‌ها خواسته نمی‌شود.
    sender_id = sender.get("id")
    if sender_id:
        username = (sender.get("username") or "").strip().lstrip("@") or None
        if username:
            await players.update_one({"tg_id": sender_id}, {"$set": {"telegram_username": username}})
        else:
            await players.update_one({"tg_id": sender_id}, {"$unset": {"telegram_username": ""}})

    if chat_id and text.startswith("/start"):
        reply_markup = (
            {"inline_keyboard": [[{"text": "🎮 ورود به بازی", "web_app": {"url": MINI_APP_URL}}]]}
            if MINI_APP_URL else None
        )
        telegram_bot.push(chat_id, WELCOME_TEXT, reply_markup=reply_markup)

    return {"ok": True}
