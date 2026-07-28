from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, tributes, hierarchy
from game import now, can_afford, pay
from ranks import my_tribute_role, HIERARCHY_ID
from routers.ravens import send_system_message

router = APIRouter(prefix="/api/tribute", tags=["tribute"])

# چرخهٔ خراج: استاد سکه از والی‌ها می‌خواد، والی از بالادست‌های اقلیم‌های زیرمجموعه‌اش،
# بالادست از لرد/لیدی‌های اقلیمش — هر خواسته ۲۴ ساعت مهلت داره؛ اگه نده، هیچ پیامدِ
# خودکاری نداره (نه افت محبوبیت نه عزل)، فقط کسی که خواسته بود باخبر می‌شه که پرداخت نشد
TRIBUTE_WINDOW_HOURS = 24
ROLE_LABEL_FA = {"coin": "استاد سکه", "warden": "والی", "overlord": "بالادست"}

def _brief(p):
    return {"tg_id": p["tg_id"], "name": p["name"], "title": p.get("title")}

@router.get("/mine")
async def my_tributes(user: dict = Depends(get_user)):
    role, target_ids = await my_tribute_role(user["id"])
    demand_targets = []
    if role:
        async for p in players.find({"tg_id": {"$in": list(target_ids)}}):
            demand_targets.append(_brief(p))

    demanded = []
    async for t in tributes.find({"from_id": user["id"]}).sort("created_at", -1).limit(50):
        demanded.append({
            "id": str(t["_id"]), "to_name": t["to_name"], "amount": t["amount"],
            "status": t["status"], "created_at": t["created_at"].isoformat(),
            "due_at": t["due_at"].isoformat(),
        })

    owed = []
    async for t in tributes.find({"to_id": user["id"], "status": "pending"}).sort("created_at", -1):
        owed.append({
            "id": str(t["_id"]), "from_name": t["from_name"], "from_role": t["from_role"],
            "from_role_label": ROLE_LABEL_FA.get(t["from_role"], t["from_role"]),
            "amount": t["amount"], "created_at": t["created_at"].isoformat(),
            "due_at": t["due_at"].isoformat(),
        })

    return {
        "my_role": role, "my_role_label": ROLE_LABEL_FA.get(role),
        "demand_targets": demand_targets,
        "demanded": demanded, "owed": owed,
    }

class DemandBody(BaseModel):
    to_tg_id: int
    amount: int

@router.post("/demand")
async def demand_tribute(body: DemandBody, user: dict = Depends(get_user)):
    if body.amount <= 0:
        raise HTTPException(400, "مبلغ باید مثبت باشد")
    role, target_ids = await my_tribute_role(user["id"])
    if not role:
        raise HTTPException(403, "مقامی نداری که بتونی خراج بخوای")
    if body.to_tg_id not in target_ids:
        raise HTTPException(400, "این بازیکن زیردستِ مستقیمِ تو نیست")
    if await tributes.find_one({"from_id": user["id"], "to_id": body.to_tg_id, "status": "pending"}):
        raise HTTPException(409, "همین الان یک خراجِ پرداخت‌نشده از این نفر خواسته‌ای — صبر کن جواب بده")

    me = await players.find_one({"tg_id": user["id"]})
    target = await players.find_one({"tg_id": body.to_tg_id})
    if not target:
        raise HTTPException(404, "این بازیکن پیدا نشد")

    created_at = now()
    doc = {
        "from_id": user["id"], "from_name": me["name"], "from_role": role,
        "to_id": body.to_tg_id, "to_name": target["name"],
        "amount": body.amount, "status": "pending",
        "created_at": created_at, "due_at": created_at + timedelta(hours=TRIBUTE_WINDOW_HOURS),
        "paid_at": None,
    }
    res = await tributes.insert_one(doc)
    await send_system_message(
        body.to_tg_id, target["name"],
        f"{ROLE_LABEL_FA[role]} {me['name']} خراجی به مبلغ {body.amount:,} سکه از تو خواسته — "
        f"تا {TRIBUTE_WINDOW_HOURS} ساعت دیگر مهلت داری بپردازی.",
    )
    return {"ok": True, "id": str(res.inserted_id)}

@router.post("/{tribute_id}/pay")
async def pay_tribute(tribute_id: str, user: dict = Depends(get_user)):
    try:
        oid = ObjectId(tribute_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ نامعتبر")
    t = await tributes.find_one({"_id": oid})
    if not t:
        raise HTTPException(404, "این خراج پیدا نشد")
    if t["to_id"] != user["id"]:
        raise HTTPException(403, "این خراجِ تو نیست")
    if t["status"] != "pending":
        raise HTTPException(400, "این خراج دیگر در انتظار پرداخت نیست")

    p = await players.find_one({"tg_id": user["id"]})
    if not can_afford(p["resources"], {"gold": t["amount"]}):
        raise HTTPException(400, "طلای کافی نداری")
    pay(p["resources"], {"gold": t["amount"]})
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    # خراجِ استاد سکه (از والی‌ها) می‌ره تو خزانهٔ رد کیپ، نه جیبِ شخصیِ خودش — بقیهٔ
    # سطوح (والی از بالادست، بالادست از لرد) مستقیم به طلای شخصیِ خواهنده اضافه می‌شه
    if t["from_role"] == "coin":
        await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$inc": {"treasury_gold": t["amount"]}}, upsert=True)
    else:
        await players.update_one({"tg_id": t["from_id"]}, {"$inc": {"resources.gold": t["amount"]}})

    await tributes.update_one({"_id": oid}, {"$set": {"status": "paid", "paid_at": now()}})
    await send_system_message(
        t["from_id"], t["from_name"],
        f"{p['name']} خراجِ {t['amount']:,} سکه‌ای که خواسته بودی را پرداخت کرد."
        + (" (به خزانهٔ رد کیپ واریز شد)" if t["from_role"] == "coin" else ""),
    )
    return {"ok": True}

async def expire_unpaid_tributes():
    """خراج‌هایی که مهلت‌شون گذشته و پرداخت نشده رو منقضی می‌کنه و فقط به کسی که خراج
    رو خواسته بود خبر می‌ده — هیچ پیامد دیگه‌ای (افت محبوبیت، عزل و امثالش) خودکار نداره"""
    cur = tributes.find({"status": "pending", "due_at": {"$lte": now()}})
    async for t in cur:
        await tributes.update_one({"_id": t["_id"]}, {"$set": {"status": "expired"}})
        await send_system_message(
            t["from_id"], t["from_name"],
            f"{t['to_name']} خراجِ {t['amount']:,} سکه‌ای که {TRIBUTE_WINDOW_HOURS} ساعت پیش خواسته بودی را پرداخت نکرد.",
        )
