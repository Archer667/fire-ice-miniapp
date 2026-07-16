import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Coin, Pick, Rock, Wood, Wheat, People, Hammer, Bastion, Market, Farm, Ranch, Winery, Warehouse, Barracks } from '../components/Icons.jsx';

const RES_ICON = { gold: Coin, iron: Pick, stone: Rock, wood: Wood, food: Wheat };
const RES_NAME = { gold: 'طلا', iron: 'آهن', stone: 'سنگ', wood: 'چوب', food: 'غذا' };

// آیکن اختصاصی هر ساختمان — بر اساس id (کلید gamedata)؛ نبودش یعنی بازگشت به هامر عمومی
const BUILDING_ICON = {
  market: Market, farm: Farm, ranch: Ranch, winery: Winery,
  granary: Warehouse, warehouse: Warehouse, village: People,
  lumber_mill: Wood, stone_mine: Rock, iron_mine: Pick, gold_mine: Coin,
  camp_sword: Barracks, camp_spear: Barracks, camp_archer: Barracks, camp_lcav: Barracks, camp_hcav: Barracks,
};

const GROUPS = [
  { key: 'economy',  label: 'ساختمان‌های اقتصادی', hint: 'منابعت رو تولید و ذخیره می‌کنن' },
  { key: 'barracks', label: 'پادگان یگان‌ها',        hint: 'بدون این، اون نیرو رو استخدام نمی‌کنی' },
  { key: 'armory',   label: 'کارگاه‌های تسلیحات',    hint: 'تسلیحاتی که همون نیرو بهش نیاز داره' },
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
  const [tab, setTab] = useState(GROUPS[0].key);

  const load = () => api.buildings().then(setRows).catch(e => toast(e.message));
  useEffect(() => { load(); }, []);

  const act = async (row) => {
    setBusyId(row.id);
    try {
      const res = row.level === 0 ? await api.buildBuilding(row.id) : await api.upgradeBuilding(row.id);
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, ...subtractCost(me.resources, res.cost) } });
      toast(row.level === 0
        ? `ساخت «${row.name}» شروع شد — سطح ۱`
        : `ارتقای «${row.name}» به سطح ${res.target_level.toLocaleString('fa-IR')} شروع شد`);
      await load();
    } catch (e) { toast(e.message); }
    setBusyId(null);
  };

  if (!rows) return <div className="loading">نقشهٔ ساخت‌وساز باز می‌شود...</div>;

  const availGroups = GROUPS.filter(g => rows.some(r => r.type === g.key));
  const activeGroup = availGroups.find(g => g.key === tab) || availGroups[0];
  const items = activeGroup ? rows.filter(r => r.type === activeGroup.key) : [];

  return (
    <>
      <div className="page-title up">ساختمان‌های قلمرو</div>
      <div className="page-sub up">تا سطح {(30).toLocaleString('fa-IR')} می‌تونی بالا ببریشون — هرچی بالاتر بری، بازدهی بیشتره ولی گرون‌تر و کندتر</div>

      <div className="tabs up u1" role="tablist">
        {availGroups.map(g => (
          <button type="button" key={g.key} role="tab" aria-selected={activeGroup?.key === g.key}
               className={`rbtn tab ${activeGroup?.key === g.key ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(g.key); }}>{g.label}</button>
        ))}
      </div>

      {activeGroup?.hint && <div className="page-sub up u1" style={{ marginTop: -6 }}>{activeGroup.hint}</div>}

      <div className="card up u2">
        {items.map(row => (
          <BuildingRow key={row.id} row={row} busy={busyId === row.id} isPort={me.is_port} onAct={() => act(row)} />
        ))}
      </div>
    </>
  );
}

function subtractCost(resources, cost) {
  const out = {};
  for (const [k, v] of Object.entries(cost || {})) out[k] = (resources[k] ?? 0) - v;
  return out;
}

function BuildingRow({ row, busy, isPort, onAct }) {
  const pct = Math.round((row.level / row.max_level) * 100);
  const locked = row.requires_port && row.level === 0 && !isPort;
  const canUpgrade = !locked && !row.upgrading && row.next_level;
  const RowIcon = BUILDING_ICON[row.id] || (row.type === 'defense' ? Bastion : Hammer);
  return (
    <div className="bld">
      <div className="bld-top">
        <div className="bld-ic"><RowIcon s={18} /></div>
        <div className="bld-n">
          {row.name}
          <small>{row.level === 0 ? 'ساخته نشده' : `سطح ${row.level.toLocaleString('fa-IR')} از ${row.max_level.toLocaleString('fa-IR')}`}</small>
        </div>
        <div className="bld-lv">{row.level.toLocaleString('fa-IR')}</div>
      </div>
      <div className="bar"><i style={{ width: pct + '%' }} /></div>

      {locked ? (
        <div className="bld-status">فقط قلعه/شهرهای دریایی و بندری می‌تونن این رو بسازن</div>
      ) : row.upgrading ? (
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
            {busy ? 'در حال ارسال...' : row.level === 0 ? 'بساز' : `ارتقا به سطح ${row.next_level.toLocaleString('fa-IR')}`}
          </button>
        </>
      ) : (
        <div className="bld-status">به سقفش رسیده — از این بالاتر نمیشه</div>
      )}
    </div>
  );
}
