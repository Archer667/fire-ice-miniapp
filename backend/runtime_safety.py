"""Reject test processes before they can connect to a live database."""
import os
import re
import sys
from urllib.parse import urlsplit


TEST_HOSTS = frozenset({
    "valyria-test-mongodb", "valyria-project-test-db", "quota-test-mongo",
    "war-audit-mongo", "valyria-character-test-db",
})


def assert_database_test_isolation(uri, database, client_factory, *, environ=None, modules=None):
    environ = os.environ if environ is None else environ
    modules = sys.modules if modules is None else modules
    testing = any(name in modules for name in ("unittest", "pytest", "_pytest")) or bool(environ.get("PYTEST_CURRENT_TEST"))
    if not testing:
        return
    if environ.get("VALYRIA_RUNTIME", "").lower() == "production":
        raise RuntimeError("Tests cannot run in a production runtime. Use the isolated test runner.")
    factory_module = getattr(client_factory, "__module__", "")
    if factory_module.startswith("mongomock_motor"):
        return
    name = str(database or "").lower()
    test_name = bool(re.fullmatch(r"(?:valyria_[a-z0-9_]*test[a-z0-9_]*|quota_test|tweet_test|war_audit_test)", name))
    try:
        hostname = urlsplit(uri).hostname
    except ValueError:
        hostname = None
    if not test_name or hostname not in TEST_HOSTS:
        raise RuntimeError("Database access from tests requires an isolated test host and a dedicated test database.")
