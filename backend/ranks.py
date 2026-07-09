"""امتیاز ترکیبی و سلسله‌مراتب مقام‌ها: بالادستی هر اقلیم، والی‌های سه‌گانه، پادشاه/ملکه"""
from db import players, hierarchy
from game_data import REGIONS, WARDEN_GROUPS, BUILDINGS
from config import SCORE_W_ECONOMY, SCORE_W_MILITARY, SCORE_W_POPULARITY, SCORE_W_ALLIANCE, TITLE_SCORE_BONUS

HIERARCHY_ID = "main"

def group_of_region(region_id: str):
    for gid, g in WARDEN_GROUPS.items():
        if region_id in g["regions"]:
            return gid
    return None

def base_score(p: dict) -> float:
    """امتیاز پایه: امتیاز خام + قدرت اقتصادی + قدرت نظامی + قدرت سیاسی (بدون بونوس مقام، تا در محاسبهٔ بالادستی چرخه ایجاد نشود)"""
    b = p.get("buildings", {})
    economy = sum(st.get("level", 0) for bid, st in b.items() if BUILDINGS.get(bid, {}).get("type") == "economy")
    military = sum(st.get("level", 0) for bid, st in b.items() if BUILDINGS.get(bid, {}).get("type") in ("barracks", "armory"))
    political = p.get("popularity", 0) * SCORE_W_POPULARITY + p.get("alliance_count", 0) * SCORE_W_ALLIANCE
    return p.get("points", 0) + economy * SCORE_W_ECONOMY + military * SCORE_W_MILITARY + political

async def get_hierarchy_doc() -> dict:
    doc = await hierarchy.find_one({"_id": HIERARCHY_ID}) or {}
    return {
        "warden_south": doc.get("warden_south"),
        "warden_central": doc.get("warden_central"),
        "warden_north": doc.get("warden_north"),
        "king": doc.get("king"),
    }

async def region_overlords() -> dict:
    """بالاترین امتیاز پایه در هر اقلیم — {region_id: player_doc | None}"""
    best = {}
    async for p in players.find({}):
        rid = p.get("region")
        if rid not in REGIONS:
            continue
        s = base_score(p)
        if rid not in best or s > best[rid][0]:
            best[rid] = (s, p)
    return {rid: (best[rid][1] if rid in best else None) for rid in REGIONS}

def wardens_of(h: dict) -> set:
    return {h.get("warden_south"), h.get("warden_central"), h.get("warden_north")} - {None}

def title_bonus_and_rank(tg_id: int, overlords: dict, h: dict):
    """بونوس امتیاز و برچسب مقامی که این بازیکن الان داره (بالاترین مقامش)"""
    if h.get("king") == tg_id:
        return TITLE_SCORE_BONUS["king"], "king"
    if tg_id in wardens_of(h):
        return TITLE_SCORE_BONUS["warden"], "warden"
    if any(o and o["tg_id"] == tg_id for o in overlords.values()):
        return TITLE_SCORE_BONUS["overlord"], "overlord"
    return 0, None

async def scored_players() -> list:
    """همهٔ بازیکن‌ها با امتیاز نهایی (پایه + بونوس مقام) — نزولی مرتب‌شده"""
    overlords = await region_overlords()
    h = await get_hierarchy_doc()
    rows = []
    async for p in players.find({}):
        bonus, rank_label = title_bonus_and_rank(p["tg_id"], overlords, h)
        score = round(base_score(p) + bonus)
        rows.append({"player": p, "score": score, "rank_label": rank_label})
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
