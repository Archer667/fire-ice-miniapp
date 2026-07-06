import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';

export default function Leaderboard() {
  const { toast } = useGame();
  const [rows, setRows] = useState(null);

  useEffect(() => { api.leaderboard().then(setRows).catch(e => toast(e.message)); }, []);
  if (!rows) return <div className="loading">شمارش تاج‌ها...</div>;

  return (
    <>
      <div className="page-title up">بازی تاج‌وتخت</div>
      <div className="page-sub up">سه لرد برتر در پایان دوره تاج می‌گیرند</div>
      <div className="up u1">
        {rows.map(r => (
          <div key={r.rank} className={`lbr ${r.rank <= 3 ? 'top' + r.rank : ''} ${r.me ? 'me' : ''}`}>
            <div className="rk">{r.rank.toLocaleString('fa-IR')}</div>
            <div className="n">{r.name}{r.me ? ' — تو' : ''}<small>{r.castle} · {r.region}</small></div>
            <div className="p">{r.points.toLocaleString('fa-IR')}</div>
          </div>
        ))}
      </div>
    </>
  );
}
