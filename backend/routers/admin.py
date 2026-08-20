import random
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin, get_full_admin, get_owner
from db import (
    campaigns, players, admin_roles, map_castles, market_listings, black_market_listings,
    spy_missions, roleplays, items, item_grants, alliances, game_settings,
    caravans, messages, rumors, hierarchy, polls, rebellions, rebellion_checks, admin_notifications,
)
import game_data
import telegram_bot
from game import now, add_resources, building_levels_for, effective_caps, resolve_building_upgrades
from medals import MEDALS, TIER_ORDER, bump_player_stat, medal_rows
from game_data import REGIONS, COMMON_TROOPS, TRADE_GOODS, BUILDINGS, ROLEPLAY_CATEGORIES, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, ALLIANCE_TYPES, CASTLE_HOUSES, MAP_TERRAINS, building_produces, building_cap_bonus, TROOP_WEAPON_KEY, WEAPON_PER_SOLDIER
from config import ADMIN_IDS
from routers.war import OP_TYPES, get_war_window, WAR_WINDOW_ID, all_castle_terrain, owner_of_castle
from routers.ravens import send_system_message
from routers.rebellions import get_settings as get_rebellion_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

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
        row = {
            "id": str(r["_id"]), "player": r["player_name"], "tg_id": r["tg_id"], "castle": r["castle"],
            "category": r["category"], "category_name": ROLEPLAY_CATEGORIES.get(r["category"], r["category"]),
            "text": r["text"], "campaign_id": r.get("campaign_id"), "sibling": None,
            "created_at": r["created_at"].isoformat(), "war": None,
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
                }
        out.append(row)
    return out

class RoleplayResultBody(BaseModel):
    result: str
    visibility: str = "participants"   # "participants" | "all" — چه کسی نتیجه را کلاغ می‌گیرد
    other_lords: list[int] = []
    winner_tg_id: int | None = None        # ادمین دستی مشخص می‌کند این رول بین چه لردهای دیگری هم بوده —
                                        # چون سناریوی یک لرد ممکن است به چند لرد دیگر اشاره کند، نه فقط
                                        # طرف مقابلِ خودکارِ لشکرکشی (که فقط برای دستهٔ «جنگ» پیدا می‌شود)

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

    if r["category"] == "war" and r.get("campaign_id"):
        sibling = await roleplays.find_one({
            "category": "war", "campaign_id": r["campaign_id"],
            "tg_id": {"$ne": r["tg_id"]}, "resolved": False,
        })
        if sibling:
            ids_to_resolve.append(sibling["_id"])
            recipient_tg_ids.add(sibling["tg_id"])
        try:
            campaign = await campaigns.find_one({"_id": ObjectId(r["campaign_id"])})
        except Exception:
            campaign = None
        if campaign:
            recipient_tg_ids.add(campaign["tg_id"])
            defender = await owner_of_castle(campaign["target_castle"])
            if defender:
                recipient_tg_ids.add(defender["tg_id"])
            valid_winners = {campaign["tg_id"]}
            if defender:
                valid_winners.add(defender["tg_id"])
            if body.winner_tg_id not in valid_winners:
                raise HTTPException(400, "برندهٔ نبرد را از بین مهاجم و مدافع انتخاب کن")
            combat_outcome = "attacker" if body.winner_tg_id == campaign["tg_id"] else "defender"

    other_lord_names = []
    for tg_id in body.other_lords:
        lord = await players.find_one({"tg_id": tg_id})
        if lord:
            recipient_tg_ids.add(tg_id)
            other_lord_names.append(lord["name"])

    # قفل نتیجه روی خود لشکرکشی مانع دوباره‌شماری پیروزی با کلیک/درخواست تکراری می‌شود.
    if campaign and combat_outcome:
        outcome_guard = await campaigns.update_one(
            {"_id": campaign["_id"], "medal_outcome_recorded": {"$ne": True}},
            {"$set": {
                "medal_outcome_recorded": True, "combat_outcome": combat_outcome,
                "winner_tg_id": body.winner_tg_id, "combat_resolved_at": now(),
            }},
        )
        if outcome_guard.modified_count:
            await bump_player_stat(
                body.winner_tg_id,
                "attack_wins" if combat_outcome == "attacker" else "defense_wins",
            )
            rebellion_settings = await get_rebellion_settings()
            war_pop = rebellion_settings["war_popularity"]
            attacker = await players.find_one({"tg_id": campaign["tg_id"]})
            if attacker:
                attacker_delta = war_pop["attack_win"] if combat_outcome == "attacker" else war_pop["attack_loss"]
                attacker_pop = max(0, min(100, int(attacker.get("popularity", 50)) + int(attacker_delta)))
                await players.update_one({"tg_id": attacker["tg_id"]}, {"$set": {"popularity": attacker_pop}})
            if defender:
                defender_delta = war_pop["defense_win"] if combat_outcome == "defender" else war_pop["defense_loss"]
                defender_pop = max(0, min(100, int(defender.get("popularity", 50)) + int(defender_delta)))
                await players.update_one({"tg_id": defender["tg_id"]}, {"$set": {"popularity": defender_pop}})

    await roleplays.update_many({"_id": {"$in": ids_to_resolve}}, {"$set": {
        "result": result[:4000], "resolved": True, "resolved_at": now(),
        **({"winner_tg_id": body.winner_tg_id, "combat_outcome": combat_outcome} if combat_outcome else {}),
    }})

    if body.visibility == "all":
        recipient_tg_ids = {p["tg_id"] async for p in players.find({}, {"tg_id": 1})}

    cat_name = ROLEPLAY_CATEGORIES.get(r["category"], r["category"])
    prefix = "اعلامیهٔ عمومی" if body.visibility == "all" else f"نتیجهٔ رول «{cat_name}»{'ِ نبرد' if r['category'] == 'war' else ''}"
    parties_line = ""
    if other_lord_names:
        all_names = list(dict.fromkeys([r["player_name"], *other_lord_names]))
        parties_line = f"\nطرف‌های این رول: {' و '.join(all_names)}"
    for tg_id in recipient_tg_ids:
        player = await players.find_one({"tg_id": tg_id})
        if player:
            await send_system_message(player["tg_id"], player["name"], f"{prefix}: {result}{parties_line}")

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
    house = CASTLE_HOUSES.get(body.castle)
    terrain = await all_castle_terrain()
    is_port = terrain.get(body.castle, "land") in ("coastal", "sea")
    await players.update_one({"tg_id": tg_id}, {"$set": {
        "region": body.region, "castle": body.castle, "is_port": is_port,
        "house": house,
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

@router.post("/admins")
async def add_admin(body: AddAdminBody, user: dict = Depends(full_admin_user)):
    if body.tg_id in ADMIN_IDS:
        raise HTTPException(400, "این کاربر از قبل ادمین کامل است")
    if not await players.find_one({"tg_id": body.tg_id}):
        raise HTTPException(404, "این کاربر هنوز ثبت‌نام نکرده")
    await admin_roles.update_one(
        {"tg_id": body.tg_id},
        {"$set": {"tg_id": body.tg_id, "role": "limited", "added_by": user["id"], "created_at": now()}},
        upsert=True,
    )
    return {"ok": True}

@router.delete("/admins/{tg_id}")
async def remove_admin(tg_id: int, user: dict = Depends(full_admin_user)):
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
        "resources": res,
        "resource_caps": resource_caps,
    }

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
            {"name": COMMON_TROOPS[t]["name"] if t in COMMON_TROOPS else t, "count": n}
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
    """ادمین هر لشکرکشیِ فعالی را (از هر بازیکنی) منحل می‌کند — نفراتش به صاحبش برمی‌گردد"""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکرکشی نامعتبر است")
    c = await campaigns.find_one({"_id": oid})
    if not c:
        raise HTTPException(404, "این لشکرکشی پیدا نشد")
    if not c.get("active"):
        raise HTTPException(400, "این لشکرکشی دیگر فعال نیست")
    await campaigns.update_one({"_id": oid}, {"$set": {"active": False, "status": "disbanded"}})
    owner = await players.find_one({"tg_id": c["tg_id"]})
    if owner:
        add_resources(owner, {"men": c["men_committed"]})
        await players.update_one({"tg_id": c["tg_id"]}, {"$set": {"resources": owner["resources"]}})
        await send_system_message(
            owner["tg_id"], owner["name"],
            f"لشکر «{c.get('name') or OP_TYPES.get(c['op_type'], {}).get('name', c['op_type'])}» به فرمان ادمین منحل شد و نفراتش به خانه برگشتند.",
        )
    return {"ok": True}

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

@router.post("/announce-event")
async def announce_event(body: AnnounceEventBody, user: dict = Depends(admin_user)):
    """توضیحِ یک رویدادِ در-حالِ-بازی (مثلاً یک فصل/چالش تازه) — برای همهٔ بازیکنان
    به‌عنوان یک «رخداد» در تب اطلاعیه‌های کلاغ‌ها می‌رود"""
    title = body.title.strip()[:80]
    description = body.description.strip()[:1500]
    if not title or not description:
        raise HTTPException(400, "عنوان و توضیحِ رویداد نمی‌توانند خالی باشند")
    text = f"🎉 رویداد: {title}\n\n{description}"
    async for p in players.find({}, {"tg_id": 1, "name": 1}):
        await send_system_message(p["tg_id"], p["name"], text)
    return {"ok": True}

class SendBotMessageBody(BaseModel):
    text: str
    send_to_all: bool = False
    to_tg_ids: list[int] | None = None

@router.post("/send-bot-message")
async def send_bot_message(body: SendBotMessageBody, user: dict = Depends(admin_user)):
    """ارسال پیام مستقیم از طرف بات تلگرام، بدون ثبت در صندوق کلاغ‌های داخل اپ."""
    text = body.text.strip()[:4000]
    if not text:
        raise HTTPException(400, "متن پیام نمی‌تواند خالی باشد")

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
        telegram_bot.push(target["tg_id"], text)
    return {"ok": True, "sent_to": len(targets)}

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

@router.post("/reset-game")
async def reset_game(body: ResetGameBody, user: dict = Depends(owner_user)):
    """ری‌استارت کامل بازی — فقط صاحب بازی، فقط با تایپ عبارت تاییدیه (RESET).
    حذف می‌شود: همهٔ بازیکنانِ غیرادمین و کل تاریخچهٔ لشکرکشی/جاسوسی/پیام/رول/
    شایعه/اتحاد/رای‌گیری/کاروان/مقام‌ها.
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
                    weapons_refund[weapon_key] = weapons_refund.get(weapon_key, 0) + n * WEAPON_PER_SOLDIER
            add_resources(owner, {"men": c["men_committed"], "gold": c["gold_cost"], **weapons_refund})
            await players.update_one({"tg_id": c["tg_id"]}, {"$set": {"resources": owner["resources"]}})

    deleted = await players.delete_many({"tg_id": {"$nin": list(admin_ids)}})

    await campaigns.delete_many({})
    await spy_missions.delete_many({})
    await messages.delete_many({})
    await roleplays.delete_many({})
    await rebellions.delete_many({})
    await rebellion_checks.delete_many({})
    await rumors.delete_many({})
    await alliances.delete_many({})
    await polls.delete_many({})
    await caravans.delete_many({})
    await hierarchy.delete_many({})
    await item_grants.delete_many({})
    # اتحادها پاک شدند، پس شمارندهٔ اتحادِ ادمین‌هایی که نگه داشته شدند هم صفر شود
    await players.update_many({}, {"$set": {"alliance_count": 0}})

    return {"ok": True, "players_deleted": deleted.deleted_count}

# ---- تعادل بازی — بازدهی/سقفِ سراسریِ ساختمان‌ها؛ روی همهٔ بازیکن‌ها یکسان اثر می‌کند
BUILDING_OVERRIDES_DOC_ID = "building_overrides"

@router.get("/building-balance")
async def get_building_balance(user: dict = Depends(full_admin_user)):
    out = []
    for bid, meta in BUILDINGS.items():
        base_produces = meta.get("produces", {})
        base_cap_bonus = meta.get("cap_bonus", {})
        if not base_produces and not base_cap_bonus:
            continue  # ساختمان‌هایی مثل پادگان/دیوار که اصلاً بازدهی یا سقفی ندارند
        override = game_data.BUILDING_OVERRIDES.get(bid, {})
        out.append({
            "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
            "base_produces": base_produces, "base_cap_bonus": base_cap_bonus,
            "overridden": bool(override),
            "produces": building_produces(bid), "cap_bonus": building_cap_bonus(bid),
        })
    return out

class BuildingBalanceBody(BaseModel):
    building_id: str
    produces: dict[str, int] = {}
    cap_bonus: dict[str, int] = {}

@router.post("/building-balance")
async def set_building_balance(body: BuildingBalanceBody, user: dict = Depends(full_admin_user)):
    """بازدهی/سقفِ یک ساختمان رو سراسری بازنویسی می‌کند — فقط برای کلیدهایی که خودِ
    ساختمان از قبل تولید/سقف می‌داده معنی دارد (کلید تازه اضافه نمی‌کند)"""
    meta = BUILDINGS.get(body.building_id)
    if not meta:
        raise HTTPException(400, "ساختمان نامعتبر")
    allowed_produces = set(meta.get("produces", {}).keys())
    allowed_cap = set(meta.get("cap_bonus", {}).keys())
    if not set(body.produces).issubset(allowed_produces) or not set(body.cap_bonus).issubset(allowed_cap):
        raise HTTPException(400, "این ساختمان چنین منبعی تولید/ذخیره نمی‌کند")
    if any(v < 0 for v in list(body.produces.values()) + list(body.cap_bonus.values())):
        raise HTTPException(400, "مقدار نمی‌تواند منفی باشد")

    override = {}
    if body.produces:
        override["produces"] = body.produces
    if body.cap_bonus:
        override["cap_bonus"] = body.cap_bonus

    if override:
        game_data.BUILDING_OVERRIDES[body.building_id] = override
    else:
        game_data.BUILDING_OVERRIDES.pop(body.building_id, None)

    await game_settings.update_one(
        {"_id": BUILDING_OVERRIDES_DOC_ID},
        {"$set": {f"overrides.{body.building_id}": override}} if override
        else {"$unset": {f"overrides.{body.building_id}": ""}},
        upsert=True,
    )
    return {"ok": True}

@router.post("/building-balance/{building_id}/reset")
async def reset_building_balance(building_id: str, user: dict = Depends(full_admin_user)):
    game_data.BUILDING_OVERRIDES.pop(building_id, None)
    await game_settings.update_one(
        {"_id": BUILDING_OVERRIDES_DOC_ID}, {"$unset": {f"overrides.{building_id}": ""}}, upsert=True,
    )
    return {"ok": True}


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
