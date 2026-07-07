import { useEffect, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { BUILDINGS } from '../gamedata.js';

const CATS = [
  { id: 'production', label: 'تولید' },
  { id: 'storage', label: 'انبار و خزانه' },
  { id: 'camp', label: 'پادگان‌ها' },
  { id: 'defense', label: 'دفاعی' },
];
const RES_NAME = { gold: 'طلا', food: 'غذا', men: 'نیرو', iron: 'آهن', stone: 'سنگ' };

function costLabel(cost) {
  return Object.entries(cost).map(([k, v]) => `${v.toLocaleString('fa-IR')} ${RES_NAME[k]}`).join(' · ');
}

function fmtRemain(ms) {
  if (ms <= 0) return '۰۰:۰۰:۰۰';
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return [h, m, s].map(n => String(n).padStart(2, '0')).join(':');
}

export default function Construction() {
  const { me, setMe, toast } = useGame();
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(null);
  const [, forceTick] = useState(0);

  useEffect(() => {
    api.construction().then(setState).catch(e => toast(e.message));
  }, []);

  useEffect(() => {
    if (!state?.queue) return;
    const iv = setInterval(() => {
      const left = new Date(state.queue.finishes_at).getTime() - Date.now();
      if (left <= 0) api.construction().then(setState);
      else forceTick(t => t + 1);
    }, 1000);
    return () => clearInterval(iv);
  }, [state?.queue]);

  if (!state) return <div className="page-title up">در حال بارگذاری...</div>;

  const remain = state.queue ? new Date(state.queue.finishes_at).getTime() - Date.now() : 0;

  const build = async (id) => {
    setBusy(id);
    try {
      const res = await api.buildStart(id);
      haptic('medium');
      setState(res);
      setMe({ ...me, resources: res.resources });
      toast('ساخت‌وساز شروع شد');
    } catch (e) { toast(e.message); }
    setBusy(null);
  };

  return (
    <>
      <div className="page-title up">ساخت‌وساز</div>
      <div className="page-sub up">ساختمان‌ها روی تولید روزانه و ظرفیت خزانه‌ات اثر واقعی دارند</div>

      {state.queue && (
        <div className="card up u1 queue-card">
          <div className="sect" style={{ margin: 0 }}>در حال ساخت</div>
          <div className="qname">{BUILDINGS.find(b => b.id === state.queue.building_id)?.name}</div>
          <div className="qtime">{fmtRemain(remain)}</div>
        </div>
      )}

      {CATS.map(cat => (
        <div key={cat.id}>
          <div className="sect up u2">{cat.label}</div>
          <div className="card up u2">
            {BUILDINGS.filter(b => b.cat === cat.id).map(b => {
              const built = !!state.buildings[b.id];
              const locked = !!state.queue && !built;
              const afford = Object.entries(b.cost).every(([k, v]) => (me.resources[k] ?? 0) >= v);
              return (
                <div className="bld" key={b.id}>
                  <div className="bn">
                    {b.name}
                    <small>{costLabel(b.cost)} · {b.hours.toLocaleString('fa-IR')} ساعت</small>
                  </div>
                  {built ? (
                    <span className="bstate">ساخته‌شده</span>
                  ) : (
                    <button className="bbtn" disabled={locked || !afford || busy === b.id}
                            onClick={() => build(b.id)}>
                      {busy === b.id ? '...' : 'بساز'}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </>
  );
}
