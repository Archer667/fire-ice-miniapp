import { useState, useEffect } from 'react';
import { fetchLeaderboard } from '../api.js';

export default function Leaderboard() {
  const [rows, setRows] = useState([]);

  useEffect(() => { fetchLeaderboard().then(setRows); }, []);

  const top3 = rows.slice(0, 3);
  const rest = rows.slice(3);
  const medals = ['👑', '🥈', '🥉'];
  const podOrder = [1, 0, 2]; // نقره - طلا - برنز (چیدمان پودیوم)

  return (
    <div className="scroll">
      <div className="logo-wrap rise" style={{ margin: '6px 0 14px' }}>
        <div style={{ fontSize: 34 }}>🏆</div>
        <div style={{ fontSize: 18, fontWeight: 800 }} className="grad-text">بازی تاج‌وتخت</div>
        <div style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 5 }}>
          ۱۲ روز تا پایان دوره · سه لرد برتر تاج می‌گیرند
        </div>
      </div>

      <div className="podium rise d1">
        {podOrder.map(i => top3[i] && (
          <div key={i} className={`pod pod-${i + 1}`}>
            <div className="medal">{medals[i]}</div>
            <div className="pd-name">{top3[i].name}</div>
            <div className="pd-pts">{top3[i].pts.toLocaleString('fa-IR')}</div>
          </div>
        ))}
      </div>

      <div className="rise d2">
        {rest.map(r => (
          <div key={r.rank} className={`lb-row ${r.me ? 'me' : ''}`}>
            <div className="lb-rank">{r.rank.toLocaleString('fa-IR')}</div>
            <div className="lb-sig">{r.sigil}</div>
            <div className="lb-name">{r.me ? `${r.name} (تو)` : r.name}</div>
            <div className="lb-pts">{r.pts.toLocaleString('fa-IR')}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
