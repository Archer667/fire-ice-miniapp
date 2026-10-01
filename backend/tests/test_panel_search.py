import asyncio
import unittest
from starlette.requests import Request
from starlette.responses import Response
from player_search import find_matches

class SearchTests(unittest.TestCase):
    def test_telegram_username_and_numeric_id(self):
        rows=[{'tg_id':12345,'name':'Lord Example','castle':'تویینز','region':'river','telegram_username':'Player_Test'},
              {'tg_id':67890,'name':'Other','castle':'وینترفل','region':'north','username':'Legacy_Name'}]
        self.assertEqual([r['tg_id'] for r in find_matches(rows,'@PLAYER_TEST')],[12345])
        self.assertEqual(find_matches(rows,'12345')[0]['telegram_username'],'Player_Test')
        self.assertEqual([r['tg_id'] for r in find_matches(rows,'legacy_name')],[67890])
        self.assertEqual(find_matches(rows,'unknown'),[])

class SearchLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_search_does_not_wait_for_state_lock(self):
        from main import serialize_game_state, game_state_lock
        request=Request({'type':'http','method':'GET','path':'/api/players/search','headers':[]})
        async def handler(request): return Response('ok')
        async with game_state_lock:
            response=await asyncio.wait_for(serialize_game_state(request,handler),.2)
        self.assertEqual(response.body,b'ok')

    async def test_mutation_still_waits_for_state_lock(self):
        from main import serialize_game_state, game_state_lock
        request=Request({'type':'http','method':'POST','path':'/api/admin/players/123/resources','headers':[]})
        async def handler(request): return Response('ok')
        async with game_state_lock:
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(serialize_game_state(request,handler),.05)
