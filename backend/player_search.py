"""Shared player selector search, including secondary castles and spelling variants."""
import unicodedata
from game import owned_castles
from game_data import CASTLE_EN_NAMES, REGIONS

def normalized(value):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold().translate(str.maketrans('يكأإآ', 'یکااا'))
    return ''.join(c for c in value if c.isalnum())

def find_matches(rows, query):
    needle = normalized(query).lstrip('@')
    if len(needle) < 2:return []
    results = []
    for p in rows:
        castles = owned_castles(p)
        if not castles:continue
        matched = next((c for c in castles if needle in normalized(c) or needle in normalized(CASTLE_EN_NAMES.get(c,''))), None)
        labels = [p.get('name'),p.get('username'),p.get('tg_id')]
        if not matched and not any(needle in normalized(v) for v in labels):continue
        results.append({'tg_id':p['tg_id'],'name':p.get('name',''),'castle':matched or p.get('castle',''),
            'region_name':REGIONS.get(p.get('region'),{}).get('name',p.get('region','')),'title':p.get('title')})
    return sorted(results,key=lambda p: (normalized(p['castle']) != needle,normalized(p['name']) != needle,p['tg_id']))[:20]
