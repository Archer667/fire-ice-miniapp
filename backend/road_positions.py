"""Orders issued by an army stationary at a physical point on a road."""
from fastapi import HTTPException
from game_data import TRAVEL_GRAPH, is_sea_edge


def endpoint_route(army, destination, terrain=None):
    point = army['stationed_edge']
    if destination not in (point['a'], point['b']):
        raise HTTPException(400, 'لشکر در میانهٔ مسیر است؛ ابتدا یکی از دو سرِ همین مسیر را انتخاب کن')
    weight = point.get('base_minutes') or TRAVEL_GRAPH.get(point['a'], {}).get(point['b'])
    if weight is None or weight <= 0:
        raise HTTPException(409, 'زمان مسیرِ محل توقف ثبت نشده؛ ادمین باید مسیر را بررسی کند')
    fraction = point['position'] if destination == point['a'] else 1 - point['position']
    return {'path': [army['target_castle'], destination], 'minutes': weight * fraction,
            'via_sea': is_sea_edge(point['a'], point['b'], terrain)}
