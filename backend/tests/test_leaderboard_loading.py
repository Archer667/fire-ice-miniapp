import unittest,base64,io
from unittest.mock import patch, AsyncMock
from PIL import Image
from portrait_thumbnails import thumbnail
from routers import leaderboard as lb

class LeaderboardTests(unittest.IsolatedAsyncioTestCase):
 async def test_pages_keep_ranks_and_last_page(self):
  rows=[{'player':{'tg_id':i,'name':str(i),'castle':'A','region':'north'},'score':100-i,'rank_label':None} for i in range(61)]
  with patch.object(lb,'scored_players',AsyncMock(return_value=rows)),patch.object(lb,'with_dead_players',AsyncMock(side_effect=lambda r:r)),patch.object(lb,'_without_admins',AsyncMock(side_effect=lambda r:r)):
   first=await lb.leaderboard({'id':0},page=1);second=await lb.leaderboard({'id':0},page=2);last=await lb.leaderboard({'id':0},page=999)
   self.assertEqual((len(first['items']),first['pages']),(25,3))
   self.assertEqual(second['items'][0]['rank'],26)
   self.assertEqual((last['page'],len(last['items']),last['items'][-1]['rank']),(3,11,61))
 def test_thumbnail_small_valid_and_invalid_safe(self):
  image=Image.new('RGB',(1000,1000),'red');buf=io.BytesIO();image.save(buf,format='PNG')
  value='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
  result=thumbnail(value);self.assertLess(len(result),5000)
  with Image.open(io.BytesIO(base64.b64decode(result.split(',')[1]))) as im:self.assertLessEqual(max(im.size),96)
  self.assertIsNone(thumbnail('data:image/png;base64,broken'))
