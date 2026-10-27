"""Create a database dump and prove it restores without production access."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time


def redact_error(value):
    value = re.sub(r"(mongodb(?:\+srv)?://)[^@\s]+@", r"\1[redacted]@", value)
    value = re.sub(r"""scrypt\$[^\s"']+""", "[password hash redacted]", value)
    value = re.sub(r"""(?i)(["']?(?:password|password_hash|token|csrf|recovery_code)["']?\s*[:=]\s*)["'][^"']*["']""", r'\1"[redacted]"', value)
    return value[-2400:]


def execute(args, *, timeout=180, stdout=None):
    result = subprocess.run(args, stdout=stdout if stdout is not None else subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        tool = next((name for name in ("mongodump", "mongorestore", "mongosh") if name in args), " ".join(args[:3]))
        error_output = result.stderr or b""
        if stdout is None and isinstance(result.stdout, bytes):
            error_output += b"\\n" + result.stdout
        detail = redact_error(error_output.decode("utf-8", "replace").strip())
        raise RuntimeError(tool + " failed (exit " + str(result.returncode) + "): " + (detail or "No diagnostic output was returned"))
    return result.stdout


def checksum(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def inventory(container, database):
    js = ("const d=db.getSiblingDB(" + json.dumps(database) + ");"
          "print(JSON.stringify(d.getCollectionInfos().filter(c=>c.type==='collection').map(c=>({"
          "name:c.name,count:d.getCollection(c.name).countDocuments({}),"
          "ttl:d.getCollection(c.name).getIndexes().some(i=>i.expireAfterSeconds!==undefined)"
          "}))));")
    return json.loads(execute(["docker", "exec", container, "mongosh", "--norc", "--quiet", "--eval", js]).decode())


def stable_counts(rows):
    return {row["name"]: row["count"] for row in rows if not row.get("ttl")}


def create_backup(edition, state_file, *, application_root=None, backup_root=None):
    os.umask(0o077)
    project = "valyria-web-app" if edition == "web" else "valyria"
    root = Path(application_root) if application_root else Path("/opt/valyria-web-app" if edition == "web" else "/opt/valyria/app")
    os.chdir(root)
    backend_name, mongo_name = project + "-backend-1", project + "-mongodb-1"
    rows = json.loads(execute(["docker", "inspect", backend_name, mongo_name]).decode())
    for row, service in zip(rows, ("backend", "mongodb")):
        labels = row.get("Config", {}).get("Labels", {})
        if labels.get("com.docker.compose.project") != project or labels.get("com.docker.compose.service") != service:
            raise RuntimeError("Edition/container mismatch; update stopped.")
        if row["State"].get("Paused"):
            raise RuntimeError("A service is paused. Resolve its state before updating.")
    if not rows[1]["State"].get("Running"):
        raise RuntimeError("MongoDB must be available for a verified backup.")
    environment = dict(item.split("=", 1) for item in rows[0]["Config"].get("Env", []) if "=" in item)
    database = environment.get("DB_NAME") or ("valyria_web_app" if edition == "web" else "fire_ice")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", database):
        raise RuntimeError("Unexpected database name; update stopped.")
    if (edition == "web" and database == "fire_ice") or (edition == "telegram" and database == "valyria_web_app"):
        raise RuntimeError("The editions must never share a database.")
    from urllib.parse import urlsplit
    uri = urlsplit(environment.get("MONGODB_URI", "mongodb://mongodb:27017"))
    if uri.hostname != "mongodb" or uri.port not in (None, 27017) or uri.username:
        raise RuntimeError("This backup runner requires the current local MongoDB service; configure a backup for other connections first.")
    image = rows[1]["Config"]["Image"]
    execute(["docker", "image", "inspect", image])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = Path(backup_root or "/opt/valyria-database-backups") / edition / (stamp + "-" + secrets.token_hex(4))
    backup.mkdir(parents=True, mode=0o700)
    archive = backup / "database.archive.gz"
    restore_name = "valyria-backup-check-" + edition + "-" + secrets.token_hex(6)
    stopped = False
    started_restore = False
    verified = False
    stage = "stopping game writes"
    try:
        if rows[0]["State"].get("Running"):
            print("Pausing game writes while creating the database backup.", flush=True)
            stopped = True
            execute(["docker", "compose", "stop", "-t", "30", "backend"])
        stage = "reading source collection counts"
        before = inventory(mongo_name, database)
        stage = "creating database archive"
        print("Creating database backup.", flush=True)
        with archive.open("xb") as stream:
            execute(["docker", "exec", mongo_name, "mongodump", "--quiet", "--gzip", "--archive",
                     "--db", database], timeout=600, stdout=stream)
            stream.flush()
            os.fsync(stream.fileno())
        stage = "checking source collection counts"
        after = inventory(mongo_name, database)
        if stable_counts(before) != stable_counts(after):
            raise RuntimeError("Database changed during backup. Update stopped.")
        archive_hash = checksum(archive)
        print("Restoring backup in a temporary MongoDB with no network or production volumes.", flush=True)
        stage = "starting isolated restore container"
        started_restore = True
        execute(["docker", "run", "-d", "--pull=never", "--name", restore_name,
                 "--network", "none", "--memory", "768m", "--cpus", "0.75",
                 "--tmpfs", "/data/db:rw,nosuid,size=1g",
                 "--tmpfs", "/data/configdb:rw,nosuid,size=32m",
                 "--mount", "type=bind,src=" + str(backup) + ",dst=/backup,readonly",
                 image, "mongod", "--bind_ip", "127.0.0.1", "--wiredTigerCacheSizeGB", "0.25",
                 "--setParameter", "ttlMonitorEnabled=false"])
        stage = "waiting for isolated MongoDB"
        for attempt in range(45):
            try:
                execute(["docker", "exec", restore_name, "mongosh", "--norc", "--quiet",
                         "--eval", "quit(db.adminCommand({ping:1}).ok ? 0 : 1)"], timeout=5)
                break
            except (RuntimeError, subprocess.TimeoutExpired):
                if attempt == 44:
                    raise RuntimeError("Isolated backup verification database did not start.")
                time.sleep(1)
        stage = "restoring archive inside isolated container"
        execute(["docker", "exec", "--user", "0", restore_name, "mongorestore", "--verbose", "--gzip",
                 "--archive=/backup/database.archive.gz", "--nsInclude=" + database + ".*",
                 "--numParallelCollections=1", "--stopOnError"], timeout=600)
        stage = "comparing restored collection counts"
        restored = inventory(restore_name, database)
        restored_counts = {row["name"]: row["count"] for row in restored}
        for row in before:
            if not row.get("ttl") and restored_counts.get(row["name"]) != row["count"]:
                raise RuntimeError("Restored database counts did not match. Update stopped.")
        state = {"edition": edition, "database": database, "archive": str(archive),
                 "sha256": archive_hash, "verified": True, "network": "none",
                 "verified_at": datetime.now(timezone.utc).isoformat(),
                 "collections": before, "restored_collections": restored}
        manifest = backup / "verified-backup.json"
        manifest.write_text(json.dumps(state, indent=2), encoding="utf-8")
        state_path = Path(state_file)
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.chmod(state_path, 0o600)
        verified = True
        print("Verified database backup: " + str(archive), flush=True)
    except Exception as exc:
        failure = {"edition": edition, "stage": stage, "error": redact_error(str(exc)),
                   "at": datetime.now(timezone.utc).isoformat()}
        (backup / "failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print("Backup failed during " + stage + ": " + failure["error"], flush=True)
        print("Diagnostic saved: " + str(backup / "failure.json"), flush=True)
        raise
    finally:
        if started_restore:
            subprocess.run(["docker", "rm", "-f", restore_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if stopped:
            try:
                execute(["docker", "compose", "start", "backend"])
            except Exception as exc:
                print("Restarting the original backend failed: " + redact_error(str(exc)), flush=True)
                raise
        if not verified:
            print("Backup verification failed; no update was activated.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=("web", "telegram"), required=True)
    parser.add_argument("--state-file", required=True)
    args = parser.parse_args()
    create_backup(args.edition, args.state_file)
