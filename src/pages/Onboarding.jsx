import { useState, useEffect } from 'react';
import { HOUSES, useGame } from '../store.jsx';
import { haptic } from '../telegram.js';

export default function Onboarding({ defaultName, onDone }) {
  const { toast } = useGame();
  const [name, setName] = useState('');
  const [house, setHouse] = useState(HOUSES[0]);

  useEffect(() => { if (defaultName) setName(defaultName); }, [defaultName]);

  const start = () => {
    const finalName = name.trim();
    if (!finalName) { toast('⚠️ نامت را بنویس، لرد بی‌نام!'); return; }
    haptic('medium');
    onDone({ name: finalName, house });
    toast(`${house.sigil} خوش آمدی به وستروس، لرد ${finalName}!`);
  };

  return (
    <div className="page">
      <div className="scroll">
        <div className="logo-wrap rise">
          <div className="logo-mark">🔥❄️</div>
          <div className="logo-title grad-text">نغمه آتش و یخ</div>
          <div className="logo-sub">وقتی بازی تاج‌وتخت می‌کنی، یا می‌بری یا می‌میری</div>
        </div>

        <div className="glass rise d1">
          <div className="sec-title">هویت تو</div>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="نام کاراکتر — مثلاً جان اسنو"
          />
        </div>

        <div className="glass rise d2">
          <div className="sec-title">خاندانت را برگزین</div>
          <div className="house-grid">
            {HOUSES.map(h => (
              <div
                key={h.id}
                className={`house-card ${house.id === h.id ? 'sel' : ''}`}
                onClick={() => { haptic(); setHouse(h); }}
              >
                <div className="sigil">{h.sigil}</div>
                <div className="h-name">{h.name}</div>
                <div className="h-seat">{h.seat}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rise d3">
          <button className="btn" onClick={start}>به وستروس قدم بگذار ⚔️</button>
        </div>
      </div>
    </div>
  );
}
