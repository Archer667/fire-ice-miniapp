import { useMemo, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { COMMON_TROOPS, SPECIAL_COST, REGIONS_STATIC } from '../gamedata.js';

const OP_TYPES = ['حملهٔ نظامی', 'محاصرهٔ قلعه', 'غارت دریایی'];

export default function War() {
  const { me, setMe, toast } = useGame();
  const gold = me.resources.gold;
  const specials = REGIONS_STATIC[me.region]?.special || [];

  const allTroops = [
    ...COMMON_TROOPS,
    ...specials.map(n => ({ id: n, name: n, cost: SPECIAL_COST, special: true })),
  ];

  const [opType, setOpType] = useState(OP_TYPES[0]);
  const [target, setTarget] = useState('');
  const [plan, setPlan] = useState('');
  const [counts, setCounts] = useState(Object.fromEntries(allTroops.map(t => [t.id, 0])));
  const [busy, setBusy] = useState(false);

  const cost = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0) * t.cost, 0),
    [counts]
  );
  const over = cost > gold;

  const send = async () => {
    if (!target.trim()) { toast('هدف را مشخص کن'); return; }
    if (plan.trim().length < 50) { toast('سناریو خیلی کوتاه است — نقشه‌ات را شرح بده'); return; }
    if (cost <= 0) { toast('هیچ نیرویی گسیل نکرده‌ای'); return; }
    setBusy(true);
    try {
      await api.submitWar({ op_type: opType, target_castle: target.trim(), plan: plan.trim(), troops: counts });
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, gold: gold - cost } });
      toast('فرمان مُهر شد — ۱۵ دقیقه دیگر روی نقشه آشکار می‌شود');
      setPlan(''); setCounts(Object.fromEntries(allTroops.map(t => [t.id, 0])));
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  return (
    <>
      <div className="page-title up">فرمان لشکرکشی</div>
      <div className="page-sub up">سناریو به دست ادمین داوری می‌شود · نتیجه تا ۲ ساعت</div>

      <div className="card up u1">
        <label className="f" style={{ marginTop: 0 }}>نوع عملیات</label>
        <select value={opType} onChange={e => setOpType(e.target.value)}>
          {OP_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
        <label className="f">قلعهٔ هدف</label>
        <input value={target} onChange={e => setTarget(e.target.value)} placeholder="مثلاً: ریورران" />
        <label className="f">سناریوی نبرد — تا دو صفحه</label>
        <textarea value={plan} onChange={e => setPlan(e.target.value)}
                  placeholder="مسیر لشکر، آرایش جنگی، نیرنگ‌ها..." />
      </div>

      <div className="sect up u2">گسیل نیرو</div>
      <div className="card up u2">
        {allTroops.map(t => (
          <div className="troop" key={t.id}>
            <div className="tn">
              {t.name}
              <small style={t.special ? { color: 'var(--az2)' } : {}}>
                {t.special ? 'نیروی ویژهٔ اقلیم تو · ' : ''}{t.cost.toLocaleString('fa-IR')} طلا به‌ازای هر نفر
              </small>
            </div>
            <input type="number" min="0" value={counts[t.id]}
                   onChange={e => setCounts({ ...counts, [t.id]: Math.max(0, +e.target.value || 0) })} />
          </div>
        ))}
        <div className={`cost ${over ? 'over' : ''}`}>
          <span>هزینه از خزانه</span>
          <b>{cost.toLocaleString('fa-IR')} / {gold.toLocaleString('fa-IR')} طلا</b>
        </div>
      </div>

      <div className="up u3">
        <button className="btn" disabled={over || busy} onClick={send}>
          {over ? 'خزانه کافی نیست — نیرو کم کن' : busy ? 'در حال ارسال...' : 'مُهر و ارسال فرمان'}
        </button>
      </div>
    </>
  );
}
