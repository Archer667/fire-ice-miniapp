from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin
from db import players, hierarchy
from game import now
from game_data import REGIONS, WARDEN_GROUPS, SMALL_COUNCIL_SEATS
from ranks import get_hierarchy_doc, group_of_region, wardens_of, HIERARCHY_ID
from config import SALARY_CYCLE_DAYS, KING_SALARY_GOLD
from routers.ravens import send_system_message

router = APIRouter(prefix="/api/titles", tags=["titles"])

def _brief(p):
    if not p:
        return None
    return {"tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"), "castle": p["castle"]}

@router.get("")
async def get_titles(user: dict = Depends(get_user)):
    h = await get_hierarchy_doc()

    overlord_holders = {}
    for rid, tg_id in h["overlords"].items():
        holder = await players.find_one({"tg_id": tg_id}) if tg_id else None
        overlord_holders[rid] = _brief(holder)
    for rid in REGIONS:
        overlord_holders.setdefault(rid, None)

    warden_holders = {}
    for gid in WARDEN_GROUPS:
        tg_id = h.get(f"warden_{gid}")
        holder = await players.find_one({"tg_id": tg_id}) if tg_id else None
        warden_holders[gid] = _brief(holder)

    king_holder = await players.find_one({"tg_id": h.get("king")}) if h.get("king") else None

    council = h.get("small_council", {})
    council_holders = {}
    for seat in SMALL_COUNCIL_SEATS:
        tg_id = council.get(seat)
        holder = await players.find_one({"tg_id": tg_id}) if tg_id else None
        council_holders[seat] = _brief(holder)

    return {
        "overlords": overlord_holders,
        "warden_groups": WARDEN_GROUPS,
        "wardens": warden_holders,
        "king": _brief(king_holder),
        "small_council_seats": SMALL_COUNCIL_SEATS,
        "small_council": council_holders,
        "is_king": h.get("king") == user["id"],
        "treasury_gold": h["treasury_gold"],
        "council_salary_rates": h["council_salary_rates"],
        "king_salary_gold": KING_SALARY_GOLD,
    }

async def admin_user(user: dict = Depends(get_user)):
    return await get_admin(user)

class OverlordBody(BaseModel):
    region: str
    tg_id: int

@router.post("/overlord")
async def set_overlord(body: OverlordBody, user: dict = Depends(admin_user)):
    """بالادستی هر اقلیم دستی و توسط ادمین تعیین می‌شود — معمولاً بعد از رای‌گیری بازیکن‌ها"""
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    target = await players.find_one({"tg_id": body.tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if target["region"] != body.region:
        raise HTTPException(400, "این بازیکن لرد این اقلیم نیست")

    await hierarchy.update_one(
        {"_id": HIERARCHY_ID},
        {"$set": {f"overlords.{body.region}": body.tg_id}},
        upsert=True,
    )
    return {"ok": True}

class WardenBody(BaseModel):
    group: str        # "south" | "central" | "north"
    tg_id: int

@router.post("/warden")
async def set_warden(body: WardenBody, user: dict = Depends(admin_user)):
    if body.group not in WARDEN_GROUPS:
        raise HTTPException(400, "والی‌نشین نامعتبر")
    target = await players.find_one({"tg_id": body.tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")

    h = await get_hierarchy_doc()
    is_overlord_of_group = any(
        h["overlords"].get(rid) == body.tg_id and group_of_region(rid) == body.group
        for rid in REGIONS
    )
    if not is_overlord_of_group:
        raise HTTPException(400, "این بازیکن الان بالادستیِ هیچ‌کدام از اقلیم‌های این والی‌نشین نیست")

    await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$set": {f"warden_{body.group}": body.tg_id}}, upsert=True)
    return {"ok": True}

class KingBody(BaseModel):
    tg_id: int

@router.post("/king")
async def set_king(body: KingBody, user: dict = Depends(admin_user)):
    h = await get_hierarchy_doc()
    if body.tg_id not in wardens_of(h):
        raise HTTPException(400, "پادشاه/ملکه فقط از بین والی‌های فعلی انتخاب می‌شود")
    await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$set": {"king": body.tg_id}}, upsert=True)
    return {"ok": True}

class EpithetBody(BaseModel):
    tg_id: int
    title: str

@router.post("/epithet")
async def set_epithet(body: EpithetBody, user: dict = Depends(admin_user)):
    title = body.title.strip()[:60]
    if not title:
        raise HTTPException(400, "عنوان خالی است")
    res = await players.update_one({"tg_id": body.tg_id}, {"$set": {"title": title}})
    if res.matched_count == 0:
        raise HTTPException(404, "بازیکن پیدا نشد")
    return {"ok": True, "title": title}

class CouncilBody(BaseModel):
    seat: str
    tg_id: int | None = None   # None = خالی کردن این کرسی

@router.post("/small-council")
async def set_small_council(body: CouncilBody, user: dict = Depends(get_user)):
    """شورای کوچک — فقط خودِ پادشاه/ملکهٔ فعلی می‌تواند لردها را به کرسی‌ها بگمارد، نه ادمین"""
    h = await get_hierarchy_doc()
    if h.get("king") != user["id"]:
        raise HTTPException(403, "فقط پادشاه/ملکهٔ فعلی می‌تواند شورای کوچک را بچیند")
    if body.seat not in SMALL_COUNCIL_SEATS:
        raise HTTPException(400, "کرسی نامعتبر")

    if body.tg_id is None:
        await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$unset": {f"small_council.{body.seat}": ""}})
        return {"ok": True}

    if body.tg_id == user["id"]:
        raise HTTPException(400, "پادشاه/ملکه نمی‌تواند خودش را عضو شورای کوچک کند")
    target = await players.find_one({"tg_id": body.tg_id})
    if not target:
        raise HTTPException(404, "لرد پیدا نشد")

    await hierarchy.update_one(
        {"_id": HIERARCHY_ID}, {"$set": {f"small_council.{body.seat}": body.tg_id}}, upsert=True,
    )
    return {"ok": True}

class CouncilSalaryBody(BaseModel):
    seat: str
    amount: int   # صفر یعنی بدون حقوق

@router.post("/council-salary")
async def set_council_salary(body: CouncilSalaryBody, user: dict = Depends(get_user)):
    """حقوقِ روزانهٔ هر کرسیِ شورای کوچک (از خزانهٔ رد کیپ، طلا) را فقط خودِ پادشاه/ملکه تعیین می‌کند"""
    h = await get_hierarchy_doc()
    if h.get("king") != user["id"]:
        raise HTTPException(403, "فقط پادشاه/ملکهٔ فعلی می‌تواند حقوقِ شورای کوچک را تعیین کند")
    if body.seat not in SMALL_COUNCIL_SEATS:
        raise HTTPException(400, "کرسی نامعتبر")
    if body.amount < 0:
        raise HTTPException(400, "حقوق نمی‌تواند منفی باشد")
    await hierarchy.update_one(
        {"_id": HIERARCHY_ID}, {"$set": {f"council_salary_rates.{body.seat}": body.amount}}, upsert=True,
    )
    return {"ok": True}

async def pay_daily_salaries():
    """حقوقِ روزانهٔ پادشاه (ثابت) و هر کرسیِ پرشدهٔ شورای کوچک (به تعیینِ خودِ پادشاه) را از
    خزانهٔ رد کیپ واریز می‌کند — هر روز یک‌بار برای هر گیرنده، فقط اگر خزانه کافی باشد
    (وگرنه تا دفعهٔ بعد که خزانه پر شود صبر می‌کند). وقتی نفرِ یک کرسی/تاجِ عوض بشه، ساعتِ
    روزانه‌اش از همون لحظه دوباره شروع می‌شه (به نفرِ قبلی چیزی برای مدتِ نگرفته تعلق نمی‌گیره)"""
    doc = await hierarchy.find_one({"_id": HIERARCHY_ID}) or {}
    treasury = doc.get("treasury_gold", 0)
    n = now()
    king_state = doc.get("king_salary_state") or {}
    council_state = doc.get("council_salary_state", {})
    rates = doc.get("council_salary_rates", {})
    council = doc.get("small_council", {})
    updates = {}

    async def try_pay(state_key, tg_id, amount, label, state):
        nonlocal treasury
        if not tg_id or amount <= 0:
            return
        if not state or state.get("holder") != tg_id:
            updates[state_key] = {"holder": tg_id, "last_paid_at": n}
            return
        last_paid = state["last_paid_at"]
        if isinstance(last_paid, str):
            last_paid = datetime.fromisoformat(last_paid)
        if (n - last_paid).days < SALARY_CYCLE_DAYS:
            return
        if treasury < amount:
            return
        p = await players.find_one({"tg_id": tg_id})
        if not p:
            return
        treasury -= amount
        await players.update_one({"tg_id": tg_id}, {"$inc": {"resources.gold": amount}})
        updates[state_key] = {"holder": tg_id, "last_paid_at": n}
        await send_system_message(
            tg_id, p["name"],
            f"حقوقِ روزانه‌ات به‌عنوان {label} — {amount:,} سکه — از خزانهٔ رد کیپ واریز شد.",
        )

    await try_pay("king_salary_state", doc.get("king"), KING_SALARY_GOLD, "پادشاه/ملکه", king_state)
    for seat, tg_id in council.items():
        await try_pay(
            f"council_salary_state.{seat}", tg_id, rates.get(seat, 0),
            SMALL_COUNCIL_SEATS.get(seat, seat), council_state.get(seat),
        )

    updates["treasury_gold"] = treasury
    await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$set": updates}, upsert=True)
