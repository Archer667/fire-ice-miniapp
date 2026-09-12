"""Small cached portraits for list responses; originals fetched on demand."""
import base64,hashlib,io
from collections import OrderedDict
from PIL import Image, ImageOps
_cache=OrderedDict()
def thumbnail(value):
    if not value or not value.startswith('data:image/'):
        return value
    key=hashlib.sha256(value.encode()).hexdigest()
    if key in _cache:
        _cache.move_to_end(key);return _cache[key]
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>20000000:return None
            im=ImageOps.exif_transpose(im)
            im.thumbnail((96,96))
            im=im.convert('RGB');out=io.BytesIO();im.save(out,format='JPEG',quality=65)
        result='data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
    except Exception:return None
    _cache[key]=result
    while len(_cache)>256:_cache.popitem(last=False)
    return result
