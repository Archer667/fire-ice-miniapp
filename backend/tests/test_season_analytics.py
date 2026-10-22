import copy
import unittest
from datetime import datetime,timedelta
from unittest.mock import patch,AsyncMock
from fastapi import HTTPException
import season_analytics as a
from tests.test_social_world import Database,Collection,matches

async def delete_many(self,query):self.rows[:]=[r for r in self.rows if not matches(r,query)]

class AnalyticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db=Database();self.at=datetime(2026,10,21,12,35);self.game=datetime(2026,10,5,0)
        self.season={'_id':'season-one','epoch':self.game,'end':self.game+timedelta(days=30),'title':'والریا · فصل اول','first_observed_real':self.at,'first_observed_game':self.game}
        self.enterContext(patch.object(a,'db',self.db));self.enterContext(patch.object(a,'players',self.db.players));self.enterContext(patch.object(a,'game_settings',self.db.game_settings))
        for field,name in [('snapshots','analytics_hourly'),('events','analytics_events'),('seasons','analytics_seasons'),('files','analytics_files'),('yearbooks','analytics_yearbooks')]:self.enterContext(patch.object(a,field,self.db[name]))
        self.enterContext(patch.object(a,'real_now',side_effect=lambda:self.at));self.enterContext(patch.object(a,'now',side_effect=lambda:self.game))
        self.enterContext(patch.object(a,'current_season',AsyncMock(side_effect=lambda:copy.deepcopy(self.season))))
        self.enterContext(patch.object(a,'admin_ids',AsyncMock(return_value={99})))
        self.enterContext(patch.object(a.game_clock,'paused',return_value=False))
        self.enterContext(patch.object(Collection,'delete_many',delete_many,create=True))
        original_find=Collection.find
        self.enterContext(patch.object(Collection,'find',lambda col,query,*projection:original_find(col,query)))
        self.enterContext(patch.object(a,'apply_production',side_effect=lambda p:p))
        self.db.players.rows=[{'_id':'p1','tg_id':1,'name':'لرد نمونه','created_at':self.game,'region':'north','castle':'A','resources':{'gold':1000,'men':500},'troops':{'infantry':5,'ship':1},'equipment':{},'buildings':{'farm':{'level':2}},'stats':{},'last_tick':self.game}]
    async def test_hourly_sampling_continues_during_pause_and_never_overwrites(self):
        with patch.object(a.game_clock,'paused',return_value=True):await a.capture()
        first=copy.deepcopy(a.snapshots.rows[0]);self.assertTrue(first['paused'])
        self.db.players.rows[0]['resources']['gold']=100
        await a.capture(force=True)
        self.assertEqual(len(a.snapshots.rows),1);self.assertEqual(a.snapshots.rows[0]['state']['resources']['gold'],1000)
        self.at+=timedelta(hours=1);await a.capture()
        self.assertEqual(len(a.snapshots.rows),2);self.assertEqual(a.snapshots.rows[1]['state']['resources']['gold'],100)
        self.assertEqual(self.db.players.rows[0]['resources']['gold'],100)
    async def test_downtime_leaves_missing_hours_not_interpolated(self):
        await a.capture();self.at+=timedelta(hours=5);await a.capture()
        self.assertEqual(len(a.snapshots.rows),2)
        html=a.render_hourly(1,a.snapshots.rows,self.at)
        self.assertIn('ثبت نشده',html);self.assertEqual(html.count('<span class="missing">ثبت نشده</span>'),22)
    async def test_campaign_groups_and_ships_are_not_double_counted(self):
        p=self.db.players.rows[0]
        armies=[{'_id':'a','name':'اول','troops':{'infantry':10,'ship':2},'equipment':{'ladder':3},'merge_group_id':'joint'},
                {'_id':'b','name':'دوم','troops':{'archer':20},'equipment':{'catapult':1},'merge_group_id':'joint'}]
        state=await a.asset_state(p,armies,{})
        self.assertEqual(state['men'],35);self.assertEqual(state['ships'],3);self.assertEqual(state['army_count'],2)
        self.assertEqual(state['equipment'],{'ladder':3,'catapult':1});self.assertEqual(p['resources']['men'],500)
    async def test_season_boundaries_and_legacy_facts_survive_source_cleanup(self):
        self.db.roleplays.rows=[{'_id':'day1','tg_id':1,'player_name':'قدیمی','created_at':self.game,'category':'economy','admin_score':80,'scored_at':self.game,'resolved':True,'resolved_at':self.game,'admin_adjustments':[{'tg_id':1,'resources':{'gold':100,'wood':30}},{'tg_id':2,'resources':{'gold':900}}]},
            {'_id':'day30','tg_id':1,'created_at':self.game+timedelta(days=29,hours=23),'category':'other'},
            {'_id':'outside','tg_id':1,'created_at':self.game+timedelta(days=30),'category':'other'}]
        await a.archive_sources(self.season);self.db.roleplays.rows=[]
        d=await a.season_data(self.season);m=d['players']['1']['metrics']
        self.assertEqual(m['roles'],2);self.assertEqual(m['role_gold_gain'],100);self.assertEqual(m['role_score'],80)
        self.assertEqual(d['daily'][29]['roles'],1);self.assertEqual(len(a.events.rows),2)
    async def test_regrading_replaces_score_and_late_score_cannot_change_closed_season(self):
        row={'_id':'r','tg_id':1,'created_at':self.game,'category':'economy','admin_score':30,'scored_at':self.game}
        await a.archive_row('roleplays',row);row.update(admin_score=60);await a.archive_row('roleplays',row)
        row.update(admin_score=100,scored_at=self.season['end']);await a.archive_row('roleplays',row)
        self.assertEqual((await a.season_data(self.season))['players']['1']['metrics']['role_score'],60)
        self.assertEqual(len(a.events.rows),1)
    async def test_frozen_yearbook_is_immutable_and_survives_source_cleanup(self):
        self.db.roleplays.rows=[{'_id':'r','tg_id':1,'player_name':'لرد نمونه','created_at':self.game,'category':'economy'}]
        frozen=await a.freeze_season('game-reset')
        self.assertEqual(frozen['reason'],'game-reset');self.assertIn('لرد نمونه',frozen['content'])
        original=frozen['content'];self.db.roleplays.rows=[];self.db.players.rows[0]['name']='نام جدید'
        again=await a.freeze_season('season-reset')
        self.assertEqual(again['content'],original);self.assertEqual(again['sha256'],frozen['sha256'])
        result=await a.export_season(a.SeasonRequest(season=self.season['_id']),{'id':99})
        self.assertIn(self.season['_id'],result['filename']);self.assertEqual(a.files.rows[-1]['content'],original)
    async def test_attack_and_battle_winners_dedup_and_admin_exclusion(self):
        for ident,uid in [('a',1),('b',1),('c',99)]:
            await a.archive_row('campaigns',{'_id':ident,'tg_id':uid,'created_at':self.game,'op_type':'attack','men_committed':100,'medal_outcome_recorded':True,'medal_outcome_battle_id':'battle','winner_tg_ids':[1,99],'combat_resolved_at':self.game})
        await a.archive_row('campaigns',{'_id':'d','tg_id':1,'created_at':self.game,'op_type':'defend','men_committed':400})
        data=await a.season_data(self.season);m=data['players']['1']['metrics']
        self.assertEqual(m['attacks'],2);self.assertEqual(m['men_dispatched'],200);self.assertEqual(m['battle_wins'],1);self.assertEqual(m['defenses'],1)
        self.assertNotIn('99',data['players'])
    async def test_real_24_hour_query_does_not_read_game_calendar(self):
        await a.capture();self.game-=timedelta(days=10);self.at+=timedelta(hours=1)
        result=await a.export_hourly(1,{'id':99});self.assertTrue(result['filename'].endswith('.html'))
        self.assertIn('ثبت نشده',a.files.rows[0]['content']);self.assertIn('لرد نمونه',a.files.rows[0]['content'])
    async def test_private_ticket_expiry_and_cross_route_security(self):
        r=await a.issue_file('<html>private</html>','test',99)
        token=r['path'].rsplit('/',1)[1];self.assertEqual(len(token),43)
        self.assertNotIn(token,str(a.files.rows));self.assertEqual((await a.download(token)).status_code,200)
        self.at+=timedelta(minutes=11)
        with self.assertRaises(HTTPException):await a.download(token)
        with self.assertRaises(HTTPException):await a.download('../bad')
    async def test_full_admin_guard_and_rate_limit(self):
        with patch.object(a,'get_full_admin',AsyncMock(side_effect=HTTPException(403,'denied'))):
            with self.assertRaises(HTTPException):await a.full({'id':1})
        for i in range(6):await a.issue_file('safe','test',99)
        with self.assertRaises(HTTPException):await a.issue_file('safe','test',99)
    def test_export_escapes_names_no_script_and_requested_ornament_present(self):
        data={'players':{'1':{'uid':'1','name':'<script>alert(1)</script>','metrics':{'roles':4,'attacks':2},'role_resources':{}}},'daily':[{'day':i+1,'roles':0,'attacks':0,'trades':0} for i in range(30)],'sources':{}}
        result=a.render_season(self.season,data)
        self.assertNotIn('<script>',result);self.assertIn('&lt;script&gt;',result);self.assertIn(a.ORNAMENT,result)
        self.assertIn('Content-Security-Policy',result);self.assertNotIn('https://',result)
    async def test_character_change_or_missing_slot_has_no_false_delta(self):
        await a.capture();self.at+=timedelta(hours=1);self.db.players.rows[0]['created_at']+=timedelta(seconds=1);await a.capture()
        result=a.render_hourly(1,a.snapshots.rows,self.at)
        self.assertNotIn('تغییر نسبت به نمونهٔ ساعتی قبل',result)
    async def test_old_24hour_window_is_anchored_to_real_minutes_not_rounded_hour(self):
        await a.capture();sample=copy.deepcopy(a.snapshots.rows[0]);sample['captured_at']=self.at-timedelta(hours=23,minutes=59)
        result=a.render_hourly(1,[sample],self.at)
        self.assertEqual(result.count('<span class="missing">ثبت نشده</span>'),23)

if __name__=='__main__':unittest.main()
