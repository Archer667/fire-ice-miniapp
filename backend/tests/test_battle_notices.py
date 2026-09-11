import sys
import types
import unittest
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,patch
from test_castle_rules import load
from test_war_regressions import Collection

class NoticeTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_failure_retries_then_acknowledges_without_duplicate_raven(self):
        row={'_id':'join:1','to_id':1,'to_name':'Player','text':'battle','raven_done':True,'bot_done':False,
             'complete':False,'next_attempt':datetime.utcnow()-timedelta(seconds=1),'attempts':0}
        outbox=Collection([row])
        post=AsyncMock(side_effect=[types.SimpleNamespace(status_code=502,json=lambda:{'ok':False}),
                                   types.SimpleNamespace(status_code=200,json=lambda:{'ok':True,'result':{'message_id':7}})])
        class Client:
            async def __aenter__(self): return types.SimpleNamespace(post=post)
            async def __aexit__(self,*args): pass
        http=types.SimpleNamespace(AsyncClient=lambda **kw:Client(),HTTPError=OSError)
        game=types.ModuleType('game');game.now=datetime.utcnow
        labels=types.ModuleType('player_labels');labels.normalize_player_names=AsyncMock(side_effect=lambda s:s)
        messages=types.SimpleNamespace(update_one=AsyncMock())
        ns={'outbox':outbox,'db':types.SimpleNamespace(messages=messages), 'httpx':http,'BOT_TOKEN':'test',
            'DEV_MODE':False,'SYSTEM_SENDER_NAME':'Game','SYSTEM_SENDER_ID':0,'datetime':datetime,'timedelta':timedelta}
        load('battle_notices.py',{'flush'},ns)
        with patch.dict(sys.modules,{'game':game,'player_labels':labels}):
            await ns['flush']()
            self.assertFalse(outbox.rows[0]['complete'])
            outbox.rows[0]['next_attempt']=datetime.utcnow()-timedelta(seconds=1)
            await ns['flush']()
        self.assertTrue(outbox.rows[0]['complete'])
        self.assertEqual(outbox.rows[0]['telegram_message_id'],7)
        self.assertEqual(post.await_count,2)
        messages.update_one.assert_not_awaited()

if __name__=='__main__': unittest.main()
