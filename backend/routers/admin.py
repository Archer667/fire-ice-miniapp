from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin, get_full_admin
from db import campaigns, players, admin_roles, map_castles
from game import now
from game_data import REGIONS
from config import ADMIN_IDS

router = APIRouter(prefix="/api/admin", tags=["admin"])

async def admin_user(user: dict = Depends(get_user)):
    """ادمین کامل یا محدود — برای سناریوها"""
    return await get_admin(user)

async def full_admin_user(user: dict = Depends(get_user)):
    """فقط ادمین کامل — برای مدیریت ادمین‌ها"""
    return await get_full_admin(user)

@router.get("/pending")
async def pending(user: dict = Depends(admin_user)):
    out = []
    async for s in campaigns.find({"status": "pending"}).sort("created_at", 1):
        out.append({
            "id": str(s["_id"]), "player": s["player_name"],
            "from": s["origin_castle"], "to": s["target_castle"],
            "op_type": s["op_type"], "plan": s["plan"],
            "troops": s["troops"], "cost": s["gold_cost"],
            "created_at": s["created_at"].isoformat(),
        })
    return out

class VerdictBody(BaseModel):
    verdict: str
    points_delta: int = 0   # امتیازی که ادمین به بازیکن می‌دهد/می‌گیرد

@router.post("/{scenario_id}/approve")
async def approve(scenario_id: str, body: VerdictBody, user: dict = Depends(admin_user)):
    """تایید فقط داوری سناریو را ثبت می‌کند — لشکر همچنان فعال می‌ماند و آذوقه می‌خورد
    تا خودِ لرد/لیدی لغوش کند"""
    s = await campaigns.find_one({"_id": ObjectId(scenario_id)})
    if not s:
        raise HTTPException(404, "سناریو پیدا نشد")
    await campaigns.update_one({"_id": s["_id"]},
        {"$set": {"status": "approved", "verdict": body.verdict}})
    if body.points_delta:
        await players.update_one({"tg_id": s["tg_id"]}, {"$inc": {"points": body.points_delta}})
    return {"ok": True}

@router.post("/{scenario_id}/reject")
async def reject(scenario_id: str, body: VerdictBody, user: dict = Depends(admin_user)):
    """رد یعنی این لشکرکشی هرگز رخ نداده — طلا و نفرات به لرد برمی‌گردد و لشکر منحل می‌شود"""
    s = await campaigns.find_one({"_id": ObjectId(scenario_id)})
    if not s:
        raise HTTPException(404, "سناریو پیدا نشد")
    await campaigns.update_one({"_id": s["_id"]},
        {"$set": {"status": "rejected", "verdict": body.verdict, "active": False}})
    await players.update_one({"tg_id": s["tg_id"]},
        {"$inc": {"resources.gold": s["gold_cost"], "resources.men": s["men_committed"]}})
    return {"ok": True}

@router.get("/map/options")
async def map_options(region: str, user: dict = Depends(admin_user)):
    """اسم قلعه/بندرهای این اقلیم که هنوز روی نقشه مکان ندارند — برای پرکردن انتخابگر ادمین"""
    if region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    placed = {m["name"] async for m in map_castles.find({"region": region}, {"name": 1})}
    r = REGIONS[region]
    options = [{"name": c, "port": False} for c in r["castles"] if c not in placed]
    options += [{"name": c, "port": True} for c in r["ports"] if c not in placed]
    return options

class MapCastleBody(BaseModel):
    region: str
    x: float
    y: float
    name: str | None = None       # انتخاب از دیتای موجودِ بازی
    new_name: str | None = None   # قلعه/شهر کاملاً جدید
    port: bool = False

@router.post("/map/castles")
async def add_map_castle(body: MapCastleBody, user: dict = Depends(admin_user)):
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    if not (0 <= body.x <= 100 and 0 <= body.y <= 100):
        raise HTTPException(400, "مختصات نامعتبر")

    r = REGIONS[body.region]
    all_names = {name async for doc in map_castles.find({}, {"name": 1}) for name in [doc["name"]]}
    for reg in REGIONS.values():
        all_names |= set(reg["castles"]) | set(reg["ports"])

    if body.new_name and body.new_name.strip():
        name = body.new_name.strip()[:40]
        if name in all_names:
            raise HTTPException(409, "این اسم قبلاً در بازی وجود دارد")
        custom, port = True, body.port
    else:
        name = (body.name or "").strip()
        if name not in r["castles"] + r["ports"]:
            raise HTTPException(400, "این قلعه/بندر در دیتای این اقلیم نیست")
        if await map_castles.find_one({"region": body.region, "name": name}):
            raise HTTPException(409, "این قلعه از قبل روی نقشه گذاشته شده")
        custom, port = False, name in r["ports"]

    await map_castles.insert_one({
        "region": body.region, "name": name, "port": port,
        "x": body.x, "y": body.y, "custom": custom, "created_at": now(),
    })
    return {"ok": True, "name": name}

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
