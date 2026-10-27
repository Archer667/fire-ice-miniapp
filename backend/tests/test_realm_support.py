import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import realm_state
import support
from routers import realm


class RealmAndSupportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mem = AsyncMongoMockClient()["realm_support_test"]
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for module, name, value in [
            (realm_state, "players", self.mem.players),
            (realm_state, "EVENTS", self.mem.game_events),
            (realm_state, "POPULARITY_EVENTS", self.mem.popularity_events),
            (realm_state, "REPUTATION", self.mem.political_reputation),
            (realm, "players", self.mem.players),
            (realm, "proposals", self.mem.council_proposals),
            (support, "players", self.mem.players),
            (support, "support_tickets", self.mem.support_tickets),
        ]:
            self.stack.enter_context(patch.object(module, name, value))
        self.stack.enter_context(patch.object(realm, "adjust_influence", realm_state.adjust_influence))
        self.stack.enter_context(patch.object(realm, "overview_for", realm_state.overview_for))
        self.stack.enter_context(patch.object(realm, "record_event", realm_state.record_event))
        self.notify = self.stack.enter_context(patch.object(support, "notify_admins", AsyncMock()))
        self.message = self.stack.enter_context(patch.object(support, "send_system_message", AsyncMock()))
        await self.mem.players.insert_many([
            {"tg_id": 1, "name": "A", "region": "north", "castle": "A", "popularity": 98, "resources": {"gold": 100}},
            {"tg_id": 2, "name": "B", "region": "north", "castle": "B", "resources": {"gold": 100}},
        ])

    async def test_popularity_is_clamped_and_audited(self):
        value = await realm_state.adjust_popularity(1, 10, "پیروزی", source_kind="battle", source_id="b1")
        self.assertEqual(value, 100)
        self.assertEqual(await self.mem.popularity_events.count_documents({"tg_id": 1}), 1)
        event = await self.mem.game_events.find_one({"_id": "popularity:battle:b1:1"})
        self.assertEqual(event["data"]["delta"], 2)

    async def test_legacy_player_gets_influence_before_spending(self):
        balance = await realm_state.adjust_influence(2, -10, "پیشنهاد", source_id="p1")
        self.assertEqual(balance, realm_state.INFLUENCE_START - 10)
        self.assertEqual((await self.mem.players.find_one({"tg_id": 2}))["political_influence"], 10)

    async def test_council_proposal_vote_and_admin_finish(self):
        self.stack.enter_context(patch.object(realm, "rules", AsyncMock(return_value={**realm.DEFAULT_RULES, "proposal_cost": 5})))
        created = await realm.create_proposal(
            realm.ProposalBody(title="قانون بازرگانی", description="شرح کامل قانون بازرگانی", options=["آری", "نه"], scope="realm"),
            {"id": 1},
        )
        await realm.vote_proposal(created["id"], realm.VoteBody(option=0), {"id": 2})
        await realm.finish_proposal(created["id"], realm.FinishBody(outcome="تصویب شد", enact=True), {"id": 99})
        row = await self.mem.council_proposals.find_one({})
        self.assertEqual(row["status"], "enacted")
        self.assertEqual(row["votes"]["2"], 0)

    async def test_support_ticket_thread_and_ownership(self):
        ticket = await support.create_ticket(
            support.CreateTicket(category="technical", title="مشکل ورود", description="صفحه برای من باز نمی‌شود"),
            {"id": 1, "first_name": "A"},
        )
        self.notify.assert_awaited_once()
        await support.player_reply(ticket["id"], support.PlayerReply(text="تصویر خطا را هم فرستادم"), {"id": 1})
        with self.assertRaises(HTTPException):
            await support.player_reply(ticket["id"], support.PlayerReply(text="دسترسی غیرمجاز"), {"id": 2})
        await support.admin_action(ticket["id"], support.AdminAction(text="بررسی و اصلاح شد", status="answered"), {"id": 99})
        mine = await support.mine({"id": 1})
        self.assertEqual(mine[0]["status"], "answered")
        self.assertEqual(len(mine[0]["messages"]), 3)
        self.message.assert_awaited_once()

