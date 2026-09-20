"""Pairwise battle relations. Peace is not a transitive team membership.

One party represents one player, not one army. Legacy attacker/defender fields
are deliberately not inputs: those bookkeeping columns cannot establish peace.
"""
from itertools import combinations


def relation_key(first, second):
    return tuple(sorted((int(first), int(second))))


def build_parties(armies, peace_pairs=(), extra_players=()):
    parties = {}
    for player in extra_players:
        uid = int(player['tg_id'])
        parties[uid] = {'tg_id': uid, 'player_name': player.get('name', str(uid)),
                        'army_ids': [], 'peace_with': [], 'hostile_to': []}
    for army in armies:
        uid = int(army['tg_id'])
        party = parties.setdefault(uid, {
            'tg_id': uid, 'player_name': army.get('player_name', str(uid)),
            'army_ids': [], 'peace_with': [], 'hostile_to': [],
        })
        army_id = str(army.get('campaign_id') or army['_id'])
        if army_id not in party['army_ids']:
            party['army_ids'].append(army_id)
    peaceful = {relation_key(a, b) for a, b in peace_pairs}
    for a, b in combinations(sorted(parties), 2):
        field = 'peace_with' if relation_key(a, b) in peaceful else 'hostile_to'
        parties[a][field].append(b)
        parties[b][field].append(a)
    return [parties[uid] for uid in sorted(parties)]


def has_hostility(parties):
    return any(party['hostile_to'] for party in parties)


def compatible_winners(parties, winners):
    selected = set(winners)
    known = {party['tg_id'] for party in parties}
    return bool(selected) and selected <= known and not any(
        selected.intersection(party['hostile_to'])
        for party in parties if party['tg_id'] in selected
    )
