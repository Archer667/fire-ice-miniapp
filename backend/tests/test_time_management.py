import unittest
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError
import game_clock
import time_management as tm

class ClockDisplay(unittest.TestCase):
    def test_old_game_date_displays_future_real_deadline(self):
        real = datetime(2026,10,8,12)
        offset = 10*86400
        with patch.object(game_clock,'real_now',return_value=real), patch.object(game_clock,'_state',{'offset_seconds':offset}):
            view = tm.deadline_view(game_clock.now()+timedelta(hours=6))
            self.assertEqual(view['display_at'],'2026-10-08T18:00:00Z')
            self.assertEqual(view['remaining_seconds'],21600)
            self.assertNotEqual(view['internal_at'],view['display_at'])

    def test_pause_freezes_remaining_not_real_clock(self):
        paused = datetime(2026,10,7,12)
        with patch.object(game_clock,'_state',{'paused_at':paused,'offset_seconds':86400}):
            deadline = game_clock.now()+timedelta(hours=3)
            with patch.object(game_clock,'real_now',return_value=datetime(2026,10,8,12)):
                first=tm.deadline_view(deadline)
            with patch.object(game_clock,'real_now',return_value=datetime(2026,10,9,12)):
                second=tm.deadline_view(deadline)
            self.assertEqual(first['remaining_seconds'],second['remaining_seconds'])
            self.assertNotEqual(first['display_at'],second['display_at'])
            self.assertTrue(second['estimated'])

    def test_worker_bounds_and_reason_required(self):
        with self.assertRaises(ValidationError):
            tm.WorkerSettings(arrival_poll_seconds=0,project_poll_seconds=15,market_poll_seconds=300,deadline_warning_hours=2)
        with self.assertRaises(ValidationError):
            tm.SeasonSettings(day=31,reason='test')

class TimerChanges(unittest.IsolatedAsyncioTestCase):
    async def test_deadline_expiry_is_not_limited_to_hourly_rebellion_roll(self):
        from routers import rebellions
        stamp=datetime(2026,10,8,12,20)
        with patch.object(rebellions,'now',return_value=stamp),patch.object(rebellions,'_last_evaluation_hour','2026-10-08-12'),patch.object(rebellions,'expire_roleplay_deadlines',AsyncMock()) as expiry,patch.object(rebellions,'get_settings',AsyncMock()) as settings:
            await rebellions.evaluate_rebellions()
            expiry.assert_awaited_once()
            settings.assert_not_awaited()

    async def test_handler_does_not_reacquire_middleware_lock(self):
        from project_engine import game_state_lock
        store=SimpleNamespace(update_one=AsyncMock())
        with patch.object(tm,'game_settings',store),patch.object(game_clock,'load',AsyncMock()):
            async with game_state_lock:
                result=await asyncio.wait_for(tm.save_workers(tm.WorkerSettings(arrival_poll_seconds=30,project_poll_seconds=15,market_poll_seconds=300,deadline_warning_hours=2),{'id':5}),timeout=.5)
                self.assertTrue(result['ok'])

    async def test_limited_admin_cannot_change_timers(self):
        with patch('auth.get_admin_role',AsyncMock(return_value='limited')):
            with self.assertRaises(HTTPException) as ctx:
                await tm.admin({'id':5})
            self.assertEqual(ctx.exception.status_code,403)

    async def test_rebellion_correction_has_compare_and_swap_and_audit(self):
        database=SimpleNamespace(rebellions=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1))))
        stamp=datetime(2026,9,28,12)
        with patch.object(tm,'db',database),patch.object(game_clock,'now',return_value=stamp):
            await tm.correct_rebellion(str(ObjectId()),tm.TimerCorrection(remaining_minutes=60,expected_internal_at=stamp,reason='اصلاح مهلت'),{'id':5})
        query,update=database.rebellions.update_one.call_args.args
        self.assertEqual(query['deadline'],stamp)
        self.assertNotIn('resolved',query['status']['$in'])
        self.assertEqual(update['$set']['deadline'],stamp+timedelta(hours=1))
        self.assertEqual(update['$push']['time_corrections']['actor'],5)

    async def test_stale_or_resolved_deadline_cannot_be_reopened(self):
        database=SimpleNamespace(rebellions=SimpleNamespace(update_one=AsyncMock(return_value=SimpleNamespace(matched_count=0))))
        with patch.object(tm,'db',database):
            with self.assertRaises(HTTPException) as ctx:
                await tm.correct_rebellion(str(ObjectId()),tm.TimerCorrection(remaining_minutes=60,expected_internal_at=datetime(2026,10,1),reason='test'),{'id':5})
            self.assertEqual(ctx.exception.status_code,409)

    async def test_invalid_zone_rejected_before_write(self):
        with patch.object(tm,'game_settings',SimpleNamespace(update_one=AsyncMock())) as store:
            with self.assertRaises(HTTPException):
                await tm.save_display(tm.DisplaySettings(timezone='Invalid/Nowhere'),{'id':5})
            store.update_one.assert_not_awaited()
