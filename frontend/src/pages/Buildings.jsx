import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Coin, Pick, Rock, Hammer, Shield } from '../components/Icons.jsx';

const RES_ICON = { gold: Coin, iron: Pick, stone: Rock };
const RES_NAME = { gold: 'طلا', iron: 'آهن', stone: 'سنگ' };

const GROUPS = [
  { key: 'economy',  label: 'ساختمان‌های اقتصادی', hint: 'تولید و ذخیرهٔ منابع' },
  { key: 'barracks', label: 'پادگان یگان‌ها',        hint: 'پیش‌نیاز اول استخدام هر نیرو' },
  { key: 'armory',   label: 'کارگاه‌های تسلیحات',    hint: 'پیش‌نیاز دوم استخدام — تسلیحات هر یگان' },
  { key: 'defense',  label: 'دفاعی و زیرساخت',       hint: '' },
];

function fmtRemaining(readyAt) {
  const ms = new Date(readyAt).getTime() - Date.now();
  if (ms <= 0) return 'به‌زودی';
  const totalMin = Math.round(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h.toLocaleString('fa-IR')} س ${m.toLocaleString('fa-IR')} د` : `${m.toLocaleString('fa-IR')} د`;
}

export default function Buildings() {
  const { me, setMe, toast } = useGame();
  const [rows, setRows] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = () => api.buildings().then(setRows).catch(e => toast(e.message));
  useEffect(() => { load(); }, []);

  const act = async (row) => {
    setBusyId(row.id);
    try {
      const res = row.level === 0 ? await api.buildBuilding(row.id) : await api.upgradeBuilding(row.id);
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, ...subtractCost(me.resources, res.cost) } });
      toast(row.level === 0
        ? `ساخت «${row.name}» آغاز شد — سطح ۱`
        : `ارتقای «${row.name}» به سطح ${res.target_level.toLocaleString('fa-IR')} آغاز شد`);
      await load();
    } catch (e) { toast(e.message); }
    setBusyId(null);
  };

  if (!rows) return <div className="loading">نقشهٔ ساخت‌وساز باز می‌شود...</div>;

  return (
    <>
      <div className="page-title up">ساختمان‌های قلمرو</div>
      <div className="page-sub up">هر ساختمان تا سطح {(30).toLocaleString('fa-IR')} ارتقا می‌پذیرد — هرچه سطح بالاتر، بازدهی و هزینه بیشتر</div>

      {GROUPS.map((g, gi) => {
        const items = rows.filter(r => r.type === g.key);
        if (!items.length) return null;
        return (
          <div key={g.key}>
            <div className={`sect up u${Math.min(gi + 1, 4)}`}>{g.label}{g.hint ? ` · ${g.hint}` : ''}</div>
            <div className={`card up u${Math.min(gi + 1, 4)}`}>
              {items.map(row => (
                <BuildingRow key={row.id} row={row} busy={busyId === row.id} onAct={() => act(row)} />
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}

function subtractCost(resources, cost) {
  const out = {};
  for (const [k, v] of Object.entries(cost || {})) out[k] = (resources[k] ?? 0) - v;
  return out;
}

function BuildingRow({ row, busy, onAct }) {
  const pct = Math.round((row.level / row.max_level) * 100);
  const canUpgrade = !row.upgrading && row.next_level;
  return (
    <div className="bld">
      <div className="bld-top">
        <div className="bld-ic">{row.type === 'barracks' ? <Shield s={18} /> : <Hammer s={18} />}</div>
        <div className="bld-n">
          {row.name}
          <small>{row.level === 0 ? 'ساخته نشده' : `سطح ${row.level.toLocaleString('fa-IR')} از ${row.max_level.toLocaleString('fa-IR')}`}</small>
        </div>
        <div className="bld-lv">{row.level.toLocaleString('fa-IR')}</div>
      </div>
      <div className="bar"><i style={{ width: pct + '%' }} /></div>

      {row.upgrading ? (
        <div className="bld-status">در حال ساخت به سطح {row.next_level.toLocaleString('fa-IR')} — آماده تا {fmtRemaining(row.ready_at)} دیگر</div>
      ) : canUpgrade ? (
        <>
          <div className="bld-cost">
            {Object.entries(row.next_cost).map(([k, v]) => {
              const Icon = RES_ICON[k];
              return <span key={k}>{Icon && <Icon s={13} />}{v.toLocaleString('fa-IR')} {RES_NAME[k] || k}</span>;
            })}
            <span className="tm">{row.next_hours.toLocaleString('fa-IR')} ساعت</span>
          </div>
          <button className="btn ghost bld-btn" disabled={busy} onClick={onAct}>
            {busy ? 'در حال ارسال...' : row.level === 0 ? 'بنا کردن' : `ارتقا به سطح ${row.next_level.toLocaleString('fa-IR')}`}
          </button>
        </>
      ) : (
        <div className="bld-status">به بیشینهٔ سطح رسیده</div>
      )}
    </div>
  );
}
