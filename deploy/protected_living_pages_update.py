"""Publish the living all-pages redesign and named commanders after a verified backup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

from protected_update import validate_backup, checksum

FILES = {
    'backend/character_travel.py', 'backend/control_settings.py', 'backend/game_data.py',
    'backend/routers/admin.py', 'backend/routers/map.py', 'backend/routers/war.py',
    'backend/tests/test_named_commanders.py', 'frontend/src/api.js', 'frontend/src/App.jsx',
    'frontend/src/components/LivingPageHero.jsx', 'frontend/src/components/LivingScreen.jsx',
    'frontend/src/components/WesterosMap.jsx',
    'frontend/src/pages/Admin.jsx', 'frontend/src/pages/Dashboard.jsx',
    'frontend/src/pages/Buildings.jsx', 'frontend/src/pages/War.jsx',
    'frontend/src/pages/Leaderboard.jsx', 'frontend/src/pages/Diplomacy.jsx',
    'frontend/src/styles/living-pages.css', 'frontend/src/styles/living-system.css',
    'frontend/src/styles/living-responsive.css', 'frontend/src/styles/ui-coherence.css',
    'frontend/public/living-assets/parchment-texture.webp',
    'frontend/public/living-assets/realm-hero.webp',
    'frontend/public/living-assets/farm-food.webp',
    'frontend/public/living-assets/war-map.webp',
    'frontend/public/living-assets/gold-treasury.webp',
    'frontend/public/living-assets/people-village.webp',
    'frontend/public/living-assets/wood-lumber.webp',
    'frontend/public/living-assets/iron-mine.webp',
    'frontend/public/living-assets/stone-mine.webp',
    'frontend/public/living-assets/castle-wall.webp',
    'frontend/public/living-assets/market.webp',
    'frontend/public/living-assets/barracks-sword.webp',
    'frontend/public/living-assets/barracks-archer.webp',
    'frontend/public/living-assets/armory-sword.webp',
    'frontend/public/living-assets/war-room.webp',
    'frontend/public/living-assets/harbor.webp',
    'deploy/living_pages_baselines.json',
    'deploy/protected_living_pages_update.py',
}


def payload(package):
    content = {}
    with tarfile.open(package, 'r:gz') as archive:
        for item in archive.getmembers():
            if item.name not in FILES or not item.isfile() or item.name in content or item.size > 2 * 1024 * 1024:
                raise RuntimeError('Unexpected source package entry; no source was changed.')
            content[item.name] = archive.extractfile(item).read()
    if set(content) != FILES:
        raise RuntimeError('Incomplete source package; no source was changed.')
    return content


def call(*args, **kwargs):
    return subprocess.run(list(args), check=True, **kwargs)


def image(service, config):
    name = config['services'][service].get('image') or config['name'] + '-' + service
    return subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', name], text=True).strip()


def healthy():
    code = "import urllib.request,json; assert json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=5)) == {'ok':True}"
    for attempt in range(45):
        result = subprocess.run(['docker', 'compose', 'exec', '-T', 'backend', 'python', '-c', code],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError('Backend health check failed. The verified database backup remains available.')


def validate_sources(root, content):
    baselines = json.loads(content['deploy/living_pages_baselines.json'])['web']
    application_files = set(content) - {
        'deploy/living_pages_baselines.json', 'deploy/protected_living_pages_update.py'
    }
    if set(baselines) != application_files:
        raise RuntimeError('Incomplete source baseline guard.')
    for name, previous in baselines.items():
        destination = root / name
        incoming = hashlib.sha256(content[name]).hexdigest()
        if not destination.is_file():
            if previous is not None:
                raise RuntimeError('Expected application source is missing: ' + name)
            continue
        if checksum(destination) not in set(previous or []) | {incoming}:
            raise RuntimeError('Server source differs from the reviewed version; no source changed: ' + name)


def activate(package, state_file, offserver_sha, package_sha):
    state, backup_dir = validate_backup('web', state_file, offserver_sha)
    if checksum(package) != package_sha:
        raise RuntimeError('Source archive checksum mismatch.')
    content = payload(package)
    root = Path('/opt/valyria-web-app').resolve()
    if not (root / '.env').is_file():
        raise RuntimeError('Web App configuration was not found.')
    os.chdir(root)
    config = json.loads(subprocess.check_output(['docker', 'compose', 'config', '--format', 'json'], text=True))
    for name in content:
        destination = root / name
        if destination.is_symlink() or not destination.resolve().is_relative_to(root):
            raise RuntimeError('Source destination leaves the Web App checkout.')
    validate_sources(root, content)
    # Rebuild the currently reviewed source before touching it. This makes the
    # rollback image independent from a stale or dangling Docker tag left by an
    # interrupted earlier publication.
    call('docker', 'compose', 'build', 'backend', 'frontend')
    old_images = {service: image(service, config) for service in ('backend', 'frontend')}
    backup_tags = {service: 'valyria-living-pages-backup-' + service + '-' + package_sha[:12]
                   for service in ('backend', 'frontend')}
    for service, identity in old_images.items():
        call('docker', 'tag', identity, backup_tags[service])
    before = {name: (root / name).read_bytes() for name in content if (root / name).is_file()}
    with tarfile.open(backup_dir / 'source-before-living-pages.tar.gz', 'x:gz') as archive:
        for name in sorted(before):
            archive.add(root / name, arcname=name, recursive=False)
    (backup_dir / 'images-before-living-pages.json').write_text(json.dumps(old_images), encoding='utf-8')
    switched = False
    try:
        for name, data in content.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # Tests have already run locally with an in-memory database. Never run them here.
        call('docker', 'compose', 'build', 'backend', 'frontend')
        audit = """import os
assert os.getenv('VALYRIA_RUNTIME') == 'production'
assert not os.path.exists('/app/tests')
import unittest
try:
    import db
except RuntimeError as exc:
    assert 'Tests cannot run in a production runtime' in str(exc)
else:
    raise SystemExit('Production database test guard failed')
print('Production isolation verified')
"""
        call('docker', 'run', '--rm', '--pull=never', '--network', 'none', '--entrypoint',
             'python', image('backend', config), '-c', audit)
        switched = True
        call('docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', 'backend')
        healthy()
        call('docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', 'frontend')
    except Exception:
        for name in content:
            target = root / name
            if name in before:
                target.write_bytes(before[name])
            elif target.is_file():
                target.unlink()
        for service in ('backend', 'frontend'):
            tag = config['services'][service].get('image') or config['name'] + '-' + service
            call('docker', 'tag', backup_tags[service], tag)
        if switched:
            call('docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', 'backend', 'frontend')
        raise
    finally:
        for backup_tag in backup_tags.values():
            subprocess.run(['docker', 'image', 'rm', backup_tag],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proof = {'edition': 'web', 'source_sha256': package_sha, 'database_backup': state['archive'],
             'images': {service: image(service, config) for service in ('backend', 'frontend')}}
    (backup_dir / 'living-pages-release.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    print('Living redesign for every Web App page and named commanders activated.')
    print('Verified database and source backups: ' + str(backup_dir))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for flag in ('package', 'backup-state', 'offserver-sha', 'package-sha'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    activate(args.package, args.backup_state, args.offserver_sha, args.package_sha)
