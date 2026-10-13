import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from routers import rebellions, players as player_routes


class TaxAccrualTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 13)
        self.settings = rebellions._merge_settings({})
        self.player = {'tg_id': 1, 'created_at': self.start, 'tax_rate': 100,
                       'popularity': 50, 'tax_effect_at': self.start}

    def test_lowering_at_night_does_not_erase_daytime_penalty(self):
        rebellions.accrue_tax_effect(self.player, self.settings, self.start + timedelta(hours=23))
        self.player['tax_rate'] = 10
        rebellions.accrue_tax_effect(self.player, self.settings, self.start + timedelta(days=1))
        expected = rebellions._tax_delta(100, self.settings, 50)*23/24 + 1/24
        self.assertAlmostEqual(self.player['tax_effect_pending'], expected)
        self.assertLess(int(expected), 0)

    def test_many_changes_equal_one_settlement(self):
        for hour in range(1,25):
            rebellions.accrue_tax_effect(self.player, self.settings, self.start + timedelta(hours=hour))
        self.assertAlmostEqual(self.player['tax_effect_pending'], rebellions._tax_delta(100,self.settings,50))

    def test_paused_clock_does_not_accrue_twice(self):
        for _ in range(10):
            rebellions.accrue_tax_effect(self.player,self.settings,self.start)
        self.assertEqual(self.player['tax_effect_pending'],0)

    def test_migration_uses_last_check_and_old_rate(self):
        self.player.pop('tax_effect_at')
        self.player['popularity_history']=[{'at': self.start + timedelta(hours=12)}]
        rebellions.accrue_tax_effect(self.player,self.settings,self.start + timedelta(days=1))
        self.assertEqual(self.player['tax_effect_pending'],rebellions._tax_delta(100,self.settings,50)/2)


class TaxRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_daily_check_preserves_fraction_and_records_accrued_effect(self):
        current=datetime(2026,10,13)
        player={'tg_id':1,'created_at':current,'tax_effect_at':current,
                'tax_effect_pending':-0.75,'tax_rate':100,'popularity':90,'resources':{}}
        with patch.object(rebellions.rebellion_checks,'update_one',AsyncMock(return_value=SimpleNamespace(upserted_id=1))), \
             patch.object(rebellions.players,'update_one',AsyncMock()) as save, \
             patch.object(rebellions,'now',return_value=current):
            await rebellions.evaluate_player(player,rebellions._merge_settings({}),'2026-10-13')
        update=save.call_args.args[1]
        self.assertEqual(update['$set']['tax_effect_pending'],-0.75)
        self.assertEqual(update['$push']['popularity_history']['$each'][0]['tax_accrued'],-0.75)

    async def test_rate_change_saves_old_rate_effect_with_new_rate(self):
        start=datetime(2026,10,13)
        player={'tg_id':1,'created_at':start,'last_tick':start,'resources':{},'tax_rate':100,
                'popularity':50,'tax_effect_at':start}
        with patch.object(player_routes.players,'find_one',AsyncMock(return_value=player)), \
             patch.object(player_routes.players,'update_one',AsyncMock()) as save, \
             patch.object(player_routes,'apply_production',side_effect=lambda p:p), \
             patch.object(player_routes,'apply_campaign_upkeep',AsyncMock(return_value={})), \
             patch.object(player_routes,'normalize_stats',return_value={}), \
             patch.object(player_routes,'sync_medals',return_value={}), \
             patch.object(player_routes,'now',return_value=start+timedelta(hours=23)), \
             patch.object(rebellions,'get_settings',AsyncMock(return_value=rebellions._merge_settings({}))):
            await player_routes.set_tax(player_routes.TaxBody(rate=10),{'id':1})
        fields=save.call_args.args[1]['$set']
        self.assertEqual(fields['tax_rate'],10)
        self.assertLess(fields['tax_effect_pending'],-10)
