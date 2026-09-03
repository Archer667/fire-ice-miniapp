"""برچسب یکپارچهٔ شخصیت در پیام‌ها و اعلان‌ها."""

import re
from datetime import datetime, timedelta, timezone

_LABEL_CACHE: tuple[datetime, list[dict]] | None = None
_LABEL_CACHE_TTL = timedelta(seconds=60)


def honorific(player: dict | None = None, *, gender: str | None = None) -> str:
    resolved = (player or {}).get("gender") or gender
    return "لیدی" if resolved == "lady" else "لرد"


def titled_name(player: dict | None = None, *, name: str | None = None, gender: str | None = None) -> str:
    resolved_name = (player or {}).get("name") or name or "نامشخص"
    return f"{honorific(player, gender=gender)} {resolved_name}"


async def normalize_player_names(text: str | None) -> str | None:
    """نام بازیکن‌های شناخته‌شده را در هر اعلان با عنوان درست یکدست می‌کند.

    این لایه علاوه بر مسیرهای تازه، متن رکوردهای قدیمی‌ای را هم که هنوز «لرد» را
    ثابت نوشته‌اند اصلاح می‌کند. کش کوتاه از کوئری تکراری در اعلان‌های همگانی
    جلوگیری می‌کند.
    """
    if not text:
        return text
    global _LABEL_CACHE
    current = datetime.now(timezone.utc).replace(tzinfo=None)
    if _LABEL_CACHE is None or current - _LABEL_CACHE[0] >= _LABEL_CACHE_TTL:
        # import تنبل، تا توابع سادهٔ برچسب‌گذاری مستقل از اتصال دیتابیس بمانند.
        from db import players
        rows = await players.find(
            {"name": {"$exists": True, "$ne": ""}}, {"name": 1, "gender": 1},
        ).to_list(None)
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("name", "")).strip(), []).append(row)
        # اگر دو اکانت دقیقاً یک نام ولی جنسیت متفاوت داشته باشند، متن بدون tg_id
        # به‌تنهایی قابل تشخیص نیست؛ در این حالت حدس اشتباه نمی‌زنیم.
        safe_rows = [
            group[0] for name, group in grouped.items()
            if name and len({row.get("gender", "lord") for row in group}) == 1
        ]
        safe_rows.sort(key=lambda row: len(str(row.get("name", ""))), reverse=True)
        _LABEL_CACHE = (current, safe_rows)
    normalized = text
    for player in _LABEL_CACHE[1]:
        name = str(player.get("name", "")).strip()
        if not name:
            continue
        pattern = re.compile(rf"(?<![\w\u200c])(?:(?:لرد|لیدی)\s+)?{re.escape(name)}(?![\w\u200c])")
        normalized = pattern.sub(titled_name(player), normalized)
    return normalized
