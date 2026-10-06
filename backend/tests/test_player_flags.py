import unittest,base64,io
from PIL import Image
from portrait_thumbnails import flag_thumbnail
class FlagTests(unittest.TestCase):
 def test_full_flag_preserves_aspect_and_alpha(self):
  source=Image.new('RGBA',(200,400),(255,0,0,0));source.putpixel((100,200),(255,255,0,255));out=io.BytesIO();source.save(out,format='PNG');value='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode();result=flag_thumbnail(value)
  image=Image.open(io.BytesIO(base64.b64decode(result.split(',')[1])))
  self.assertEqual(image.size,(48,96));self.assertEqual(image.getpixel((0,0))[3],0);self.assertEqual(result,flag_thumbnail(value))
 def test_missing_and_invalid_flags(self):
  for value in (None,'','data:image/png;base64,broken'):
   self.assertIsNone(flag_thumbnail(value))
if __name__=='__main__':unittest.main()
