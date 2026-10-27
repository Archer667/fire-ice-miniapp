"""Explicit server permissions for the war and roleplay adjudicator."""
import re

WAR_ROLEPLAY_ROLE = 'war_roleplay'
_READ = {
    '/api/admin/campaigns', '/api/admin/army-groups', '/api/admin/ambushes', '/api/admin/battles',
    '/api/admin/war-window', '/api/admin/roleplay', '/api/admin/roleplay-score/settings',
}
_WRITE = {
    'POST': [r'/api/admin/battle-reports', r'/api/admin/roleplay-score/settings',
             r'/api/admin/roleplay/[^/]+/(?:score|respond)',
             r'/api/admin/battles/[^/]+/(?:loot|dismiss|resolve)',
             r'/api/admin/ambushes/[^/]+/score'],
    'PUT': [r'/api/admin/ambushes/[^/]+'],
    'DELETE': [r'/api/admin/ambushes/[^/]+'],
}

def war_roleplay_allowed(method, path):
    if method in ('GET', 'HEAD'):
        return path in _READ
    return any(re.fullmatch(pattern, path) for pattern in _WRITE.get(method, []))
