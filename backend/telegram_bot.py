"""پوش واقعی تلگرام — علاوه بر ذخیرهٔ نامه در صندوق کلاغ‌های داخل اپ، یک پیام
واقعی به چت تلگرام بازیکن می‌فرستد تا حتی وقتی اپ بسته است هم از رویدادهای
مهم (رسیدن لشکر، نتیجهٔ جنگ/جاسوسی/رول، شایعه، نامه) خبردار شود."""
import asyncio
import logging
import httpx
from config import BOT_TOKEN, DEV_MODE

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
# ارجاع نگه‌داشته می‌شود چون asyncio تسک‌های بدون ارجاعِ قوی را ممکن است زودتر از
# اتمام garbage-collect کند
_background_tasks: set[asyncio.Task] = set()

async def _post_message(chat_id: int, text: str):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                _TELEGRAM_API.format(token=BOT_TOKEN),
                json={"chat_id": chat_id, "text": text[:4000]},
            )
            if resp.status_code >= 400:
                logger.warning("telegram push failed for chat_id=%s: %s", chat_id, resp.text[:200])
    except Exception:
        logger.exception("telegram push errored for chat_id=%s", chat_id)

def push(chat_id: int, text: str):
    """فرستادن fire-and-forget — نباید جلوی جواب API را بگیرد یا اگر کاربر بات را
    بلاک کرده باشد کل اکشن (لشکرکشی، جنگ، ...) را خراب کند"""
    if DEV_MODE or not BOT_TOKEN:
        return
    task = asyncio.create_task(_post_message(chat_id, text))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
