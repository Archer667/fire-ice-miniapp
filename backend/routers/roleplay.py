from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, campaigns, roleplays
from game import now, owned_castles
from game_data import ROLEPLAY_CATEGORIES
from routers.war import ATTACK_OP_TYPES, ROLEPLAY_WINDOW_HOURS, roleplay_window_hours
from admin_notifications import notify_admins

router = APIRouter(prefix="/api/roleplay", tags=["roleplay"])

TEXT_MIN_LEN = 10

class RoleplayBody(BaseModel):
    category: str
    text: str
    campaign_id: str | None = None
    target_tg_id: int | None = None

@router.post("/send")
async def send(body: RoleplayBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    if body.category not in ROLEPLAY_CATEGORIES:
        raise HTTPException(400, "دسته‌بندی نامعتبر است")
    text = body.text.strip()
    if len(text) < TEXT_MIN_LEN:
        raise HTTPException(400, "رول خیلی کوتاه است — کمی بیشتر بنویس")

    campaign_id = None
    target_player = None
    if body.category == "sabotage":
        if not body.target_tg_id:
            raise HTTPException(400, "برای رول خرابکاری باید لرد هدف را مشخص کنی")
        if body.target_tg_id == user["id"]:
            raise HTTPException(400, "نمی‌توانی خودت را هدف خرابکاری قرار بدهی")
        target_player = await players.find_one({"tg_id": body.target_tg_id})
        if not target_player:
            raise HTTPException(404, "لرد هدف پیدا نشد")
    if body.category == "war":
        if not body.campaign_id:
            raise HTTPException(400, "برای دستهٔ جنگ باید نبردت را انتخاب کنی")
        try:
            oid = ObjectId(body.campaign_id)
        except Exception:
            raise HTTPException(400, "شناسهٔ نبرد نامعتبر است")
        c = await campaigns.find_one({"_id": oid})
        if not c or not c.get("engagement_locked"):
            raise HTTPException(404, "این نبرد پیدا نشد")
        is_attacker = c["tg_id"] == user["id"]
        is_defender = c["target_castle"] in owned_castles(p) and c["tg_id"] != user["id"]
        is_opponent = c.get("opponent_tg_id") == user["id"]
        if not (is_attacker or is_defender or is_opponent):
            raise HTTPException(403, "این نبرد به تو ربطی ندارد")
        arrival_at = c.get("battle_started_at") or c.get("arrival_at")
        if not arrival_at or now() < arrival_at:
            raise HTTPException(400, "این نبرد هنوز به مقصد نرسیده")
        if now() > arrival_at + timedelta(hours=roleplay_window_hours()):
            raise HTTPException(400, f"مهلت {roleplay_window_hours():g} ساعته برای فرستادن سناریوی این نبرد گذشته")
        if await roleplays.find_one({"tg_id": user["id"], "campaign_id": body.campaign_id}):
            raise HTTPException(400, "قبلاً سناریوی این نبرد را فرستاده‌ای")
        campaign_id = body.campaign_id

    result_required = body.category != "security"
    doc = {
        "tg_id": user["id"], "player_name": p["name"], "castle": p["castle"],
        "category": body.category, "text": text[:4000], "campaign_id": campaign_id,
        "target_tg_id": target_player["tg_id"] if target_player else None,
        "target_player_name": target_player["name"] if target_player else None,
        "result": None, "resolved": not result_required,
        "result_required": result_required,
        "created_at": now(),
    }
    res = await roleplays.insert_one(doc)
    target_line = f"\nهدف: {target_player['name']}" if target_player else ""
    admin_detail = (
        f"فرستنده: {p['name']}\n"
        f"دسته: {ROLEPLAY_CATEGORIES[body.category]}{target_line}\n"
        f"متن کامل رول:\n{text[:2800]}"
    )
    if campaign_id:
        submitted = await roleplays.count_documents({"campaign_id": campaign_id})
        deadline = c["arrival_at"] + timedelta(hours=roleplay_window_hours())
        both_ready = submitted >= 2
        await notify_admins(
            "war_roleplay",
            "⚔️ هر دو رول جنگ آمادهٔ داوری‌اند" if both_ready else "📜 رول جنگ تازه ثبت شد",
            f"{admin_detail}\nنبرد: «{c.get('name') or 'بدون نام'}»\nمحل: {c['target_castle']}"
            + (f" حالا هر {submitted} رول موجود است." if both_ready else " هنوز منتظر رول طرف دیگر هستیم."),
            dedupe_key=(f"war-both-ready:{campaign_id}" if both_ready else f"war-roleplay:{res.inserted_id}"),
            priority="high" if both_ready else "normal",
            player_name=p["name"],
            player_tg_id=user["id"],
            castle=c["target_castle"],
            action="از پنل ادمین ← جنگ و رول‌ها ← رول‌ها، روایت طرفین را بررسی کن.",
            source_id=campaign_id,
            deadline=deadline,
        )
    else:
        await notify_admins(
            "roleplay",
            "🛡️ رول امنیتی تازه ثبت شد" if not result_required else "📜 رول تازه منتظر داوری است",
            admin_detail,
            dedupe_key=f"roleplay:{res.inserted_id}",
            player_name=p["name"],
            player_tg_id=user["id"],
            castle=p.get("castle"),
            action="از پنل ادمین ← جنگ و رول‌ها ← رول‌ها، نتیجه را ثبت کن.",
            source_id=str(res.inserted_id),
        )
    return {"ok": True, "id": str(res.inserted_id), "result_required": result_required}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    cur = roleplays.find({"tg_id": user["id"]}).sort("created_at", -1).limit(50)
    out = []
    async for r in cur:
        out.append({
            "id": str(r["_id"]), "category": r["category"],
            "category_name": ROLEPLAY_CATEGORIES.get(r["category"], r["category"]),
            "text": r["text"], "resolved": r["resolved"], "result": r["result"],
            "result_required": r.get("result_required", r.get("category") != "security"),
            "campaign_id": r.get("campaign_id"),
            "target_tg_id": r.get("target_tg_id"), "target_player_name": r.get("target_player_name"),
            "admin_score": r.get("admin_score"),
            "created_at": r["created_at"].isoformat(),
        })
    return out
