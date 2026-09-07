import unittest
from unittest.mock import patch, AsyncMock
import public_audience
class Cursor:
    def __aiter__(self):
        async def rows():
            for p in [{'tg_id':1,'name':'player'}, {'tg_id':2,'name':'admin-player'}]: yield p
        return rows()
class AudienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_without_character_and_no_duplicates(self):
        with patch.object(public_audience.players,'find',return_value=Cursor()), patch.object(public_audience,'_admin_ids',AsyncMock(return_value={2,3,4})):
            rows=await public_audience.public_recipients()
            self.assertEqual(sorted(p['tg_id'] for p in rows),[1,2,3,4])
            self.assertEqual(len(rows),4)
