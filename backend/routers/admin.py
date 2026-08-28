import random
import re
import html
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin, get_full_admin, get_owner
from db import (
    campaigns, ambushes, players, admin_roles, map_castles, market_listings, black_market_listings,
    spy_missions, roleplays, items, item_grants, alliances, game_settings,
    caravans, messages, rumors, hierarchy, polls, rebellions, rebellion_checks, admin_notifications,
)
import game_data
import telegram_bot
from game import now, add_resources, building_levels_for, effective_caps, resolve_building_upgrades, owned_castles, castle_building_state, normalize_building_state
from medals import MEDALS, TIER_ORDER, bump_player_stat, medal_rows, normalize_stats
from game_data import REGIONS, COMMON_TROOPS, TRADE_GOODS, BUILDINGS, ROLEPLAY_CATEGORIES, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, ALLIANCE_TYPES, CASTLE_HOUSES, MAP_TERRAINS, building_produces, building_cap_bonus, building_base_cost, building_cost_step, building_cost, building_max_level, TROOP_WEAPON_KEY, WEAPON_PER_SOLDIER, campaign_power, SIEGE_EQUIPMENT
from config import ADMIN_IDS, STARTING_RESOURCES, POPULARITY_START, TAX_RATE_DEFAULT, DEFAULT_TITLE
from routers.war import OP_TYPES, DEFENSE_OP_TYPES, get_war_window, WAR_WINDOW_ID, all_castle_terrain, owner_of_castle, battle_army_snapshot
from routers.ravens import send_system_message
from routers.rebellions import get_settings as get_rebellion_settings
from admin_notifications import notify_admins

router = APIRouter(prefix="/api/admin", tags=["admin"])
MUSIC_SETTINGS_ID = "background_music"
MAX_MUSIC_DATA_URL_CHARS = 10_000_000
ROLEPLAY_RESOURCE_NAMES = {
    "gold": "طلا", "wood": "چوب", "stone": "سنگ", "iron": "آهن", "food": "غذا", "wine": "شراب", "men": "نیروی انسانی",
    "weapon_sword": "شمشیر", "weapon_spear": "نیزه", "weapon_archer": "کمان", "weapon_lcav": "تجهیزات سواره‌نظام سبک", "weapon_hcav": "تجهیزات سواره‌نظام سنگین",
}

class MusicSettingsBody(BaseModel):
    enabled: bool = False
    title: str = "موسیقی والریا"
    audio_url: str = ""
    volume: int = 35
    loop: bool = True
    autoplay: bool = True

@router.get("/music")
async def admin_music_settings(user: dict = Depends(get_user)):
    user = await get_full_admin(user)
    doc = await game_settings.find_one({"_id": MUSIC_SETTINGS_ID}) or {}
    return {
        "enabled": bool(doc.get("enabled", False)), "title": doc.get("title", "موسیقی والریا"),
        "audio_url": doc.get("audio_url", ""), "volume": int(doc.get("volume", 35)),
        "loop": bool(doc.get("loop", True)), "autoplay": bool(doc.get("autoplay", True)),
    }

@router.post("/music")
async def save_admin_music_settings(body: MusicSettingsBody, user: dict = Depends(get_user)):
    user = await get_full_admin(user)
    source = body.audio_url.strip()
    if source and not (source.startswith("data:audio/") or source.startswith("https://")):
        raise HTTPException(400, "فایل صوتی یا لینک امن https وارد کن")
    if len(source) > MAX_MUSIC_DATA_URL_CHARS:
        raise HTTPException(400, "حجم فایل موسیقی زیاد است؛ فایل باید حداکثر حدود ۷ مگابایت باشد")
    if body.enabled and not source:
        raise HTTPException(400, "برای فعال‌کردن موسیقی ابتدا فایل یا لینک آن را وارد کن")
    doc = {
        "enabled": body.enabled, "title": body.title.strip()[:80] or "موسیقی والریا",
        "audio_url": source, "volume": max(0, min(100, body.volume)),
        "loop": body.loop, "autoplay": body.autoplay, "updated_at": now(),
        "updated_by": user["id"],
    }
    await game_settings.update_one({"_id": MUSIC_SETTINGS_ID}, {"$set": doc}, upsert=True)
    return {k: v for k, v in doc.items() if k not in ("updated_at", "updated_by")}

async def admin_user(user: dict = Depends(get_user)):
    """ادمین کامل یا محدود — برای سناریوها"""
    return await get_admin(user)

async def full_admin_user(user: dict = Depends(get_user)):
    """فقط ادمین کامل — برای مدیریت ادمین‌ها"""
    return await get_full_admin(user)

async def owner_user(user: dict = Depends(get_user)):
    """فقط صاحبِ بازی — برای ری‌استارت کامل"""
    return await get_owner(user)

@router.get("/notifications")
async def list_admin_notifications(user: dict = Depends(admin_user)):
    out = []
    async for row in admin_notifications.find({}).sort("created_at", -1).limit(100):
        out.append({
            "id": str(row["_id"]), "kind": row.get("kind", "general"),
            "title": row.get("title", "اعلان مدیریتی"), "detail": row.get("detail", ""),
            "priority": row.get("priority", "normal"), "player_name": row.get("player_name"),
            "player_tg_id": row.get("player_tg_id"), "castle": row.get("castle"),
            "action": row.get("action"), "source_id": row.get("source_id"),
            "deadline": row["deadline"].isoformat() if row.get("deadline") else None,
            "created_at": row["created_at"].isoformat(),
            "read": user["id"] in row.get("read_by", []),
        })
    return out


@router.post("/notifications/read-all")
async def read_all_admin_notifications(user: dict = Depends(admin_user)):
    await admin_notifications.update_many(
        {"read_by": {"$ne": user["id"]}},
        {"$addToSet": {"read_by": user["id"]}},
    )
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
async def read_admin_notification(notification_id: str, user: dict = Depends(admin_user)):
    try:
        oid = ObjectId(notification_id)
    except Exception:
        raise HTTPException(400, "شناسه اعلان نامعتبر است")
    result = await admin_notifications.update_one({"_id": oid}, {"$addToSet": {"read_by": user["id"]}})
    if not result.matched_count:
        raise HTTPException(404, "اعلان پیدا نشد")
    return {"ok": True}


@router.get("/rumors")
async def admin_list_rumors(user: dict = Depends(admin_user)):
    out = []
    async for row in rumors.find({}).sort("created_at", -1).limit(200):
        reactions = row.get("reactions", {})
        out.append({
            "id": str(row["_id"]),
            "author_tg_id": row.get("author_tg_id"),
            "author_name": row.get("author_name", "نامشخص"),
            "target_tg_id": row.get("target_tg_id"),
            "target_name": row.get("target_name", "نامشخص"),
            "text": row.get("text", ""),
            "likes": sum(1 for value in reactions.values() if value == "like"),
            "dislikes": sum(1 for value in reactions.values() if value == "dislike"),
            "created_at": row["created_at"].isoformat(),
        })
    return out


@router.delete("/rumors/{rumor_id}")
async def admin_delete_rumor(rumor_id: str, user: dict = Depends(admin_user)):
    try:
        oid = ObjectId(rumor_id)
    except Exception:
        raise HTTPException(400, "شناسه توییت نامعتبر است")
    result = await rumors.delete_one({"_id": oid})
    if not result.deleted_count:
        raise HTTPException(404, "توییت پیدا نشد")
    return {"ok": True}


@router.get("/cleanup/preview")
async def cleanup_preview(user: dict = Depends(full_admin_user)):
    return {
        "messages": await messages.count_documents({}),
        "rumors": await rumors.count_documents({}),
        "campaigns": await campaigns.count_documents({"active": {"$ne": True}}),
        "reports": (
            await spy_missions.count_documents({"resolved": True})
            + await roleplays.count_documents({"resolved": True, "category": {"$ne": "security"}})
        ),
        "protected": {
            "active_campaigns": await campaigns.count_documents({"active": True}),
            "pending_spy": await spy_missions.count_documents({"resolved": {"$ne": True}}),
            "pending_roleplays": await roleplays.count_documents({"resolved": {"$ne": True}}),
        },
    }


class CleanupBody(BaseModel):
    category: str
    confirm: str


@router.post("/cleanup")
async def cleanup_data(body: CleanupBody, user: dict = Depends(full_admin_user)):
    labels = {
        "messages": ("MESSAGES", "پیام"),
        "rumors": ("RUMORS", "توییت"),
        "campaigns": ("CAMPAIGNS", "لشکرکشی بسته"),
        "reports": ("REPORTS", "گزارش حل‌شده"),
    }
    if body.category not in labels:
        raise HTTPException(400, "نوع پاک‌سازی نامعتبر است")
    expected, label = labels[body.category]
    if body.confirm.strip() != expected:
        raise HTTPException(400, f"برای تایید باید دقیقاً {expected} را وارد کنی")

    if body.category == "messages":
        deleted = (await messages.delete_many({})).deleted_count
    elif body.category == "rumors":
        deleted = (await rumors.delete_many({})).deleted_count
    elif body.category == "campaigns":
        deleted = (await campaigns.delete_many({"active": {"$ne": True}})).deleted_count
    else:
        spy_deleted = (await spy_missions.delete_many({"resolved": True})).deleted_count
        # رول امنیتی آرشیو دائمی است و با پاک‌سازی گزارش‌های حل‌شده حذف نمی‌شود.
        roleplay_deleted = (await roleplays.delete_many({"resolved": True, "category": {"$ne": "security"}})).deleted_count
        deleted = spy_deleted + roleplay_deleted

    return {"ok": True, "deleted": deleted, "label": label}


@router.get("/campaigns")
async def list_campaigns(user: dict = Depends(admin_user)):
    """اطلاعات کامل لشکرکشی‌ها برای ادمین — فقط نمایشی، بدون تایید/رد"""
    out = []
    cur = campaigns.find({}).sort("created_at", -1).limit(50)
    async for s in cur:
        troops = [
            {"name": COMMON_TROOPS[tid]["name"] if tid in COMMON_TROOPS else tid, "count": n}
            for tid, n in s["troops"].items() if n and n > 0
        ]
        arrival_at = s.get("arrival_at")
        target_owner = None
        if s["target_castle"] != s["origin_castle"]:
            target_owner = await owner_of_castle(s["target_castle"])
        out.append({
            "id": str(s["_id"]), "player": s["player_name"], "tg_id": s["tg_id"],
            "from": s["origin_castle"], "to": s["target_castle"],
            "target_tg_id": target_owner["tg_id"] if target_owner else None,
            "target_player": target_owner["name"] if target_owner else None,
            "op_type": s["op_type"], "op_name": OP_TYPES.get(s["op_type"], {}).get("name", s["op_type"]),
            "name": s.get("name") or OP_TYPES.get(s["op_type"], {}).get("name", s["op_type"]),
            "troops": troops, "power": s.get("power", 0),
            "gold_cost": s["gold_cost"], "men_committed": s["men_committed"], "food_per_day": s["food_per_day"],
            "travel_minutes": s.get("travel_minutes", 0),
            "arrived": (now() >= arrival_at) if arrival_at else True,
            "active": s.get("active", False),
            "created_at": s["created_at"].isoformat(),
        })
    return out

@router.get("/espionage")
async def list_spy_pending(user: dict = Depends(admin_user)):
    """سناریوهای جاسوسی که بازیکنان فرستاده‌اند و هنوز امتیازدهی نشده‌اند"""
    out = []
    cur = spy_missions.find({"resolved": False}).sort("created_at", -1).limit(50)
    async for m in cur:
        out.append({
            "id": str(m["_id"]), "player": m["player_name"], "tg_id": m["tg_id"],
            "origin": m["origin_castle"], "target": m["target_castle"],
            "scenario": m["scenario"], "arrived": now() >= m["arrival_at"],
            "created_at": m["created_at"].isoformat(),
        })
    return out

@router.get("/espionage/resolved")
async def list_spy_resolved(user: dict = Depends(admin_user)):
    """سناریوهای جاسوسی‌ای که قبلاً امتیازدهی شده‌اند — برای مرور نتیجه‌ای که ادمین
    خودش قبلاً داده، چون بعد از امتیازدهی از لیست «در انتظار» ناپدید می‌شوند"""
    out = []
    cur = spy_missions.find({"resolved": True}).sort("resolved_at", -1).limit(50)
    async for m in cur:
        out.append({
            "id": str(m["_id"]), "player": m["player_name"], "tg_id": m["tg_id"],
            "target": m["target_castle"], "scenario": m["scenario"],
            "admin_score": m.get("admin_score"), "success": m.get("success"),
            "resolved_at": m["resolved_at"].isoformat() if m.get("resolved_at") else None,
        })
    return out

class SpyScoreBody(BaseModel):
    score: int

@router.post("/espionage/{mission_id}/score")
async def score_spy(mission_id: str, body: SpyScoreBody, user: dict = Depends(admin_user)):
    """ادمین سناریو را می‌خواند و امتیاز جاسوسی (۰ تا ۱۰۰) می‌دهد — همان امتیاز
    مستقیماً شانس موفقیت است؛ نتیجه فوراً برای بازیکن کلاغ می‌شود"""
    if not (0 <= body.score <= 100):
        raise HTTPException(400, "امتیاز باید بین ۰ تا ۱۰۰ باشد")
    try:
        oid = ObjectId(mission_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ ماموریت نامعتبر است")
    m = await spy_missions.find_one({"_id": oid})
    if not m:
        raise HTTPException(404, "این ماموریت پیدا نشد")
    if m.get("resolved"):
        raise HTTPException(400, "این ماموریت قبلاً امتیازدهی شده")

    success = random.random() * 100 < body.score
    spy_player = await players.find_one({"tg_id": m["tg_id"]})
    target = await players.find_one({"tg_id": m["target_tg_id"]})

    report = None
    if success and target:
        # فقط ساختمان‌های همون قلعه‌ای که جاسوس واقعاً بهش نفوذ کرده — نه کلِ
        # امپراتوریِ هدف؛ منابع (که سراسری/مشترکه، نه قلعه‌ای) استثناست
        levels = dict(building_levels_for(target, m["target_castle"]))
        military = [{"name": BUILDINGS[bid]["name"], "level": lvl}
                    for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") in ("barracks", "armory")]
        defense = [{"name": BUILDINGS[bid]["name"], "level": lvl}
                   for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") == "defense"]
        camps = []
        async for c in campaigns.find({
            "tg_id": target["tg_id"], "active": True,
            "$or": [{"origin_castle": m["target_castle"]}, {"target_castle": m["target_castle"]}],
        }):
            camps.append({
                "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
                "origin": c["origin_castle"], "target": c["target_castle"],
                "men_committed": c["men_committed"],
                "arrived": now() >= c.get("arrival_at", now()),
            })
        report = {"resources": target["resources"], "military": military, "defense": defense, "campaigns": camps}

    await spy_missions.update_one({"_id": m["_id"]}, {"$set": {
        "admin_score": body.score, "success": success, "report": report,
        "resolved": True, "resolved_at": now(),
    }})

    if spy_player:
        if success:
            await bump_player_stat(spy_player["tg_id"], "successful_spies")
            add_resources(spy_player, {"men": m["men_sent"]})
            await players.update_one({"tg_id": spy_player["tg_id"]}, {"$set": {"resources": spy_player["resources"]}})
            await send_system_message(
                spy_player["tg_id"], spy_player["name"],
                f"جاسوس‌های تو با موفقیت به {m['target_castle']} نفوذ کردند و گزارش کاملی به دست آوردند — نتیجه در بخش جاسوسی منتظر توست.",
            )
        else:
            await send_system_message(
                spy_player["tg_id"], spy_player["name"],
                f"جاسوسی تو در {m['target_castle']} شناسایی و دستگیر شد — نفرات اعزامی برنگشتند.",
            )
    if not success and target:
        await send_system_message(
            target["tg_id"], target["name"],
            f"جاسوسی از سوی {m['player_name']} در تلاش برای نفوذ به {m['target_castle']} شناسایی و دستگیر شد.",
        )

    return {"ok": True, "success": success}

@router.get("/roleplay")
async def list_roleplay_pending(user: dict = Depends(admin_user)):
    """رول‌های بازیکنان که هنوز ادمین نتیجه‌شان را ننوشته — برای دستهٔ «جنگ» طرف
    مقابلِ همان نبرد (اگر او هم سناریواش را فرستاده باشد) هم برای مقایسه نشان داده می‌شود"""
    out = []
    cur = roleplays.find({"resolved": False}).sort("created_at", -1).limit(50)
    async for r in cur:
        actor = await players.find_one({"tg_id": r["tg_id"]})
        target = await players.find_one({"tg_id": r.get("target_tg_id")}) if r.get("target_tg_id") else None
        def player_state(player):
            if not player:
                return None
            return {
                "tg_id": player["tg_id"], "name": player["name"],
                "popularity": max(0, min(100, int(player.get("popularity", POPULARITY_START)))),
                "resources": {key: round(player.get("resources", {}).get(key, 0)) for key in PLAYER_RESOURCE_KEYS},
            }
        row = {
            "id": str(r["_id"]), "player": r["player_name"], "tg_id": r["tg_id"], "castle": r["castle"],
            "category": r["category"], "category_name": ROLEPLAY_CATEGORIES.get(r["category"], r["category"]),
            "text": r["text"], "campaign_id": r.get("campaign_id"), "sibling": None,
            "created_at": r["created_at"].isoformat(), "war": None,
            "actor_state": player_state(actor) if r["category"] in ("economy", "sabotage") else None,
            "target_state": player_state(target) if r["category"] == "sabotage" else None,
            "target_tg_id": r.get("target_tg_id"), "target_player_name": r.get("target_player_name"),
        }
        if r["category"] == "war" and r.get("campaign_id"):
            sib = await roleplays.find_one({"category": "war", "campaign_id": r["campaign_id"], "tg_id": {"$ne": r["tg_id"]}})
            if sib:
                row["sibling"] = {"player": sib["player_name"], "tg_id": sib["tg_id"], "text": sib["text"], "resolved": sib.get("resolved", False)}
            try:
                campaign = await campaigns.find_one({"_id": ObjectId(r["campaign_id"])})
            except Exception:
                campaign = None
            if campaign:
                attacker = await players.find_one({"tg_id": campaign["tg_id"]})
                defender = await owner_of_castle(campaign["target_castle"])
                row["war"] = {
                    "campaign_id": r["campaign_id"],
                    "attacker_tg_id": campaign["tg_id"],
                    "attacker_name": attacker["name"] if attacker else campaign.get("player_name", "مهاجم"),
                    "defender_tg_id": defender["tg_id"] if defender else None,
                    "defender_name": defender["name"] if defender else "مدافع نامشخص",
                    "target_castle": campaign["target_castle"],
                    "attacker_army": {
                        "campaign_id": str(campaign["_id"]),
                        "men": campaign.get("men_committed", sum(campaign.get("troops", {}).values())),
                        "troops": [
                            {"id": tid, "name": COMMON_TROOPS.get(tid, {}).get("name", tid), "count": n}
                            for tid, n in campaign.get("troops", {}).items() if n and n > 0
                        ],
                    },
                    "defender_armies": [],
                }
                if defender:
                    async for dc in campaigns.find({
                        "tg_id": defender["tg_id"], "active": True,
                        "op_type": {"$in": list(DEFENSE_OP_TYPES)},
                        "target_castle": campaign["target_castle"],
                        "arrival_at": {"$lte": now()},
                    }):
                        row["war"]["defender_armies"].append({
                            "campaign_id": str(dc["_id"]), "name": dc.get("name", "لشکر دفاعی"),
                            "men": dc.get("men_committed", sum(dc.get("troops", {}).values())),
                            "troops": [
                                {"id": tid, "name": COMMON_TROOPS.get(tid, {}).get("name", tid), "count": n}
                                for tid, n in dc.get("troops", {}).items() if n and n > 0
                            ],
                        })
        out.append(row)
    return out

@router.get("/ambushes")
async def admin_list_ambushes(user: dict = Depends(admin_user)):
    out = []
    async for a in ambushes.find({}).sort("created_at", -1).limit(100):
        out.append({
            "id": str(a["_id"]), "player": a["player_name"], "tg_id": a["tg_id"],
            "origin_castle": a["origin_castle"], "target_castle": a["target_castle"],
            "scenario": a["scenario"], "troops": [
                {"id": tid, "name": COMMON_TROOPS.get(tid, {}).get("name", tid), "count": count}
                for tid, count in a.get("troops", {}).items() if count
            ],
            "men_committed": a.get("soldiers_committed", a["men_committed"]), "status": a["status"],
            "coefficient": a.get("coefficient"), "casualties": a.get("casualties"),
            "ambush_score": a.get("ambush_score"), "ambusher_losses": a.get("ambusher_losses"),
            "refund": a.get("refund"), "victim_name": a.get("victim_name"),
        })
    return out

class AmbushScoreBody(BaseModel):
    coefficient: float
    ambush_score: int

@router.post("/ambushes/{ambush_id}/score")
async def admin_score_ambush(ambush_id: str, body: AmbushScoreBody, user: dict = Depends(admin_user)):
    if body.coefficient < 0 or body.coefficient > 10:
        raise HTTPException(400, "ضریب کمین باید بین صفر تا ۱۰ باشد")
    if body.ambush_score < 0 or body.ambush_score > 100:
        raise HTTPException(400, "امتیاز کمین باید بین صفر تا ۱۰۰ باشد")
    try:
        oid = ObjectId(ambush_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ کمین نامعتبر است")
    a = await ambushes.find_one({"_id": oid, "status": "pending_score"})
    if not a:
        raise HTTPException(404, "کمین منتظر امتیاز پیدا نشد")
    await ambushes.update_one({"_id": oid, "status": "pending_score"}, {"$set": {
        "coefficient": round(body.coefficient, 2), "ambush_score": body.ambush_score,
        "status": "active", "scored_at": now(), "scored_by": user["id"],
    }})
    owner = await players.find_one({"tg_id": a["tg_id"]}, {"tg_id": 1, "name": 1})
    if owner:
        await send_system_message(owner["tg_id"], owner["name"], f"کمینت در مسیر {a['origin_castle']} — {a['target_castle']} با ضریب {body.coefficient:g} و امتیاز {body.ambush_score} آماده شد.", kind="ambush")
    return {"ok": True, "status": "active"}

@router.get("/roleplay/security")
async def search_security_roleplays(q: str = "", tg_id: int | None = None, user: dict = Depends(admin_user)):
    """آرشیو رول‌های دفاعی/امنیتی؛ نتیجه ندارند و صرفاً با نام بازیکن یا متن قابل جست‌وجویند."""
    query = {"category": "security"}
    if tg_id is not None:
        query["tg_id"] = tg_id
    term = q.strip()
    if term:
        safe = re.escape(term[:100])
        query["$or"] = [{"player_name": {"$regex": safe, "$options": "i"}}, {"text": {"$regex": safe, "$options": "i"}}]
    out = []
    async for row in roleplays.find(query).sort("created_at", -1).limit(200):
        out.append({
            "id": str(row["_id"]), "tg_id": row["tg_id"],
            "player": row.get("player_name", "نامشخص"), "castle": row.get("castle"),
            "text": row.get("text", ""), "created_at": row["created_at"].isoformat(),
        })
    return out

async def _battle_root(battle_id: str):
    """ریشهٔ پروندهٔ جدید را با شناسهٔ مستقل نبرد پیدا می‌کند؛ پرونده‌های قدیمی هم پشتیبانی می‌شوند."""
    root = await campaigns.find_one({"engagement_campaign_id": battle_id, "battle_is_root": True})
    if root:
        return root
    try:
        return await campaigns.find_one({"_id": ObjectId(battle_id)})
    except Exception:
        return None

def _battle_member_ids(root: dict) -> list[ObjectId]:
    """تمام شناسه‌هایی که ممکن است عضو پرونده باشند؛ برای داده‌های جدید و قدیمی."""
    raw_ids = [
        str(root["_id"]), root.get("opponent_campaign_id"),
        *(root.get("battle_attacker_army_ids") or []),
        *(root.get("battle_defender_army_ids") or []),
    ]
    out = []
    for raw_id in raw_ids:
        if not raw_id:
            continue
        try:
            oid = ObjectId(raw_id)
        except Exception:
            continue
        if oid not in out:
            out.append(oid)
    return out

def _battle_members_query(root: dict, battle_id: str) -> dict:
    root_id = str(root["_id"])
    return {"$or": [
        {"_id": {"$in": _battle_member_ids(root)}},
        {"engagement_campaign_id": battle_id},
        {"battle_root_campaign_id": root_id},
    ]}

async def _close_battle_state(root: dict, battle_id: str, *, cancelled: bool = False):
    """پرونده را برای همهٔ اعضا یک‌جا می‌بندد تا هیچ قفل یا ریشهٔ یتیمی باقی نماند."""
    timestamp = now()
    state = {
        "engagement_locked": False, "battle_open": False,
        "battle_cancelled_at" if cancelled else "combat_resolved_at": timestamp,
    }
    return await campaigns.update_many(
        _battle_members_query(root, battle_id),
        {"$set": state, "$unset": {
            "engagement_campaign_id": "", "battle_root_campaign_id": "", "battle_is_root": "",
            "opponent_campaign_id": "", "opponent_tg_id": "",
        }},
    )

async def _dismiss_battle_record(root: dict, battle_id: str, message: str):
    """انحلال واحد و مشترک برای دکمهٔ نبرد و عملیات مستقیم روی لشکر."""
    member_query = _battle_members_query(root, battle_id)
    members = await campaigns.find(member_query, {"tg_id": 1}).to_list(None)
    changed = await _close_battle_state(root, battle_id, cancelled=True)
    await roleplays.update_many({"category": "war", "campaign_id": battle_id, "resolved": False}, {"$set": {
        "resolved": True, "resolved_at": now(), "result": message,
    }})
    recipients = {m.get("tg_id") for m in members} | {
        root.get("tg_id"), root.get("battle_defender_tg_id"), root.get("opponent_tg_id"),
        *(root.get("battle_participant_tg_ids") or []),
    }
    recipients.discard(None)
    async for participant in players.find({"tg_id": {"$in": list(recipients)}}):
        await send_system_message(participant["tg_id"], participant["name"], message)
    return changed

async def _dismiss_battle_for_campaign(campaign: dict, reason: str) -> bool:
    battle_id = campaign.get("engagement_campaign_id")
    if not battle_id and campaign.get("battle_is_root") and campaign.get("battle_open"):
        battle_id = str(campaign["_id"])
    if not battle_id:
        return False
    root = await _battle_root(battle_id)
    if not root:
        raw_root_id = campaign.get("battle_root_campaign_id")
        try:
            root = await campaigns.find_one({"_id": ObjectId(raw_root_id)}) if raw_root_id else None
        except Exception:
            root = None
    if not root or root.get("combat_resolved_at") or root.get("battle_cancelled_at"):
        return False
    await _dismiss_battle_record(root, battle_id, reason)
    return True

async def _remove_campaign_from_battle(campaign: dict, reason: str) -> dict:
    """فقط یک لشکر را از پروندهٔ گروهی جدا می‌کند؛ اگر یک سمت خالی شد پرونده پایان می‌یابد."""
    battle_id = campaign.get("engagement_campaign_id")
    if not battle_id:
        return {"removed": False, "battle_closed": False}
    root = await _battle_root(battle_id)
    if not root or root.get("combat_resolved_at") or root.get("battle_cancelled_at"):
        return {"removed": False, "battle_closed": False}
    campaign_id = str(campaign["_id"])
    side = "defender" if campaign_id in (root.get("battle_defender_army_ids") or []) else "attacker"
    await campaigns.update_one({"_id": root["_id"]}, {
        "$pull": {
            "battle_attacker_army_ids": campaign_id, "battle_defender_army_ids": campaign_id,
            "battle_attacker_snapshots": {"campaign_id": campaign_id}, "battle_defender_snapshot": {"campaign_id": campaign_id},
            "battle_attacker_joins": {"campaign_id": campaign_id}, "battle_defender_joins": {"campaign_id": campaign_id},
            "battle_joins": {"campaign_id": campaign_id},
        },
    })
    member_set = {"engagement_locked": False, "battle_left_at": now(), "battle_left_reason": reason}
    member_unset = {"battle_root_campaign_id": "", "opponent_campaign_id": "", "opponent_tg_id": ""}
    # سند ریشه هم پروندهٔ نبرد است هم یک لشکر. اگر همان لشکر خارج شد، هویت پرونده
    # را تا پایان داوری نگه می‌داریم ولی دیگر عضو/قفل‌شده حسابش نمی‌کنیم.
    if not campaign.get("battle_is_root"):
        member_set["battle_open"] = False
        member_unset.update({"engagement_campaign_id": "", "battle_is_root": ""})
    await campaigns.update_one({"_id": campaign["_id"]}, {"$set": member_set, "$unset": member_unset})
    root = await campaigns.find_one({"_id": root["_id"]})
    attacker_ids = root.get("battle_attacker_army_ids") or []
    defender_ids = root.get("battle_defender_army_ids") or []
    active_attackers = await campaigns.count_documents({"_id": {"$in": [ObjectId(x) for x in attacker_ids]}, "active": True}) if attacker_ids else 0
    active_defenders = await campaigns.count_documents({"_id": {"$in": [ObjectId(x) for x in defender_ids]}, "active": True}) if defender_ids else 0
    castle_owner = await owner_of_castle(root.get("battle_location") or root.get("target_castle"))
    if castle_owner and castle_owner.get("tg_id") == root.get("battle_defender_tg_id"):
        # صاحب قلعه حتی بدون لشکر جداگانه با زیرساخت دفاعی طرف نبرد باقی می‌ماند.
        active_defenders = max(1, active_defenders)
    remaining = await campaigns.find({"engagement_campaign_id": battle_id, "active": True}, {"tg_id": 1}).to_list(None)
    remaining_tg_ids = list({row["tg_id"] for row in remaining})
    await campaigns.update_one({"_id": root["_id"]}, {"$set": {"battle_participant_tg_ids": remaining_tg_ids}})
    battle_closed = active_attackers == 0 or active_defenders == 0
    message = f"لشکر «{campaign.get('name', 'بی‌نام')}» از نبرد خارج شد. {reason}"
    if battle_closed:
        message += " چون یکی از طرفین دیگر لشکر فعالی نداشت، پروندهٔ نبرد بدون نتیجه بسته شد."
        await _dismiss_battle_record(root, battle_id, message)
    else:
        recipients = set(remaining_tg_ids) | {campaign.get("tg_id")}
        async for participant in players.find({"tg_id": {"$in": list(recipients)}}):
            await send_system_message(participant["tg_id"], participant["name"], message, kind="battle")
    return {"removed": True, "battle_closed": battle_closed, "side": side}

@router.get("/battles")
async def list_open_battles(user: dict = Depends(admin_user)):
    """پرونده‌های نبرد مستقل از رول؛ بنابراین حتی با صفر رول هم قابل داوری‌اند."""
    out = []
    seen = set()
    cur = campaigns.find({
        "combat_resolved_at": {"$exists": False}, "battle_cancelled_at": {"$exists": False},
        "$or": [
            {"battle_open": True},
            {"engagement_locked": True},
            {"battle_started_at": {"$exists": True}, "opponent_campaign_id": {"$exists": True}},
        ],
    }).sort("arrival_at", -1).limit(150)
    async for c in cur:
        engagement_id = c.get("engagement_campaign_id") or str(c["_id"])
        if engagement_id in seen:
            continue
        seen.add(engagement_id)
        root = await _battle_root(engagement_id) or c
        attacker = await players.find_one({"tg_id": root["tg_id"]})
        defender = None
        defender_armies = []
        opponent_id = root.get("opponent_campaign_id")
        if opponent_id:
            try:
                opponent = await campaigns.find_one({"_id": ObjectId(opponent_id)})
            except Exception:
                opponent = None
            if opponent:
                defender = await players.find_one({"tg_id": opponent["tg_id"]})
                defender_armies.append(opponent)
        if root.get("battle_defender_tg_id"):
            defender = await players.find_one({"tg_id": root["battle_defender_tg_id"]})
        if not defender:
            defender = await owner_of_castle(root["target_castle"])
        defender_ids = root.get("battle_defender_army_ids") or []
        if defender_ids:
            defender_armies = [a async for a in campaigns.find({
                "_id": {"$in": [ObjectId(x) for x in defender_ids]}, "active": True,
                "engagement_locked": True, "engagement_campaign_id": engagement_id,
            })]
        elif "battle_defender_army_ids" not in root and root.get("battle_defender_snapshot") is not None:
            defender_armies = root.get("battle_defender_snapshot", [])
        elif defender and not defender_armies:
            defender_armies = [d async for d in campaigns.find({
                "tg_id": defender["tg_id"], "active": True,
                "op_type": {"$in": list(DEFENSE_OP_TYPES)}, "target_castle": root["target_castle"],
                "arrival_at": {"$lte": now()},
                # پرونده‌های قدیمی snapshot ندارند؛ دست‌کم فقط نیروهایی را نشان بده
                # که واقعاً با شناسهٔ همین نبرد قفل شده‌اند، نه تمام ارتش‌های قلعه.
                "engagement_campaign_id": engagement_id,
            })]
        rolls = []
        async for rp in roleplays.find({"category": "war", "campaign_id": engagement_id}):
            rolls.append({"id": str(rp["_id"]), "tg_id": rp["tg_id"], "player": rp["player_name"], "text": rp["text"]})
        army_row = lambda a: {
            "campaign_id": a.get("campaign_id") or str(a.get("_id", "")), "name": a.get("name", "لشکر"),
            "tg_id": a.get("tg_id"), "player_name": a.get("player_name", "مهاجم"),
            "men": a.get("men_committed", sum(a.get("troops", {}).values())),
            "troops": [{"id": tid, "name": COMMON_TROOPS.get(tid, {}).get("name", tid), "count": n} for tid, n in a.get("troops", {}).items() if n and n > 0],
            "equipment": [{"id": eid, "name": SIEGE_EQUIPMENT.get(eid, {}).get("name", eid), "count": n} for eid, n in a.get("equipment", {}).items() if n and n > 0],
        }
        attacker_ids = root.get("battle_attacker_army_ids") or []
        attacker_snapshots = [a async for a in campaigns.find({
            "_id": {"$in": [ObjectId(x) for x in attacker_ids]}, "active": True,
            "engagement_locked": True, "engagement_campaign_id": engagement_id,
        })] if attacker_ids else []
        if not attacker_snapshots and not root.get("battle_attacker_army_ids"):
            attacker_snapshots = list(root.get("battle_attacker_snapshots") or [])
            root_snapshot = root.get("battle_attacker_snapshot") or battle_army_snapshot(root)
            if not any(a.get("campaign_id") == str(root["_id"]) for a in attacker_snapshots):
                attacker_snapshots.insert(0, root_snapshot)
        battle_row = {
            "campaign_id": engagement_id, "name": root.get("name", "نبرد"),
            "location": root.get("battle_location") or root["target_castle"],
            "attacker_tg_id": root["tg_id"], "attacker_name": attacker["name"] if attacker else root.get("player_name", "طرف اول"),
            "defender_tg_id": defender["tg_id"] if defender else None,
            "defender_name": defender["name"] if defender else root.get("battle_defender_name", "بدون مدافع"),
            "attacker_army": army_row(root.get("battle_attacker_snapshot") or root), "defender_armies": [army_row(a) for a in defender_armies],
            "attacker_armies": [army_row(a) for a in attacker_snapshots],
            "attacker_joins": [{**j, "joined_at": j["joined_at"].isoformat() if j.get("joined_at") else None} for j in root.get("battle_attacker_joins", [])],
            "defender_joins": [{**j, "joined_at": j["joined_at"].isoformat() if j.get("joined_at") else None} for j in root.get("battle_defender_joins", [])],
            "battle_joins": [{**j, "joined_at": j["joined_at"].isoformat() if j.get("joined_at") else None} for j in root.get("battle_joins", [])],
            "defense_infrastructure": root.get("battle_defense_infrastructure", []),
            "rolls": rolls, "started_at": root.get("battle_started_at", root.get("arrival_at")).isoformat() if (root.get("battle_started_at") or root.get("arrival_at")) else None,
            "arrival_at": root["arrival_at"].isoformat() if root.get("arrival_at") else None,
        }
        out.append(battle_row)
        # repair اعلان: اگر پرونده در نسخهٔ قدیمی ساخته شده و اعلان لحظه‌ای‌اش جا افتاده،
        # اولین بار که پنل آن را بازیابی می‌کند فقط یک اعلان ماندگار/تلگرامی ساخته می‌شود.
        await notify_admins(
            "battle_started", "⚔️ نبرد باز نیاز به رسیدگی دارد",
            f"{battle_row['attacker_name']} در برابر {battle_row['defender_name']}\nمحل: {battle_row['location']}",
            dedupe_key=f"battle-started:{engagement_id}", priority="urgent",
            player_name=battle_row["attacker_name"], player_tg_id=battle_row["attacker_tg_id"],
            castle=battle_row["location"], source_id=engagement_id,
            action="در پنل ادمین ← نبردها، پرونده را بررسی یا منحل کن.",
        )
    return out

class RoleplayResultBody(BaseModel):
    result: str
    visibility: str = "participants"   # "participants" | "all" — چه کسی نتیجه را کلاغ می‌گیرد
    other_lords: list[int] = []
    winner_tg_id: int | None = None        # ادمین دستی مشخص می‌کند این رول بین چه لردهای دیگری هم بوده —
    winner_tg_ids: list[int] = []
    image_url: str | None = None
    attacker_losses: dict[str, int] = {}
    defender_losses: dict[str, int] = {}
    attacker_equipment_losses: dict[str, int] = {}
    defender_equipment_losses: dict[str, int] = {}
    attacker_army_losses: dict[str, dict[str, int]] = {}
    attacker_army_equipment_losses: dict[str, dict[str, int]] = {}
    defender_army_losses: dict[str, dict[str, int]] = {}
    defender_army_equipment_losses: dict[str, dict[str, int]] = {}
    actor_resource_deltas: dict[str, int] = {}
    actor_popularity_delta: int = 0
    target_resource_deltas: dict[str, int] = {}
    target_popularity_delta: int = 0
                                        # چون سناریوی یک لرد ممکن است به چند لرد دیگر اشاره کند، نه فقط
                                        # طرف مقابلِ خودکارِ لشکرکشی (که فقط برای دستهٔ «جنگ» پیدا می‌شود)

@router.post("/battles/{campaign_id}/dismiss")
async def dismiss_battle(campaign_id: str, user: dict = Depends(admin_user)):
    """انحلال اداری نبرد بدون برنده/تلفات؛ لشکرهای همان پرونده آزاد می‌شوند."""
    root = await _battle_root(campaign_id)
    if not root or root.get("combat_resolved_at") or root.get("battle_cancelled_at"):
        raise HTTPException(404, "پروندهٔ نبرد باز پیدا نشد")

    unlocked = await _dismiss_battle_record(root, campaign_id, "این نبرد توسط ادمین منحل شد و لشکرهای درگیر آزاد شدند.")
    return {"ok": True, "armies_unlocked": unlocked.modified_count}

@router.post("/battles/{campaign_id}/resolve")
async def resolve_battle_without_required_roll(campaign_id: str, body: RoleplayResultBody, user: dict = Depends(admin_user)):
    """اگر هیچ‌کدام رول نداده باشند، یک رکورد داوری سیستمی می‌سازد و همان مسیر امن نتیجه را اجرا می‌کند."""
    existing = await roleplays.find_one({"category": "war", "campaign_id": campaign_id, "resolved": False})
    if existing:
        return await respond_roleplay(str(existing["_id"]), body, user)
    campaign = await _battle_root(campaign_id)
    if not campaign or campaign.get("combat_resolved_at"):
        raise HTTPException(404, "پروندهٔ نبرد باز پیدا نشد")
    doc = {
        "tg_id": campaign["tg_id"], "player_name": campaign.get("player_name", "طرف اول"),
        "castle": campaign.get("origin_castle"), "category": "war",
        "text": "رولی از طرف بازیکنان ارسال نشد؛ نتیجه مستقیماً توسط ادمین ثبت شد.",
        "campaign_id": campaign_id, "result": None, "resolved": False, "created_at": now(),
        "admin_generated": True,
    }
    inserted = await roleplays.insert_one(doc)
    return await respond_roleplay(str(inserted.inserted_id), body, user)

async def _apply_campaign_losses(campaign: dict, losses: dict[str, int]):
    """تلفات را از ترکیب واقعی همان لشکر کم می‌کند؛ نفرات قبلاً موقع ساخت از منابع
    پلیر کم شده‌اند، بنابراین اینجا چیزی دوباره از منابع قلمرو کم نمی‌شود."""
    troops = dict(campaign.get("troops", {}))
    for tid, raw in losses.items():
        loss = int(raw or 0)
        if loss < 0:
            raise HTTPException(400, "تلفات نمی‌تواند منفی باشد")
        if tid not in troops and loss:
            raise HTTPException(400, f"نیروی {tid} در این لشکر وجود ندارد")
        if loss > int(troops.get(tid, 0)):
            raise HTTPException(400, f"تلفات {tid} از تعداد حاضر در لشکر بیشتر است")
        troops[tid] = int(troops.get(tid, 0)) - loss
    men = sum(max(0, int(n or 0)) for n in troops.values())
    owner = await players.find_one({"tg_id": campaign["tg_id"]})
    levels = dict(building_levels_for(owner, campaign.get("origin_castle"))) if owner else {}
    update = {"troops": troops, "men_committed": men, "power": campaign_power(troops, levels)}
    if men == 0:
        update.update({"active": False, "status": "destroyed", "engagement_locked": False})
    await campaigns.update_one({"_id": campaign["_id"]}, {"$set": update})

def _validate_campaign_losses(campaign: dict, losses: dict[str, int]):
    troops = campaign.get("troops", {})
    for tid, raw in losses.items():
        loss = int(raw or 0)
        if loss < 0 or (tid not in troops and loss) or loss > int(troops.get(tid, 0) or 0):
            raise HTTPException(400, f"تلفات {tid} از تعداد حاضر در لشکر بیشتر است")

async def _apply_equipment_losses(campaign: dict, losses: dict[str, int]):
    equipment = dict(campaign.get("equipment", {}))
    for eid, raw in losses.items():
        loss = int(raw or 0)
        if loss < 0 or loss > int(equipment.get(eid, 0)):
            raise HTTPException(400, f"تلفات ادوات {eid} از تعداد حاضر بیشتر است")
        equipment[eid] = int(equipment.get(eid, 0)) - loss
    equipment_power = sum(SIEGE_EQUIPMENT.get(eid, {}).get("siege_power", 0) * count for eid, count in equipment.items())
    await campaigns.update_one({"_id": campaign["_id"]}, {"$set": {"equipment": equipment, "equipment_power": equipment_power}})

def _validate_equipment_losses(campaign: dict, losses: dict[str, int]):
    equipment = campaign.get("equipment", {})
    for eid, raw in losses.items():
        loss = int(raw or 0)
        if loss < 0 or loss > int(equipment.get(eid, 0) or 0):
            raise HTTPException(400, f"تلفات ادوات {eid} از تعداد حاضر بیشتر است")

async def _apply_defender_losses(defender_tg_id: int, target_castle: str, engagement_id: str, losses: dict[str, int], army_ids: list[str] | None = None):
    """تلفات تجمیعی مدافع را میان لشکرهای دفاعی همان قلعه پخش می‌کند."""
    query = {
        "tg_id": defender_tg_id, "active": True,
        "op_type": {"$in": list(DEFENSE_OP_TYPES)}, "target_castle": target_castle,
        "engagement_campaign_id": engagement_id,
    }
    if army_ids:
        query["_id"] = {"$in": [ObjectId(x) for x in army_ids]}
    armies = [c async for c in campaigns.find(query).sort("created_at", 1)]
    available = {}
    for army in armies:
        for tid, n in army.get("troops", {}).items():
            available[tid] = available.get(tid, 0) + int(n or 0)
    for tid, raw in losses.items():
        if int(raw or 0) < 0 or int(raw or 0) > available.get(tid, 0):
            raise HTTPException(400, f"تلفات {tid} از تعداد کل مدافعان بیشتر است")
    remaining = {tid: int(n or 0) for tid, n in losses.items()}
    for army in armies:
        share = {}
        for tid, left in list(remaining.items()):
            take = min(left, int(army.get("troops", {}).get(tid, 0) or 0))
            if take:
                share[tid] = take
                remaining[tid] -= take
        await _apply_campaign_losses(army, share)

async def _apply_defender_equipment_losses(defender_tg_id: int, engagement_id: str, losses: dict[str, int], army_ids: list[str] | None = None):
    query = {"tg_id": defender_tg_id, "active": True, "engagement_campaign_id": engagement_id}
    if army_ids:
        query["_id"] = {"$in": [ObjectId(x) for x in army_ids]}
    armies = [c async for c in campaigns.find(query).sort("created_at", 1)]
    available = {}
    for army in armies:
        for eid, count in army.get("equipment", {}).items():
            available[eid] = available.get(eid, 0) + int(count or 0)
    for eid, raw in losses.items():
        if int(raw or 0) < 0 or int(raw or 0) > available.get(eid, 0):
            raise HTTPException(400, f"تلفات ادوات {eid} از تعداد کل مدافعان بیشتر است")
    remaining = {eid: int(count or 0) for eid, count in losses.items()}
    for army in armies:
        share = {}
        for eid, left in list(remaining.items()):
            take = min(left, int(army.get("equipment", {}).get(eid, 0) or 0))
            if take:
                share[eid] = take
                remaining[eid] -= take
        await _apply_equipment_losses(army, share)

def _sum_nested_counts(flat: dict[str, int], nested: dict[str, dict[str, int]]) -> dict[str, int]:
    """فرمت قدیمیِ تجمیعی و فرمت جدیدِ تلفات هر لشکر را برای گزارش یکی می‌کند."""
    # اگر فرمت جدید حاضر است، flat فقط fallback سازگاری است و نباید دوباره جمع شود.
    total = {} if nested else {key: max(0, int(value or 0)) for key, value in (flat or {}).items()}
    for values in (nested or {}).values():
        for key, value in values.items():
            total[key] = total.get(key, 0) + max(0, int(value or 0))
    return total

def _sum_campaign_field(rows: list[dict], field: str) -> dict[str, int]:
    total = {}
    for row in rows:
        for key, value in (row.get(field) or {}).items():
            total[key] = total.get(key, 0) + max(0, int(value or 0))
    return total

async def _apply_roleplay_player_adjustments(tg_id: int, resource_deltas: dict[str, int], popularity_delta: int) -> dict:
    player = await players.find_one({"tg_id": tg_id})
    if not player:
        raise HTTPException(404, "بازیکن مربوط به رول پیدا نشد")
    resources = dict(player.get("resources", {}))
    applied_resources = {}
    for key, raw in resource_deltas.items():
        if key not in PLAYER_RESOURCE_KEYS:
            raise HTTPException(400, f"منبع نامعتبر: {key}")
        delta = int(raw or 0)
        if abs(delta) > 1_000_000:
            raise HTTPException(400, "تغییر منبع بیش از حد بزرگ است")
        if delta:
            before = int(resources.get(key, 0) or 0)
            resources[key] = max(0, before + delta)
            applied_resources[key] = resources[key] - before
    pop_delta = int(popularity_delta or 0)
    if abs(pop_delta) > 100:
        raise HTTPException(400, "تغییر محبوبیت نمی‌تواند بیشتر از ۱۰۰ باشد")
    old_popularity = max(0, min(100, int(player.get("popularity", POPULARITY_START))))
    popularity = max(0, min(100, old_popularity + pop_delta))
    await players.update_one({"tg_id": tg_id}, {"$set": {"resources": resources, "popularity": popularity}})
    return {"tg_id": tg_id, "resources": applied_resources, "popularity": popularity - old_popularity}

def _validate_roleplay_adjustments(resource_deltas: dict[str, int], popularity_delta: int):
    for key, raw in resource_deltas.items():
        if key not in PLAYER_RESOURCE_KEYS:
            raise HTTPException(400, f"منبع نامعتبر: {key}")
        if abs(int(raw or 0)) > 1_000_000:
            raise HTTPException(400, "تغییر منبع بیش از حد بزرگ است")
    if abs(int(popularity_delta or 0)) > 100:
        raise HTTPException(400, "تغییر محبوبیت نمی‌تواند بیشتر از ۱۰۰ باشد")

@router.post("/roleplay/{roleplay_id}/respond")
async def respond_roleplay(roleplay_id: str, body: RoleplayResultBody, user: dict = Depends(admin_user)):
    """برای دستهٔ «جنگ»، نتیجه برای هر دو طرف نبرد فرستاده می‌شود — چه هر دو سناریو
    فرستاده باشند چه فقط یکی؛ طرفی که ننوشته هم از طریق خودِ لشکرکشی پیدا و باخبر می‌شود.
    ادمین می‌تواند دستی هم لردهای دیگری را به‌عنوان «طرف این رول» اضافه کند (other_lords) —
    اسم‌شان در پیام هم نوشته می‌شود تا برای گیرنده روشن باشد این نتیجه بین چه کسانی بوده.
    اگر visibility=all باشد، علاوه بر شرکت‌کننده‌ها، همهٔ بازیکنان بازی هم کلاغ می‌گیرند —
    جایگزین «روایت جنگ» قدیمی برای وقتی نتیجه باید عمومی اعلام شود"""
    result = body.result.strip()
    if len(result) < 3:
        raise HTTPException(400, "متن نتیجه خیلی کوتاه است")
    if body.visibility not in ("participants", "all"):
        raise HTTPException(400, "نوع نمایش نامعتبر")
    try:
        oid = ObjectId(roleplay_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ رول نامعتبر است")
    r = await roleplays.find_one({"_id": oid})
    if not r:
        raise HTTPException(404, "این رول پیدا نشد")
    if r.get("resolved"):
        raise HTTPException(400, "این رول قبلاً پاسخ داده شده")

    ids_to_resolve = [r["_id"]]
    recipient_tg_ids = {r["tg_id"]}
    campaign = None
    defender = None
    combat_outcome = None
    opponent_campaign = None
    attacker_campaigns = []
    defender_campaigns = []
    attacker_before = {}
    defender_before = {}
    attacker_equipment_before = {}
    defender_equipment_before = {}
    attacker_report_losses = _sum_nested_counts(body.attacker_losses, body.attacker_army_losses)
    defender_report_losses = _sum_nested_counts(body.defender_losses, body.defender_army_losses)
    attacker_report_equipment_losses = _sum_nested_counts(body.attacker_equipment_losses, body.attacker_army_equipment_losses)
    defender_report_equipment_losses = _sum_nested_counts(body.defender_equipment_losses, body.defender_army_equipment_losses)
    winner_tg_ids = list(dict.fromkeys(body.winner_tg_ids or ([body.winner_tg_id] if body.winner_tg_id else [])))
    loser_tg_ids = []

    if r["category"] == "war" and r.get("campaign_id"):
        siblings = await roleplays.find({
            "category": "war", "campaign_id": r["campaign_id"],
            "tg_id": {"$ne": r["tg_id"]}, "resolved": False,
        }).to_list(None)
        for sibling in siblings:
            ids_to_resolve.append(sibling["_id"])
            recipient_tg_ids.add(sibling["tg_id"])
        campaign = await _battle_root(r["campaign_id"])
        if campaign:
            recipient_tg_ids.add(campaign["tg_id"])
            if campaign.get("opponent_campaign_id"):
                try:
                    opponent_campaign = await campaigns.find_one({"_id": ObjectId(campaign["opponent_campaign_id"])})
                except Exception:
                    opponent_campaign = None
            defender = await players.find_one({"tg_id": opponent_campaign["tg_id"]}) if opponent_campaign else await owner_of_castle(campaign["target_castle"])
            if defender:
                recipient_tg_ids.add(defender["tg_id"])
            attacker_ids = campaign.get("battle_attacker_army_ids") or [str(campaign["_id"])]
            for army_id in attacker_ids:
                try:
                    army = await campaigns.find_one({"_id": ObjectId(army_id), "active": True, "engagement_locked": True})
                except Exception:
                    army = None
                if army:
                    attacker_campaigns.append(army)
                    recipient_tg_ids.add(army["tg_id"])
            for army_id in campaign.get("battle_defender_army_ids") or []:
                try:
                    army = await campaigns.find_one({"_id": ObjectId(army_id), "active": True, "engagement_locked": True})
                except Exception:
                    army = None
                if army:
                    defender_campaigns.append(army)
                    recipient_tg_ids.add(army["tg_id"])
            attacker_tg_ids = {a["tg_id"] for a in attacker_campaigns} or {campaign["tg_id"]}
            defender_tg_ids = {a["tg_id"] for a in defender_campaigns}
            if defender:
                defender_tg_ids.add(defender["tg_id"])
            valid_winners = attacker_tg_ids | defender_tg_ids
            if not winner_tg_ids or not set(winner_tg_ids).issubset(valid_winners):
                raise HTTPException(400, "برنده‌های نبرد را از بین لردهای درگیر انتخاب کن")
            winner_sides = {"attacker" if tg_id in attacker_tg_ids else "defender" for tg_id in winner_tg_ids}
            if len(winner_sides) != 1:
                raise HTTPException(400, "برنده‌ها باید همگی از یک سمت نبرد باشند")
            combat_outcome = winner_sides.pop()
            loser_tg_ids = sorted((attacker_tg_ids | defender_tg_ids) - set(winner_tg_ids))

            attacker_before = _sum_campaign_field(attacker_campaigns or [campaign], "troops")
            attacker_equipment_before = _sum_campaign_field(attacker_campaigns or [campaign], "equipment")
            if defender_campaigns:
                defender_before = _sum_campaign_field(defender_campaigns, "troops")
                defender_equipment_before = _sum_campaign_field(defender_campaigns, "equipment")
            else:
                defender_before = _sum_campaign_field(campaign.get("battle_defender_snapshot", []), "troops")
                defender_equipment_before = _sum_campaign_field(campaign.get("battle_defender_snapshot", []), "equipment")

            # تلفات دقیق همزمان با نتیجه ثبت می‌شود. برای مدافع، جمع هر نوع نیرو
            # میان همهٔ لشکرهای دفاعی حاضر در همان قلعه تقسیم می‌شود.
            # همهٔ ورودی‌ها قبل از اولین write اعتبارسنجی می‌شوند تا خطای یک ارتش
            # باعث ثبت نصفه‌ونیمهٔ تلفات روی ارتش قبلی نشود.
            for attacker_army in attacker_campaigns or [campaign]:
                aid = str(attacker_army["_id"])
                _validate_campaign_losses(attacker_army, body.attacker_army_losses.get(aid, body.attacker_losses if aid == str(campaign["_id"]) else {}))
                _validate_equipment_losses(attacker_army, body.attacker_army_equipment_losses.get(aid, body.attacker_equipment_losses if aid == str(campaign["_id"]) else {}))
            if body.defender_army_losses or body.defender_army_equipment_losses:
                for defender_army in defender_campaigns:
                    did = str(defender_army["_id"])
                    _validate_campaign_losses(defender_army, body.defender_army_losses.get(did, {}))
                    _validate_equipment_losses(defender_army, body.defender_army_equipment_losses.get(did, {}))
            elif opponent_campaign:
                _validate_campaign_losses(opponent_campaign, body.defender_losses)
                _validate_equipment_losses(opponent_campaign, body.defender_equipment_losses)
            for attacker_army in attacker_campaigns or [campaign]:
                aid = str(attacker_army["_id"])
                await _apply_campaign_losses(attacker_army, body.attacker_army_losses.get(aid, body.attacker_losses if aid == str(campaign["_id"]) else {}))
                await _apply_equipment_losses(attacker_army, body.attacker_army_equipment_losses.get(aid, body.attacker_equipment_losses if aid == str(campaign["_id"]) else {}))
            if body.defender_army_losses or body.defender_army_equipment_losses:
                for defender_army in defender_campaigns:
                    did = str(defender_army["_id"])
                    await _apply_campaign_losses(defender_army, body.defender_army_losses.get(did, {}))
                    await _apply_equipment_losses(defender_army, body.defender_army_equipment_losses.get(did, {}))
            elif opponent_campaign:
                await _apply_campaign_losses(opponent_campaign, body.defender_losses)
                await _apply_equipment_losses(opponent_campaign, body.defender_equipment_losses)
            elif defender:
                await _apply_defender_losses(
                    defender["tg_id"], campaign["target_castle"], r["campaign_id"], body.defender_losses,
                    campaign.get("battle_defender_army_ids"),
                )
                await _apply_defender_equipment_losses(
                    defender["tg_id"], r["campaign_id"], body.defender_equipment_losses,
                    campaign.get("battle_defender_army_ids"),
                )

    adjustment_results = []
    adjustments_requested = bool(
        body.actor_resource_deltas or body.actor_popularity_delta
        or body.target_resource_deltas or body.target_popularity_delta
    )
    if adjustments_requested and r["category"] not in ("economy", "sabotage"):
        raise HTTPException(400, "تغییر منابع و محبوبیت فقط برای رول اقتصادی و خرابکاری مجاز است")
    _validate_roleplay_adjustments(body.actor_resource_deltas, body.actor_popularity_delta)
    _validate_roleplay_adjustments(body.target_resource_deltas, body.target_popularity_delta)
    if r["category"] in ("economy", "sabotage"):
        adjustment_results.append(await _apply_roleplay_player_adjustments(
            r["tg_id"], body.actor_resource_deltas, body.actor_popularity_delta,
        ))
    if r["category"] == "sabotage":
        target_tg_id = r.get("target_tg_id")
        if target_tg_id:
            recipient_tg_ids.add(target_tg_id)
            adjustment_results.append(await _apply_roleplay_player_adjustments(
                target_tg_id, body.target_resource_deltas, body.target_popularity_delta,
            ))

    other_lord_names = []
    for tg_id in body.other_lords:
        lord = await players.find_one({"tg_id": tg_id})
        if lord:
            recipient_tg_ids.add(tg_id)
            other_lord_names.append(lord["name"])

    # قفل نتیجه روی خود لشکرکشی مانع دوباره‌شماری پیروزی با کلیک/درخواست تکراری می‌شود.
    if campaign and combat_outcome:
        outcome_guard = await campaigns.update_one(
            {"_id": campaign["_id"], "medal_outcome_battle_id": {"$ne": r.get("campaign_id")}},
            {"$set": {
                "medal_outcome_recorded": True, "medal_outcome_battle_id": r.get("campaign_id"), "combat_outcome": combat_outcome,
                "winner_tg_id": winner_tg_ids[0], "winner_tg_ids": winner_tg_ids,
                "loser_tg_ids": loser_tg_ids, "combat_resolved_at": now(), "battle_open": False,
            }},
        )
        if outcome_guard.modified_count:
            rebellion_settings = await get_rebellion_settings()
            war_pop = rebellion_settings["war_popularity"]
            winner_delta = int(war_pop["attack_win"] if combat_outcome == "attacker" else war_pop["defense_win"])
            loser_delta = int(war_pop["defense_loss"] if combat_outcome == "attacker" else war_pop["attack_loss"])
            win_stat = "attack_wins" if combat_outcome == "attacker" else "defense_wins"
            for tg_id in winner_tg_ids:
                await bump_player_stat(tg_id, win_stat)
                lord = await players.find_one({"tg_id": tg_id})
                if lord:
                    new_pop = max(0, min(100, int(lord.get("popularity", 50)) + winner_delta))
                    await players.update_one({"tg_id": tg_id}, {"$set": {"popularity": new_pop}})
            for tg_id in loser_tg_ids:
                lord = await players.find_one({"tg_id": tg_id})
                if lord:
                    new_pop = max(0, min(100, int(lord.get("popularity", 50)) + loser_delta))
                    await players.update_one({"tg_id": tg_id}, {"$set": {"popularity": new_pop}})

        # با نهایی‌شدن جواب، تمام لشکرهای درگیر آزاد می‌شوند؛ بازمانده‌ها دوباره
        # قابل حرکت‌اند و لشکرهای نابودشده active=False مانده‌اند.
        await _close_battle_state(campaign, r.get("campaign_id"), cancelled=False)

    await roleplays.update_many({"_id": {"$in": ids_to_resolve}}, {"$set": {
        "result": result[:4000], "resolved": True, "resolved_at": now(),
        "admin_adjustments": adjustment_results,
        **({"winner_tg_id": winner_tg_ids[0], "winner_tg_ids": winner_tg_ids, "loser_tg_ids": loser_tg_ids, "combat_outcome": combat_outcome} if combat_outcome else {}),
    }})

    # شروع و پایان جنگ رویداد عمومی‌اند؛ گزینهٔ visibility برای رول‌های غیرجنگی
    # همچنان معتبر است، اما نتیجهٔ خودِ نبرد همیشه برای همه می‌رود.
    if body.visibility == "all" or (campaign and combat_outcome):
        recipient_tg_ids = {p["tg_id"] async for p in players.find({}, {"tg_id": 1})}

    cat_name = ROLEPLAY_CATEGORIES.get(r["category"], r["category"])
    prefix = "اعلامیهٔ عمومی" if body.visibility == "all" or (campaign and combat_outcome) else f"نتیجهٔ رول «{cat_name}»{'ِ نبرد' if r['category'] == 'war' else ''}"
    parties_line = ""
    battle_report_plain = None
    battle_report_bot = None
    if campaign and combat_outcome:
        attacker_player = await players.find_one({"tg_id": campaign["tg_id"]})
        winner_players = await players.find({"tg_id": {"$in": winner_tg_ids}}, {"tg_id": 1, "name": 1}).to_list(None)
        loser_players = await players.find({"tg_id": {"$in": loser_tg_ids}}, {"tg_id": 1, "name": 1}).to_list(None)
        winner_name_map = {p["tg_id"]: p["name"] for p in winner_players}
        loser_name_map = {p["tg_id"]: p["name"] for p in loser_players}
        winner_names = [winner_name_map.get(tg_id, str(tg_id)) for tg_id in winner_tg_ids]
        loser_names = [loser_name_map.get(tg_id, str(tg_id)) for tg_id in loser_tg_ids]
        attacker_names = list(dict.fromkeys(a.get("player_name") for a in attacker_campaigns if a.get("player_name")))
        defender_names = list(dict.fromkeys(a.get("player_name") for a in defender_campaigns if a.get("player_name")))
        attacker_name = " و ".join(attacker_names) or (attacker_player["name"] if attacker_player else campaign.get("player_name", "مهاجم"))
        defender_name = " و ".join(defender_names) or (defender["name"] if defender else campaign.get("battle_defender_name", "مدافع"))

        def count_line(values: dict, empty_text: str = "بدون تلفات") -> str:
            parts = []
            for tid, raw in values.items():
                count = max(0, int(raw or 0))
                if count:
                    parts.append(f"{COMMON_TROOPS.get(tid, {}).get('name', tid)}: {count:,}")
            return "، ".join(parts) if parts else empty_text

        attacker_after = {tid: max(0, n - int(attacker_report_losses.get(tid, 0) or 0)) for tid, n in attacker_before.items()}
        defender_after = {tid: max(0, n - int(defender_report_losses.get(tid, 0) or 0)) for tid, n in defender_before.items()}
        attacker_equipment_after = {eid: max(0, int(count or 0) - int(attacker_report_equipment_losses.get(eid, 0) or 0)) for eid, count in attacker_equipment_before.items()}
        defender_equipment_after = {eid: max(0, int(count or 0) - int(defender_report_equipment_losses.get(eid, 0) or 0)) for eid, count in defender_equipment_before.items()}

        def equipment_line(values: dict, empty_text: str) -> str:
            parts = [f"{SIEGE_EQUIPMENT.get(eid, {}).get('name', eid)}: {int(count):,}" for eid, count in values.items() if int(count or 0) > 0]
            return "، ".join(parts) if parts else empty_text
        location = campaign.get("battle_location") or campaign.get("target_castle", "محل نامشخص")
        battle_title = campaign.get("name") or "نتیجهٔ نبرد"
        battle_report_rest = (
            f"⚔️ طرفین: لرد {attacker_name} در برابر لرد {defender_name}\n"
            f"📍 محل نبرد: {location}\n\n"
            f"📜 نتیجهٔ داوری\n{result}\n\n"
            f"🏆 برنده‌ها: {'، '.join('لرد ' + name for name in winner_names)}\n"
            f"🏳️ بازنده‌ها: {('، '.join('لرد ' + name for name in loser_names) if loser_names else 'ندارد')}\n\n"
            f"🩸 تلفات {attacker_name}: {count_line(attacker_report_losses)}\n"
            f"🛡️ نیروهای باقی‌مانده {attacker_name}: {count_line(attacker_after, 'هیچ نیرویی باقی نمانده')}\n\n"
            f"🩸 تلفات {defender_name}: {count_line(defender_report_losses)}\n"
            f"🛡️ نیروهای باقی‌مانده {defender_name}: {count_line(defender_after, 'هیچ نیرویی باقی نمانده')}\n\n"
            f"💥 ادوات منهدم‌شده {attacker_name}: {equipment_line(attacker_report_equipment_losses, 'هیچ‌کدام')}\n"
            f"💥 ادوات منهدم‌شده {defender_name}: {equipment_line(defender_report_equipment_losses, 'هیچ‌کدام')}\n"
            f"🏗️ ادوات باقی‌مانده {attacker_name}: {equipment_line(attacker_equipment_after, 'ندارد')}\n"
            f"🏗️ ادوات باقی‌مانده {defender_name}: {equipment_line(defender_equipment_after, 'ندارد')}"
        )
        battle_report_plain = f"⚔️ {battle_title}\n\n{battle_report_rest}"
        battle_report_bot = f"<b>⚔️ {html.escape(battle_title)}</b>\n\n{html.escape(battle_report_rest)}"
    elif r["category"] == "sabotage" and r.get("target_player_name"):
        parties_line = f"\nفرستندهٔ خرابکاری: {r['player_name']}\nهدف خرابکاری: {r['target_player_name']}"
    elif other_lord_names:
        all_names = list(dict.fromkeys([r["player_name"], *other_lord_names]))
        parties_line = f"\nطرف‌های این رول: {' و '.join(all_names)}"
    adjustment_lines = []
    for adjustment in adjustment_results:
        adjusted_player = await players.find_one({"tg_id": adjustment["tg_id"]}, {"name": 1})
        changes = [
            f"{ROLEPLAY_RESOURCE_NAMES.get(key, key)} {delta:+,}"
            for key, delta in adjustment["resources"].items() if delta
        ]
        if adjustment["popularity"]:
            changes.append(f"محبوبیت {adjustment['popularity']:+}")
        if changes:
            adjustment_lines.append(f"{adjusted_player['name'] if adjusted_player else adjustment['tg_id']}: " + "، ".join(changes))
    adjustment_line = ("\n\nتغییرات ثبت‌شده:\n" + "\n".join(adjustment_lines)) if adjustment_lines else ""
    for tg_id in recipient_tg_ids:
        player = await players.find_one({"tg_id": tg_id})
        if player:
            if battle_report_plain:
                await send_system_message(
                    player["tg_id"], player["name"], battle_report_plain, kind="battle",
                    bot_text=battle_report_bot, bot_parse_mode="HTML", image_url=_validated_message_image(body.image_url),
                )
            else:
                await send_system_message(player["tg_id"], player["name"], f"{prefix}: {result}{parties_line}{adjustment_line}", image_url=_validated_message_image(body.image_url))

    return {"ok": True, "sent_to": len(recipient_tg_ids)}

async def _castle_region_map() -> dict:
    """اسم قلعه/بندر → شناسهٔ اقلیمش، از دیتای ثابت + هرچه ادمین به نقشه اضافه کرده"""
    out = {}
    for rid, r in REGIONS.items():
        for c in r["castles"] + r["ports"]:
            out[c] = rid
    async for m in map_castles.find({}, {"name": 1, "region": 1}):
        out[m["name"]] = m["region"]
    return out

@router.get("/players/pending")
async def list_pending_players(user: dict = Depends(admin_user)):
    """بازیکن‌هایی که فقط اسم‌نویسی کرده‌اند و هنوز خاندان (اقلیم) و قلعه‌شان تعیین نشده"""
    castle_region = await _castle_region_map()
    occupied = {p["castle"] async for p in players.find({"castle": {"$ne": None}}, {"castle": 1})}
    out = []
    cur = players.find({"$or": [{"region": None}, {"castle": None}]}).sort("created_at", 1)
    async for p in cur:
        requested = [
            {"name": c, "region": castle_region.get(c), "occupied": c in occupied}
            for c in p.get("requested_castles", [])
        ]
        out.append({
            "tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"),
            "gender": p.get("gender"), "created_at": p["created_at"].isoformat(),
            "requested_castles": requested,
        })
    return out

@router.get("/players/roster")
async def list_roster(user: dict = Depends(admin_user)):
    """همهٔ بازیکن‌های خاندان‌دار — برای مرور، حذف از خاندان یا تخصیص دوباره"""
    out = []
    cur = players.find({"region": {"$ne": None}, "castle": {"$ne": None}}).sort("name", 1)
    async for p in cur:
        out.append({
            "tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"),
            "region": p["region"], "region_name": REGIONS.get(p["region"], {}).get("name", p["region"]),
            "castle": p["castle"], "is_port": p.get("is_port", False),
            "house": p.get("house") or CASTLE_HOUSES.get(p["castle"]),
            "castles": list(p.get("castle_buildings", {}).keys()),
        })
    return out

class AssignHouseBody(BaseModel):
    region: str
    castle: str

@router.post("/players/{tg_id}/assign")
async def admin_assign_house(tg_id: int, body: AssignHouseBody, user: dict = Depends(admin_user)):
    """خاندان (اقلیم) و قلعهٔ یک بازیکن را دستی تعیین می‌کند — چه تازه‌ثبت‌نامی چه
    بازیکنی که می‌خواهی به خاندان/قلعهٔ دیگری منتقلش کنی"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    region = REGIONS[body.region]
    if body.castle not in region["castles"] + region["ports"]:
        raise HTTPException(400, "این قلعه در این اقلیم نیست")
    holder = await owner_of_castle(body.castle)
    if holder and holder["tg_id"] != tg_id:
        raise HTTPException(409, "این قلعه صاحب دارد — یکی دیگر برگزین")

    was_assigned = bool(target.get("region") and target.get("castle"))
    old_castle = target.get("castle")
    extra_castles = dict(target.get("castle_buildings", {}))
    # انتقال خاندان یعنی قلعهٔ قبلی واقعاً آزاد می‌شود. ساختمان‌های قلعهٔ مقصد فقط
    # وقتی حفظ می‌شوند که مقصد از قبل یکی از قلعه‌های اضافهٔ خود بازیکن بوده باشد.
    new_home_buildings = extra_castles.pop(body.castle, {})
    if old_castle:
        extra_castles.pop(old_castle, None)
    house = CASTLE_HOUSES.get(body.castle)
    terrain = await all_castle_terrain()
    is_port = terrain.get(body.castle, "land") in ("coastal", "sea")
    await players.update_one({"tg_id": tg_id}, {"$set": {
        "region": body.region, "castle": body.castle, "is_port": is_port,
        "house": house, "buildings": new_home_buildings, "castle_buildings": extra_castles,
    }})
    house_note = f" نامِ خاندانت «خاندان {house}» شد." if house else ""
    msg = (
        f"خاندانت جابه‌جا شد — حالا به {region['name']} تعلق داری و قلعه‌ات {body.castle} است.{house_note}"
        if was_assigned else
        f"خاندانت مشخص شد — به {region['name']} تعلق داری و قلعه‌ات {body.castle} است.{house_note} اکنون می‌توانی وارد بازی شوی."
    )
    await send_system_message(tg_id, target["name"], msg)
    return {"ok": True}

@router.post("/players/{tg_id}/unassign")
async def admin_unassign_house(tg_id: int, user: dict = Depends(admin_user)):
    """خاندان و قلعهٔ یک بازیکن را از او می‌گیرد — دوباره «در انتظار تخصیص» می‌شود
    و قلعه‌اش برای بازیکن دیگری آزاد می‌شود؛ منابع/ساختمان‌هایش دست‌نخورده می‌ماند"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if not target.get("region") and not target.get("castle"):
        raise HTTPException(400, "این بازیکن اصلاً خاندانی ندارد")
    await players.update_one({"tg_id": tg_id}, {"$set": {
        "region": None, "castle": None, "is_port": False, "house": None, "castle_buildings": {},
    }})
    await send_system_message(
        tg_id, target["name"],
        "خاندان و قلعه‌ات (و هر قلعهٔ اضافه‌ای که داشتی) از تو گرفته شد — "
        "منتظر بمان تا ادمین دوباره خاندانی برایت مشخص کند.",
    )
    return {"ok": True}

class AddCastleBody(BaseModel):
    castle: str

@router.post("/players/{tg_id}/castles")
async def admin_add_castle(tg_id: int, body: AddCastleBody, user: dict = Depends(admin_user)):
    """قلعهٔ اضافه (پایگاهِ دومِ کامل، با ساختمان‌های خودش) به این بازیکن می‌دهد —
    مثلاً وقتی توی جنگ قلعهٔ یک بازیکنِ دیگر را گرفته. اگر آن قلعه الان دستِ کسِ
    دیگری باشد (چه قلعهٔ اصلی‌اش چه یکی از قلعه‌های اضافه‌اش)، خودکار ازش گرفته
    می‌شود و ساختمان‌هایش (غنیمتِ جنگ) هم با خودش می‌آیند — قلعه هیچ‌وقت هم‌زمان
    مالِ دو بازیکن نمی‌ماند"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if not target.get("region") or not target.get("castle"):
        raise HTTPException(400, "اول باید خاندان و قلعهٔ اصلی داشته باشد")
    castle_region = await _castle_region_map()
    if body.castle not in castle_region:
        raise HTTPException(400, "این قلعه در بازی شناخته‌شده نیست")
    if body.castle == target["castle"] or body.castle in target.get("castle_buildings", {}):
        raise HTTPException(400, "این قلعه از قبل مالِ همین بازیکن است")

    captured_buildings = {}
    previous_owner = await players.find_one({"$or": [
        {"castle": body.castle}, {f"castle_buildings.{body.castle}": {"$exists": True}},
    ]})
    if previous_owner and previous_owner["tg_id"] != tg_id:
        if previous_owner["castle"] == body.castle:
            captured_buildings = previous_owner.get("buildings", {})
            extra = dict(previous_owner.get("castle_buildings", {}))
            if extra:
                new_home = next(iter(extra))
                new_home_buildings = extra.pop(new_home)
                terrain = await all_castle_terrain()
                await players.update_one({"tg_id": previous_owner["tg_id"]}, {"$set": {
                    "castle": new_home, "buildings": new_home_buildings, "castle_buildings": extra,
                    "is_port": terrain.get(new_home, "land") in ("coastal", "sea"),
                    "house": CASTLE_HOUSES.get(new_home),
                }})
                await send_system_message(
                    previous_owner["tg_id"], previous_owner["name"],
                    f"قلعهٔ اصلی‌ات «{body.castle}» به دستِ دشمن افتاد — حالا «{new_home}» قلعهٔ اصلی‌ات است.",
                )
            else:
                await players.update_one({"tg_id": previous_owner["tg_id"]}, {"$set": {
                    "region": None, "castle": None, "is_port": False, "house": None,
                }})
                await send_system_message(
                    previous_owner["tg_id"], previous_owner["name"],
                    f"قلعه‌ات «{body.castle}» به دستِ دشمن افتاد و دیگر خاندانی نداری — "
                    "منتظر بمان تا ادمین دوباره برایت مشخص کند.",
                )
        else:
            captured_buildings = previous_owner.get("castle_buildings", {}).get(body.castle, {})
            await players.update_one({"tg_id": previous_owner["tg_id"]}, {"$unset": {f"castle_buildings.{body.castle}": ""}})
            await send_system_message(
                previous_owner["tg_id"], previous_owner["name"], f"قلعهٔ «{body.castle}» به دستِ دشمن افتاد.",
            )

    await players.update_one({"tg_id": tg_id}, {"$set": {f"castle_buildings.{body.castle}": captured_buildings}})
    if previous_owner and previous_owner["tg_id"] != tg_id:
        await bump_player_stat(tg_id, "castles_captured")
    spoils_note = " (به‌همراهِ ساختمان‌هایی که رویش ساخته بودند — غنیمتِ جنگ)" if captured_buildings else ""
    await send_system_message(tg_id, target["name"], f"قلعهٔ «{body.castle}»{spoils_note} به قلمروِ تو اضافه شد.")
    return {"ok": True, "captured_from": previous_owner["name"] if previous_owner and previous_owner["tg_id"] != tg_id else None}

@router.delete("/players/{tg_id}/castles/{castle}")
async def admin_remove_castle(tg_id: int, castle: str, user: dict = Depends(admin_user)):
    """یکی از قلعه‌های اضافهٔ این بازیکن را ازش می‌گیرد (قلعه دوباره آزاد می‌شود) —
    برای گرفتنِ قلعهٔ اصلی از «حذف از خاندان» استفاده کن"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if castle not in target.get("castle_buildings", {}):
        raise HTTPException(400, "این قلعه جزوِ قلعه‌های اضافهٔ این بازیکن نیست")
    await players.update_one({"tg_id": tg_id}, {"$unset": {f"castle_buildings.{castle}": ""}})
    await send_system_message(tg_id, target["name"], f"قلعهٔ «{castle}» از قلمروِ تو گرفته شد.")
    return {"ok": True}

@router.delete("/players/{tg_id}/pending")
async def delete_pending_player(tg_id: int, user: dict = Depends(admin_user)):
    """درخواستِ ثبت‌نامِ یک بازیکنِ هنوز-تخصیص‌نیافته را کاملاً پاک می‌کند — برای
    ثبت‌نام‌های آزمایشی/اشتباهی که اصلاً نباید وارد صف تخصیص خاندان بمانند.
    فقط روی کسی کار می‌کند که هنوز خاندان/قلعه ندارد — برای بازیکنِ واقعاً
    واردشده به بازی باید اول از خاندانش خارجش کرد"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if target.get("region") or target.get("castle"):
        raise HTTPException(400, "این بازیکن وارد بازی شده — اول باید از خاندانش خارجش کنی")
    await players.delete_one({"tg_id": tg_id})
    return {"ok": True}

MAP_KINDS = {"castle", "city", "ruin", "port"}

@router.get("/map/options")
async def map_options(region: str, user: dict = Depends(admin_user)):
    """اسم قلعه/بندرهای این اقلیم که هنوز روی نقشه مکان ندارند — برای پرکردن انتخابگر ادمین"""
    if region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    placed = {m["name"] async for m in map_castles.find({"region": region}, {"name": 1})}
    r = REGIONS[region]
    options = [{"name": c, "kind": "castle", "terrain": "land"} for c in r["castles"] if c not in placed]
    options += [{"name": c, "kind": "port", "terrain": "coastal"} for c in r["ports"] if c not in placed]
    return options

class MapCastleBody(BaseModel):
    region: str
    x: float
    y: float
    name: str | None = None       # انتخاب از دیتای موجودِ بازی
    new_name: str | None = None   # قلعه/شهر کاملاً جدید
    kind: str = "castle"          # نوع آیکن روی نقشه: castle | city | ruin | port
    terrain: str = "land"         # نوع دسترسی زمینی/دریایی: land | coastal | sea

@router.post("/map/castles")
async def add_map_castle(body: MapCastleBody, user: dict = Depends(admin_user)):
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    if not (0 <= body.x <= 100 and 0 <= body.y <= 100):
        raise HTTPException(400, "مختصات نامعتبر")
    if body.kind not in MAP_KINDS:
        raise HTTPException(400, "نوع آیکن نامعتبر")
    if body.terrain not in MAP_TERRAINS:
        raise HTTPException(400, "نوع زمین نامعتبر")

    r = REGIONS[body.region]
    all_names = {name async for doc in map_castles.find({}, {"name": 1}) for name in [doc["name"]]}
    for reg in REGIONS.values():
        all_names |= set(reg["castles"]) | set(reg["ports"])

    if body.new_name and body.new_name.strip():
        name = body.new_name.strip()[:40]
        if name in all_names:
            raise HTTPException(409, "این اسم قبلاً در بازی وجود دارد")
        custom = True
    else:
        name = (body.name or "").strip()
        if name not in r["castles"] + r["ports"]:
            raise HTTPException(400, "این قلعه/بندر در دیتای این اقلیم نیست")
        if await map_castles.find_one({"region": body.region, "name": name}):
            raise HTTPException(409, "این قلعه از قبل روی نقشه گذاشته شده")
        custom = False

    # نوع آیکن (قلعه/شهر/مخروبه/بندر) و نوع زمین (خشکی/خشکی‌دریایی/دریایی) را ادمین
    # همیشه دستی مشخص می‌کند — چه برای اسم تازه چه موجود
    await map_castles.insert_one({
        "region": body.region, "name": name, "kind": body.kind, "terrain": body.terrain,
        "x": body.x, "y": body.y, "custom": custom, "created_at": now(),
    })
    return {"ok": True, "name": name}

@router.delete("/map/castles/{name}")
async def delete_map_castle(name: str, user: dict = Depends(admin_user)):
    res = await map_castles.delete_one({"name": name})
    if res.deleted_count == 0:
        raise HTTPException(404, "این نشانه روی نقشه پیدا نشد")
    return {"ok": True}

class EditMapCastleBody(BaseModel):
    kind: str = "castle"      # نوع آیکن روی نقشه: castle | city | ruin | port
    terrain: str = "land"     # نوع دسترسی زمینی/دریایی: land | coastal | sea

@router.patch("/map/castles/{name}")
async def edit_map_castle(name: str, body: EditMapCastleBody, user: dict = Depends(admin_user)):
    """آیکن یا نوع زمینِ یک نشانهٔ ازقبل‌گذاشته‌شده را عوض می‌کند — بدون نیاز به حذف و
    دوباره‌گذاشتنش (مختصاتش دست‌نخورده می‌ماند)"""
    if body.kind not in MAP_KINDS:
        raise HTTPException(400, "نوع آیکن نامعتبر")
    if body.terrain not in MAP_TERRAINS:
        raise HTTPException(400, "نوع زمین نامعتبر")
    res = await map_castles.update_one({"name": name}, {"$set": {"kind": body.kind, "terrain": body.terrain}})
    if res.matched_count == 0:
        raise HTTPException(404, "این نشانه روی نقشه پیدا نشد")
    # اگر بازیکنی همین الان صاحبِ این قلعه است، is_port ذخیره‌شده‌اش را هم فوراً هماهنگ کن
    await players.update_one({"castle": name}, {"$set": {"is_port": body.terrain in ("coastal", "sea")}})
    return {"ok": True}

@router.get("/admins")
async def list_admins(user: dict = Depends(full_admin_user)):
    """همهٔ ادمین‌ها — کامل (از env) و محدود (از دیتابیس)"""
    tg_ids = list(ADMIN_IDS) + [a["tg_id"] async for a in admin_roles.find({})]
    names = {}
    async for p in players.find({"tg_id": {"$in": tg_ids}}, {"tg_id": 1, "name": 1, "castle": 1}):
        names[p["tg_id"]] = {"name": p["name"], "castle": p["castle"]}

    out = [{"tg_id": tid, "role": "full", "source": "env", **names.get(tid, {})} for tid in ADMIN_IDS]
    async for a in admin_roles.find({}):
        out.append({"tg_id": a["tg_id"], "role": a["role"], "source": "db", **names.get(a["tg_id"], {})})
    return out

class AddAdminBody(BaseModel):
    tg_id: int
    role: str = "limited"

@router.post("/admins")
async def add_admin(body: AddAdminBody, user: dict = Depends(owner_user)):
    if body.role not in ("limited", "full"):
        raise HTTPException(400, "سطح دسترسی ادمین نامعتبر است")
    if body.tg_id in ADMIN_IDS:
        raise HTTPException(400, "این کاربر از قبل ادمین کامل است")
    if not await players.find_one({"tg_id": body.tg_id}):
        raise HTTPException(404, "این کاربر هنوز ثبت‌نام نکرده")
    await admin_roles.update_one(
        {"tg_id": body.tg_id},
        {"$set": {"tg_id": body.tg_id, "role": body.role, "added_by": user["id"], "created_at": now()}},
        upsert=True,
    )
    # ادمین عضو بازی نیست؛ قلعه/اقلیم و پیشرفت قلمرویی‌اش فوراً آزاد می‌شود.
    await players.update_one({"tg_id": body.tg_id}, {"$set": {
        "region": None, "castle": None, "is_port": False, "house": None,
        "castles": [], "castle_buildings": {}, "buildings": {},
    }})
    return {"ok": True}

@router.delete("/admins/{tg_id}")
async def remove_admin(tg_id: int, user: dict = Depends(owner_user)):
    if tg_id in ADMIN_IDS:
        raise HTTPException(400, "ادمین کامل از env مدیریت می‌شود، نه از اینجا")
    res = await admin_roles.delete_one({"tg_id": tg_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "ادمین محدود پیدا نشد")
    return {"ok": True}

@router.get("/market")
async def admin_market_list(user: dict = Depends(full_admin_user)):
    out = []
    async for m in market_listings.find({}):
        out.append({"resource": m["resource"], "qty": m["qty"], "price": m["price"],
                    "base_price": m.get("base_price", m["price"])})
    return out

class MarketListingBody(BaseModel):
    resource: str
    qty: int
    price: int

@router.post("/market")
async def admin_market_set(body: MarketListingBody, user: dict = Depends(full_admin_user)):
    if body.resource not in TRADE_GOODS:
        raise HTTPException(400, "کالای نامعتبر")
    if body.qty < 0 or body.price <= 0:
        raise HTTPException(400, "مقدار یا قیمت نامعتبر")
    await market_listings.update_one(
        {"resource": body.resource},
        {"$set": {"resource": body.resource, "qty": body.qty, "price": body.price,
                   "prev_price": body.price, "base_price": body.price, "updated_at": now()}},
        upsert=True,
    )
    return {"ok": True}

@router.delete("/market/{resource}")
async def admin_market_delete(resource: str, user: dict = Depends(full_admin_user)):
    res = await market_listings.delete_one({"resource": resource})
    if res.deleted_count == 0:
        raise HTTPException(404, "این کالا توی بازار نیست")
    return {"ok": True}

@router.get("/market/black")
async def admin_black_market_list(user: dict = Depends(full_admin_user)):
    out = []
    async for m in black_market_listings.find({}).sort("created_at", -1):
        out.append({
            "id": str(m["_id"]), "resource": m["resource"], "qty": m["qty"], "price": m["price"],
            "expires_in_minutes": max(0, int((m["expires_at"] - now()).total_seconds() // 60)),
        })
    return out

class BlackMarketBody(BaseModel):
    resource: str
    qty: int
    price: int
    hours: int = 6

@router.post("/market/black")
async def admin_black_market_create(body: BlackMarketBody, user: dict = Depends(full_admin_user)):
    if body.resource not in TRADE_GOODS:
        raise HTTPException(400, "کالای نامعتبر")
    if body.qty <= 0 or body.price <= 0 or body.hours <= 0:
        raise HTTPException(400, "مقدار، قیمت یا مدت نامعتبر")
    doc = {
        "resource": body.resource, "qty": body.qty, "price": body.price,
        "expires_at": now() + timedelta(hours=body.hours), "created_at": now(),
    }
    res = await black_market_listings.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id)}

@router.delete("/market/black/{listing_id}")
async def admin_black_market_delete(listing_id: str, user: dict = Depends(full_admin_user)):
    try:
        oid = ObjectId(listing_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ نامعتبر")
    res = await black_market_listings.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(404, "این نشانی بازار سیاه پیدا نشد")
    return {"ok": True}

PLAYER_RESOURCE_KEYS = {
    "gold", "wood", "stone", "iron", "food", "wine", "men",
    "weapon_sword", "weapon_spear", "weapon_archer", "weapon_lcav", "weapon_hcav",
}

@router.get("/items")
async def admin_list_items(user: dict = Depends(full_admin_user)):
    """قالب‌های آیتم — همراه با تعداد بارِ داده‌شده به لردها"""
    out = []
    async for tpl in items.find({}).sort("created_at", -1):
        grant_count = await item_grants.count_documents({"item_id": tpl["_id"]})
        out.append({
            "id": str(tpl["_id"]), "name": tpl["name"],
            "type": tpl["type"], "type_name": ITEM_TYPES.get(tpl["type"], tpl["type"]),
            "duration": tpl["duration"], "duration_name": ITEM_DURATIONS.get(tpl["duration"], tpl["duration"]),
            "duration_hours": tpl.get("duration_hours"),
            "description": tpl.get("description", ""),
            "grant_count": grant_count,
        })
    return out

class ItemBody(BaseModel):
    name: str
    type: str
    duration: str
    duration_hours: int | None = None
    description: str = ""

@router.post("/items")
async def admin_create_item(body: ItemBody, user: dict = Depends(full_admin_user)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "نام آیتم را بنویس")
    if body.type not in ITEM_TYPES:
        raise HTTPException(400, "نوع آیتم نامعتبر")
    if body.duration not in ITEM_DURATIONS:
        raise HTTPException(400, "مدت آیتم نامعتبر")
    duration_hours = None
    if body.duration == "temporary":
        if not body.duration_hours or body.duration_hours <= 0:
            raise HTTPException(400, "برای آیتم موقتی، مدت (ساعت) را مشخص کن")
        duration_hours = body.duration_hours

    doc = {
        "name": name[:60], "type": body.type, "duration": body.duration,
        "duration_hours": duration_hours, "description": body.description.strip()[:300],
        "created_by": user["id"], "created_at": now(),
    }
    res = await items.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id)}

@router.delete("/items/{item_id}")
async def admin_delete_item(item_id: str, user: dict = Depends(full_admin_user)):
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ آیتم نامعتبر است")
    res = await items.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(404, "این آیتم پیدا نشد")
    await item_grants.delete_many({"item_id": oid})
    return {"ok": True}

class ItemGrantBody(BaseModel):
    tg_id: int
    color: str

@router.post("/items/{item_id}/grant")
async def admin_grant_item(item_id: str, body: ItemGrantBody, user: dict = Depends(full_admin_user)):
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ آیتم نامعتبر است")
    tpl = await items.find_one({"_id": oid})
    if not tpl:
        raise HTTPException(404, "این آیتم پیدا نشد")
    if body.color not in ITEM_RARITY_COLORS:
        raise HTTPException(400, "رنگ نامعتبر")
    target = await players.find_one({"tg_id": body.tg_id})
    if not target:
        raise HTTPException(404, "این لرد پیدا نشد")

    expires_at = now() + timedelta(hours=tpl["duration_hours"]) if tpl["duration"] == "temporary" else None
    await item_grants.insert_one({
        "item_id": oid, "tg_id": body.tg_id, "color": body.color,
        "granted_by": user["id"], "granted_at": now(), "expires_at": expires_at,
    })
    await send_system_message(
        target["tg_id"], target["name"],
        f"آیتم «{tpl['name']}» ({ITEM_RARITY_COLORS[body.color]}) به دارایی‌های تو اضافه شد — در صفحهٔ «دارایی‌ها» ببینش.",
    )
    return {"ok": True}

@router.get("/players/{tg_id}/resources")
async def admin_get_player_resources(tg_id: int, user: dict = Depends(full_admin_user)):
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    # سقف دقیق همین بازیکن: پایه + بونوس ساختمان‌های قلعهٔ اصلی و همهٔ قلعه‌های اضافه.
    # ارتقاهای تمام‌شده را اول resolve می‌کنیم تا عددی که ادمین می‌بیند با تولید واقعی یکی باشد.
    resolve_building_upgrades(p)
    res = {k: round(p.get("resources", {}).get(k, 0)) for k in PLAYER_RESOURCE_KEYS}
    caps = effective_caps(p)
    resource_caps = {k: round(caps.get(k, 0)) for k in PLAYER_RESOURCE_KEYS}
    return {
        "name": p["name"],
        "castle": p["castle"],
        "points": int(p.get("points", 0)),
        "popularity": max(0, min(100, int(p.get("popularity", POPULARITY_START)))),
        "resources": res,
        "resource_caps": resource_caps,
    }

class AdjustPlayerPointsBody(BaseModel):
    delta: int

class AdjustPlayerPopularityBody(BaseModel):
    delta: int

@router.post("/players/{tg_id}/points")
async def admin_adjust_player_points(tg_id: int, body: AdjustPlayerPointsBody, user: dict = Depends(full_admin_user)):
    """امتیاز بازیکن را به مقدار مثبت/منفی تغییر می‌دهد؛ امتیاز هیچ‌وقت زیر صفر نمی‌رود."""
    if body.delta == 0:
        raise HTTPException(400, "مقدار تغییر امتیاز نباید صفر باشد")
    if abs(body.delta) > 1_000_000:
        raise HTTPException(400, "مقدار تغییر امتیاز بیش از حد بزرگ است")
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    old_points = int(p.get("points", 0))
    new_points = max(0, old_points + int(body.delta))
    await players.update_one({"tg_id": tg_id}, {"$set": {"points": new_points}})
    return {"ok": True, "old_points": old_points, "points": new_points, "applied_delta": new_points - old_points}

@router.post("/players/{tg_id}/popularity")
async def admin_adjust_player_popularity(tg_id: int, body: AdjustPlayerPopularityBody, user: dict = Depends(full_admin_user)):
    """محبوبیت را مستقیم کم یا زیاد می‌کند و مقدار نهایی را در بازهٔ صفر تا صد نگه می‌دارد."""
    if body.delta == 0:
        raise HTTPException(400, "مقدار تغییر محبوبیت نباید صفر باشد")
    if abs(body.delta) > 100:
        raise HTTPException(400, "مقدار تغییر محبوبیت نمی‌تواند بیشتر از ۱۰۰ باشد")
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    old_popularity = max(0, min(100, int(p.get("popularity", POPULARITY_START))))
    new_popularity = max(0, min(100, old_popularity + int(body.delta)))
    await players.update_one({"tg_id": tg_id}, {"$set": {"popularity": new_popularity}})
    return {"ok": True, "old_popularity": old_popularity, "popularity": new_popularity, "applied_delta": new_popularity - old_popularity}

class SetPlayerResourcesBody(BaseModel):
    resources: dict

@router.post("/players/{tg_id}/resources")
async def admin_set_player_resources(tg_id: int, body: SetPlayerResourcesBody, user: dict = Depends(full_admin_user)):
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    updates = {}
    for k, v in body.resources.items():
        if k not in PLAYER_RESOURCE_KEYS:
            raise HTTPException(400, f"منبع نامعتبر: {k}")
        v = int(v)
        if v < 0:
            raise HTTPException(400, "مقدار منفی مجاز نیست")
        updates[f"resources.{k}"] = v
    if not updates:
        raise HTTPException(400, "هیچ منبعی برای تغییر مشخص نشده")
    await players.update_one({"tg_id": tg_id}, {"$set": updates})
    return {"ok": True}

@router.get("/players/{tg_id}/campaigns")
async def admin_player_campaigns(tg_id: int, user: dict = Depends(full_admin_user)):
    """لشکرکشی‌های یک بازیکن خاص — برای دیدن و در صورت نیاز منحل‌کردن، کنار ویرایش منابع"""
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    out = []
    cur = campaigns.find({"tg_id": tg_id}).sort("created_at", -1).limit(30)
    async for c in cur:
        troops = [
            {"id": t, "name": COMMON_TROOPS[t]["name"] if t in COMMON_TROOPS else t, "count": n}
            for t, n in c["troops"].items() if n and n > 0
        ]
        arrival_at = c.get("arrival_at")
        out.append({
            "id": str(c["_id"]),
            "name": c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "from": c["origin_castle"], "to": c["target_castle"],
            "troops": troops, "power": c.get("power", 0), "men_committed": c["men_committed"],
            "active": c.get("active", False),
            "arrived": (now() >= arrival_at) if arrival_at else True,
        })
    return out

@router.post("/campaigns/{campaign_id}/disband")
async def admin_disband_campaign(campaign_id: str, user: dict = Depends(full_admin_user)):
    """انحلال اداری: تمام نفرات، سکه، سلاح و ادوات به صاحب لشکر برمی‌گردد."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکرکشی نامعتبر است")
    c = await campaigns.find_one({"_id": oid})
    if not c:
        raise HTTPException(404, "این لشکرکشی پیدا نشد")
    if not c.get("active"):
        raise HTTPException(400, "این لشکرکشی دیگر فعال نیست")
    battle_change = await _remove_campaign_from_battle(c, "این لشکر به فرمان ادمین منحل شد.")
    changed = await campaigns.update_one({"_id": oid, "active": True}, {"$set": {"active": False, "status": "disbanded"}})
    if not changed.matched_count:
        raise HTTPException(409, "وضعیت لشکر همین الان تغییر کرد")
    owner = await players.find_one({"tg_id": c["tg_id"]})
    if owner:
        refund = {"men": c.get("men_committed", 0), "gold": c.get("gold_cost", 0)}
        for troop_id, count in c.get("troops", {}).items():
            weapon = TROOP_WEAPON_KEY.get(troop_id)
            if weapon:
                refund[weapon] = refund.get(weapon, 0) + int(count or 0) * int(game_data.GAME_RULES["weapon_per_soldier"])
        # فقط ادواتی که واقعاً هنوز در لشکر مانده‌اند برمی‌گردند؛ بازگرداندن
        # equipment_cost اولیه، ادوات منهدم‌شده در نبرد را دوباره زنده می‌کرد.
        for equipment_id, count in c.get("equipment", {}).items():
            for resource, unit_cost in SIEGE_EQUIPMENT.get(equipment_id, {}).get("cost", {}).items():
                refund[resource] = refund.get(resource, 0) + int(count or 0) * int(unit_cost or 0)
        add_resources(owner, refund)
        await players.update_one({"tg_id": c["tg_id"]}, {"$set": {"resources": owner["resources"]}})
        await send_system_message(
            owner["tg_id"], owner["name"],
            f"لشکر «{c.get('name') or OP_TYPES.get(c['op_type'], {}).get('name', c['op_type'])}» به فرمان ادمین منحل شد و تمام هزینه‌های باقی‌مانده‌اش برگشت.",
        )
    return {"ok": True, "battle_member_removed": battle_change["removed"], "battle_closed": battle_change["battle_closed"]}

@router.post("/campaigns/{campaign_id}/destroy")
async def admin_destroy_campaign(campaign_id: str, user: dict = Depends(full_admin_user)):
    """انهدام کامل لشکر؛ هیچ هزینه یا نیرویی برنمی‌گردد."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکرکشی نامعتبر است")
    c = await campaigns.find_one({"_id": oid, "active": True})
    if not c:
        raise HTTPException(404, "لشکر فعال پیدا نشد")
    battle_change = await _remove_campaign_from_battle(c, "این لشکر به فرمان ادمین کاملاً منهدم شد.")
    result = await campaigns.update_one(
        {"_id": oid, "active": True},
        {"$set": {"active": False, "status": "destroyed", "troops": {}, "men_committed": 0, "power": 0, "destroyed_at": now()}},
    )
    if not result.matched_count:
        raise HTTPException(409, "وضعیت لشکر همین الان تغییر کرد")
    owner = await players.find_one({"tg_id": c["tg_id"]}, {"tg_id": 1, "name": 1})
    if owner:
        await send_system_message(owner["tg_id"], owner["name"], f"لشکر «{c.get('name', 'بی‌نام')}» به فرمان ادمین کاملاً منهدم شد؛ هیچ هزینه‌ای برنگشت.")
    return {"ok": True, "battle_member_removed": battle_change["removed"], "battle_closed": battle_change["battle_closed"]}

class ReduceCampaignBody(BaseModel):
    troops: dict[str, int]

@router.post("/campaigns/{campaign_id}/reduce")
async def admin_reduce_campaign(campaign_id: str, body: ReduceCampaignBody, user: dict = Depends(full_admin_user)):
    """تلفات مستقیم ادمین؛ مقدار هر فیلد از همان نوع نیرو کم می‌شود و بازپرداخت ندارد."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکرکشی نامعتبر است")
    c = await campaigns.find_one({"_id": oid, "active": True})
    if not c:
        raise HTTPException(404, "لشکر فعال پیدا نشد")
    if c.get("engagement_locked") or c.get("engagement_campaign_id"):
        raise HTTPException(409, "این لشکر داخل نبرد باز است؛ تلفاتش را از همان پروندهٔ نبرد ثبت کن")
    current = dict(c.get("troops", {}))
    removed = {}
    for troop_id, raw in body.troops.items():
        loss = max(0, int(raw or 0))
        if troop_id not in current or loss > int(current[troop_id] or 0):
            raise HTTPException(400, f"تلفات {troop_id} از نیروی حاضر بیشتر است")
        if loss:
            current[troop_id] -= loss
            removed[troop_id] = loss
    if not removed:
        raise HTTPException(400, "حداقل یک تلفات وارد کن")
    old_men = max(1, int(c.get("men_committed", 0) or 0))
    men = sum(int(v or 0) for v in current.values())
    campaign_update = {
        "troops": current, "men_committed": men,
        "power": round(float(c.get("power", 0)) * men / old_men, 2), "admin_losses_at": now(),
    }
    if men == 0:
        campaign_update.update({"active": False, "status": "destroyed", "destroyed_at": now()})
    result = await campaigns.update_one(
        {"_id": oid, "active": True},
        {"$set": campaign_update},
    )
    if not result.matched_count:
        raise HTTPException(409, "وضعیت لشکر همین الان تغییر کرد")
    return {"ok": True, "removed": removed, "men_remaining": men, "destroyed": men == 0}

@router.get("/war-window")
async def admin_get_war_window(user: dict = Depends(admin_user)):
    """وضعیت فعلیِ پنجرهٔ لشکرکشی — پیش‌فرض باز است تا وقتی ادمین صریحاً ببندتش"""
    w = await get_war_window()
    updated_by_name = None
    if w["updated_by"]:
        p = await players.find_one({"tg_id": w["updated_by"]})
        updated_by_name = p["name"] if p else None
    return {"open": w["open"], "updated_at": w["updated_at"].isoformat() if w["updated_at"] else None, "updated_by": updated_by_name}

class AnnounceEventBody(BaseModel):
    title: str
    description: str
    image_url: str | None = None

@router.post("/announce-event")
async def announce_event(body: AnnounceEventBody, user: dict = Depends(admin_user)):
    """توضیحِ یک رویدادِ در-حالِ-بازی (مثلاً یک فصل/چالش تازه) — برای همهٔ بازیکنان
    به‌عنوان یک «رخداد» در تب اطلاعیه‌های کلاغ‌ها می‌رود"""
    title = body.title.strip()[:80]
    description = body.description.strip()[:1500]
    if not title or not description:
        raise HTTPException(400, "عنوان و توضیحِ رویداد نمی‌توانند خالی باشند")
    image_url = _validated_message_image(body.image_url)
    text = f"🎉 رویداد: {title}\n\n{description}"
    async for p in players.find({}, {"tg_id": 1, "name": 1}):
        await send_system_message(p["tg_id"], p["name"], text, kind="event", image_url=image_url)
    return {"ok": True}

class SendBotMessageBody(BaseModel):
    text: str
    send_to_all: bool = False
    to_tg_ids: list[int] | None = None
    via_bot: bool = True
    via_raven: bool = False
    image_url: str | None = None

def _validated_message_image(value: str | None):
    if not value: return None
    if not value.startswith(("https://", "data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
        raise HTTPException(400, "تصویر باید لینک HTTPS یا فایل JPG/PNG/WebP باشد")
    if len(value) > 3_500_000: raise HTTPException(400, "حجم تصویر باید حداکثر ۲٫۵ مگابایت باشد")
    return value

@router.post("/send-bot-message")
async def send_bot_message(body: SendBotMessageBody, user: dict = Depends(admin_user)):
    """ارسال انتخابی در بات تلگرام، صندوق کلاغ، یا هر دو."""
    text = body.text.strip()[:4000]
    if not text:
        raise HTTPException(400, "متن پیام نمی‌تواند خالی باشد")
    if not body.via_bot and not body.via_raven:
        raise HTTPException(400, "حداقل یکی از مسیرهای بات یا کلاغ را انتخاب کن")
    image_url = _validated_message_image(body.image_url)

    if body.send_to_all:
        targets = await players.find({}, {"tg_id": 1, "name": 1}).to_list(None)
    else:
        to_ids = list(dict.fromkeys(body.to_tg_ids or []))
        if not to_ids:
            raise HTTPException(400, "حداقل یک بازیکن را انتخاب کن")
        targets = await players.find(
            {"tg_id": {"$in": to_ids}}, {"tg_id": 1, "name": 1},
        ).to_list(len(to_ids))

    if not targets:
        raise HTTPException(404, "هیچ بازیکنی برای ارسال پیدا نشد")

    for target in targets:
        await send_system_message(
            target["tg_id"], target["name"], text,
            via_bot=body.via_bot, via_raven=body.via_raven,
            image_url=image_url,
        )
    return {"ok": True, "sent_to": len(targets), "via_bot": body.via_bot, "via_raven": body.via_raven}

class WarWindowBody(BaseModel):
    open: bool

@router.post("/war-window")
async def admin_set_war_window(body: WarWindowBody, user: dict = Depends(admin_user)):
    """باز/بستن پنجرهٔ لشکرکشی برای همهٔ بازیکنان — مثلاً فقط چند ساعت در روز
    اجازهٔ فرمانِ گسیل بدهی؛ بستن، لشکرهای در حال حرکت را متوقف نمی‌کند، فقط
    فرمان تازه نمی‌گیرد. با هر تغییر همهٔ بازیکنان کلاغ می‌گیرند"""
    was = await get_war_window()
    if was["open"] == body.open:
        raise HTTPException(400, f"پنجرهٔ لشکرکشی همین الان هم {'باز' if body.open else 'بسته'} است")
    await game_settings.update_one(
        {"_id": WAR_WINDOW_ID},
        {"$set": {"open": body.open, "updated_at": now(), "updated_by": user["id"]}},
        upsert=True,
    )
    text = (
        "پنجرهٔ لشکرکشی باز شد — از این لحظه می‌توانی فرمان گسیل نیرو بدهی."
        if body.open else
        "پنجرهٔ لشکرکشی بسته شد — تا اطلاع بعدی فرمان گسیل نیروی تازه ممکن نیست؛ لشکرهایی که در راهند دست‌نخورده می‌مانند."
    )
    async for p in players.find({}, {"tg_id": 1, "name": 1}):
        await send_system_message(p["tg_id"], p["name"], text)
    return {"ok": True, "open": body.open}

@router.get("/alliances")
async def admin_list_alliances(user: dict = Depends(admin_user)):
    """همهٔ پیمان‌ها — از جمله خصوصی و رد/در انتظار — برای مرور و در صورت نیاز انحلال"""
    out = []
    cur = alliances.find({}).sort("created_at", -1).limit(100)
    async for a in cur:
        out.append({
            "id": str(a["_id"]), "from": a["from_name"], "from_tg_id": a["from_id"],
            "to": a["to_name"], "to_tg_id": a["to_id"],
            "type": a["type"], "type_name": ALLIANCE_TYPES.get(a["type"], {}).get("name", a["type"]),
            "name": a.get("name") or "", "status": a["status"], "public": a.get("public", True),
            "created_at": a["created_at"].isoformat(),
        })
    return out

@router.post("/alliances/{alliance_id}/dissolve")
async def admin_dissolve_alliance(alliance_id: str, user: dict = Depends(full_admin_user)):
    """ادمین یک پیمانِ برقرار را زورکی منحل می‌کند — شمار اتحاد هر دو طرف کم می‌شود و هر دو باخبر می‌شوند"""
    try:
        oid = ObjectId(alliance_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ پیمان نامعتبر است")
    a = await alliances.find_one({"_id": oid})
    if not a:
        raise HTTPException(404, "این پیمان پیدا نشد")
    if a["status"] != "accepted":
        raise HTTPException(400, "فقط پیمان برقرار را می‌شود منحل کرد")

    await alliances.update_one({"_id": oid}, {"$set": {"status": "dissolved"}})
    await players.update_one({"tg_id": a["from_id"]}, {"$inc": {"alliance_count": -1}})
    await players.update_one({"tg_id": a["to_id"]}, {"$inc": {"alliance_count": -1}})
    for tg_id, name, other_name in [(a["from_id"], a["from_name"], a["to_name"]), (a["to_id"], a["to_name"], a["from_name"])]:
        await send_system_message(tg_id, name, f"پیمانت با لرد {other_name} به فرمان ادمین منحل شد.")
    return {"ok": True}

async def _current_admin_ids() -> set:
    admin_ids = set(ADMIN_IDS)
    async for a in admin_roles.find({}, {"tg_id": 1}):
        admin_ids.add(a["tg_id"])
    return admin_ids

@router.get("/reset-game/preview")
async def reset_game_preview(user: dict = Depends(owner_user)):
    """پیش‌نمایشِ اثر ری‌استارت — قبل از تاییدِ نهایی نشان بده چند نفر حذف می‌شوند"""
    admin_ids = await _current_admin_ids()
    total = await players.count_documents({})
    non_admin = await players.count_documents({"tg_id": {"$nin": list(admin_ids)}})
    return {"total_players": total, "non_admin_players": non_admin, "admins_kept": total - non_admin}

class ResetGameBody(BaseModel):
    confirm: str

async def _clear_season_history():
    """پرونده‌های مربوط به یک فصل را پاک می‌کند؛ داده‌های تنظیمی ادمین دست‌نخورده‌اند."""
    for collection in (
        campaigns, ambushes, spy_missions, messages, roleplays, rebellions, rebellion_checks,
        rumors, alliances, polls, caravans, hierarchy, item_grants, admin_notifications,
    ):
        await collection.delete_many({})

@router.post("/reset-season")
async def reset_season(body: ResetGameBody, user: dict = Depends(owner_user)):
    """شروع فصل تازه بدون حذف بازیکن، جایگاه، قلعه، خاندان یا قلعه‌های فتح‌شده."""
    if body.confirm.strip() != "NEWSEASON":
        raise HTTPException(400, "برای تایید، دقیقاً عبارت NEWSEASON را تایپ کن")
    started_at = now()
    rebellion_settings = await get_rebellion_settings()
    reset_count = 0
    async for player in players.find({}):
        extra_castles = {castle: {} for castle in (player.get("castle_buildings") or {})}
        blank = {}
        normalize_stats(blank)
        title = DEFAULT_TITLE.get(player.get("gender", "lord"), DEFAULT_TITLE["lord"])
        await players.update_one({"_id": player["_id"]}, {
            "$set": {
                "resources": dict(STARTING_RESOURCES), "troops": {}, "buildings": {},
                "castle_buildings": extra_castles, "points": 100, "scoreboard_baseline": 0,
                "popularity": POPULARITY_START, "tax_rate": TAX_RATE_DEFAULT,
                "alliance_count": 0, "last_feast": None, "last_tick": started_at,
                "season_started_at": started_at, "stats": blank["stats"], "medals": {},
                "title": title, "food_ration": rebellion_settings.get("default_ration", "normal"), "daily_streak": 0,
            },
            "$unset": {
                "daily_last_claim_date": "", "weekly_baseline_score": "",
                "weekly_baseline_at": "", "epithet": "",
            },
        })
        reset_count += 1
    await _clear_season_history()
    return {"ok": True, "players_reset": reset_count}

@router.post("/reset-scoreboard")
async def reset_scoreboard(body: ResetGameBody, user: dict = Depends(owner_user)):
    """صفرکردن مبنای جدول، بدون تغییر منابع، ساختمان‌ها و دارایی بازیکنان."""
    if body.confirm.strip() != "SCOREBOARD":
        raise HTTPException(400, "برای تایید، دقیقاً عبارت SCOREBOARD را تایپ کن")
    from ranks import base_score, get_hierarchy_doc, title_bonus_and_rank
    hierarchy_doc = await get_hierarchy_doc()
    count = 0
    async for player in players.find({}):
        bonus, _ = title_bonus_and_rank(player["tg_id"], hierarchy_doc)
        baseline = round(base_score(player) + bonus)
        await players.update_one({"_id": player["_id"]}, {
            "$set": {"scoreboard_baseline": baseline},
            "$unset": {"weekly_baseline_score": "", "weekly_baseline_at": ""},
        })
        count += 1
    return {"ok": True, "players_reset": count}

@router.post("/reset-game")
async def reset_game(body: ResetGameBody, user: dict = Depends(owner_user)):
    """ری‌استارت کامل بازی — فقط صاحب بازی، فقط با تایپ عبارت تاییدیه (RESET).
    حذف می‌شود: همهٔ بازیکنانِ غیرادمین و کل تاریخچهٔ لشکرکشی/جاسوسی/پیام/رول/
    توییت/اتحاد/رای‌گیری/کاروان/مقام‌ها.
    دست‌نخورده می‌ماند: قلعه‌های ثبت‌شده روی نقشه (map_castles)، آیتم‌ها و
    بازارهایی که ادمین‌ها ساخته‌اند (items، market_listings، black_market_listings)،
    خودِ نقش‌های ادمین (admin_roles)، و حساب/پیشرفتِ خودِ ادمین‌ها دست‌نخورده می‌ماند"""
    if body.confirm.strip() != "RESET":
        raise HTTPException(400, "برای تایید، دقیقاً عبارت RESET را تایپ کن")

    admin_ids = await _current_admin_ids()

    # ادمین‌هایی که نگه داشته می‌شن ممکنه لشکرکشیِ فعال داشته باشن — قبل از پاک‌کردنِ
    # کاملِ campaigns، نفرات/طلا/تسلیحاتشون رو برمی‌گردونیم (دقیقاً مثلِ منحل‌کردنِ دستی
    # در /war/{id}/cancel)، وگرنه ادعای «پیشرفتِ ادمین دست‌نخورده می‌ماند» درست نبود
    async for c in campaigns.find({"tg_id": {"$in": list(admin_ids)}, "active": True}):
        owner = await players.find_one({"tg_id": c["tg_id"]})
        if owner:
            weapons_refund = {}
            for tid, n in c.get("troops", {}).items():
                if not n or n <= 0:
                    continue
                weapon_key = TROOP_WEAPON_KEY.get(tid)
                if weapon_key:
                    weapons_refund[weapon_key] = weapons_refund.get(weapon_key, 0) + n * int(game_data.GAME_RULES["weapon_per_soldier"])
            refunds = {"men": c["men_committed"], "gold": c["gold_cost"], **weapons_refund}
            for resource, amount in c.get("equipment_cost", {}).items():
                refunds[resource] = refunds.get(resource, 0) + amount
            add_resources(owner, refunds)
            await players.update_one({"tg_id": c["tg_id"]}, {"$set": {"resources": owner["resources"]}})

    deleted = await players.delete_many({"tg_id": {"$nin": list(admin_ids)}})

    await _clear_season_history()
    # اتحادها پاک شدند، پس شمارندهٔ اتحادِ ادمین‌هایی که نگه داشته شدند هم صفر شود
    await players.update_many({}, {"$set": {"alliance_count": 0}})

    return {"ok": True, "players_deleted": deleted.deleted_count}

# ---- تعادل بازی — هزینه، رشد ارتقا، بازدهی و سقفِ سراسریِ ساختمان‌ها
BUILDING_OVERRIDES_DOC_ID = "building_overrides"

@router.get("/building-balance")
async def get_building_balance(user: dict = Depends(full_admin_user)):
    out = []
    for bid, meta in BUILDINGS.items():
        base_cost = meta.get("cost", {})
        base_produces = meta.get("produces", {})
        base_cap_bonus = meta.get("cap_bonus", {})
        override = game_data.BUILDING_OVERRIDES.get(bid, {})
        out.append({
            "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
            "base_cost": base_cost, "cost": building_base_cost(bid),
            "base_cost_step_percent": round(game_data.LEVEL_COST_STEP * 100, 2),
            "cost_step_percent": round(building_cost_step(bid) * 100, 2),
            "base_hours": meta.get("hours", 0), "hours": override.get("hours", meta.get("hours", 0)),
            "base_max_level": int(meta.get("max_level", game_data.MAX_BUILDING_LEVEL)),
            "max_level": building_max_level(bid),
            "base_produces": base_produces, "base_cap_bonus": base_cap_bonus,
            "overridden": bool(override),
            "produces": building_produces(bid), "cap_bonus": building_cap_bonus(bid),
            "cost_preview": {
                "level_1": building_cost(bid, 1),
                "level_2": building_cost(bid, 2),
                "level_10": building_cost(bid, 10),
            },
        })
    return out

class BuildingBalanceBody(BaseModel):
    building_id: str
    cost: dict[str, int] = {}
    cost_step_percent: float = 15
    produces: dict[str, int] = {}
    cap_bonus: dict[str, int] = {}
    hours: float = 0
    max_level: int = 30

@router.post("/building-balance")
async def set_building_balance(body: BuildingBalanceBody, user: dict = Depends(full_admin_user)):
    """تنظیم سراسری هزینهٔ پایه، رشد هزینهٔ ارتقا، تولید و افزایش سقف هر ساختمان."""
    meta = BUILDINGS.get(body.building_id)
    if not meta:
        raise HTTPException(400, "ساختمان نامعتبر")
    allowed_cost = set(meta.get("cost", {}).keys())
    allowed_produces = set(meta.get("produces", {}).keys())
    allowed_cap = set(meta.get("cap_bonus", {}).keys())
    if not set(body.cost).issubset(allowed_cost):
        raise HTTPException(400, "این ساختمان چنین منبعی در هزینهٔ ساخت ندارد")
    if not set(body.produces).issubset(allowed_produces) or not set(body.cap_bonus).issubset(allowed_cap):
        raise HTTPException(400, "این ساختمان چنین منبعی تولید/ذخیره نمی‌کند")
    values = list(body.cost.values()) + list(body.produces.values()) + list(body.cap_bonus.values())
    if any(v < 0 for v in values):
        raise HTTPException(400, "مقدار نمی‌تواند منفی باشد")
    if not 0 <= float(body.cost_step_percent) <= 500:
        raise HTTPException(400, "درصد رشد هزینه باید بین صفر تا ۵۰۰ باشد")
    if body.hours < 0.1 or not 1 <= body.max_level <= 100:
        raise HTTPException(400, "زمان پایه باید مثبت و سقف سطح بین ۱ تا ۱۰۰ باشد")

    override = {
        "cost": body.cost,
        "cost_step": float(body.cost_step_percent) / 100,
        "hours": float(body.hours), "max_level": int(body.max_level),
    }
    if body.produces:
        override["produces"] = body.produces
    if body.cap_bonus:
        override["cap_bonus"] = body.cap_bonus

    game_data.BUILDING_OVERRIDES[body.building_id] = override
    await game_settings.update_one(
        {"_id": BUILDING_OVERRIDES_DOC_ID},
        {"$set": {f"overrides.{body.building_id}": override}},
        upsert=True,
    )
    return {"ok": True}

@router.post("/building-balance/{building_id}/reset")
async def reset_building_balance(building_id: str, user: dict = Depends(full_admin_user)):
    if building_id not in BUILDINGS:
        raise HTTPException(400, "ساختمان نامعتبر")
    game_data.BUILDING_OVERRIDES.pop(building_id, None)
    await game_settings.update_one(
        {"_id": BUILDING_OVERRIDES_DOC_ID}, {"$unset": {f"overrides.{building_id}": ""}}, upsert=True,
    )
    return {"ok": True}


# ---- تعادل کامل نیروها، کشتی‌ها، ادوات و قواعد مشترک
GAMEPLAY_BALANCE_DOC_ID = "gameplay_balance"

def _gameplay_balance_payload():
    rules = dict(game_data.GAME_RULES)
    return {
        "rules": {
            "camp_power_step_percent": round(float(rules["camp_power_step"]) * 100, 3),
            "special_troop_cost": rules["special_troop_cost"],
            "special_troop_power": rules["special_troop_power"],
            "food_cost_regular": rules["food_cost_regular"],
            "food_cost_special": rules["food_cost_special"],
            "weapon_per_soldier": rules["weapon_per_soldier"],
            "level_hours_step_percent": round(float(rules["level_hours_step"]) * 100, 3),
            "default_max_building_level": rules["default_max_building_level"],
            "equipment_slowdown_cap_percent": round(float(rules["equipment_slowdown_cap"]) * 100, 3),
            "commander_power_bonus_percent": round(float(rules["commander_power_bonus"]) * 100, 3),
            "commander_speed_bonus_percent": round(float(rules["commander_speed_bonus"]) * 100, 3),
        },
        "common_troops": [{"id": tid, **meta} for tid, meta in game_data.COMMON_TROOPS.items()],
        "naval_troops": [{"id": tid, **meta} for tid, meta in game_data.NAVAL_TROOPS.items()],
        "equipment": [{**meta, "id": eid, "slowdown_percent": round(float(meta.get("slowdown", 0)) * 100, 3)} for eid, meta in game_data.SIEGE_EQUIPMENT.items()],
    }

@router.get("/gameplay-balance")
async def get_gameplay_balance(user: dict = Depends(full_admin_user)):
    return _gameplay_balance_payload()

class GameplayBalanceBody(BaseModel):
    rules: dict = {}
    common_troops: list[dict] = []
    naval_troops: list[dict] = []
    equipment: list[dict] = []

def _num(value, name: str, minimum=0, maximum=1_000_000):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{name} باید عدد باشد")
    if not minimum <= number <= maximum:
        raise HTTPException(400, f"{name} باید بین {minimum} و {maximum} باشد")
    return number

@router.post("/gameplay-balance")
async def set_gameplay_balance(body: GameplayBalanceBody, user: dict = Depends(full_admin_user)):
    r = body.rules
    clean_rules = {
        "camp_power_step": _num(r.get("camp_power_step_percent"), "رشد قدرت پادگان", 0, 500) / 100,
        "special_troop_cost": _num(r.get("special_troop_cost"), "هزینه نیروی ویژه"),
        "special_troop_power": _num(r.get("special_troop_power"), "قدرت نیروی ویژه"),
        "food_cost_regular": _num(r.get("food_cost_regular"), "مصرف غذای نیروی عادی"),
        "food_cost_special": _num(r.get("food_cost_special"), "مصرف غذای نیروی ویژه"),
        "weapon_per_soldier": int(_num(r.get("weapon_per_soldier"), "تسلیحات هر سرباز", 0, 100)),
        "level_hours_step": _num(r.get("level_hours_step_percent"), "رشد زمان ارتقا", 0, 500) / 100,
        "default_max_building_level": int(_num(r.get("default_max_building_level"), "سقف عمومی سطح", 1, 100)),
        "equipment_slowdown_cap": _num(r.get("equipment_slowdown_cap_percent"), "سقف کندی ادوات", 0, 1000) / 100,
        "commander_power_bonus": _num(r.get("commander_power_bonus_percent"), "امتیاز قدرت فرمانده", 0, 500) / 100,
        "commander_speed_bonus": _num(r.get("commander_speed_bonus_percent"), "امتیاز سرعت فرمانده", 0, 100) / 100,
    }

    common = {}
    for row in body.common_troops:
        tid = row.get("id")
        if tid not in game_data.DEFAULT_COMMON_TROOPS:
            raise HTTPException(400, "نوع سرباز نامعتبر است")
        common[tid] = {
            "name": game_data.DEFAULT_COMMON_TROOPS[tid]["name"],
            "cost": _num(row.get("cost"), f"هزینه {tid}"),
            "power": _num(row.get("power"), f"قدرت {tid}"),
            "food": _num(row.get("food"), f"مصرف غذای {tid}"),
        }

    naval = {}
    for row in body.naval_troops:
        tid = row.get("id")
        if tid not in game_data.DEFAULT_NAVAL_TROOPS:
            raise HTTPException(400, "نوع کشتی نامعتبر است")
        naval[tid] = {
            "name": game_data.DEFAULT_NAVAL_TROOPS[tid]["name"],
            "cost": _num(row.get("cost"), f"هزینه {tid}"),
            "power": _num(row.get("power"), f"قدرت {tid}"),
            "capacity": int(_num(row.get("capacity"), f"ظرفیت {tid}", 0, 100000)),
            "food": _num(row.get("food"), f"مصرف غذای {tid}"),
        }

    equipment = {}
    for row in body.equipment:
        eid = row.get("id")
        default = game_data.DEFAULT_SIEGE_EQUIPMENT.get(eid)
        if not default:
            raise HTTPException(400, "نوع ادوات نامعتبر است")
        raw_cost = row.get("cost") or {}
        if not set(raw_cost).issubset({"gold", "wood", "stone", "iron", "food", "wine"}):
            raise HTTPException(400, "منبع هزینه ادوات نامعتبر است")
        equipment[eid] = {
            "name": default["name"],
            "level": int(_num(row.get("level"), f"سطح {eid}", 1, 100)),
            "cost": {k: int(_num(v, f"هزینه {eid}")) for k, v in raw_cost.items()},
            "siege_power": _num(row.get("siege_power"), f"قدرت {eid}"),
            "slowdown": _num(row.get("slowdown_percent"), f"کندی {eid}", 0, 1000) / 100,
        }

    if set(common) != set(game_data.DEFAULT_COMMON_TROOPS) or set(naval) != set(game_data.DEFAULT_NAVAL_TROOPS) or set(equipment) != set(game_data.DEFAULT_SIEGE_EQUIPMENT):
        raise HTTPException(400, "فهرست کامل نیروها و ادوات باید ارسال شود")
    game_data.GAME_RULES.clear(); game_data.GAME_RULES.update(clean_rules)
    game_data.COMMON_TROOPS.clear(); game_data.COMMON_TROOPS.update(common)
    game_data.NAVAL_TROOPS.clear(); game_data.NAVAL_TROOPS.update(naval)
    game_data.SIEGE_EQUIPMENT.clear(); game_data.SIEGE_EQUIPMENT.update(equipment)
    await game_settings.update_one(
        {"_id": GAMEPLAY_BALANCE_DOC_ID},
        {"$set": {"rules": clean_rules, "common_troops": common, "naval_troops": naval, "equipment": equipment}},
        upsert=True,
    )
    return _gameplay_balance_payload()

@router.post("/gameplay-balance/reset")
async def reset_gameplay_balance(user: dict = Depends(full_admin_user)):
    game_data.GAME_RULES.clear(); game_data.GAME_RULES.update(game_data.DEFAULT_GAME_RULES)
    game_data.COMMON_TROOPS.clear(); game_data.COMMON_TROOPS.update(game_data._copy.deepcopy(game_data.DEFAULT_COMMON_TROOPS))
    game_data.NAVAL_TROOPS.clear(); game_data.NAVAL_TROOPS.update(game_data._copy.deepcopy(game_data.DEFAULT_NAVAL_TROOPS))
    game_data.SIEGE_EQUIPMENT.clear(); game_data.SIEGE_EQUIPMENT.update(game_data._copy.deepcopy(game_data.DEFAULT_SIEGE_EQUIPMENT))
    await game_settings.delete_one({"_id": GAMEPLAY_BALANCE_DOC_ID})
    return _gameplay_balance_payload()


class AdminPlayerBuildingBody(BaseModel):
    castle: str
    level: int

@router.get("/players/{tg_id}/buildings")
async def admin_player_buildings(tg_id: int, user: dict = Depends(full_admin_user)):
    """وضعیت همهٔ ساختمان‌ها در تک‌تک قلعه‌های یک بازیکن برای مدیریت مستقیم."""
    player = await players.find_one({"tg_id": tg_id})
    if not player:
        raise HTTPException(404, "بازیکن پیدا نشد")
    resolve_building_upgrades(player)
    await players.update_one({"tg_id": tg_id}, {"$set": {
        "buildings": player.get("buildings", {}),
        "castle_buildings": player.get("castle_buildings", {}),
    }})
    castles = []
    for castle in owned_castles(player):
        state = castle_building_state(player, castle)
        rows = []
        for bid, meta in BUILDINGS.items():
            st = normalize_building_state(state.get(bid))
            rows.append({
                "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
                "requires_port": bool(meta.get("requires_port")),
                "level": int(st.get("level", 0)),
                "max_level": building_max_level(bid),
                "upgrade_to": st.get("upgrade_to"),
                "ready_at": st.get("ready_at").isoformat() if st.get("ready_at") else None,
            })
        castles.append({"castle": castle, "home": castle == player.get("castle"), "buildings": rows})
    return {"tg_id": tg_id, "player_name": player.get("name"), "castles": castles, "max_level": game_data.MAX_BUILDING_LEVEL}

@router.post("/players/{tg_id}/buildings/{building_id}")
async def admin_set_player_building(
    tg_id: int, building_id: str, body: AdminPlayerBuildingBody,
    user: dict = Depends(full_admin_user),
):
    """سطح ساختمان را مستقیم تعیین می‌کند؛ صفر یعنی حذف و ثبت سطح، ساختِ درحال‌انجام را لغو می‌کند."""
    if building_id not in BUILDINGS:
        raise HTTPException(400, "ساختمان نامعتبر")
    max_level = building_max_level(building_id)
    if not 0 <= body.level <= max_level:
        raise HTTPException(400, f"سطح باید بین صفر تا {max_level} باشد")
    player = await players.find_one({"tg_id": tg_id})
    if not player:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if body.castle not in owned_castles(player):
        raise HTTPException(400, "این قلعه متعلق به بازیکن نیست")
    state = castle_building_state(player, body.castle)
    if body.level == 0:
        state.pop(building_id, None)
    else:
        state[building_id] = {"level": body.level, "upgrade_to": None, "ready_at": None}
    await players.update_one({"tg_id": tg_id}, {"$set": {
        "buildings": player.get("buildings", {}),
        "castle_buildings": player.get("castle_buildings", {}),
    }})
    return {"ok": True, "building_id": building_id, "castle": body.castle, "level": body.level}


class MedalAwardBody(BaseModel):
    tier: str
    reason: str = ""


@router.post("/players/{tg_id}/medals/realm-storyteller")
async def award_realm_storyteller(tg_id: int, body: MedalAwardBody, user: dict = Depends(admin_user)):
    """اعطای دستی مدال راوی قلمرو؛ سطح پایین‌تر مدال قبلی را تنزل نمی‌دهد."""
    if body.tier not in TIER_ORDER:
        raise HTTPException(400, "سطح مدال نامعتبر است")
    player = await players.find_one({"tg_id": tg_id})
    if not player:
        raise HTTPException(404, "بازیکن پیدا نشد")
    medals = dict(player.get("medals") or {})
    current = medals.get("realm_storyteller")
    current_tier = current.get("tier") if isinstance(current, dict) else current
    if TIER_ORDER[body.tier] < TIER_ORDER.get(current_tier, 0):
        raise HTTPException(400, "مدال بازیکن را نمی‌توان به سطح پایین‌تر تنزل داد")
    medals["realm_storyteller"] = {
        "tier": body.tier, "reason": body.reason.strip(), "awarded_at": now(),
        "awarded_by": user["id"],
    }
    await players.update_one({"tg_id": tg_id}, {"$set": {"medals": medals}})
    player["medals"] = medals
    return {"ok": True, "medals": medal_rows(player)}


class SpecialMedalBody(BaseModel):
    name: str
    icon: str = "🏅"
    tier: str = "gold"
    reason: str = ""


@router.post("/players/{tg_id}/medals/special")
async def award_special_medal(tg_id: int, body: SpecialMedalBody, user: dict = Depends(admin_user)):
    """مدال ویژه و کاملاً سفارشی ادمین؛ چند مدال ویژه می‌تواند به یک بازیکن داده شود."""
    name = body.name.strip()[:60]
    icon = body.icon.strip()[:8] or "🏅"
    if not name:
        raise HTTPException(400, "نام مدال الزامی است")
    if body.tier not in TIER_ORDER:
        raise HTTPException(400, "سطح مدال نامعتبر است")
    player = await players.find_one({"tg_id": tg_id})
    if not player:
        raise HTTPException(404, "بازیکن پیدا نشد")
    medals = dict(player.get("medals") or {})
    key = f"special_{ObjectId()}"
    medals[key] = {
        "tier": body.tier, "name": name, "icon": icon,
        "reason": body.reason.strip()[:300], "manual": True,
        "awarded_at": now(), "awarded_by": user["id"],
    }
    await players.update_one({"tg_id": tg_id}, {"$set": {"medals": medals}})
    player["medals"] = medals
    return {"ok": True, "medals": medal_rows(player)}
    image_url = _validated_message_image(body.image_url)
