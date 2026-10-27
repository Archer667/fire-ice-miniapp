"""Activate a source update only after off-server backup verification."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import time


FILES = {
    "backend/db.py", "backend/runtime_safety.py", "backend/.dockerignore",
    "backend/Dockerfile", "backend/run_safe_tests.py",
    "backend/tests/test_urgent_food_recruit.py", "backend/tests/test_runtime_safety.py",
    "deploy/verified_database_backup.py", "deploy/protected_update.py",
    "docs/DATABASE_SAFETY.md",
}


def checksum(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def validate_backup(edition, state_file, offserver_sha, *, backup_root=None):
    state = json.loads(Path(state_file).read_text(encoding="utf-8"))
    if state.get("edition") != edition or state.get("verified") is not True or state.get("network") != "none":
        raise RuntimeError("A verified backup for the selected edition is required.")
    if state.get("sha256") != offserver_sha:
        raise RuntimeError("The off-server backup checksum does not match.")
    archive = Path(state["archive"]).resolve()
    base = Path(backup_root or "/opt/valyria-database-backups") / edition
    if not archive.is_relative_to(base) or archive.name != "database.archive.gz":
        raise RuntimeError("Unexpected backup archive path.")
    verified = datetime.fromisoformat(state["verified_at"])
    elapsed = datetime.now(timezone.utc) - verified
    if elapsed < timedelta(minutes=-1) or elapsed > timedelta(hours=2):
        raise RuntimeError("Create a fresh verified backup before updating.")
    if checksum(archive) != offserver_sha:
        raise RuntimeError("The database backup changed; update stopped.")
    return state, archive.parent


def payload(package):
    result = {}
    with tarfile.open(package, "r:gz") as archive:
        for item in archive.getmembers():
            if item.name not in FILES or not item.isfile() or item.name in result or item.size > 2 * 1024 * 1024:
                raise RuntimeError("Unexpected source package entry.")
            result[item.name] = archive.extractfile(item).read()
    if set(result) != FILES:
        raise RuntimeError("Incomplete source package.")
    return result


def activate(edition, package, state_file, offserver_sha, package_sha):
    state, backup_dir = validate_backup(edition, state_file, offserver_sha)
    if checksum(package) != package_sha:
        raise RuntimeError("Source package checksum mismatch.")
    content = payload(package)
    root = Path("/opt/valyria-web-app" if edition == "web" else "/opt/valyria/app").resolve()
    if not (root / ".env").is_file():
        raise RuntimeError("Application configuration was not found.")
    os.chdir(root)
    for name in content:
        destination = root.joinpath(*PurePosixPath(name).parts)
        if destination.is_symlink() or not destination.resolve().is_relative_to(root):
            raise RuntimeError("Source path leaves the application checkout.")

    subprocess.run(["docker", "compose", "config", "--quiet"], check=True)
    with tarfile.open(backup_dir / "source-before-protection.tar.gz", "x:gz") as archive:
        for name in sorted(content):
            existing = root / name
            if existing.is_file():
                archive.add(existing, arcname=name, recursive=False)
    for name, data in content.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    subprocess.run(["docker", "compose", "build", "backend"], check=True)
    compose_config = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"], text=True))
    image_name = compose_config["services"]["backend"].get("image") or compose_config["name"] + "-backend"
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image_name], text=True).strip()
    if not image_id or "\n" in image_id:
        raise RuntimeError("Could not identify the backend image.")
    audit = """import os
assert os.getenv('VALYRIA_RUNTIME') == 'production'
assert not os.path.exists('/app/tests')
import unittest
try:
    import db
except RuntimeError as exc:
    assert 'Tests cannot run in a production runtime' in str(exc)
else:
    raise SystemExit('Production test guard failed')
print('Production image protection: OK')
"""
    subprocess.run(["docker", "run", "--rm", "--pull=never", "--network", "none",
                    "--entrypoint", "python", image_id, "-c", audit], check=True)
    subprocess.run(["docker", "compose", "up", "-d", "--no-deps", "--force-recreate", "backend"], check=True)
    health = "import urllib.request,json; assert json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=5)) == {'ok': True}"
    for attempt in range(30):
        response = subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-c", health],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if response.returncode == 0:
            break
        if attempt == 29:
            raise RuntimeError("Updated backend did not become healthy. The database backup remains available.")
        time.sleep(2)
    print("Database protection is active for " + edition + ".")
    print("Verified backup: " + state["archive"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=("web", "telegram"), required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--backup-state", required=True)
    parser.add_argument("--offserver-sha", required=True)
    parser.add_argument("--package-sha", required=True)
    args = parser.parse_args()
    activate(args.edition, args.package, args.backup_state, args.offserver_sha, args.package_sha)
