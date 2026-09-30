"""Army upkeep is derived from surviving troops, never a stale cached total."""
import game_data

def food_rate(troops):
    total=0
    for tid,n in (troops or {}).items():
        meta=game_data.COMMON_TROOPS.get(tid) or game_data.NAVAL_TROOPS.get(tid)
        cost=meta.get('food',1) if meta else game_data.GAME_RULES['food_cost_special']
        total+=max(0,int(n or 0))*float(cost)
    from control_settings import get
    return total * float(get("food.army_consumption_percent", 100)) / 100

def campaign_food(c):
    return food_rate(c.get('troops',{})) if c.get('active',True) else 0


def civilian_food_rate(settings):
    from control_settings import get
    return float(settings['base_food_per_100_men']) / 100 * float(get('food.civilian_consumption_percent', 100)) / 100
