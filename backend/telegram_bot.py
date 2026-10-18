"""Web compatibility adapter; no external Telegram calls."""
WEBHOOK_SECRET = ''
async def push(chat_id,text,reply_markup=None,parse_mode=None):
    from web_notifications import persist_notice
    await persist_notice(chat_id,text,parse_mode=parse_mode)
async def push_photo(chat_id,image,caption,parse_mode=None):
    from web_notifications import persist_notice
    await persist_notice(chat_id,caption,image,parse_mode)
async def register_webhook(): return None
async def get_chat_profile(chat_id):
    from db import db
    row=await db.web_accounts.find_one({'uid':chat_id})
    return {'username':row['username']} if row else None
async def send_report_document(chat_id,filename,text):
    from fastapi import HTTPException
    raise HTTPException(400,'گزارش را با گزینهٔ دریافت فایل از پنل دانلود کنید')
