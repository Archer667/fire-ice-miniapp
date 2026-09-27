"""Reverse the physically travelled leg, including a battle partway along a road."""
from datetime import timedelta
from encounter_geometry import legs, coordinates, position


def return_plan(army, battle_id, at, graph):
    source = next((m for m in reversed(army.get('movement_history', []))
                   if m.get('reason') == 'battle' and m.get('battle_id') == battle_id), army)
    # Repeated battles at the same stop create stationary snapshots. Follow the
    # recorded movement back to the last actual journey with this origin.
    if len(source.get('route_path') or []) < 2 and not source.get('route_segments'):
        origin = source.get('origin_castle') or army.get('origin_castle')
        candidates = list(army.get('movement_history', []))
        source_index = next((i for i, m in enumerate(candidates) if m is source), len(candidates))
        for previous in reversed(candidates[:source_index]):
            if previous.get('origin_castle') != origin:
                break
            if len(previous.get('route_path') or []) >= 2 or previous.get('route_segments'):
                source = previous
                break
    source = {**source, 'created_at': source.get('created_at') or army.get('created_at')}
    if len(source.get('route_path') or []) == 2 and not source.get('route_edge_minutes'):
        # Legacy direct journeys retain elapsed time even if that map edge was replaced.
        source['route_edge_minutes'] = [1]

    contact_at = source.get('ended_at') or army.get('battle_started_at') or at
    travelled = []
    for leg in legs(source, graph, contact_at):
        if leg[2] >= contact_at:
            break
        end = min(contact_at, leg[3])
        p0, _ = coordinates(leg)
        p1 = position(leg, end)
        seconds = (end - leg[2]).total_seconds()
        if seconds > 0 and abs(p0 - p1) > 1e-9:
            travelled.append({'a': leg[0], 'b': leg[1], 'p0': p1, 'p1': p0, 'seconds': seconds})
    current = army.get('target_castle')
    destination = source.get('origin_castle') or army.get('origin_castle')
    if not travelled:
        if current == destination:
            return None
        raise ValueError('مسیر قبلی این لشکر برای بازگشت مشخص نیست؛ قبل از بستن نبرد مسیر را بررسی کن')
    segments = list(reversed(travelled))
    path = [current]
    for s in segments:
        endpoint = s['a'] if s['p1'] == 0 else s['b'] if s['p1'] == 1 else destination
        if path[-1] != endpoint:
            path.append(endpoint)
    seconds = sum(s['seconds'] for s in segments)
    first = travelled[0]
    destination_edge = source.get('route_start_position')
    if first['p1'] not in (0, 1):
        destination_edge = {'a': first['a'], 'b': first['b'], 'position': first['p1'],
                            'base_minutes': graph.get(first['a'], {}).get(first['b'])}

    return {'origin_castle': current, 'target_castle': destination, 'op_type': 'garrison',
            'route_path': path, 'route_segments': segments, 'route_edge_minutes': [],
            'travel_minutes': seconds / 60, 'moved_at': at, 'arrival_at': at + timedelta(seconds=seconds),
            'returning_from_battle': battle_id, 'return_destination_edge': destination_edge,
            'arrival_notified': False}
