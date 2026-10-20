import unittest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from pydantic import ValidationError
import text_limits as rules
from system_reports import LimitsBody, save_limits
from routers import roleplay, rebellions, espionage, war, projects
import institution_citadel as citadel
import institution_services as services
import institution_mercenaries as mercenaries

class NarrativeLimits(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings=AsyncMock()
        self.settings.find_one.return_value={'roleplay_words':3,'scenario_words':4,'request_words':5}
        self.enterContext(patch.object(rules,'game_settings',self.settings))

    async def test_persian_whitespace_and_half_space(self):
        self.assertEqual(rules.word_count('  می\u200cروم\nبه\tقلعه\u00a0امروز\ufeff '),4)
        await rules.check_text('یک دو سه چهار')
        with self.assertRaises(HTTPException): await rules.check_text('یک دو سه چهار پنج')
        with self.assertRaises(HTTPException): await rules.check_text('یک دو سه چهار','roleplay_words')

    async def test_large_single_word_is_bounded(self):
        with self.assertRaises(HTTPException): await rules.check_text('x'*500001)

    async def test_setting_update_applies_without_restart(self):
        with self.assertRaises(HTTPException): await rules.check_text('a b c d e')
        self.settings.find_one.return_value={'scenario_words':5}
        await rules.check_text('a b c d e')
        self.assertEqual((await rules.text_limits())['roleplay_words'],1000)

    async def test_partial_legacy_save_keeps_new_limits(self):
        import system_reports
        store=AsyncMock();store.find_one.return_value={}
        with patch.object(system_reports,'game_settings',store):
            await save_limits(LimitsBody(roleplays=3,projects=1),{'id':1})
        self.assertEqual(store.update_one.await_args.args[1]['$set'],{'roleplays':3,'projects':1})

    def test_invalid_limits_and_no_coercion(self):
        for value in [0,-1,50001,True,'100']:
            with self.assertRaises(ValidationError):LimitsBody(roleplays=3,projects=1,scenario_words=value)

    async def test_rebellion_does_not_store_over_limit_text(self):
        store=AsyncMock()
        with patch.object(rebellions,'rebellions',store):
            with self.assertRaises(HTTPException):await rebellions.submit_roleplay('bad-id',rebellions.RoleplayBody(text='one two three four five'),{'id':1})
        store.update_one.assert_not_awaited()

    async def test_roleplay_rejects_before_quota_or_insert(self):
        store=AsyncMock();store.find_one.return_value={'tg_id':1}
        quota=AsyncMock()
        with patch.object(roleplay,'players',store),patch.object(roleplay,'check_quota',quota):
            with self.assertRaises(HTTPException): await roleplay.send(roleplay.RoleplayBody(category='other',text='one two three four five'),{'id':1})
        quota.assert_not_awaited()

    async def test_institution_scenario_and_proposal_checked(self):
        for module,args in [(citadel,[]),(services,['alchemists'])]:
            row=module.Submission(version='v',scenario='one two three four five six',proposal='suggested result here')
            with patch.object(module,'change',AsyncMock()) as change:
                with self.assertRaises(HTTPException):await module.submit(*args,'case',row,{'id':1})
                change.assert_not_awaited()

    async def test_institution_requests_reject_before_reserving_resources(self):
        for module,args,kind in [(citadel,[],'research'),(services,['alchemists'],'craft')]:
            row=module.Request(request_id='request',kind=kind,title='new request',description='one two three four five six seven',**({'resources':{'gold':50}} if module is services else {}))
            with patch.object(module,'living',AsyncMock()) as living:
                with self.assertRaises(HTTPException):await module.request(*args,row,{'id':1})
                living.assert_not_awaited()
