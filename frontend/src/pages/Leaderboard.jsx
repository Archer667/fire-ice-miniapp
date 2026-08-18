import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { castleLabel } from '../gamedata.js';

const TABS = [
  { id: 'regions', label: 'اقلیم‌ها' },
  { id: 'lords', label: 'لردها' },
  { id: 'weekly', label: 'این‌هفته' },
];
const MEDAL = { 1: '🥇', 2: '🥈', 3: '🥉' };
const TIER_FA = { bronze: 'برنز', silver: 'نقره', gold: 'طلا' };
const MEDAL_GUIDE = [
  { key: 'blood_and_steel', icon: '⚔️', name: 'خون و فولاد', desc: 'نشان پیروزی در حمله', rule: 'برنز ۳، نقره ۷، طلا ۱۰ پیروزی' },
  { key: 'peaceful_warrior', icon: '🛡️', name: 'صلح‌طلب، ولی جنگ بلده', desc: 'نشان دفاع موفق از قلمرو', rule: 'برنز ۲، نقره ۵، طلا ۷ دفاع موفق' },
  { key: 'conqueror', icon: '🏰', name: 'فاتح', desc: 'نشان تصرف واقعی قلعه', rule: 'برنز ۱، نقره ۳، طلا ۶ قلعه' },
  { key: 'rich_father', icon: '🪙', name: 'پدر پولدار', desc: 'نشان تولید طلا', rule: 'برنز ۵هزار، نقره ۲۰هزار، طلا ۴۰هزار' },
  { key: 'oathbound', icon: '🤝', name: 'سوگنددار', desc: 'نشان پیمان‌های پایدار', rule: 'پیمان ۷ روزه، ۳ پیمان، یا ۵ پیمان ده‌روزه' },
  { key: 'eye_in_shadow', icon: '👁️', name: 'چشم در سایه', desc: 'نشان جاسوسی موفق', rule: 'برنز ۲، نقره ۷، طلا ۱۰ جاسوسی' },
  { key: 'realm_storyteller', icon: '📜', name: 'راوی قلمرو', desc: 'با تشخیص ادمین به راویان بازی داده می‌شود', rule: 'اعطای دستی ادمین' },
  { key: 'oath_loyal', icon: '🔥', name: 'وفادار به عهد', desc: 'نشان حضور متوالی در بازی', rule: 'برنز ۵، نقره ۱۰، طلا ۱۵ روز' },
  { key: 'season_champion', icon: '🏆', name: 'قهرمان فصل', desc: 'افتخار ویژهٔ قهرمان فصل', rule: 'اعطای دستی ادمین' },
  { key: 'realm_savior', icon: '🪽', name: 'ناجی قلمرو', desc: 'افتخار ویژهٔ نجات قلمرو', rule: 'اعطای دستی ادمین' },
  { key: 'immortal', icon: '♾️', name: 'نامیرا', desc: 'افتخار ویژه برای نامیراهای میدان', rule: 'اعطای دستی ادمین' },
  { key: 'golden_quill', icon: '✒️', name: 'صاحب قلم زرین', desc: 'افتخار ویژهٔ نویسندگی و روایت', rule: 'اعطای دستی ادمین' },
  { key: 'crown_enemy', icon: '🗡️', name: 'دشمن تاج', desc: 'افتخار ویژهٔ دشمنان تاج‌وتخت', rule: 'اعطای دستی ادمین' },
];

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

export default function Leaderboard() {
  const { toast } = useGame();
  const [tab, setTab] = useState('regions');
  const [regionRows, setRegionRows] = useState(null);
  const [lordRows, setLordRows] = useState(null);
  const [weeklyRows, setWeeklyRows] = useState(null);
  const [selectedMedal, setSelectedMedal] = useState(null);

  useEffect(() => {
    api.regionLeaderboard().then(setRegionRows).catch(e => toast(e.message));
    api.leaderboard().then(setLordRows).catch(e => toast(e.message));
    api.weeklyLeaderboard().then(setWeeklyRows).catch(e => toast(e.message));
  }, []);

  return (
    <>
      <div className="page-title up">بازی تاج‌وتخت</div>
      <div className="page-sub up">یا اقلیمت رو ببر بالا، یا خودت بدرخش — هرکی به روش خودش</div>

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.id} role="tab" aria-selected={tab === t.id}
               className={`rbtn tab ${tab === t.id ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.id); }}>{t.label}</button>
        ))}
      </div>
      {tab === 'regions' && (
        !regionRows ? <div className="loading">شمارش اقلیم‌ها...</div> : (
          <div className="up u2">
            {regionRows.map(r => (
              <div key={r.region} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.mine ? 'me' : ''}`}>
                <div className="rk">{MEDAL[r.rank] ? <span className="medal">{MEDAL[r.rank]}</span> : r.rank.toLocaleString('fa-IR')}</div>
                <div className="n">{r.name}{r.mine ? ' — اقلیم تو' : ''}<small>{r.lord_count.toLocaleString('fa-IR')} لرد</small></div>
                <div className="p">{r.total_score.toLocaleString('fa-IR')}</div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'lords' && (
        !lordRows ? <div className="loading">شمارش تاج‌ها...</div> : (
          <div className="up u2">
            {lordRows.map(r => (
              <div key={r.rank} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.me ? 'me' : ''}`}>
                <div className="rk">{MEDAL[r.rank] ? <span className="medal">{MEDAL[r.rank]}</span> : r.rank.toLocaleString('fa-IR')}</div>
                <div className="n">
                  {r.name}{r.me ? ' — تو' : ''}
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

      {tab === 'weekly' && (
        !weeklyRows ? <div className="loading">شمارش این‌هفته...</div> : (
          <>
            <div className="page-sub up u2" style={{ marginTop: -6 }}>امتیازی که هرکس فقط از اول همین هفته کسب کرده — رقابت تازه، بدون انباشت کل بازی</div>
            <div className="up u2">
              {weeklyRows.map(r => (
                <div key={r.rank} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.me ? 'me' : ''}`}>
                  <div className="rk">{MEDAL[r.rank] ? <span className="medal">{MEDAL[r.rank]}</span> : r.rank.toLocaleString('fa-IR')}</div>
                  <div className="n">
                    {r.name}{r.me ? ' — تو' : ''}
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

      {selectedMedal && (
        <div role="dialog" aria-modal="true" onClick={() => setSelectedMedal(null)}
             style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.72)', display: 'grid', placeItems: 'center', padding: 20 }}>
          <div className="card" onClick={e => e.stopPropagation()} style={{ width: 'min(380px,100%)', textAlign: 'center', padding: 22 }}>
            <div style={{ fontSize: 52 }}>{selectedMedal.icon}</div>
            <div style={{ fontWeight: 900, fontSize: 18, marginTop: 6 }}>{selectedMedal.name}</div>
            {selectedMedal.tier && <div style={{ marginTop: 5, color: 'var(--az2)' }}>سطح {TIER_FA[selectedMedal.tier] || selectedMedal.tier}</div>}
            {selectedMedal.title && <div style={{ marginTop: 5 }}>{selectedMedal.title}</div>}
            <div style={{ color: 'var(--mid)', lineHeight: 1.9, marginTop: 10 }}>
              {selectedMedal.desc || MEDAL_GUIDE.find(m => m.key === selectedMedal.key)?.desc || 'مدال ویژهٔ ادمین'}
            </div>
            <div style={{ fontSize: 12, marginTop: 8 }}>
              {selectedMedal.rule || MEDAL_GUIDE.find(m => m.key === selectedMedal.key)?.rule || 'با تشخیص ادمین اعطا شده است'}
            </div>
            {selectedMedal.reason && <div style={{ marginTop: 10, padding: 9, borderRadius: 10, background: 'rgba(255,255,255,.06)' }}>دلیل اعطا: {selectedMedal.reason}</div>}
            <button type="button" className="btn" style={{ marginTop: 16 }} onClick={() => setSelectedMedal(null)}>بستن</button>
          </div>
        </div>
      )}
    </>
  );
}
