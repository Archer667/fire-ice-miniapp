import { useState, useMemo } from 'react';
import { useGame } from '../store.jsx';
import { submitScenario } from '../api.js';
import { haptic } from '../telegram.js';

const TROOPS = [
  { id: 'cav',   name: '🐎 سواره سنگین', cost: 3, def: 100 },
  { id: 'inf',   name: '🛡️ پیاده سنگین', cost: 2, def: 300 },
  { id: 'arc',   name: '🏹 کماندار',      cost: 1, def: 100 },
  { id: 'spear', name: '🔱 نیزه‌دار',     cost: 1, def: 50 },
];

export default function War() {
  const { resources, spendGold, toast } = useGame();
  const gold = resources.gold.val;

  const [counts, setCounts] = useState(
    Object.fromEntries(TROOPS.map(t => [t.id, t.def]))
  );
  const [type, setType] = useState('⚔️ حملهٔ نظامی');
  const [target, setTarget] = useState('دنریس تارگرین · دراگون‌استون');
  const [plan, setPlan] = useState('');

  // هزینه — خودکار با هر تغییر دوباره حساب می‌شود
  const cost = useMemo(
    () => TROOPS.reduce((sum, t) => sum + (counts[t.id] || 0) * t.cost, 0),
    [counts]
  );
  const over = cost > gold;

  const setCount = (id, v) =>
    setCounts(prev => ({ ...prev, [id]: Math.max(0, +v || 0) }));

  const send = async () => {
    if (over) return;
    haptic('medium');
    spendGold(cost); // طلا واقعاً کم می‌شود — داشبورد خودکار آپدیت می‌شود!
    await submitScenario({ type, target, plan, troops: counts, cost });
    toast('📜 سناریو نزد ادمین فرستاده شد — نتیجه تا ۲ ساعت');
    setPlan('');
  };

  return (
    <div className="scroll">
      <div className="logo-wrap rise" style={{ margin: '6px 0 18px' }}>
        <div style={{ fontSize: 34 }}>⚔️</div>
        <div style={{ fontSize: 18, fontWeight: 800 }} className="grad-text">فرمان لشکرکشی</div>
        <div style={{ fontSize: 10, color: 'var(--txt-3)', marginTop: 5 }}>
          سناریو به دست ادمین داوری می‌شود · نتیجه تا ۲ ساعت
        </div>
      </div>

      <div className="glass rise d1">
        <label className="lbl" style={{ marginTop: 0 }}>نوع عملیات</label>
        <select value={type} onChange={e => setType(e.target.value)}>
          <option>⚔️ حملهٔ نظامی</option>
          <option>🏰 محاصرهٔ قلعه</option>
          <option>🕵️ عملیات مخفی</option>
          <option>💣 خرابکاری</option>
        </select>

        <label className="lbl">هدف</label>
        <select value={target} onChange={e => setTarget(e.target.value)}>
          <option>دنریس تارگرین · دراگون‌استون</option>
          <option>جیمی لنیستر · کسترلی‌راک</option>
          <option>یورون گریجوی · پایک</option>
        </select>

        <label className="lbl">سناریوی نبرد (تا ۲ صفحه)</label>
        <textarea
          value={plan}
          onChange={e => setPlan(e.target.value)}
          placeholder="نقشه‌ات را شرح بده... مسیر لشکر، آرایش جنگی، نیرنگ‌ها"
        />
      </div>

      <div className="glass rise d2">
        <div className="sec-title">گسیل نیرو</div>
        {TROOPS.map(t => (
          <div className="troop" key={t.id}>
            <div className="t-name">
              {t.name} <span className="t-cost">· {t.cost} طلا/نفر</span>
            </div>
            <input
              type="number" min="0"
              value={counts[t.id]}
              onChange={e => setCount(t.id, e.target.value)}
            />
          </div>
        ))}
        <div className={`cost-bar ${over ? 'over' : ''}`}>
          <span>هزینهٔ کل لشکر</span>
          <b>{cost.toLocaleString('fa-IR')} / {gold.toLocaleString('fa-IR')} 🪙</b>
        </div>
      </div>

      <div className="rise d3">
        <button className="btn" disabled={over} onClick={send}>
          {over ? '🪙 خزانه کافی نیست — نیرو کم کن' : 'مُهر و ارسال فرمان 📜'}
        </button>
      </div>
    </div>
  );
}
