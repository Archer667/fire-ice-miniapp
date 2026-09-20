"""Pure physical movement geometry; all timestamps use the game clock."""
from datetime import timedelta


def legs(army, graph, horizon=None):
    stationed = army.get('stationed_edge')
    if stationed:
        start = army.get('stationed_at') or army.get('arrival_at')
        end = max(horizon or start, start + timedelta(microseconds=1)) if start else None
        return [(stationed['a'], stationed['b'], start, end, stationed['position'], stationed['position'])] if start and end > start else []
    path = army.get('route_path') or [army.get('target_castle')]
    start = army.get('moved_at') or army.get('created_at')
    end = army.get('arrival_at')
    if not start or not end or len(path) < 2 or end <= start:
        return []
    partial = army.get('route_start_position')
    if partial:
        destination = 0 if army['target_castle'] == partial['a'] else 1
        return [(partial['a'], partial['b'], start, end, partial['position'], destination)]
    weights = army.get('route_edge_minutes')
    if not weights or len(weights) != len(path) - 1:
        weights = [graph.get(a, {}).get(b) for a, b in zip(path, path[1:])]
    if any(w is None or w <= 0 for w in weights):
        return []
    total, elapsed, out = sum(weights), 0, []
    for a, b, weight in zip(path, path[1:], weights):
        t0 = start + (end - start) * (elapsed / total)
        elapsed += weight
        out.append((a, b, t0, start + (end - start) * (elapsed / total)))
    return out


def coordinates(leg):
    return leg[4:6] if len(leg) > 4 else (0, 1)


def position(leg, at):
    p0, p1 = coordinates(leg)
    return p0 + (p1 - p0) * ((at - leg[2]).total_seconds() / (leg[3] - leg[2]).total_seconds())


def meeting(a, b):
    """Actual intersection, including overtaking and an army stopped on a road."""
    u, v, a0, a1 = a[:4]
    x, y, b0, b1 = b[:4]
    if {u, v} != {x, y} or a1 <= a0 or b1 <= b0:
        return None
    lo, hi = max(a0, b0), min(a1, b1)
    if lo > hi:
        return None
    ap0, ap1 = coordinates(a)
    bp0, bp1 = coordinates(b)
    if u != x:
        bp0, bp1 = 1 - bp0, 1 - bp1
    va = (ap1 - ap0) / (a1 - a0).total_seconds()
    vb = (bp1 - bp0) / (b1 - b0).total_seconds()
    pa = ap0 + (lo - a0).total_seconds() * va
    pb = bp0 + (lo - b0).total_seconds() * vb
    if abs(va - vb) < 1e-12:
        return lo if abs(pa - pb) < 1e-8 else None
    when = lo + timedelta(seconds=(pb - pa) / (va - vb))
    return when if lo <= when <= hi else None


def visits(army, segments, end):
    if army.get('stationed_edge'):
        return []
    start = army.get('moved_at') or army.get('created_at')
    arrival = army.get('arrival_at') or start
    if not arrival:
        return []
    if not segments:
        if len(army.get('route_path') or []) > 1 and start and arrival > start:
            return []  # Unknown geometry is not evidence of arrival.
        return [(army.get('target_castle'), arrival, end)]
    out = []
    for segment in segments:
        a, b, t0, t1 = segment[:4]
        p0, p1 = coordinates(segment)
        if p0 in (0, 1):
            out.append((a if p0 == 0 else b, t0, t0))
        if p1 in (0, 1):
            out.append((a if p1 == 0 else b, t1, end if segment == segments[-1] else t1))
    return out


def encounters(a, b, graph, end):
    aa, bb, out = legs(a, graph, end), legs(b, graph, end), []
    for first in aa:
        for second in bb:
            at = meeting(first, second)
            if at and at <= end:
                fraction = position(first, at)
                if fraction <= 1e-8 or fraction >= 1 - 1e-8:
                    out.append((at, 'castle', (first[0] if fraction <= 1e-8 else first[1],)))
                else:
                    out.append((at, 'edge', (first[0], first[1])))
    for ca, sa, ea in visits(a, aa, end):
        for cb, sb, eb in visits(b, bb, end):
            if ca and ca == cb and max(sa, sb) <= min(ea, eb, end):
                out.append((max(sa, sb), 'castle', (ca,)))
    return sorted(set(out))
