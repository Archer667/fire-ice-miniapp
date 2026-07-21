"""ارتباط دوطرفه با بات تلگرام:
- push(): پوش واقعی — علاوه بر ذخیرهٔ نامه در صندوق کلاغ‌های داخل اپ، یک پیام واقعی
  به چت تلگرام بازیکن می‌فرستد تا حتی وقتی اپ بسته است هم از رویدادهای مهم خبردار شود.
- register_webhook()/WEBHOOK_SECRET: راه‌اندازی دستور /start — تلگرام آپدیت‌ها (از
  جمله پیام‌های کاربر) را به‌جای اینکه ما بپرسیم (getUpdates)، خودش به آدرس بک‌اند
  ما پوش می‌کند (webhook). routers/bot.py همان آدرس را می‌شنود."""
import asyncio
import hashlib
import logging
import httpx
from config import BOT_TOKEN, DEV_MODE, PUBLIC_BASE_URL, TELEGRAM_WEBHOOK_PATH

logger = logging.getLogger(__name__)

_SEND_MESSAGE_API = "https://api.telegram.org/bot{token}/sendMessage"
_SET_WEBHOOK_API = "https://api.telegram.org/bot{token}/setWebhook"
# ارجاع نگه‌داشته می‌شود چون asyncio تسک‌های بدون ارجاعِ قوی را ممکن است زودتر از
# اتمام garbage-collect کند
_background_tasks: set[asyncio.Task] = set()

# مقداری مخفی و ثابت (وابسته به خودِ BOT_TOKEN) که موقع setWebhook به تلگرام می‌دهیم
# و تلگرام همان را در هر آپدیت واقعی برمی‌گرداند — جلوی جعل درخواست به آدرس webhook را می‌گیرد
WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32] if BOT_TOKEN else ""

async def _post_message(chat_id: int, text: str, reply_markup: dict | None = None):
    payload = {"chat_id": chat_id, "text": text[:4000]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(_SEND_MESSAGE_API.format(token=BOT_TOKEN), json=payload)
            if resp.status_code >= 400:
                logger.warning("telegram push failed for chat_id=%s: %s", chat_id, resp.text[:200])
    except Exception:
        logger.exception("telegram push errored for chat_id=%s", chat_id)

def push(chat_id: int, text: str, reply_markup: dict | None = None):
    """فرستادن fire-and-forget — نباید جلوی جواب API را بگیرد یا اگر کاربر بات را
    بلاک کرده باشد کل اکشن (لشکرکشی، جنگ، ...) را خراب کند"""
    if DEV_MODE or not BOT_TOKEN:
        return
    task = asyncio.create_task(_post_message(chat_id, text, reply_markup))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

async def register_webhook():
    """موقع بالاآمدن سرور یک‌بار صدا زده می‌شود — آدرس همین بک‌اند را به تلگرام
    به‌عنوان webhook معرفی می‌کند تا از این به بعد /start (و بقیهٔ پیام‌ها) به
    routers/bot.py برسد. بدون PUBLIC_BASE_URL کاری نمی‌کند (یعنی /start خاموش می‌ماند)"""
    if DEV_MODE or not BOT_TOKEN or not PUBLIC_BASE_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                _SET_WEBHOOK_API.format(token=BOT_TOKEN),
                json={"url": PUBLIC_BASE_URL + TELEGRAM_WEBHOOK_PATH, "secret_token": WEBHOOK_SECRET},
            )
            if resp.status_code >= 400:
                logger.warning("telegram setWebhook failed: %s", resp.text[:300])
            else:
                logger.info("telegram webhook registered at %s", PUBLIC_BASE_URL + TELEGRAM_WEBHOOK_PATH)
    except Exception:
        logger.exception("telegram setWebhook errored")
