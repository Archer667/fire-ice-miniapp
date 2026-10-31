import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { castleLabel, REGION_COLORS, REGIONS_STATIC } from '../gamedata.js';
import ProfileImageModal from '../components/ProfileImageModal.jsx';
import PlayerFlag from '../components/PlayerFlag.jsx';
import LivingPageHero from '../components/LivingPageHero.jsx';

const TABS = [
  { id: 'lords', label: 'لردها' },
  { id: 'regions', label: 'اقلیم‌ها' },
  { id: 'weekly', label: 'این‌هفته' },
  { id: 'medals', label: 'مدال‌ها' },
];
const MEDAL = { 1: '🥇', 2: '🥈', 3: '🥉' };
const TIER_FA = { bronze: 'برنز', silver: 'نقره', gold: 'طلا' };
const MEDAL_GUIDE = [
  { key: 'blood_and_steel', icon: '⚔️', name: 'خون و فولاد', desc: 'نشان پیروزی در حمله', rule: 'برنز ۳، نقره ۷، طلا ۱۰ پیروزی' },
  { key: 'peaceful_warrior', icon: '🛡️', name: 'صلح‌طلب، ولی جنگ بلده', desc: 'نشان دفاع موفق از قلمرو', rule: 'برنز ۲، نقره ۵، طلا ۷ دفاع موفق' },
  { key: 'conqueror', icon: '🏰', name: 'فاتح', desc: 'نشان فتح قلعه', rule: 'برنز ۱، نقره ۳، طلا ۶ قلعه' },
  { key: 'rich_father', icon: '🪙', name: 'پدر پولدار', desc: 'نشان تولید طلا', rule: 'برنز ۵هزار، نقره ۲۰هزار، طلا ۴۰هزار' },
  { key: 'oathbound', icon: '🤝', name: 'سوگنددار', desc: 'نشان پیمان‌های پایدار', rule: 'پیمان ۷ روزه، ۳ پیمان، یا ۵ پیمان ده‌روزه' },
  { key: 'eye_in_shadow', icon: '👁️', name: 'چشم در سایه', desc: 'نشان جاسوسی موفق', rule: 'برنز ۲، نقره ۷، طلا ۱۰ جاسوسی' },
  { key: 'realm_storyteller', icon: '📜', name: 'راوی قلمرو', desc: 'با تشخیص ادمین به راویان بازی داده می‌شود', rule: 'اعطای افتخار با تأیید مدیریت' },
  { key: 'oath_loyal', icon: '🔥', name: 'وفادار به عهد', desc: 'نشان حضور متوالی در بازی', rule: 'برنز ۵، نقره ۱۰، طلا ۱۵ روز' },
  { key: 'season_champion', icon: '🏆', name: 'قهرمان فصل', desc: 'افتخار ویژهٔ قهرمان فصل', rule: 'اعطای افتخار با تأیید مدیریت' },
  { key: 'realm_savior', icon: '🪽', name: 'ناجی قلمرو', desc: 'افتخار ویژهٔ نجات قلمرو', rule: 'اعطای افتخار با تأیید مدیریت' },
  { key: 'immortal', icon: '♾️', name: 'نامیرا', desc: 'افتخار ویژه برای نامیراهای میدان', rule: 'اعطای افتخار با تأیید مدیریت' },
  { key: 'golden_quill', icon: '✒️', name: 'صاحب قلم زرین', desc: 'افتخار ویژهٔ نویسندگی و روایت', rule: 'اعطای افتخار با تأیید مدیریت' },
  { key: 'crown_enemy', icon: '🗡️', name: 'دشمن تاج', desc: 'افتخار ویژهٔ دشمنان تاج‌وتخت', rule: 'اعطای افتخار با تأیید مدیریت' },
];
const regionColor = region => REGION_COLORS[region] || REGION_COLORS[Object.entries(REGIONS_STATIC).find(([, meta]) => meta.name === region)?.[0]] || '#9b7650';

function RankMovement({ value }) {
  const delta = value?.delta;
  const known = value?.state === 'known';
  const label = !known ? (value?.state === 'new' ? 'جدید' : '—') : delta ? Math.abs(delta).toLocaleString('fa-IR') : '—';
  const title = !known ? (value?.state === 'new' ? 'در جدول ۲۴ ساعت قبل حضور نداشته' : 'هنوز سابقهٔ کافی برای مقایسهٔ ۲۴ساعته وجود ندارد') : delta ? `${Math.abs(delta).toLocaleString('fa-IR')} پله ${delta > 0 ? 'صعود' : 'نزول'} نسبت به ۲۴ ساعت قبل` : 'بدون تغییر نسبت به ۲۴ ساعت قبل';
  return <span title={title} aria-label={title} style={{display:'inline-flex',alignItems:'center',gap:2,fontSize:11,fontWeight:500,color:known && delta ? (delta > 0 ? '#78c69b' : 'var(--danger)') : 'var(--low)',marginInlineStart:6,whiteSpace:'nowrap'}}>
    {known && !!delta && <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d={delta > 0 ? 'M3 10 L8 5 L13 10' : 'M3 6 L8 11 L13 6'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}{label}
  </span>;
}

function MedalChips({ medals, onSelect, player }) {
  if (!medals?.length) return null;
  return <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 6 }}>
    {medals.map(m => (
      <button type="button" key={m.key} className="rbtn" onClick={() => { haptic(); onSelect({ ...m, player }); }}
              style={{ width: 'auto', padding: '4px 7px', borderRadius: 9, fontSize: 10.5, display: 'flex', gap: 4, alignItems: 'center', border: '1px solid rgba(255,255,255,.12)' }}>
        <span style={{ fontSize: 15 }}>{m.icon}</span><span>{m.name}</span>
      </button>
    ))}
  </div>;
}

function CompetitionPulse({ rows }) {
  if (!rows?.length) return null;
  const colors = ['#9f2030', '#527da8', '#927548', '#46745c', '#b77f38', '#714779', '#6e5f55'];
  const visible = rows.filter(row => Number(row.total_score || 0) > 0).slice(0, 7);
  const source = visible.length ? visible : rows.slice(0, 7);
  const totalScore = Math.max(1, source.reduce((sum, row) => sum + Number(row.total_score || 0), 0));
  const activeHouses = rows.reduce((sum, row) => sum + Number(row.lord_count || 0), 0);
  let cursor = 0;
  const segments = source.map((row, index) => {
    const share = visible.length ? Number(row.total_score || 0) / totalScore * 100 : 100 / Math.max(1, source.length);
    const start = cursor; cursor += share;
    const color = regionColor(row.region) || colors[index % colors.length];
    return `${color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
  });
  const top = rows.slice(0, 3);
  return <section className="competition-pulse up u2" aria-label="نبض رقابت اقلیم‌ها">
    <header><div><span>قدرت‌های زندهٔ فصل</span><h2>نبض رقابت</h2></div><small>سهم هر اقلیم از قدرت ثبت‌شده</small></header>
    <div className="competition-pulse-body">
      <div className="competition-donut" style={{ '--pulse-fill': `conic-gradient(${segments.join(',')})` }}>
        <div><b>{activeHouses.toLocaleString('fa-IR')}</b><span>خاندان فعال</span></div>
      </div>
      <div className="competition-top-regions">
        {top.map((row, index) => {
          const share = Number(row.total_score || 0) / totalScore * 100;
          return <article key={row.region || row.name} style={{ '--region-color': regionColor(row.region) || colors[index] }}>
            <span>{row.name}</span>
            <b>{Number(row.total_score || 0).toLocaleString('fa-IR')}</b>
            <small>{share.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪ از قدرت</small>
          </article>;
        })}
      </div>
    </div>
  </section>;
}

const searchable = value => String(value || '').trim().toLocaleLowerCase('fa-IR');
const filterLeaderboard = (rows, query) => {
  const needle = searchable(query);
  if (!needle) return rows || [];
  return (rows || []).filter(row => searchable([row.name, row.region, row.title, row.rank_label, castleLabel(row.castle)].filter(Boolean).join(' ')).includes(needle));
};

export default function Leaderboard() {
  const { toast, seasonBranding } = useGame();
  const [tab, setTab] = useState('regions');
  const [regionRows, setRegionRows] = useState(null);
  const [lordPage, setLordPage] = useState(1);
  const [lordPages, setLordPages] = useState(1);
  const [lordBusy, setLordBusy] = useState(false);
  const [lordRows, setLordRows] = useState(null);
  const [lordError, setLordError] = useState('');
  const [retry, setRetry] = useState(0);
  const [pictureBusy, setPictureBusy] = useState(false);
  const [weeklyRows, setWeeklyRows] = useState(null);
  const [selectedMedal, setSelectedMedal] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [leaderSearch, setLeaderSearch] = useState('');

  const openPicture = async r => {
    if (pictureBusy) return;
    haptic(); setPictureBusy(true);
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 25000);
    try { const data = r.profile_key ? await api.leaderboardPicture(r.profile_key, controller.signal) : {image:r.profile_image}; setSelectedProfile({image:data.image || r.profile_image,name:r.name}); }
    catch(e) { toast(e.name === 'AbortError' ? 'دریافت تصویر طول کشید؛ دوباره تلاش کن' : e.message); }
    finally { clearTimeout(timer); setPictureBusy(false); }
  };
  const playerPicture = r => r.profile_image ? (
    <button type="button" className="leader-profile-trigger"
            aria-label={`نمایش تصویر پروفایل ${r.name}`}
            disabled={pictureBusy} onClick={() => openPicture(r)}>
      <img src={r.profile_image} alt="" loading="lazy" decoding="async" />
    </button>
  ) : <span className="leader-initial" aria-hidden="true">{String(r.name || '؟').trim().charAt(0) || '؟'}</span>;

  useEffect(() => {
    // هر جدول فقط وقتی تب خودش باز می‌شود دریافت می‌شود. قبلاً هر سه جدول با
    // ورود به صفحه هم‌زمان محاسبه و دانلود می‌شدند و روی WebView موبایل مکث
    // محسوسی ایجاد می‌کردند.
    if (tab === 'regions' && regionRows === null) {
      api.regionLeaderboard().then(setRegionRows).catch(e => { setRegionRows([]); toast(e.message); });

    } else if (tab === 'weekly' && weeklyRows === null) {
      api.weeklyLeaderboard().then(setWeeklyRows).catch(e => { setWeeklyRows([]); toast(e.message); });
    }
  }, [tab, regionRows, lordRows, weeklyRows, toast]);

  useEffect(() => {
    if (tab !== 'lords') return;
    let active = true; setLordBusy(true); setLordError('');
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 25000);
    api.leaderboardPage(lordPage, controller.signal).then(r => { if(active){setLordRows(r.items);setLordPages(r.pages);if(r.page!==lordPage)setLordPage(r.page);} })
      .catch(e=>{if(active)setLordError(e.name === 'AbortError' ? 'دریافت جدول طول کشید؛ دوباره تلاش کن.' : e.message);})
      .finally(()=>{clearTimeout(timer);if(active)setLordBusy(false);});
    return ()=>{active=false;clearTimeout(timer);controller.abort();};
  },[tab,lordPage,retry]);
  const pager = <nav className="leader-pager" aria-label="صفحه‌بندی لردها"><button className="rbtn" disabled={lordBusy||lordPage<=1} onClick={()=>setLordPage(p=>p-1)}>قبلی</button><span>صفحهٔ {lordPage.toLocaleString('fa-IR')} از {lordPages.toLocaleString('fa-IR')}</span><button className="rbtn" disabled={lordBusy||lordPage>=lordPages} onClick={()=>setLordPage(p=>p+1)}>بعدی</button></nav>;
  const visibleRegionRows = filterLeaderboard(regionRows, leaderSearch);
  const visibleLordRows = filterLeaderboard(lordRows, leaderSearch);
  const visibleWeeklyRows = filterLeaderboard(weeklyRows, leaderSearch);
  const visibleMedals = MEDAL_GUIDE.filter(medal => !searchable(leaderSearch) || searchable(`${medal.name} ${medal.desc} ${medal.rule}`).includes(searchable(leaderSearch)));
  const tabMeta = {
    regions: ['رده‌بندی اقلیم‌ها', 'قدرت هر اقلیم از مجموع امتیاز خاندان‌های آن ساخته می‌شود.'],
    lords: ['رده‌بندی لردها و لیدی‌ها', 'تغییر رتبه نسبت به ۲۴ ساعت قبل'],
    weekly: ['رقابت هفتگی', 'امتیازهای تازه‌ای که از آغاز هفته به دست آمده‌اند.'],
    medals: ['تالار مدال‌ها', 'نشان‌ها و افتخاراتی که در طول فصل به دست می‌آیند.'],
  }[tab];
  return (
    <div className="living-page living-throne-page">
      <LivingPageHero kind="throne" art="/living-assets/gold-treasury.webp" eyebrow="قدرت، افتخار و آوازه" title={seasonBranding.title} subtitle="جایگاه خاندان‌ها، قدرت اقلیم‌ها و مدال‌هایی که تاریخ فصل را ساخته‌اند." badges={["رتبه‌بندی زنده", "حرکت ۲۴ ساعته", "تالار افتخارات"]} />
      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.id} role="tab" aria-selected={tab === t.id}
               className={`rbtn tab ${tab === t.id ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.id); setLeaderSearch(''); }}>{t.label}</button>
        ))}
      </div>
      <div className="throne-dashboard">
      <main className="throne-leaderboard-main">
      <section className="leaderboard-heading up u2">
        <div><span>جدول زندهٔ فصل</span><h2>{tabMeta[0]}</h2><p>{tabMeta[1]}</p></div>
        <label className="leaderboard-search"><input aria-label="جستجو در جدول" value={leaderSearch} onChange={event => setLeaderSearch(event.target.value)} placeholder={tab === 'medals' ? 'جست‌وجوی مدال…' : 'جست‌وجوی این جدول…'} /></label>
      </section>
      {tab === 'regions' && (
        !regionRows ? <div className="loading">شمارش اقلیم‌ها...</div> : (
          <div className="up u2 leaderboard-board">
            {visibleRegionRows.map(r => (
              <div key={r.region} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.mine ? 'me' : ''}`} style={{ '--player-region': regionColor(r.region) }}>
                <div className="leader-rank-number">{r.rank.toLocaleString('fa-IR')}</div>
                <div className="rk">{MEDAL[r.rank] ? <span className="medal">{MEDAL[r.rank]}</span> : r.rank.toLocaleString('fa-IR')}</div>
                <div className="n">{r.name}<RankMovement value={r.movement} />{r.mine ? ' — اقلیم تو' : ''}<small>{r.lord_count.toLocaleString('fa-IR')} لرد</small></div>
                <div className="p">{r.total_score.toLocaleString('fa-IR')}</div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'lords' && pager}
      {tab === 'lords' && (
        lordError ? <div className="card"><p className="page-sub">{lordError}</p><button className="rbtn" onClick={()=>setRetry(n=>n+1)}>تلاش مجدد</button></div> : lordBusy || lordRows === null ? <div className="loading">شمارش تاج‌ها...</div> : lordRows.length === 0 ? (
          <div className="empty up u2">هنوز لرد تأییدشده‌ای وارد جدول امتیازات نشده است.</div>
        ) : (
          <div className="up u2 leaderboard-board">
            {visibleLordRows.map(r => (
              <div key={r.rank} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.me ? 'me' : ''} ${r.is_dead ? 'is-dead' : ''}`} style={{ '--player-region': regionColor(r.region) }}>
                {r.is_dead && <span className="death-stamp">کشته شد</span>}
                <div className="leader-rank-number">{r.rank.toLocaleString('fa-IR')}</div>
                <div className={`rk ${r.profile_image ? 'profile-rk' : ''} ${r.flag_image ? 'flag-rk' : ''}`}>{playerPicture(r)}<PlayerFlag src={r.flag_image} name={r.name} className="leader-player-flag" /></div>
                <div className="n">
                  {r.name}<RankMovement value={r.movement} />{r.me ? ' — تو' : ''}
                  {r.rank_label && <span className="title-tag">{r.rank_label}</span>}
                  <small>{castleLabel(r.castle)} · {r.region}{r.title ? ` · ${r.title}` : ''}</small>
                  <small style={{ display: 'block', marginTop: 4 }}>
                    ⚔️ {(r.stats?.attack_wins || 0).toLocaleString('fa-IR')} پیروزی · 🛡️ {(r.stats?.defense_wins || 0).toLocaleString('fa-IR')} دفاع موفق · 🏰 {(r.stats?.castles_captured || 0).toLocaleString('fa-IR')} فتح
                  </small>
                  <MedalChips medals={r.medals} player={r} onSelect={setSelectedMedal} />
                </div>
                <div className="p">{r.points.toLocaleString('fa-IR')}</div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'lords' && pager}
      {tab === 'weekly' && (
        weeklyRows === null ? <div className="loading">شمارش این‌هفته...</div> : weeklyRows.length === 0 ? (
          <div className="empty up u2">هنوز امتیازی برای این هفته ثبت نشده است.</div>
        ) : (
          <>
            <div className="page-sub up u2" style={{ marginTop: -6 }}>رتبه‌بندی هفتگی بر پایهٔ امتیازهای کسب‌شده از آغاز هفته است.</div>
            <div className="up u2 leaderboard-board">
              {visibleWeeklyRows.map(r => (
                <div key={r.rank} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.me ? 'me' : ''} ${r.is_dead ? 'is-dead' : ''}`} style={{ '--player-region': regionColor(r.region) }}>
                {r.is_dead && <span className="death-stamp">کشته شد</span>}
                  <div className="leader-rank-number">{r.rank.toLocaleString('fa-IR')}</div>
                  <div className={`rk ${r.profile_image ? 'profile-rk' : ''} ${r.flag_image ? 'flag-rk' : ''}`}>{playerPicture(r)}<PlayerFlag src={r.flag_image} name={r.name} className="leader-player-flag" /></div>
                  <div className="n">
                    {r.name}<RankMovement value={r.movement} />{r.me ? ' — تو' : ''}
                    {r.rank_label && <span className="title-tag">{r.rank_label}</span>}
                    <small>{castleLabel(r.castle)} · {r.region}{r.title ? ` · ${r.title}` : ''}</small>
                  <small style={{ display: 'block', marginTop: 4 }}>
                    ⚔️ {(r.stats?.attack_wins || 0).toLocaleString('fa-IR')} پیروزی · 🛡️ {(r.stats?.defense_wins || 0).toLocaleString('fa-IR')} دفاع موفق · 🏰 {(r.stats?.castles_captured || 0).toLocaleString('fa-IR')} فتح
                  </small>
                  <MedalChips medals={r.medals} player={r} onSelect={setSelectedMedal} />
                  </div>
                  <div className="p">{r.points.toLocaleString('fa-IR')}</div>
                </div>
              ))}
            </div>
          </>
        )
      )}

      {tab === 'medals' && (
        <div className="medal-catalog up u2">
          {visibleMedals.map(medal => (
            <button type="button" className="medal-catalog-card" key={medal.key} onClick={() => { haptic(); setSelectedMedal(medal); }}>
              <span className="medal-catalog-icon">{medal.icon}</span>
              <span><b>{medal.name}</b><small>{medal.desc}</small><em>{medal.rule}</em></span>
            </button>
          ))}
        </div>
      )}
      </main>
      {regionRows && <CompetitionPulse rows={regionRows} />}
      </div>

      {selectedMedal && (
        <div role="dialog" aria-modal="true" onClick={() => setSelectedMedal(null)}
             style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.72)', display: 'grid', placeItems: 'center', padding: 20 }}>
          <div className="card" onClick={e => e.stopPropagation()} style={{ width: 'min(380px,100%)', textAlign: 'center', padding: 22 }}>
            <div style={{ fontSize: 52 }}>{selectedMedal.icon}</div>
            <div style={{ fontWeight: 900, fontSize: 18, marginTop: 6 }}>{selectedMedal.name}</div>
            {selectedMedal.tier && <div style={{ marginTop: 5, color: 'var(--az2)' }}>سطح {TIER_FA[selectedMedal.tier] || selectedMedal.tier}</div>}
            {selectedMedal.title && <div style={{ marginTop: 5 }}>{selectedMedal.title}</div>}
            <div style={{ color: 'var(--mid)', lineHeight: 1.9, marginTop: 10 }}>
              {selectedMedal.desc || MEDAL_GUIDE.find(m => m.key === selectedMedal.key)?.desc || 'افتخار ویژه'}
            </div>
            <div style={{ fontSize: 12, marginTop: 8 }}>
              {selectedMedal.rule || MEDAL_GUIDE.find(m => m.key === selectedMedal.key)?.rule || 'افتخار ویژهٔ اعطاشده به خاندان'}
            </div>
            {selectedMedal.reason && <div style={{ marginTop: 10, padding: 9, borderRadius: 10, background: 'rgba(255,255,255,.06)' }}>دلیل اعطا: {selectedMedal.reason}</div>}
            <button type="button" className="btn" style={{ marginTop: 16 }} onClick={() => setSelectedMedal(null)}>بستن</button>
          </div>
        </div>
      )}
      <ProfileImageModal image={selectedProfile?.image} name={selectedProfile?.name || ''}
                         onClose={() => setSelectedProfile(null)} />
    </div>
  );
}
