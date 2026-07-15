"""امتیاز ترکیبی و سلسله‌مراتب مقام‌ها: بالادستی هر اقلیم، والی‌های سه‌گانه، پادشاه/ملکه

مقام‌ها (بالادستی/والی/پادشاه) همه به‌صورت دستی توسط ادمین تعیین می‌شوند — معمولاً
بعد از یک رای‌گیری بین بازیکن‌ها (سکشن دیپلماسی). امتیاز فقط برای لیدربرد استفاده
می‌شود، دیگر خودکار کسی را بالادستی نمی‌کند."""
from db import players, hierarchy
from game_data import REGIONS, WARDEN_GROUPS, BUILDINGS
from config import SCORE_W_ECONOMY, SCORE_W_MILITARY, SCORE_W_POPULARITY, SCORE_W_ALLIANCE, TITLE_SCORE_BONUS
from game import normalize_building_state

HIERARCHY_ID = "main"

def group_of_region(region_id: str):
    for gid, g in WARDEN_GROUPS.items():
        if region_id in g["regions"]:
            return gid
    return None

def base_score(p: dict) -> float:
    """امتیاز پایه: امتیاز خام + قدرت اقتصادی + قدرت نظامی + قدرت سیاسی (بدون بونوس مقام)"""
    b = p.get("buildings", {})
    levels = {bid: normalize_building_state(raw)["level"] for bid, raw in b.items()}
    economy = sum(lvl for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") == "economy")
    military = sum(lvl for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") in ("barracks", "armory"))
    political = p.get("popularity", 0) * SCORE_W_POPULARITY + p.get("alliance_count", 0) * SCORE_W_ALLIANCE
    return p.get("points", 0) + economy * SCORE_W_ECONOMY + military * SCORE_W_MILITARY + political

async def get_hierarchy_doc() -> dict:
    doc = await hierarchy.find_one({"_id": HIERARCHY_ID}) or {}
    return {
        "overlords": doc.get("overlords", {}),   # {region_id: tg_id} — با دست ادمین
        "warden_south": doc.get("warden_south"),
        "warden_central": doc.get("warden_central"),
        "warden_north": doc.get("warden_north"),
        "king": doc.get("king"),
        "small_council": doc.get("small_council", {}),   # {seat_id: tg_id} — با دست خودِ پادشاه
    }

def wardens_of(h: dict) -> set:
    return {h.get("warden_south"), h.get("warden_central"), h.get("warden_north")} - {None}

def title_bonus_and_rank(tg_id: int, h: dict):
    """بونوس امتیاز و برچسب مقامی که این بازیکن الان داره (بالاترین مقامش)"""
    if h.get("king") == tg_id:
        return TITLE_SCORE_BONUS["king"], "king"
    if tg_id in wardens_of(h):
        return TITLE_SCORE_BONUS["warden"], "warden"
    if tg_id in h.get("overlords", {}).values():
        return TITLE_SCORE_BONUS["overlord"], "overlord"
    return 0, None

async def scored_players() -> list:
    """همهٔ بازیکن‌ها با امتیاز نهایی (پایه + بونوس مقام) — نزولی مرتب‌شده"""
    h = await get_hierarchy_doc()
    rows = []
    async for p in players.find({}):
        bonus, rank_label = title_bonus_and_rank(p["tg_id"], h)
        score = round(base_score(p) + bonus)
        rows.append({"player": p, "score": score, "rank_label": rank_label})
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
