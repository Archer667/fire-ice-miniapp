from datetime import timedelta

from config import ADMIN_IDS, OWNER_ID
from db import admin_roles, admin_notifications, campaigns, roleplays, rebellions
from game import now
import telegram_bot


async def _admin_ids(roles: tuple[str, ...] | None = None) -> set[int]:
    """گیرنده‌های اعلان؛ در صورت تعیین roles فقط همان سطح‌ها را برمی‌گرداند."""
    ids = set(ADMIN_IDS) if roles is None or "full" in roles else set()
    if OWNER_ID is not None:
        if roles is None or "owner" in roles:
            ids.add(OWNER_ID)
        else:
            ids.discard(OWNER_ID)
    async for row in admin_roles.find({}, {"tg_id": 1, "role": 1}):
        if roles is None or row.get("role") in roles:
            ids.add(row["tg_id"])
        else:
            ids.discard(row["tg_id"])
    return ids


async def notify_admins(
    kind: str,
    title: str,
    detail: str,
    *,
    dedupe_key: str,
    priority: str = "normal",
    player_name: str | None = None,
    player_tg_id: int | None = None,
    castle: str | None = None,
    action: str | None = None,
    source_id: str | None = None,
    deadline=None,
    audience_roles: tuple[str, ...] | None = None,
):
    """اعلان ماندگار پنل را می‌سازد و خلاصه را برای سطح‌های مجاز تلگرام می‌کند."""
    doc = {
        "kind": kind,
        "title": title,
        "detail": detail,
        "priority": priority,
        "player_name": player_name,
        "player_tg_id": player_tg_id,
        "castle": castle,
        "action": action,
        "source_id": source_id,
        "deadline": deadline,
        "created_at": now(),
        "read_by": [],
        "audience_roles": list(audience_roles) if audience_roles else None,
    }
    claimed = await admin_notifications.update_one(
        {"dedupe_key": dedupe_key},
        {"$setOnInsert": {**doc, "dedupe_key": dedupe_key}},
        upsert=True,
    )
    if claimed.upserted_id is None:
        return False

    message = f"{title}\n{detail}"
    if action:
        message += f"\nاقدام پیشنهادی: {action}"
    for tg_id in await _admin_ids(audience_roles):
        telegram_bot.push(tg_id, message)
    return True


async def notify_admin_deadlines():
    """یادآوری کنترل‌شده برای پرونده‌هایی که کمتر از دو ساعت تا پایان مهلت‌شان مانده."""
    current = now()
    soon = current + timedelta(hours=2)

    async for row in rebellions.find({
        "status": {"$in": ["awaiting_roleplay", "roleplay_submitted"]},
        "deadline": {"$gt": current, "$lte": soon},
    }):
        await notify_admins(
            "rebellion_deadline",
            "⏳ مهلت شورش رو به پایان است",
            f"{row.get('player_name', 'بازیکن')} در {row.get('castle') or 'قلعه نامشخص'} کمتر از دو ساعت فرصت دارد."
            + (" رولش را فرستاده و منتظر داوری است." if row.get("status") == "roleplay_submitted" else " هنوز رولش را نفرستاده."),
            dedupe_key=f"rebellion-deadline:{row['_id']}",
            priority="high",
            player_name=row.get("player_name"),
            player_tg_id=row.get("tg_id"),
            castle=row.get("castle"),
            action="پرونده را در تب شورش‌ها بررسی کن.",
            source_id=str(row["_id"]),
            deadline=row.get("deadline"),
        )

    # مهلت رول جنگ از زمان رسیدن لشکر شروع می‌شود.
    from routers.war import ATTACK_OP_TYPES, ROLEPLAY_WINDOW_HOURS
    cutoff = current - timedelta(hours=ROLEPLAY_WINDOW_HOURS)
    async for campaign in campaigns.find({
        "op_type": {"$in": list(ATTACK_OP_TYPES)},
        "arrival_at": {"$gt": cutoff, "$lte": current},
    }):
        deadline = campaign["arrival_at"] + timedelta(hours=ROLEPLAY_WINDOW_HOURS)
        if deadline > soon:
            continue
        battle_id = campaign.get("engagement_campaign_id") or str(campaign["_id"])
        submitted = await roleplays.count_documents({"campaign_id": battle_id})
        if submitted >= 2:
            continue
        await notify_admins(
            "war_deadline",
            "⏳ مهلت رول جنگ رو به پایان است",
            f"نبرد «{campaign.get('name') or 'بدون نام'}» در {campaign.get('target_castle')} کمتر از دو ساعت مهلت دارد؛ {submitted} طرف از ۲ طرف رول فرستاده.",
            dedupe_key=f"war-deadline:{battle_id}",
            priority="high",
            player_name=campaign.get("player_name"),
            player_tg_id=campaign.get("tg_id"),
            castle=campaign.get("target_castle"),
            action="رول‌های نبرد را بررسی کن و در صورت نیاز به طرفین یادآوری کن.",
            source_id=battle_id,
            deadline=deadline,
        )
