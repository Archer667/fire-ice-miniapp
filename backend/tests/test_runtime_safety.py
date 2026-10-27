import unittest
from unittest.mock import Mock
from runtime_safety import assert_database_test_isolation


class RuntimeIsolationTests(unittest.TestCase):
    def check(self, uri="mongodb://mongodb:27017", name="valyria_web_app", *, runtime="test", factory=None, modules=None):
        if factory is None:
            factory = type("Client", (), {"__module__": "motor.motor_asyncio"})
        assert_database_test_isolation(uri, name, factory,
            environ={"VALYRIA_RUNTIME": runtime}, modules={"unittest": object()} if modules is None else modules)

    def test_production_runtime_rejects_even_test_database_and_mock_clients(self):
        memory = type("Client", (), {"__module__": "mongomock_motor"})
        with self.assertRaises(RuntimeError):
            self.check("mongodb://valyria-test-mongodb:27017", "valyria_unit_test", runtime="production", factory=memory)

    def test_live_database_or_host_cannot_be_used_by_test_runner(self):
        for uri, name in (
            ("mongodb://mongodb:27017", "fire_ice"),
            ("mongodb://mongodb:27017", "valyria_web_app"),
            ("mongodb://mongodb:27017", "valyria_unit_test"),
            ("mongodb://valyria-test-mongodb:27017", "fire_ice"),
        ):
            with self.subTest(uri=uri, database=name), self.assertRaises(RuntimeError):
                self.check(uri, name)

    def test_error_never_echoes_connection_credentials(self):
        with self.assertRaises(RuntimeError) as caught:
            self.check("mongodb://hidden:secret@mongodb:27017", "fire_ice")
        self.assertNotIn("hidden", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_memory_and_dedicated_test_host_are_accepted_outside_production(self):
        self.check(factory=type("Client", (), {"__module__": "mongomock_motor"}))
        self.check("mongodb://valyria-test-mongodb:27017", "valyria_unit_test")

    def test_application_runtime_is_unaffected(self):
        self.check(runtime="production", modules={})
