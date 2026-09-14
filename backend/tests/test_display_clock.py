import unittest
from datetime import datetime, timedelta
from display_clock import DisplayClock, tehran_text

class DisplayClockTests(unittest.TestCase):
 def test_offset_changes_do_not_rewrite_old_events(self):
  start=datetime(2026,9,1)
  clock=DisplayClock([(start,3600),(start+timedelta(days=1),7200)])
  self.assertEqual(clock.real(start+timedelta(hours=2)),start+timedelta(hours=3))
  self.assertEqual(clock.real(start+timedelta(days=1,hours=2)),start+timedelta(days=1,hours=4))
  self.assertIsNone(clock.real(start-timedelta(days=1)))
 def test_tehran_midnight(self):
  self.assertEqual(tehran_text(datetime(2026,9,14,20,58)), '2026-09-15 00:28:00')
 def test_real_iso_has_utc_marker(self):
  self.assertEqual(DisplayClock([(datetime.min,0)]).iso(datetime(2026,9,14,20,58)), '2026-09-14T20:58:00Z')
