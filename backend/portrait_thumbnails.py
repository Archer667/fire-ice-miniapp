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


_flag_cache = OrderedDict()
def flag_thumbnail(value):
    """Preserve the full approved flag and transparency in compact list images."""
    if not value or not value.startswith('data:image/'):
        return None
    key = hashlib.sha256(value.encode()).hexdigest()
    if key in _flag_cache:
        _flag_cache.move_to_end(key)
        return _flag_cache[key]
    try:
        raw = base64.b64decode(value.split(',', 1)[1], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 20000000:
                return None
            image = ImageOps.exif_transpose(image).convert('RGBA')
            image.thumbnail((96, 96), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, format='WEBP', quality=85)
        result = 'data:image/webp;base64,' + base64.b64encode(out.getvalue()).decode()
    except Exception:
        return None
    _flag_cache[key] = result
    while len(_flag_cache) > 256:
        _flag_cache.popitem(last=False)
    return result
