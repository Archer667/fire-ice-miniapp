import unittest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException

import auth


class FakeAdminRoles:
    def __init__(self, rows=None):
        self.rows = rows or {}

    async def find_one(self, query):
        return self.rows.get(query["tg_id"])


class AdminRoleTests(unittest.IsolatedAsyncioTestCase):
    async def test_restricted_admin_does_not_receive_unrelated_notifications(self):
        import admin_notifications as notifications
        async def rows():
            yield {'tg_id':2,'role':'full'}
            yield {'tg_id':3,'role':'war_roleplay'}
        with patch.object(notifications,'OWNER_ID',1), patch.object(notifications,'ADMIN_IDS',[]), \
             patch.object(notifications.admin_roles,'find',side_effect=lambda *a,**k:rows()):
            self.assertNotIn(3,await notifications._admin_ids())
            self.assertIn(3,await notifications._admin_ids(('owner','full','limited','war_roleplay')))

    async def test_http_uses_actual_request_scope_for_restricted_admin(self):
        import httpx, main, game_clock
        for target in ('item_effects.recover_item_effects', 'food_settlement.recover_pending_food',
                       'army_groups.recover_moves', 'battle_passage.recover', 'character_records.recover_swaps',
                       'road_victory.recover', 'pact_exits.recover_exits', 'institution_bank.recover',
                       'institution_finance.recover', 'system_reports.begin_admin'):
            self.enterContext(patch(target, AsyncMock(return_value=None)))
        with patch.object(auth,'OWNER_ID',1), patch.object(auth,'ADMIN_IDS',[]), \
             patch.object(auth,'DEV_MODE',True), patch.object(auth,'players') as players, \
             patch.object(auth,'admin_roles',FakeAdminRoles({3:{'role':'war_roleplay'}})), \
             patch.object(game_clock,'load',AsyncMock()), patch.object(game_clock,'_state',{}), \
             patch('routers.admin.game_settings.find_one',AsyncMock(return_value={'max_score':90})):
            players.find_one=AsyncMock(return_value=None)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test',
                                         headers={'x-dev-user':'3:Judge'}) as client:
                self.assertEqual((await client.get('/api/admin/roleplay-score/settings')).status_code,200)
                self.assertEqual((await client.get('/api/admin/players/pending',headers={'x-admin-request':'/api/admin/roleplay'})).status_code,403)
                self.assertEqual((await client.get('/api/admin/notifications')).status_code,403)
                self.assertEqual((await client.get('/api/admin/admins')).status_code,403)

    async def test_war_roleplay_admin_can_only_use_permitted_endpoints(self):
        with patch.object(auth, 'OWNER_ID', 1), patch.object(auth, 'ADMIN_IDS', []), \
             patch.object(auth, 'admin_roles', FakeAdminRoles({3:{'role':'war_roleplay'}})):
            for method,path in [('GET','/api/admin/battles'), ('GET','/api/admin/roleplay'),
                                ('POST','/api/admin/battles/case/resolve'), ('POST','/api/admin/roleplay/case/respond')]:
                self.assertEqual((await auth.get_admin({'id':3,'_admin_request':(method,path)}))['admin_role'],'war_roleplay')
            for method,path in [('GET','/api/admin/players/pending'),('GET','/api/admin/notifications'),
                                ('POST','/api/admin/send-bot-message'),('GET','/api/admin/roleplay/security'),
                                ('POST','/api/admin/war-window'),('POST','/api/admin/battles/case/unknown')]:
                with self.subTest(path=path), self.assertRaises(HTTPException):
                    await auth.get_admin({'id':3,'_admin_request':(method,path)})
            with self.assertRaises(HTTPException): await auth.get_admin({'id':3})
            with self.assertRaises(HTTPException): await auth.get_full_admin({'id':3})
            with self.assertRaises(HTTPException): await auth.get_owner({'id':3})

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
