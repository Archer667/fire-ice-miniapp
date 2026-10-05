"""Public map locations only; no troop counts or private battle participants."""

def effect_for_campaign(row, at):
    if row.get('combat_resolved_at') or row.get('battle_cancelled_at') or row.get('status') in ('cancelled','destroyed','disbanded','battle_dismissed'):
        return None
    battle = row.get('battle_open') and row.get('battle_is_root', True)
    siege = row.get('active') and row.get('op_type') == 'siege' and row.get('arrival_at') and row['arrival_at'] <= at
    if not battle and not siege:
        return None
    contact = row.get('battle_contact') or {}
    if contact.get('kind') == 'edge':
        return {'kind':'battle', 'a':contact['a'], 'b':contact['b'], 'position':max(0,min(1,contact.get('position',.5)))}
    castle = contact.get('castle') or row.get('battle_location') or row.get('target_castle')
    if not castle or castle.startswith('مسیر '):
        return None
    return {'kind':'siege' if siege else 'battle', 'castle':castle}

async def active_map_effects(campaigns, at):
    query = {'$or':[{'battle_open':True},{'active':True,'op_type':'siege','arrival_at':{'$lte':at}}]}
    effects = []
    seen = set()
    async for row in campaigns.find(query):
        effect = effect_for_campaign(row, at)
        if effect:
            key = tuple(sorted(effect.items()))
            if key not in seen:
                seen.add(key)
                effects.append(effect)
    return effects
