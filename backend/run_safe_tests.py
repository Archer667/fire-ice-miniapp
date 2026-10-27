"""Run local tests against an in-memory database without production credentials."""
import os
import sys

os.environ["VALYRIA_RUNTIME"] = "test"
os.environ["MONGODB_URI"] = "mongodb://valyria-test-mongodb:27017"
os.environ["DB_NAME"] = "valyria_unit_test"
os.environ["DEV_MODE"] = "true"
os.environ["PUBLIC_APP_ORIGIN"] = "https://web.test"

try:
    from mongomock_motor import AsyncMongoMockClient
except ImportError:
    raise SystemExit("Install requirements-dev.txt in your local test environment first.")

import motor.motor_asyncio
motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient

import unittest
unittest.main(module=None, argv=[sys.argv[0], *sys.argv[1:]])
