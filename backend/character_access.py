"""Shared gameplay state; ownership and character presence are independent."""
PERSONAL_WRITES = ('/api/character-travel', '/api/character/profile', '/api/family', '/api/ravens', '/api/institutions', '/api/roleplay', '/api/item-store')
def status(p):
    if not p: return 'unregistered'
    if p.get('is_dead'): return 'dead'
    if p.get('registration_reset'): return 'unregistered'
    if p.get('region') and p.get('castle'): return 'landed'
    if p.get('region') and p.get('landless'): return 'landless'
    return 'pending'
def personal_write(path):
    return any(path == prefix or path.startswith(prefix + '/') for prefix in PERSONAL_WRITES)
