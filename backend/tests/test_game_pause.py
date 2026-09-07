import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import httpx
import game_clock
from game import now

class ClockTests(unittest.IsolatedAsyncioTestCase):
    async def test_freeze_resume_restart_and_duplicate_requests(self):
        stored = {}
        async def read(*args, **kwargs): return dict(stored)
        async def write(query, update, **kwargs): stored.update(update['$set'])
        start = datetime(2026, 9, 7, 12)
        with patch.object(game_clock.game_settings, 'find_one', side_effect=read), patch.object(game_clock.game_settings, 'update_one', side_effect=write), patch.object(game_clock, 'real_now') as real:
            real.return_value = start
            await game_clock.load()
            deadline = now() + timedelta(minutes=20)
            await game_clock.change(True, 'test', 1)
            real.return_value = start + timedelta(hours=5)
            await game_clock.load()  # persisted state after worker restart
            self.assertEqual(now(), start)
            await game_clock.change(True, 'duplicate', 1)
            await game_clock.change(False, '', 1)
            self.assertEqual(deadline - now(), timedelta(minutes=20))
            real.return_value += timedelta(minutes=3)
            await game_clock.change(False, '', 1)
            self.assertEqual(deadline - now(), timedelta(minutes=17))
        game_clock._state = {}

    async def test_http_mutations_blocked_and_owner_only_resume(self):
        import main
        from routers.pause import owner_user as get_owner
        from fastapi import HTTPException
        from routers.pause import change_pause
        with patch.object(game_clock, 'load', AsyncMock()), patch.object(game_clock, '_state', {'paused_at': datetime.utcnow()}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                for method,path in [('POST','/api/market/players'),('POST','/api/war/send'),('DELETE','/api/market/players/test'),('POST','/api/admin/reset')]:
                    response = await client.request(method,path,json={})
                    self.assertEqual(response.status_code,423)
                self.assertEqual((await client.get('/api/game/status')).status_code,200)
                self.assertEqual((await client.post('/api/admin/game-pause',json={'paused':False})).status_code,401)
                main.app.dependency_overrides[get_owner] = lambda: {'id': 1}
                try:
                    with patch.object(game_clock, 'change', AsyncMock(return_value={'paused':False})):
                        self.assertEqual((await client.post('/api/admin/game-pause',json={'paused':False})).status_code,200)
                finally: main.app.dependency_overrides.pop(get_owner,None)

    async def test_projects_do_not_settle_while_paused(self):
        import project_engine
        project={'status':'active'}
        with patch.object(game_clock,'paused',return_value=True), patch.object(project_engine,'recover',AsyncMock()) as recover:
            self.assertEqual(await project_engine.tick_project(project),project)
            recover.assert_not_awaited()
