import unittest
from unittest.mock import patch
from fastapi import HTTPException

import auth


class FakeAdminRoles:
    def __init__(self, rows=None):
        self.rows = rows or {}

    async def find_one(self, query):
        return self.rows.get(query["tg_id"])


class AdminRoleTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_owner_has_every_owner_permission(self):
        with patch.object(auth, "OWNER_ID", 1), patch.object(auth, "ADMIN_IDS", []), patch.object(
            auth, "admin_roles", FakeAdminRoles({2: {"tg_id": 2, "role": "owner"}})
        ):
            user = await auth.get_owner({"id": 2})
        self.assertEqual(user["admin_role"], "owner")

    async def test_full_admin_cannot_manage_admins(self):
        with patch.object(auth, "OWNER_ID", 1), patch.object(auth, "ADMIN_IDS", []), patch.object(
            auth, "admin_roles", FakeAdminRoles({2: {"tg_id": 2, "role": "full"}})
        ):
            with self.assertRaises(HTTPException) as caught:
                await auth.get_owner({"id": 2})
        self.assertEqual(caught.exception.status_code, 403)

    async def test_executive_admin_cannot_use_full_tools(self):
        with patch.object(auth, "OWNER_ID", 1), patch.object(auth, "ADMIN_IDS", []), patch.object(
            auth, "admin_roles", FakeAdminRoles({3: {"tg_id": 3, "role": "limited"}})
        ):
            self.assertEqual((await auth.get_admin({"id": 3}))["admin_role"], "limited")
            with self.assertRaises(HTTPException) as caught:
                await auth.get_full_admin({"id": 3})
        self.assertEqual(caught.exception.status_code, 403)

    async def test_unknown_database_role_is_not_an_admin(self):
        with patch.object(auth, "OWNER_ID", 1), patch.object(auth, "ADMIN_IDS", []), patch.object(
            auth, "admin_roles", FakeAdminRoles({4: {"tg_id": 4, "role": "legacy"}})
        ):
            self.assertIsNone(await auth.get_admin_role({"id": 4}))


if __name__ == "__main__":
    unittest.main()
