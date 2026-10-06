import unittest,io,base64
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from PIL import Image
from fastapi import HTTPException
from character_images import decode_character_image,map_flag_image,MAX_IMAGE_BYTES
from routers import character_profiles as cp

def png(size=(16,16)):
    out=io.BytesIO();Image.new('RGBA',size,(250,30,50,255)).save(out,format='PNG');return out.getvalue()
def data(raw):return 'data:image/png;base64,'+base64.b64encode(raw).decode()

class ImageTests(unittest.TestCase):
    def test_exact_byte_limit_and_over_limit(self):
        raw=png();limit=raw+b'\0'*(MAX_IMAGE_BYTES-len(raw))
        self.assertEqual(len(decode_character_image(data(limit))[0]),MAX_IMAGE_BYTES)
        with self.assertRaises(HTTPException):decode_character_image(data(limit+b'\0'))
    def test_invalid_and_oversized_images(self):
        for value in (data(b'not an image'),data(png((4097,1))),'data:image/svg+xml;base64,PHN2Zz4='):
            with self.subTest(value=value[:40]),self.assertRaises(HTTPException):decode_character_image(value)
    def test_map_flag_is_small_and_transparent(self):
        output=map_flag_image(data(png((800,400))));raw,_=decode_character_image(output)
        with Image.open(io.BytesIO(raw)) as image:self.assertEqual(image.size,(512,256))

class ApprovalTests(unittest.IsolatedAsyncioTestCase):
    def request(self):
        before={'name':'Old','backstory':'Old story','profile_image':None,'flag_image':None}
        p={'tg_id':1,**before,'created_at':'start'}
        r={'_id':1,'tg_id':1,'revision':2,'reviewer':9,'character_key':cp.character_key(p),'before':before,'proposed':{**before,'name':'New'}}
        return p,r
    async def test_approval_writes_only_reviewed_revision(self):
        p,r=self.request();store=SimpleNamespace(find_one=AsyncMock(return_value=p),update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        req=SimpleNamespace(update_one=AsyncMock())
        with patch.object(cp,'players',store),patch.object(cp,'requests',req):self.assertEqual(await cp.finish_review(r),'approved')
        self.assertEqual(store.update_one.call_args.args[1]['$set']['name'],'New')
        self.assertEqual(store.update_one.call_args.args[0]['name'],'Old')
    async def test_successor_cannot_inherit_pending_request(self):
        p,r=self.request();p['family_child_id']='heir'
        store=SimpleNamespace(find_one=AsyncMock(return_value=p),update_one=AsyncMock())
        with patch.object(cp,'players',store),patch.object(cp,'requests',SimpleNamespace(update_one=AsyncMock())):self.assertEqual(await cp.finish_review(r),'stale')
        store.update_one.assert_not_awaited()
    async def test_recovery_is_idempotent(self):
        p,r=self.request();p['approved_profile_request']='1:2'
        store=SimpleNamespace(find_one=AsyncMock(return_value=p),update_one=AsyncMock())
        with patch.object(cp,'players',store),patch.object(cp,'requests',SimpleNamespace(update_one=AsyncMock())):self.assertEqual(await cp.finish_review(r),'approved')
        store.update_one.assert_not_awaited()

if __name__=='__main__':unittest.main()
