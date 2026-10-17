import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, Mock

from fastapi import HTTPException, Response
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

import season_branding as branding


class SeasonIdentity(unittest.TestCase):
    def test_optional_name_and_ordinals(self):
        self.assertEqual(branding.season_title(1), 'والریا : سیزن اول')
        self.assertEqual(branding.season_title(2, 'عصر اژدها'), 'والریا : سیزن دوم — عصر اژدها')
        self.assertEqual(branding.season_title(3), 'والریا : سیزن سوم')
        self.assertEqual(branding.season_title(11), 'والریا : سیزن ۱۱')

    def test_reject_invalid_numbers_and_overlong_names(self):
        for number in [0, -1, 10000, True, 1.5, '2']:
            with self.subTest(number=number), self.assertRaises(ValidationError):
                branding.SeasonBrandingBody(number=number, revision=0)
        with self.assertRaises(ValidationError):
            branding.SeasonBrandingBody(number=2, name='الف'*81, revision=0)


class SeasonChanges(unittest.IsolatedAsyncioTestCase):
    async def test_first_season_default_without_database_mutation(self):
        store = SimpleNamespace(find_one=AsyncMock(return_value=None), update_one=AsyncMock())
        with patch.object(branding, 'game_settings', store):
            result = await branding.read_branding()
        self.assertEqual(result, {'number': 1, 'name': '', 'revision': 0, 'title': 'والریا : سیزن اول'})
        store.update_one.assert_not_awaited()

    async def test_public_response_is_not_cached(self):
        response = Response()
        with patch.object(branding, 'read_branding', AsyncMock(return_value={'number': 3})):
            self.assertEqual(await branding.public_branding(response), {'number': 3})
        self.assertEqual(response.headers['cache-control'], 'no-store')

    async def test_public_route_works_before_login_and_skips_game_processing(self):
        import main
        import httpx
        with patch.object(branding, 'game_settings', SimpleNamespace(find_one=AsyncMock(return_value=None))), patch('game_clock.load', AsyncMock(side_effect=AssertionError('Branding must be read-only'))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                response = await client.get('/api/season-branding')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['number'], 1)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    async def test_saved_value_is_read_each_time(self):
        store = SimpleNamespace(find_one=AsyncMock(side_effect=[
            {'number': 2, 'name': 'نام', 'revision': 1},
            {'number': 3, 'name': '', 'revision': 2}]))
        with patch.object(branding, 'game_settings', store):
            first = await branding.read_branding()
            second = await branding.read_branding()
        self.assertIn('نام', first['title'])
        self.assertEqual(second['title'], 'والریا : سیزن سوم')

    async def test_only_branding_document_changes_and_name_can_be_cleared(self):
        store = SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1, upserted_id=None)))
        with patch.object(branding, 'game_settings', store), patch.object(branding, 'get_full_admin', AsyncMock(return_value={'id': 5})):
            result = await branding.save_branding(branding.SeasonBrandingBody(number=3, name='   ', revision=7), {'id': 5})
        query, update = store.update_one.call_args.args
        self.assertEqual(query, {'_id': branding.SETTINGS_ID, 'revision': 7})
        self.assertEqual(set(update['$set']), {'number', 'name', 'updated_at', 'updated_by'})
        self.assertEqual(result, {'number': 3, 'name': '', 'revision': 8, 'title': 'والریا : سیزن سوم'})
        self.assertFalse(store.update_one.call_args.kwargs['upsert'])

    async def test_first_save_creates_revision(self):
        store = SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=0, upserted_id=branding.SETTINGS_ID)))
        with patch.object(branding, 'game_settings', store), patch.object(branding, 'get_full_admin', AsyncMock(return_value={'id': 5})):
            result = await branding.save_branding(branding.SeasonBrandingBody(number=2, name=' عصر اژدها ', revision=0), {'id': 5})
        self.assertEqual(result['name'], 'عصر اژدها')
        self.assertEqual(result['revision'], 1)
        self.assertTrue(store.update_one.call_args.kwargs['upsert'])

    async def test_outdated_editor_cannot_overwrite_new_settings(self):
        for reply in [SimpleNamespace(matched_count=0, upserted_id=None), DuplicateKeyError('existing revision')]:
            update = AsyncMock(side_effect=reply) if isinstance(reply, Exception) else AsyncMock(return_value=reply)
            with self.subTest(reply=reply), patch.object(branding, 'game_settings', SimpleNamespace(update_one=update)), patch.object(branding, 'get_full_admin', AsyncMock(return_value={'id': 5})):
                with self.assertRaises(HTTPException) as ctx:
                    await branding.save_branding(branding.SeasonBrandingBody(number=2, revision=0), {'id': 5})
                self.assertEqual(ctx.exception.status_code, 409)

    async def test_player_and_limited_roles_cannot_save(self):
        for role in [None, 'limited', 'war_roleplay']:
            with self.subTest(role=role), patch('auth.get_admin_role', AsyncMock(return_value=role)), patch.object(branding, 'game_settings', SimpleNamespace(update_one=AsyncMock())) as store:
                with self.assertRaises(HTTPException) as ctx:
                    await branding.save_branding(branding.SeasonBrandingBody(number=2, revision=0), {'id': 5})
                self.assertEqual(ctx.exception.status_code, 403)
                store.update_one.assert_not_awaited()

    async def test_full_and_owner_roles_can_save(self):
        for role in ['full', 'owner']:
            with self.subTest(role=role), patch('auth.get_admin_role', AsyncMock(return_value=role)), patch.object(branding, 'game_settings', SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1, upserted_id=None)))):
                result = await branding.save_branding(branding.SeasonBrandingBody(number=2, revision=1), {'id': 5})
                self.assertEqual(result['number'], 2)

    async def test_multiline_name_rejected_before_write(self):
        with patch.object(branding, 'get_full_admin', AsyncMock(return_value={'id': 5})), patch.object(branding, 'game_settings', SimpleNamespace(update_one=AsyncMock())) as store:
            with self.assertRaises(HTTPException) as ctx:
                await branding.save_branding(branding.SeasonBrandingBody(number=2, name='عصر\nاژدها', revision=0), {'id': 5})
            self.assertEqual(ctx.exception.status_code, 400)
            store.update_one.assert_not_awaited()

    async def test_bot_welcome_uses_current_season(self):
        from routers import bot
        request = SimpleNamespace(json=AsyncMock(return_value={'message': {'text': '/start', 'chat': {'id': 7}}}))
        with patch.object(bot, 'read_branding', AsyncMock(return_value={'title': 'والریا : سیزن سوم — زمستان'})), patch.object(bot.telegram_bot, 'WEBHOOK_SECRET', ''), patch.object(bot.telegram_bot, 'push', Mock()) as push:
            await bot.webhook(request, '')
        self.assertIn('سیزن سوم — زمستان', push.call_args.args[1])
