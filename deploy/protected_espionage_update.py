"""Deploy intelligence networks after a verified, downloaded database backup."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

from protected_update import validate_backup, checksum

COMMON = {
    'backend/espionage_networks.py', 'backend/routers/espionage.py', 'backend/routers/admin.py',
    'backend/admin_permissions.py', 'backend/admin_notifications.py', 'backend/character_access.py',
    'backend/main.py', 'backend/time_management.py', 'backend/season_analytics.py', 'backend/tests/test_espionage_networks.py', 'backend/tests/test_season_quota.py',
    'frontend/src/api.js', 'frontend/src/characterAccess.js', 'frontend/src/pages/Admin.jsx',
    'frontend/src/pages/Espionage.jsx', 'frontend/src/pages/EspionageNetworks.jsx',
    'frontend/src/pages/PlayerGuide.jsx', 'frontend/src/components/EspionageShared.jsx',
    'frontend/src/components/espionage.css', 'frontend/src/components/AdminEspionage.jsx',
    'frontend/src/components/AdminControlCenter.jsx', 'docs/PLAYER_GUIDE.md',
    'docs/ESPIONAGE_NETWORKS_FA.md', 'deploy/protected_espionage_update.py',
}


def source_payload(package, edition):
    expected = COMMON | ({'backend/telegram_bot.py', 'backend/tests/test_admin_roles.py'} if edition == 'web' else set())
    content = {}
    with tarfile.open(package, 'r:gz') as archive:
        for item in archive.getmembers():
            if item.name not in expected or not item.isfile() or item.name in content or item.size > 2 * 1024 * 1024:
                raise RuntimeError('Unexpected source package entry; no source was changed.')
            content[item.name] = archive.extractfile(item).read()
    if set(content) != expected:
        raise RuntimeError('Incomplete source package; no source was changed.')
    return content


def call(*args, **kw):
    return subprocess.run(list(args), check=True, **kw)


def image(service, config):
    name = config['services'][service].get('image') or config['name'] + '-' + service
    return subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',name],text=True).strip()


def healthy():
    code = "import urllib.request,json; assert json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=5)) == {'ok':True}"
    for attempt in range(45):
        result = subprocess.run(['docker','compose','exec','-T','backend','python','-c',code],
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError('Backend health check failed. The database backup remains available.')


def activate(edition, package, state_file, offserver_sha, package_sha):
    state, backup_dir = validate_backup(edition,state_file,offserver_sha)
    if checksum(package) != package_sha:
        raise RuntimeError('Source archive checksum mismatch.')
    content = source_payload(package,edition)
    root = Path('/opt/valyria-web-app' if edition == 'web' else '/opt/valyria/app').resolve()
    if not (root/'.env').is_file():
        raise RuntimeError('Edition configuration was not found.')
    os.chdir(root)
    config = json.loads(subprocess.check_output(['docker','compose','config','--format','json'],text=True))
    for name in content:
        destination = root/name
        if destination.is_symlink() or not destination.resolve().is_relative_to(root):
            raise RuntimeError('Source destination leaves the selected edition.')
    old_images = {service:image(service,config) for service in ('backend','frontend')}
    before = {name:(root/name).read_bytes() for name in content if (root/name).is_file()}
    with tarfile.open(backup_dir/'source-before-espionage.tar.gz','x:gz') as archive:
        for name in sorted(before):
            archive.add(root/name,arcname=name,recursive=False)
    (backup_dir/'images-before-espionage.json').write_text(json.dumps(old_images),encoding='utf-8')
    switched = False
    try:
        for name,data in content.items():
            target=root/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
        # Tests run locally with an in-memory database. Never run a suite here.
        call('docker','compose','build','backend','frontend')
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
        call('docker','run','--rm','--pull=never','--network','none','--entrypoint','python',image('backend',config),'-c',audit)
        switched = True
        call('docker','compose','up','-d','--no-deps','--force-recreate','backend')
        healthy()
        call('docker','compose','up','-d','--no-deps','--force-recreate','frontend')
    except Exception:
        for name in content:
            target=root/name
            if name in before:
                target.write_bytes(before[name])
            elif target.is_file():
                target.unlink()
        for service,identity in old_images.items():
            tag=config['services'][service].get('image') or config['name']+'-'+service
            call('docker','tag',identity,tag)
        if switched:
            call('docker','compose','up','-d','--no-deps','--force-recreate','backend','frontend')
        raise
    proof={'edition':edition,'source_sha256':package_sha,'database_backup':state['archive'],
           'images':{service:image(service,config) for service in ('backend','frontend')}}
    (backup_dir/'espionage-release.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print('Intelligence networks activated for '+edition+'.')
    print('Verified database and source backups: '+str(backup_dir))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--edition',choices=('web','telegram'),required=True)
    for flag in ('package','backup-state','offserver-sha','package-sha'):
        parser.add_argument('--'+flag,required=True)
    args=parser.parse_args()
    activate(args.edition,args.package,args.backup_state,args.offserver_sha,args.package_sha)
