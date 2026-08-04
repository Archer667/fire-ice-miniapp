# راهنمای دولوپر — نغمهٔ آتش و یخ

این راهنما برایِ کسیه که می‌خواد رویِ این پروژه کار کنه ولی مدت‌هاست کد نزده. سعی کردم همه‌چیز
رو با مثالِ واقعی از خودِ کد توضیح بدم، نه فقط تئوری. اگه یک بخش گنگ بود، دنبالِ مسیرِ فایلی که
کنارش نوشتم برو و خودِ کد رو ببین — بهترین معلم همینه.

## فهرست
1. [ساختارِ کلی](#۱-ساختارِ-کلی)
2. [الگویِ روترهایِ بک‌اند](#۲-الگویِ-روترهایِ-بک‌اند)
3. [قانونِ شمارهٔ یک: mock تو api.js](#۳-قانونِ-شمارهٔ-یک-mock-تو-apijs)
4. [ساختارِ صفحاتِ فرانت‌اند](#۴-ساختارِ-صفحاتِ-فرانت‌اند)
5. [چطور یک ساختمان یا یگانِ جدید اضافه کنم](#۵-چطور-یک-ساختمان-یا-یگانِ-جدید-اضافه-کنم)
6. [چطور یک عددِ تعادلی رو عوض کنم](#۶-چطور-یک-عددِ-تعادلی-رو-عوض-کنم)
7. [احراز هویت](#۷-احراز-هویت)
8. [اجرایِ محلی (local dev)](#۸-اجرایِ-محلی-local-dev)
9. [تست‌نویسی — یا نبودش](#۹-تست‌نویسی--یا-نبودش)
10. [مرورِ گیت و شیوهٔ کامیت](#۱۰-مرورِ-گیت-و-شیوهٔ-کامیت)
11. [نکته‌هایی که از کامنت‌هایِ خودِ کد یاد می‌گیری](#۱۱-نکته‌هایی-که-از-کامنت‌هایِ-خودِ-کد-یاد-می‌گیری)
12. [معماریِ چندقلعه‌ای — رایج‌ترین منبعِ باگ](#۱۲-معماریِ-چندقلعه‌ای--رایج‌ترین-منبعِ-باگ)

---

## ۱. ساختارِ کلی

```
fire-ice-miniapp/
├── backend/     FastAPI (پایتون) + MongoDB (از طریقِ motor) — کلِ منطقِ بازی
└── frontend/    React 18 + Vite — رابطِ Telegram Mini App
```
هیچ `CLAUDE.md` یا مستندِ دیگه‌ای تو ریپو نبود قبل از این چهار فایل — پس هرچی این‌جا نوشتم رو
جدی بگیر، جایِ دیگه‌ای تکرار نشده.

### فایل‌هایِ اصلیِ `backend/`
| فایل | کارش چیه |
|---|---|
| `main.py` | اپِ FastAPI، میدل‌ورِ CORS، هندلرِ خطایِ سراسری، ثبتِ همهٔ روترها، ساختِ ایندکس‌هایِ Mongo، و دو حلقهٔ پس‌زمینه (هر ۳۰ ثانیه و هر ۵ دقیقه) |
| `config.py` | همه‌چیزی که از env خونده می‌شه (`BOT_TOKEN`, `MONGODB_URI`, `ADMIN_IDS`...) به‌علاوهٔ ثابت‌هایِ اقتصادیِ بازی (`STARTING_RESOURCES`, `DAILY_PRODUCTION`, `RESOURCE_CAPS`...) |
| `db.py` | یک `AsyncIOMotorClient` می‌سازه و ۲۰ تا هندلِ کالکشن (`players`, `campaigns`, ...) صادر می‌کنه — هیچ ORM یا اسکیمایی در کار نیست، همه‌چیز dict خامه |
| `auth.py` | تابعِ `get_user` (وابستگیِ FastAPI) برایِ احرازِ هویتِ تلگرام، به‌علاوهٔ سه سطحِ ادمین |
| `game.py` | منطقِ مشترکِ بازی: `now()`, تولیدِ lazy (`apply_production`), سقفِ منابع (`effective_caps`), `can_afford`/`pay`, و — مهم‌ترینش — کمک‌تابع‌هایِ چندقلعه‌ای (`owned_castles` و بقیه، بخشِ ۱۲ رو ببین) |
| `game_data.py` | دیتایِ ثابتِ ساختاریافته: مناطق، قلعه‌ها، یگان‌ها، ساختمان‌ها، انواعِ پیمان، فرمولِ هزینه/زمانِ سطح، گرافِ سفر |
| `ranks.py` | فرمولِ امتیازِ ترکیبی + سلسله‌مراتبِ سیاسی + خراج + حقوق |
| `telegram_bot.py` | ارسالِ پیامِ واقعیِ تلگرام + ثبتِ webhook |

### فایل‌هایِ اصلیِ `frontend/src/`
| فایل | کارش چیه |
|---|---|
| `App.jsx` | کامپوننتِ ریشه — یک‌بار `api.me()` صدا می‌زنه، بعد بینِ `Onboarding`/`Pending`/صفحه‌ها سوییچ می‌کنه |
| `store.jsx` | تنها استیتِ سراسری: `me`, `toast`, `unread` — از طریقِ `useGame()` |
| `api.js` (**۱۶۶۴ خط**) | هم کلاینتِ API واقعی، هم یک شبیه‌سازِ کاملِ بک‌اند تو مرورگر. **مهم‌ترین فایلِ کل ریپو** — بخشِ ۳ رو حتماً بخون |
| `gamedata.js` | یک آینهٔ دستی‌نگهداری‌شده از `backend/game_data.py` + بخشِ عددیِ `config.py`، برایِ mock و نمایشِ UI |
| `telegram.js` | یک wrapper سبک رویِ `window.Telegram.WebApp` |
| `components/` | `Header`, `NavBar`, `SideMenu`, `Toast`, `Icons.jsx` (۴۲ آیکنِ SVG)، `WesterosMap`, `ZoomPanMap`, `CastlePicker`, `PlayerPicker` |
| `pages/` | ۱۳ کامپوننتِ صفحه |

---

## ۲. الگویِ روترهایِ بک‌اند

هر فایلِ تو `backend/routers/` همین هفت‌بخشیِ ثابت رو دنبال می‌کنه:

```python
# ۱) importهای استاندارد/شخص‌ثالث
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# ۲) importهایِ خودِ پروژه
from auth import get_user
from db import players, rumors
from game import now, apply_production, can_afford, pay
from config import RUMOR_GOLD_COST
from routers.ravens import send_system_message

# ۳) خودِ روتر
router = APIRouter(prefix="/api/rumors", tags=["rumors"])

# ۴) ثابت‌هایِ محلیِ همین قابلیت
RUMOR_COOLDOWN_HOURS = 6

# ۵) یک BaseModel به‌ازایِ هر POST body
class RumorBody(BaseModel):
    target_tg_id: int
    text: str

# ۶) خودِ endpointها
@router.post("/send")
async def send_rumor(body: RumorBody, user: dict = Depends(get_user)):
    ...
    raise HTTPException(400, "پیامِ خطا به فارسی، دقیقاً همونی که کاربر می‌بینه")
    ...

# ۷) کمک‌تابع‌هایِ خصوصی، پیشوندِ _
def _rumor_brief(r, user_id):
    """سندِ Mongo رو به شکلِ JSON‌ایی که فرانت‌اند انتظار داره تبدیل می‌کنه"""
    ...
```

دسترسیِ دیتابیس همیشه مستقیم رویِ کالکشن‌هایِ `db.py`ست — نه لایهٔ ریپازیتوری، نه ORM:
```python
p = await players.find_one({"tg_id": user["id"]})
await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})
async for x in campaigns.find({"tg_id": user["id"], "active": True}):
    ...
```

**ترتیبِ استانداردِ تغییرِ یک بازیکن** (این الگو رو همه‌جا می‌بینی):
```python
p = await players.find_one({"tg_id": user["id"]})
if not p: raise HTTPException(403, "اول ثبت‌نام کن")
p = resolve_building_upgrades(p)   # اول ارتقاهایِ تمام‌شده نهایی می‌شن
p = apply_production(p)            # بعد تولیدِ lazy حساب می‌شه
...چک‌ها...
pay(p["resources"], cost)
await players.update_one({"tg_id": user["id"]},
    {"$set": {"resources": p["resources"], "last_tick": p["last_tick"]}})
```
**نکتهٔ حیاتی**: هر جا `apply_production` صدا می‌زنی، حتماً `last_tick` رو هم تو همون `$set`
برگردون — وگرنه دفعهٔ بعد همون بازهٔ زمانی دوباره حساب می‌شه (تولیدِ دوبل).

**ثبتِ روترِ جدید** فقط دو خط تو `main.py` می‌خواد: اضافه‌کردن به importِ `from routers import (...)`
و اضافه‌کردنِ `app.include_router(x.router)`.

بهترین نمونه‌هایِ کوچیک برایِ کپی‌کردنِ الگو: `backend/routers/rumors.py` و
`backend/routers/tribute.py` (که این یکی مثالِ `DuplicateKeyError` رویِ ایندکسِ یکتایِ partial
هم داره).

---

## ۳. قانونِ شمارهٔ یک: mock تو api.js

**هر تغییرِ منطقِ بک‌اند باید تو `frontend/src/api.js` هم آینه بشه.** این تنها قاعده‌ایه که اگه
یادت بره، به‌سرعت خرابی می‌سازه — پس بذار دقیق توضیح بدم.

### پرچمِ MOCK از کجا میاد؟
```js
const BASE = import.meta.env.VITE_API_URL || '';
export const MOCK = !BASE;
```
یعنی: **اگه `VITE_API_URL` خالی/ست‌نشده باشه، `MOCK` برابرِ `true`ست.** تو این حالت هیچ بک‌اند و
هیچ MongoDBای درکار نیست — کلِ بازی تو حافظهٔ مرورگر شبیه‌سازی می‌شه.

### ساختارِ سه‌بخشیِ api.js
۱. **استیتِ mock** (خطِ ~۲۳ تا ~۳۰۲) — آرایه‌ها/دیکشنری‌هایِ ماژول‌لِولِ قابل‌تغییر که جایِ
   کالکشن‌هایِ MongoDB رو می‌گیرن: `mockMe`, `mockCampaigns`, `mockAlliances`, `MOCK_PLAYERS`
   (یک NPCی ثابت)، به‌علاوهٔ کمک‌تابع‌هایی که خودِ `game.py` رو تقلید می‌کنن
   (`mockApplyProduction`, `mockCanAfford`, `mockOwnedCastles`, ...).
۲. **`const M = { ... }`** (خطِ ~۳۰۳ تا ~۱۶۰۹) — به‌ازایِ هر endpointِ بک‌اند، یک پیاده‌سازیِ
   sync که **همون قواعد، همون ترتیبِ چک، همون پیام‌هایِ فارسی**یِ روترِ پایتونی رو تکرار می‌کنه.
۳. **`export const api = { ... }`** (خطِ ~۱۵۰۶ تا آخر) — هر تابعِ صادرشده یک ternary یک‌خطیه.

### یک مثالِ کاملِ سه‌لایه — شایعه
```js
// لایهٔ سوم — export const api
sendRumor: (targetTgId, text) => MOCK ? Promise.resolve(M.sendRumor(targetTgId, text))
  : req('/api/rumors/send', { method: 'POST', body: JSON.stringify({ target_tg_id: targetTgId, text }) }),

// لایهٔ دوم — const M
sendRumor: (targetTgId, text) => {
  if (targetTgId === 1) throw new Error('نمی‌توانی علیه خودت شایعه بسازی');
  const t = text.trim();
  if (t.length < 10) throw new Error('متن شایعه خیلی کوتاه است');
  ...
  if (!mockCanAfford({ gold: RUMOR_GOLD_COST })) throw new Error('طلای کافی برای پخش این شایعه نداری');
  mockPay({ gold: RUMOR_GOLD_COST });
  target.popularity = Math.max(0, (target.popularity ?? 50) - RUMOR_POPULARITY_DAMAGE);
  mockRumors.unshift({ id: String(mockRumorSeq++), ... });
  return { ok: true };
},
```
با `backend/routers/rumors.py` مقایسه کن — همون چک‌ها، همون ترتیب، همون متنِ فارسی.

### پیامدهایی که باید تو ذهنت باشه
- **پیامِ خطا هم دوبار نوشته می‌شه.** اگه تو بک‌اند یک پیامِ فارسی رو عوض کنی ولی تو `M.*` عوضش
  نکنی، تستِ محلی‌ات (که تو MOCK اجرا می‌شه) پیامِ قدیمی رو نشون می‌ده.
- **ثابت‌ها هم تو `gamedata.js` دوبار تعریف می‌شن.** خودِ فایل تو کامنتِ بالاش می‌گه:
  `آینه‌ی DAILY_PRODUCTION/RESOURCE_CAPS در backend/config.py`.
- **قاعده**: یک endpointِ جدید یعنی حداقل ۳ تغییر — روترِ پایتون، یک `M.x`، و ternaryِ `api.x`.
  این الگو تو خودِ تاریخچهٔ گیت هم دیده می‌شه (هر کامیتِ بک‌اندی معمولاً `api.js` رو هم تغییر داده).
- `M.adminResetGame` همهٔ آرایه‌های mock رو ریست می‌کنه — اگه استیتِ mockِ جدیدی اضافه کردی،
  اون‌جا هم پاکش کن.

---

## ۴. ساختارِ صفحاتِ فرانت‌اند

### الگویِ tab/PAGES
هیچ روتر‌لایبرری‌ای در کار نیست. ناوبری فقط یک عددِ صحیحه: `const [tab, setTab] = useState(0)`
تو `App.jsx`، و `const Page = PAGES[tab]`. `NavBar.jsx` خودش این کامنت رو داره:
```jsx
// هر آیتم index خودش رو جدا نگه می‌داره (نه ترتیب آرایه) چون همین index مستقیم
// به PAGES توی App.jsx اشاره می‌کنه — هر صفحهٔ جدید همین‌جا و اونجا اضافه شود
```
`NAV_ITEMS` = ۵ تبِ نوارِ پایین. `EXTRA_PAGES` = بقیه، فقط از منویِ کشویی قابل‌دسترس.

**برایِ اضافه‌کردنِ یک صفحهٔ جدید**: `pages/X.jsx` رو بساز، تو `App.jsx` importش کن و به `PAGES`
اضافه کن، و یک ورودیِ `{index, Icon, label}` به `NAV_ITEMS` یا `EXTRA_PAGES` اضافه کن. همیشه
**آخرش** اضافه کن — وسط اضافه‌کردن یعنی همه‌چیز شماره‌گذاریِ مجدد می‌خواد.

### چطور یک صفحه دیتاشو می‌گیره
```jsx
const { me, setMe, toast } = useGame();
const [data, setData] = useState(null);
const load = (c) => api.buildings(c).then(d => { setData(d); }).catch(e => toast(e.message));
useEffect(() => { load(castle); }, []);
...
if (!data) return <div className="loading">در حال بارگذاری...</div>;
```
الگویِ mutation:
```jsx
const act = async (row) => {
  setBusyId(row.id);
  try {
    const res = await api.buildBuilding(row.id, castle);
    setMe({ ...me, resources: {...} });   // آپدیتِ خوش‌بینانه، نه رفچ کامل
    toast('پیام موفقیت');
    await load(castle);
  } catch (e) { toast(e.message); }
  setBusyId(null);
};
```
قواعدِ تکرارشونده: `useEffect(..., [])` رویِ mount، `null` یعنی «در حالِ بارگذاری»، هر mutation
تویِ try/catch با `toast(e.message)`، یک `busy`/`busyId` که دکمه رو غیرفعال می‌کنه، `haptic()`
رویِ هر اکشن، و **همیشه** `.toLocaleString('fa-IR')` رویِ عددها برایِ رقمِ فارسی.

### استیتِ سراسری (`store.jsx`) در برابرِ استیتِ محلی
`store.jsx` فقط چهار چیز داره: `me`/`setMe`، `toast(msg)`، `unread`/`refreshUnread`. **همهٔ
بقیه، استیتِ محلیِ همون صفحه‌ست** — نه cache، نه لایهٔ fetchِ مشترک. هر صفحه بعدِ mutation دوباره
دیتاشو می‌گیره.

---

## ۵. چطور یک ساختمان یا یگانِ جدید اضافه کنم

### ساختمانِ جدید
۱. تو `backend/game_data.py`، یک کلید به دیکشنریِ `BUILDINGS` اضافه کن: `name`, `cost`, `hours`,
   `type` (`economy`/`barracks`/`armory`/`defense`)، اختیاری `produces`، `cap_bonus`،
   `requires_port: True`، `unit` (فقط برایِ پادگان/کارگاه).
۲. **همون ورودیِ دقیق** رو تو `frontend/src/gamedata.js`ی `BUILDINGS_STATIC` هم اضافه کن —
   کلیدها باید کاملاً یکی باشن.
۳. `frontend/src/api.js` معمولاً نیازی به تغییر نداره — `M.buildings` خودش رویِ
   `BUILDINGS_STATIC` حلقه می‌زنه.
۴. اختیاری: تو `frontend/src/pages/Buildings.jsx`ی `BUILDING_ICON` یک آیکن براش بذار — وگرنه
   یک آیکنِ پیش‌فرض می‌گیره (بدون خطا، فقط کم‌جذاب‌تر).
۵. اگه یک منبعِ کاملاً جدید اختراع کردی (نه از این ۱۲ تایِ فعلی)، باید تو `config.py`ی
   `RESOURCE_CAPS`/`STARTING_RESOURCES`، تو `gamedata.js`ی `RESOURCE_CAPS`، و تو نقشه‌هایِ
   نمایشیِ `Dashboard.jsx`/`Buildings.jsx` هم اضافه‌اش کنی.
۶. `backend/routers/buildings.py` و `ranks.py` (امتیازدهی) نیازی به تغییر ندارن — خودکار از
   رویِ `type` عمل می‌کنن.

### یگانِ جدید
۱. `backend/game_data.py`ی `COMMON_TROOPS`/`NAVAL_TROOPS`.
۲. یک پادگان/کارگاهِ متناظر تو `BUILDINGS` با `"unit": "<troop_id>"` — کلیدِ کارگاه باید
   `armory_<پسوند>` باشه تا `TROOP_WEAPON_KEY` خودکار درستش کنه.
۳. `config.py`ی `STARTING_RESOURCES`/`RESOURCE_CAPS` — کلیدِ `weapon_<پسوند>` جدید.
۴. مثلِ همیشه، همهٔ این‌ها رو تو `gamedata.js` هم آینه کن.
۵. `WEAPON_NAMES` (هم بک‌اند هم فرانت‌اند) — پیامِ «تسلیحاتِ کافی نداری» از این‌جا میاد.

---

## ۶. چطور یک عددِ تعادلی رو عوض کنم

سه خونهٔ متفاوت، به‌ترتیبِ اولویتِ جستجو:

**الف) `backend/config.py`** — ثابت‌هایِ اسکالرِ مسطح (تولیدِ پایه، سقف‌ها، هزینهٔ جاسوسی/شایعه/
ضیافت، وزن‌هایِ امتیاز). مثال:
```python
DAILY_PRODUCTION = {"gold": 200, "food": 300, ...}
RUMOR_GOLD_COST = 100
```
همیشه تو `gamedata.js` هم آینه کن.

**ب) `backend/game_data.py`** — دیتایِ ساختاریافتهٔ هر موجودیت (هزینه/بازدهیِ هر ساختمان، توان/
هزینهٔ هر یگان، فرمولِ سطح‌بندی `LEVEL_COST_STEP`/`LEVEL_HOURS_STEP`). همیشه تو `gamedata.js`
هم آینه کن.

**پ) هاردکد داخلِ یک روتر** — استثنا، ولی واقعیه:
- `war.py`ی `OP_TYPES`، `REPORT_VISIBLE_HOURS`
- `tribute.py`ی `TRIBUTE_WINDOW_HOURS`
- `market.py`ی فرمولِ افزایشِ قیمت (`1 + 0.015 * qty`)

**راهِ بدونِ تغییرِ کد**: تبِ «تعادل بازی» تو پنلِ ادمین می‌تونه `produces`/`cap_bonus` هر ساختمون
رو زنده و برایِ همهٔ بازیکن‌ها عوض کنه (تو `game_settings` ذخیره و موقعِ استارت لود می‌شه). برایِ
همین، وقتی می‌خوای بازدهیِ یک ساختمون رو تو کدِ خودت بخونی، **همیشه** از تابعِ
`building_produces(bid)`/`building_cap_bonus(bid)` استفاده کن، نه مستقیم
`BUILDINGS[bid]["produces"]` — وگرنه override هایِ ادمین رو نادیده می‌گیری.

---

## ۷. احراز هویت

`backend/auth.py` (۶۹ خط، کاملاً همین‌جا):

**مسیرِ واقعیِ تلگرام**: فرانت‌اند `Authorization: tma <initData>` می‌فرسته. سرور با HMAC-SHA256
(کلیدش از `BOT_TOKEN` مشتق می‌شه) صحتش رو چک می‌کنه و اگه از ۲۴ ساعت قدیمی‌تر باشه رد می‌کنه.

**مسیرِ توسعه**:
```python
if DEV_MODE and x_dev_user:
    uid, _, name = x_dev_user.partition(":")
    return {"id": int(uid), "first_name": name or "Dev"}
```
یعنی هم `DEV_MODE=true` تو env بک‌اند، هم هدرِ `X-Dev-User: <tg_id>:<name>` لازمه. خودِ
`api.js` این هدر رو زیرِ `import.meta.env.DEV` خودکار می‌فرسته، پس زیرِ `npm run dev` این کار
خودش انجام می‌شه.

**سه سطحِ ادمین** — همه از `get_admin_role(user)`:
| تابع | قبول می‌کنه | برایِ چی |
|---|---|---|
| `get_admin` | `full` یا `limited` | بیشترِ `/api/admin` |
| `get_full_admin` | فقط `full` | مدیریتِ ادمین‌ها، بازار، تعادل |
| `get_owner` | فقط `user["id"] == OWNER_ID` | ری‌استارتِ کامل |

`admin.py` این‌ها رو تو dependencyهایِ محلی می‌پیچه تا endpointها کوتاه بمونن:
```python
async def admin_user(user: dict = Depends(get_user)): return await get_admin(user)
@router.get("/campaigns")
async def list_campaigns(user: dict = Depends(admin_user)): ...
```

---

## ۸. اجرایِ محلی (local dev)

### حالتِ A — فقط فرانت‌اند، بدونِ بک‌اند، بدونِ MongoDB (سریع‌ترین)
```bash
cd frontend
npm install
npm run dev              # پیش‌فرض پورتِ ۳۰۰۰ (vite.config.js)
# یا: npm run dev -- --port 5219
```
چون `VITE_API_URL` ست نشده، `MOCK = true` می‌شه و کلِ بازی تو حافظهٔ مرورگر اجرا می‌شه. با هر
رفرشِ صفحه استیت پاک می‌شه.

### حالتِ B — واقعی، سرتاسری (فرانت‌اند + بک‌اند + MongoDB)
```bash
# ترمینال ۱
cd backend
pip install -r requirements.txt
# یک backend/.env بساز:
#   MONGODB_URI=mongodb://localhost:27017
#   DEV_MODE=true
#   ADMIN_IDS=1
#   OWNER_ID=1
#   CORS_ORIGINS=http://localhost:3000
uvicorn main:app --reload
curl http://127.0.0.1:8000/api/health   # باید {"ok":true} بده

# ترمینال ۲
cd frontend
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```
MongoDB باید از قبل روی سیستم بالا باشه (لوکال یا Atlas). `BOT_TOKEN` می‌تونه خالی بمونه —
فقط فرستادنِ پیامِ واقعیِ تلگرام و `/start` غیرفعال می‌مونن.

موقعِ استارت، بک‌اند خودکار ایندکس‌ها رو می‌سازه، override هایِ تعادل رو لود می‌کنه، و دو حلقهٔ
پس‌زمینه (هر ۳۰ ثانیه: رسیدنِ لشکر/کاروان، انقضایِ خراج، حقوق؛ هر ۵ دقیقه: نوسانِ قیمتِ بازار)
راه می‌افته.

---

## ۹. تست‌نویسی — یا نبودش

**هیچ تستِ خودکاری تو این پروژه نیست** — نه pytest، نه vitest/jest، نه هیچ فایلِ
`*test*`/`*spec*`ای، نه CI. گردش‌کارِ واقعی، تستِ دستیِ مرورگری‌ست:

۱. فرانت‌اند رو تو حالتِ MOCK اجرا کن (بخشِ ۸، حالتِ A) و رویِ صفحاتِ تحت‌تأثیر کلیک کن.
۲. اگه تغییرت چیزی مثلِ persistence، چندنفره‌بودن، یا حلقه‌هایِ پس‌زمینه رو لمس می‌کنه، حالتِ B
   (بک‌اندِ واقعی + MongoDB) رو هم امتحان کن.

**برایِ همینه که وفاداریِ mock تو `api.js` این‌قدر مهمه — mock همون fixtureِ تسته.** اگه یک
باگ رو تو بک‌اند فیکس کنی ولی تو mock فیکس نکنی، تستِ محلی‌ات همچنان باگ رو نشون نمی‌ده و
گمراه‌کننده می‌شه.

یک محدودیتِ mock: تک‌بازیکنه (همیشه `tg_id: 1` و همیشه پادشاهی) — پس خراج و حقوقِ چندنفره فقط
رویِ بک‌اندِ واقعی با چند بازیکن قابل‌تسته.

---

## ۱۰. مرورِ گیت و شیوهٔ کامیت

شاخهٔ فعلی: `new-design`. کامیت‌ها همه فارسی، بدونِ پیشوندِ conventional-commits، بدونِ شمارهٔ
ایشو، توصیف‌کنندهٔ **اثرِ قابل‌دیدنِ بازیکن** نه خودِ تغییرِ کد:
```
رفعِ ریسِ دوبار-برگشتِ منابع در لغوِ لشکر و پاسخ به پیمان
کاروانِ تجاری حالا از/به هرکدوم از قلعه‌های دو طرف قابل‌فرستادنه
محاصره دیگه نمی‌تونه علیه هدف‌های بندری استفاده بشه
```
معمولاً یک کامیت هم‌زمان بک‌اند و `api.js`/صفحاتِ مرتبط رو تغییر می‌ده (چون قانونِ بخشِ ۳ همینو
می‌خواد). رفعِ باگ با «رفع باگ»/«رفعِ» شروع می‌شه؛ `+` برایِ به‌هم‌چسبوندنِ دو تغییرِ مرتبط.

---

## ۱۱. نکته‌هایی که از کامنت‌هایِ خودِ کد یاد می‌گیری

این‌ها کامنت‌هایی هستن که هرکدوم یک باگِ واقعی که قبلاً اتفاق افتاده رو مستند می‌کنن — پس درسِ
واقعی‌ان، نه فرضی:

1. **`main.py`** — قبلاً `players` هم اسمِ ماژولِ `routers.players` بود هم اسمِ کالکشنِ Mongo؛
   قاطی‌شون کردنِ این دو باعث شد `create_index` رویِ چیزِ اشتباه صدا زده بشه، بی‌سروصدا شکست
   بخوره (تو try/except بود)، و **هیچ‌وقت هیچ ایندکسِ یکتایی واقعاً ساخته نشه**. برایِ همین الان
   کالکشن `players as players_col` importِ می‌شه.
2. **`main.py`** — Mongo تو ایندکسِ یکتا، `null` رو هم مثلِ یک مقدارِ عادی می‌بینه. برایِ همین
   ایندکسِ یکتایِ `castle` باید `partialFilterExpression` داشته باشه، وگرنه به‌محضِ دومین
   بازیکنِ بی‌خاندان، خطایِ E11000 می‌خوری.
3. **`buildings.py`/`players.py`** — همیشه `resolve_building_upgrades` رو **قبل از**
   `apply_production` صدا بزن، وگرنه تولیدِ فاصلهٔ زمانیِ سپری‌شده با سطحِ قدیمی (پیش‌ازارتقا)
   حساب می‌شه.
4. **`game.py`** — منابع عمداً اعشاری نگه داشته می‌شن، فقط موقعِ نمایش رند می‌شن — وگرنه تولیدِ
   کم‌مقدار تو چک‌هایِ پیاپی صفر رند می‌شه و گم می‌شه. **هیچ‌وقت قبلِ نوشتن تو Mongo رند نکن.**
5. **`game.py`** — همیشه از `add_resources()` استفاده کن، نه `$inc` خام — چون `$inc` سقف رو
   کاملاً نادیده می‌گیره.
6. **`game.py`** — همیشه از `now()`ی خودِ پروژه استفاده کن (naive UTC)، نه
   `datetime.now(timezone.utc)` — چون تفریق با مقدارِ خونده‌شده از Mongo (که naive‌ست) خطایِ
   TypeError می‌ده.
7. **`market.py`** — الگویِ آپدیتِ اتمیکِ مشروط، به‌جایِ خواندن-سپس-نوشتن:
   ```python
   result = await market_listings.update_one(
       {"_id": listing["_id"], "qty": {"$gte": body.qty}}, {...})
   if result.matched_count == 0:
       raise HTTPException(409, "موجودیِ بازار همین الان تغییر کرد — دوباره امتحان کن")
   ```
   همین الگو رو هرجا دو کاربر می‌تونن هم‌زمان یک منبعِ محدود رو تغییر بدن، به کار ببر (لغوِ لشکر،
   پذیرفتنِ پیمان و امثالش هم به همین دلیل به این الگو نیاز پیدا کردن).
8. **`game.py`** — `buildings[id]` معمولاً `{"level","upgrade_to","ready_at"}`ست، ولی
   نسخه‌هایِ خیلی قدیمیِ بازی فقط `True/False` ذخیره می‌کردن. هیچ‌وقت مستقیم `buildings[bid]["level"]`
   نخون — همیشه از `normalize_building_state()`/`building_levels_for()` رد شو.
9. **`config.py`** — چرا شراب با ۳۰ شروع می‌شه و تسلیحات با ۲۰: چون تولیدِ پایهٔ شراب صفره و
   ارزون‌ترین پیمان ۳۰ شراب می‌خواد؛ بدونِ این استوکِ آغازین، بازیکنِ تازه‌کار تا ساختنِ می‌کده
   اصلاً نمی‌تونست پیمان ببنده.
10. **`api.js`** — mock باید حتماً **stateful** باشه، نه یک fixtureِ ثابت — قبلاً inbox یک
    آرایهٔ ثابتِ نمایشی بود که هیچ‌وقت با اکشن‌های واقعی به‌روز نمی‌شد، و نتیجهٔ جاسوسی/رول تو
    حالتِ تست اصلاً دیده نمی‌شد.

---

## ۱۲. معماریِ چندقلعه‌ای — رایج‌ترین منبعِ باگ

### مدلِ دیتا
هر سندِ بازیکن دو فیلدِ قلعه داره:
- `player["castle"]` — یک رشته: **قلعهٔ خانگی**.
- `player["castle_buildings"]` — دیکشنریِ `{اسمِ_قلعه: {ساختمان‌ها}}`، یعنی هر قلعهٔ **اضافه‌ای**
  که تو جنگ گرفته یا ادمین بهش داده، هرکدوم با ساختمان‌هایِ کاملاً مستقل.

### سه کمک‌تابعِ `game.py`
```python
def owned_castles(player):
    """قلعهٔ اصلی + هر قلعهٔ اضافه‌ای"""
def castle_building_state(player, castle):
    """قلعهٔ اصلی از buildings، بقیه از castle_buildings[castle]"""
def all_building_levels(player):
    """سطحِ هر ساختمان جمع‌شده رویِ همهٔ قلعه‌هاش — چون خزانه ملیه، نه قلعه‌ای"""
```

### قاعده‌ی اقتصادی
**ساختمان‌ها قلعه‌به‌قلعه‌ان؛ منابع ملی‌ان.** هر قلعه ساختمان‌هایِ خودش رو داره، ولی فقط یک
`player["resources"]` وجود داره. تولید/سقف/امتیاز همیشه **جمعِ** همهٔ قلعه‌هاست
(`all_building_levels`). ساخت‌وساز همیشه رویِ **یک قلعهٔ مشخص** انجام می‌شه
(`castle_building_state`).

### باگِ رایج
هر جا کدی `player["castle"]` رو می‌خونه به‌قصدِ «هر قلعه‌ای که این بازیکن کنترل می‌کنه»، برایِ
لردهایِ دوقلعه‌ای اشتباهه. یک کامیتِ کاملِ این ریپو (`رفعِ باگ‌هایِ تقسیم‌بندیِ لردِ دوقلعه‌ای`)
دقیقاً همینو فیکس کرد و ۸ فایل رو لمس کرد — یک باگِ مفهومی، همه‌جا پخش.

### اصطلاحاتِ درست، بسته‌به‌موقعیت
- **«این قلعه مالِ منه؟»** → `if castle not in owned_castles(p): raise HTTPException(403, ...)`
- **«این قلعه مالِ کیه؟»** →
  ```python
  async def owner_of_castle(castle):
      return await players.find_one({"$or": [
          {"castle": castle}, {f"castle_buildings.{castle}": {"$exists": True}},
      ]})
  ```
  یک `find_one({"castle": castle})ی` ساده، رایج‌ترین شکلِ همین باگه.
- **«چه قلعه‌هایی سرِ راهِ منن؟»** → `owned_castles(other)` رویِ هر بازیکنِ دیگه.
- **همیشه هر دو دیکشنری رو با هم ذخیره کن**: `{"buildings": p["buildings"], "castle_buildings": p.get("castle_buildings", {})}`.

### mock هم همینو آینه می‌کنه
`api.js`ی `mockOwnedCastles()`, `mockCastleBuildingState()`, `mockAllBuildingLevels()` دقیقاً
ترجمهٔ جاوااسکریپتیِ همین سه تابعن. اگه یک باگِ چندقلعه‌ای رو تو پایتون فیکس کردی، تقریباً مطمئن
باش همون باگ تو این کمک‌تابع‌هایِ mock هم هست.
