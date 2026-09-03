const RESOURCES = {
  gold: 'طلا', food: 'غذا', men: 'جمعیت', iron: 'آهن', stone: 'سنگ', wood: 'چوب', wine: 'شراب',
  weapon_sword: 'شمشیر', weapon_spear: 'نیزه', weapon_archer: 'کمان', weapon_lcav: 'تجهیزات سوارهٔ سبک', weapon_hcav: 'تجهیزات سوارهٔ سنگین',
};
const PACTS = { trade: 'پیمان تجاری', non_aggression: 'پیمان عدم تجاوز', full_alliance: 'اتحاد کامل' };
const MEDALS = {
  blood_and_steel: 'خون و فولاد', peaceful_warrior: 'صلح‌طلب، ولی جنگ بلده', conqueror: 'فاتح',
  rich_father: 'پدر پولدار', oathbound: 'سوگنددار', eye_in_shadow: 'چشم در سایه', oath_loyal: 'وفادار به عهد',
};
const EVENTS = {
  general: 'عمومی', tweet: 'توییت', battle: 'نبرد', ambush: 'کمین', rebellion: 'شورش',
  diplomacy: 'دیپلماسی', building: 'ساختمان', trade: 'تجارت و کاروان', daily: 'جایزه روزانه',
  roleplay: 'رول', espionage: 'جاسوسی', event: 'رویداد',
};
const FEATURES = { war: 'جنگ و لشکرکشی', espionage: 'جاسوسی', tweets: 'توییت', market: 'بازار', caravans: 'کاروان', registration: 'ثبت‌نام' };

const SIMPLE_SECTIONS = [
  { key: 'tweets', title: 'توییت‌ها', help: 'هزینه، محدودیت و اثر مستقیم توییت و واکنش‌های بازیکنان.', fields: [
    ['gold_cost','هزینه انتشار','سکه'], ['popularity_damage','کاهش محبوبیت هدف','واحد'], ['cooldown_hours','کول‌داون برای یک هدف','ساعت'],
    ['text_min','حداقل طول متن','نویسه'], ['text_max','حداکثر طول متن','نویسه'], ['like_popularity','اثر هر لایک','محبوبیت'], ['dislike_popularity','اثر هر دیس‌لایک','محبوبیت'],
  ]},
  { key: 'tax', title: 'مالیات و محبوبیت', help: 'فرمول درآمد مالیاتی و محدوده‌هایی که خطر شورش را تعیین می‌کنند.', fields: [
    ['default_rate','مالیات پیش‌فرض','درصد'], ['income_population_factor','ضریب درآمد نسبت به جمعیت','ضریب',.1],
    ['income_min_multiplier','ضریب درآمد در محبوبیت صفر','ضریب',.05], ['income_max_multiplier','ضریب درآمد در محبوبیت صد','ضریب',.05],
    ['overage_start','آستانه مالیات سنگین','درصد'], ['overage_step','اندازه هر پله مالیات اضافه','درصد'], ['overage_popularity_penalty','جریمه هر پله','محبوبیت'],
    ['safe_popularity','مرز امن','محبوبیت'], ['high_risk_popularity','مرز خطر بالا','محبوبیت'], ['guaranteed_popularity','مرز شورش قطعی','محبوبیت'],
  ]},
  { key: 'war', title: 'جنگ و داوری', help: 'قواعد تشکیل نیرو، مهلت رول، نگهداری گزارش و لغو لشکر.', fields: [
    ['minimum_army_men','حداقل نفرات لشکر','نفر'], ['minimum_ambush_men','حداقل نفرات کمین','نفر'], ['roleplay_hours','مهلت ارسال رول جنگ','ساعت'],
    ['report_visible_hours','مدت نمایش گزارش','ساعت'], ['cancel_penalty_percent','جریمه لغو','درصد'], ['cancel_grace_minutes','مهلت لغو بدون جریمه','دقیقه'],
    ['spy_gold_cost','هزینه جاسوسی','سکه'], ['spy_men_cost','نفرات جاسوسی','نفر'],
  ]},
  { key: 'movement', title: 'حرکت لشکر', help: 'درصد ۱۰۰ یعنی سرعت و زمان استاندارد فعلی.', fields: [
    ['base_speed_percent','سرعت پایه','درصد'], ['route_time_percent','ضریب زمان تمام مسیرها','درصد'], ['equipment_slowdown_cap_percent','سقف کندی ادوات','درصد'],
    ['commander_power_bonus_percent','مزیت قدرت فرمانده','درصد'], ['commander_speed_bonus_percent','مزیت سرعت فرمانده','درصد'],
  ]},
  { key: 'scoring', title: 'امتیازدهی و مقام‌ها', help: 'وزن هر فعالیت در جدول امتیازات. تغییر این اعداد روی محاسبه‌های بعدی اثر دارد.', fields: [
    ['building_economy','هر سطح ساختمان اقتصادی','امتیاز',.1], ['building_military','هر سطح ساختمان نظامی','امتیاز',.1], ['popularity','هر واحد محبوبیت','امتیاز',.1],
    ['alliance','هر اتحاد فعال','امتیاز',.1], ['victory','پیروزی','امتیاز'], ['defense','دفاع موفق','امتیاز'], ['castle_capture','فتح قلعه','امتیاز'],
    ['title_overlord','مقام بالادست','امتیاز'], ['title_warden','مقام والی','امتیاز'], ['title_king','شاه یا ملکه','امتیاز'],
  ]},
];

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function updateAt(data, path, value) {
  const next = clone(data); let cursor = next;
  path.slice(0, -1).forEach(key => { cursor = cursor[key]; });
  cursor[path[path.length - 1]] = value; return next;
}

function Numeric({ label, unit, value, onChange, step = 1 }) {
  return <label className="control-field"><span>{label}</span><div><input type="number" step={step} value={value ?? 0} onChange={e => onChange(Number(e.target.value))} /><small>{unit}</small></div></label>;
}

export default function AdminControlCenter({ data, onChange, onSave, onReset, busy }) {
  if (!data) return <div className="loading">در حال بارگذاری قوانین بازی...</div>;
  const set = (path, value) => onChange(updateAt(data, path, value));
  return <>
    <div className="notice-guide"><strong>مرکز کنترل قوانین بازی</strong><span>تمام تغییرات این صفحه سراسری و زنده‌اند. هر بخش را جداگانه بخوان و در پایان «ذخیره همه تغییرات» را بزن.</span></div>

    {SIMPLE_SECTIONS.map(section => <section className="card control-section" key={section.key}>
      <h3>{section.title}</h3><p>{section.help}</p>
      <div className="control-grid">{section.fields.map(([key,label,unit,step]) => <Numeric key={key} label={label} unit={unit} step={step} value={data[section.key]?.[key]} onChange={v => set([section.key,key], v)} />)}</div>
    </section>)}

    <section className="card control-section"><h3>اقتصاد پایه</h3><p>منابع شروع فقط برای ثبت‌نام‌ها و شروع فصل بعدی است؛ تولید و سقف‌ها بلافاصله در محاسبه بازی استفاده می‌شوند.</p>
      {[['starting_resources','منابع اولیه'],['daily_production','تولید پایه روزانه'],['base_caps','سقف اولیه انبارها']].map(([key,title]) => <div key={key} className="control-sub"><b>{title}</b><div className="control-grid">{Object.entries(data.economy?.[key] || {}).map(([res,value]) => <Numeric key={res} label={RESOURCES[res] || res} unit="واحد" value={value} onChange={v => set(['economy',key,res],v)} />)}</div></div>)}
      <div className="control-sub"><b>رشد جمعیت</b><div className="control-grid">
        <Numeric label="ضریب رشد در محبوبیت صفر" unit="ضریب" step={.05} value={data.economy.population_min_multiplier} onChange={v=>set(['economy','population_min_multiplier'],v)} />
        <Numeric label="ضریب رشد در محبوبیت صد" unit="ضریب" step={.05} value={data.economy.population_max_multiplier} onChange={v=>set(['economy','population_max_multiplier'],v)} />
        <Numeric label="محبوبیت معمول" unit="محبوبیت" value={data.economy.population_normal_popularity} onChange={v=>set(['economy','population_normal_popularity'],v)} />
      </div></div>
    </section>

    <section className="card control-section"><h3>دیپلماسی و ضیافت</h3><p>هزینه پیمان برای هر گیرنده حساب می‌شود و پیمان خصوصی در ضریب خصوصی ضرب می‌شود.</p>
      <div className="control-grid">{Object.entries(data.diplomacy.pact_costs || {}).map(([key,value]) => <Numeric key={key} label={PACTS[key] || key} unit="شراب" value={value} onChange={v=>set(['diplomacy','pact_costs',key],v)} />)}
        <Numeric label="ضریب پیمان خصوصی" unit="برابر" step={.1} value={data.diplomacy.private_multiplier} onChange={v=>set(['diplomacy','private_multiplier'],v)} />
        <Numeric label="هزینه غذای ضیافت" unit="غذا" value={data.diplomacy.feast_food_cost} onChange={v=>set(['diplomacy','feast_food_cost'],v)} />
        <Numeric label="هزینه شراب ضیافت" unit="شراب" value={data.diplomacy.feast_wine_cost} onChange={v=>set(['diplomacy','feast_wine_cost'],v)} />
        <Numeric label="اثر ضیافت" unit="محبوبیت" value={data.diplomacy.feast_popularity_gain} onChange={v=>set(['diplomacy','feast_popularity_gain'],v)} />
        <Numeric label="کول‌داون ضیافت" unit="ساعت" value={data.diplomacy.feast_cooldown_hours} onChange={v=>set(['diplomacy','feast_cooldown_hours'],v)} />
      </div>
    </section>

    <section className="card control-section"><h3>جایزه روزانه</h3><p>برای هر روز چرخه، پاداش هر منبع را جدا تعیین کن. قانون قطع زنجیره هم پایین جدول است.</p>
      {(data.daily_rewards.rewards || []).map((reward,day) => <div className="control-sub" key={day}><b>روز {day + 1}</b><div className="control-grid">{Object.entries(reward).map(([res,value]) => <Numeric key={res} label={RESOURCES[res] || res} unit="واحد" value={value} onChange={v=>set(['daily_rewards','rewards',day,res],v)} />)}</div></div>)}
      <Numeric label="قطع زنجیره پس از چند روز غیبت" unit="روز" value={data.daily_rewards.reset_after_missed_days} onChange={v=>set(['daily_rewards','reset_after_missed_days'],v)} />
    </section>

    <section className="card control-section"><h3>شرط مدال‌ها</h3><p>آستانه‌های برنز، نقره و طلا باید صعودی باشند. مدال‌های دستی ادمین شرط خودکار ندارند.</p>
      {Object.entries(data.medals || {}).map(([key,tiers]) => <div className="control-sub" key={key}><b>{MEDALS[key] || key}</b><div className="control-grid">
        {['bronze','silver','gold'].map((tier,i)=><Numeric key={tier} label={['برنز','نقره','طلا'][i]} unit="شرط" value={tiers[tier]} onChange={v=>set(['medals',key,tier],v)} />)}
      </div></div>)}
    </section>

    <section className="card control-section"><h3>مسیر اعلان‌ها</h3><p>برای هر نوع رخداد مشخص کن پیام در تلگرام بازیکن، کلاغ داخل بازی و اعلان پنل ادمین ثبت شود یا نه.</p>
      <div className="notification-route-grid">{Object.entries(data.notifications || {}).map(([key,route]) => <div className="route-row" key={key}><b>{EVENTS[key] || key}</b>
        {[['bot','بات تلگرام'],['raven','کلاغ'],['admin_panel','پنل ادمین']].map(([channel,label]) => <label key={channel}><input type="checkbox" checked={!!route[channel]} onChange={e=>set(['notifications',key,channel],e.target.checked)} />{label}</label>)}
      </div>)}</div>
    </section>

    <section className="card control-section"><h3>کلید قابلیت‌ها</h3><p>خاموش‌کردن، عملیات تازه را می‌بندد؛ اطلاعات قبلی حذف نمی‌شوند و صفحه‌های خواندنی همچنان در دسترس می‌مانند.</p>
      <div className="feature-grid">{Object.entries(data.features || {}).map(([key,enabled]) => <label className={enabled ? 'feature-toggle on' : 'feature-toggle'} key={key}><span><b>{FEATURES[key] || key}</b><small>{enabled ? 'فعال' : 'موقتاً بسته'}</small></span><input type="checkbox" checked={!!enabled} onChange={e=>set(['features',key],e.target.checked)} /></label>)}</div>
    </section>

    <div className="control-actions"><button className="btn" disabled={busy} onClick={onSave}>{busy ? 'در حال ذخیره...' : 'ذخیره همه تغییرات'}</button><button className="btn ghost" disabled={busy} onClick={onReset}>بازگشت همه به پیش‌فرض</button></div>
  </>;
}
