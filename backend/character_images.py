import base64,io,warnings
from PIL import Image
from fastapi import HTTPException

MAX_IMAGE_BYTES=256*1024
def decode_character_image(value):
    if value is None:return None
    formats={'data:image/png;base64,':'PNG','data:image/jpeg;base64,':'JPEG','data:image/webp;base64,':'WEBP'}
    prefix=next((p for p in formats if value.startswith(p)),None)
    if not prefix or len(value)>MAX_IMAGE_BYTES*4//3+100:
        raise HTTPException(422,'عکس و پرچم باید PNG، JPG یا WebP و حداکثر ۲۵۶ کیلوبایت باشند')
    try:
        raw=base64.b64decode(value[len(prefix):],validate=True)
        if not raw or len(raw)>MAX_IMAGE_BYTES:raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!=formats[prefix] or max(image.size)>4096 or getattr(image,'n_frames',1)!=1:raise ValueError()
                image.verify()
    except Exception:raise HTTPException(422,'فایل تصویر معتبر نیست؛ تصویر ثابت تا ۲۵۶ کیلوبایت و حداکثر ۴۰۹۶ پیکسل بفرست')
    return raw,prefix.split(':')[1].split(';')[0]

def map_flag_image(value):
    if not value:return None
    raw,_=decode_character_image(value)
    with Image.open(io.BytesIO(raw)) as image:
        image=image.convert('RGBA');image.thumbnail((512,512),Image.Resampling.LANCZOS)
        output=io.BytesIO();image.save(output,format='WEBP',quality=90,method=4)
    return 'data:image/webp;base64,'+base64.b64encode(output.getvalue()).decode()
