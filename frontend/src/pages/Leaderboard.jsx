import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';

const TABS = [
  { id: 'regions', label: 'اقلیم‌ها' },
  { id: 'lords', label: 'لردها' },
  { id: 'weekly', label: 'این‌هفته' },
];
const MEDAL = { 1: '🥇', 2: '🥈', 3: '🥉' };

export default function Leaderboard() {
  const { toast } = useGame();
  const [tab, setTab] = useState('regions');
  const [regionRows, setRegionRows] = useState(null);
  const [lordRows, setLordRows] = useState(null);
  const [weeklyRows, setWeeklyRows] = useState(null);

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
                  <small>{r.castle} · {r.region}{r.title ? ` · ${r.title}` : ''}</small>
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
                    <small>{r.castle} · {r.region}{r.title ? ` · ${r.title}` : ''}</small>
                  </div>
                  <div className="p">{r.points.toLocaleString('fa-IR')}</div>
                </div>
              ))}
            </div>
          </>
        )
      )}
    </>
  );
}
