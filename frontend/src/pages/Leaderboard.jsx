import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';

const TABS = [
  { id: 'regions', label: 'اقلیم‌ها' },
  { id: 'lords', label: 'لردها' },
];

export default function Leaderboard() {
  const { toast } = useGame();
  const [tab, setTab] = useState('regions');
  const [regionRows, setRegionRows] = useState(null);
  const [lordRows, setLordRows] = useState(null);

  useEffect(() => {
    api.regionLeaderboard().then(setRegionRows).catch(e => toast(e.message));
    api.leaderboard().then(setLordRows).catch(e => toast(e.message));
  }, []);

  return (
    <>
      <div className="page-title up">بازی تاج‌وتخت</div>
      <div className="page-sub up">اقلیم‌ها به‌عنوان یک تیم، لردها به‌صورت فردی رقابت می‌کنند</div>

      <div className="tabs up u1">
        {TABS.map(t => (
          <div key={t.id} className={`tab ${tab === t.id ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.id); }}>{t.label}</div>
        ))}
      </div>

      {tab === 'regions' ? (
        !regionRows ? <div className="loading">شمارش اقلیم‌ها...</div> : (
          <div className="up u2">
            {regionRows.map(r => (
              <div key={r.region} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.mine ? 'me' : ''}`}>
                <div className="rk">{r.rank.toLocaleString('fa-IR')}</div>
                <div className="n">{r.name}{r.mine ? ' — اقلیم تو' : ''}<small>{r.lord_count.toLocaleString('fa-IR')} لرد</small></div>
                <div className="p">{r.total_score.toLocaleString('fa-IR')}</div>
              </div>
            ))}
          </div>
        )
      ) : (
        !lordRows ? <div className="loading">شمارش تاج‌ها...</div> : (
          <div className="up u2">
            {lordRows.map(r => (
              <div key={r.rank} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.me ? 'me' : ''}`}>
                <div className="rk">{r.rank.toLocaleString('fa-IR')}</div>
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
    </>
  );
}
