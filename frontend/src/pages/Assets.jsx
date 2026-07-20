import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Coin, Pick, Rock, Wood, Wheat, Wine, People, Hammer, Market, Farm, Ranch, Winery, Warehouse } from '../components/Icons.jsx';
import { ITEM_RARITY_HEX } from '../gamedata.js';

const RES_ICON = { gold: Coin, iron: Pick, stone: Rock, wood: Wood, food: Wheat, wine: Wine, men: People };
const RES_NAME = { gold: 'طلا', iron: 'آهن', stone: 'سنگ', wood: 'چوب', food: 'غذا', wine: 'شراب', men: 'نیروی انسانی' };
const BUILDING_ICON = { market: Market, farm: Farm, ranch: Ranch, winery: Winery, granary: Warehouse, warehouse: Warehouse, village: People };

const TABS = [
  { key: 'castle', label: 'دارایی‌های قلعه' },
  { key: 'items',  label: 'آیتم‌های لرد' },
];

function fmtRemaining(iso) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return 'به‌زودی منقضی می‌شود';
  const h = Math.floor(ms / 3600000);
  const m = Math.round((ms % 3600000) / 60000);
  if (h > 0) return `${h.toLocaleString('fa-IR')} ساعت و ${m.toLocaleString('fa-IR')} دقیقه مانده`;
  return `${m.toLocaleString('fa-IR')} دقیقه مانده`;
}

export default function Assets() {
  const { toast } = useGame();
  const [tab, setTab] = useState('castle');
  const [castle, setCastle] = useState(null);
  const [items, setItems] = useState(null);

  const loadCastle = () => api.castleAssets().then(setCastle).catch(e => { toast(e.message); setCastle([]); });
  const loadItems = () => api.myItems().then(setItems).catch(e => { toast(e.message); setItems([]); });

  useEffect(() => { loadCastle(); loadItems(); }, []);

  return (
    <>
      <div className="page-title up">دارایی‌ها</div>
      <div className="page-sub up">هرچه قلعه‌ات می‌سازد و هر آیتمی که به تو داده شده، همین‌جاست</div>

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
               className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.key); }}>{t.label}</button>
        ))}
      </div>

      {tab === 'castle' && (
        <div className="up u2">
          {castle === null && <div className="loading">در حال بارگذاری...</div>}
          {castle && castle.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
              هنوز ساختمانی نساخته‌ای — از تب «ساختمان‌ها» شروع کن
            </div>
          )}
          {castle && castle.map(b => {
            const Icon = BUILDING_ICON[b.id] || Hammer;
            const produceEntries = Object.entries(b.produces || {}).filter(([, v]) => v);
            const capEntries = Object.entries(b.cap_bonus || {}).filter(([, v]) => v);
            return (
              <div className="card" key={b.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Icon s={16} /></div>
                  <div className="n">{b.name}<small>سطح {b.level.toLocaleString('fa-IR')}</small></div>
                </div>
                {(produceEntries.length > 0 || capEntries.length > 0) && (
                  <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 8, lineHeight: 1.9 }}>
                    {produceEntries.map(([k, v]) => (
                      <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginInlineEnd: 12 }}>
                        {RES_ICON[k] && (() => { const RI = RES_ICON[k]; return <RI s={12} />; })()}
                        +{v.toLocaleString('fa-IR')} {RES_NAME[k] || k}/روز
                      </span>
                    ))}
                    {capEntries.map(([k, v]) => (
                      <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginInlineEnd: 12 }}>
                        {RES_ICON[k] && (() => { const RI = RES_ICON[k]; return <RI s={12} />; })()}
                        سقف +{v.toLocaleString('fa-IR')} {RES_NAME[k] || k}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {tab === 'items' && (
        <div className="up u2">
          {items === null && <div className="loading">در حال بارگذاری...</div>}
          {items && items.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
              هنوز هیچ آیتمی نداری — وقتی ادمین چیزی به تو بدهد، همین‌جا ظاهر می‌شود
            </div>
          )}
          {items && items.map(it => (
            <div className="card" key={it.id} style={{ marginBottom: 10, borderInlineStart: `3px solid ${ITEM_RARITY_HEX[it.color] || 'var(--edge)'}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <b style={{ fontSize: 13.5 }}>{it.name}</b>
                <span className="title-tag" style={{ marginInlineStart: 0, color: ITEM_RARITY_HEX[it.color] }}>{it.color_name}</span>
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 6 }}>
                {it.type_name} · {it.duration_name}{it.expires_at ? ` · ${fmtRemaining(it.expires_at)}` : ''}
              </div>
              {it.description && (
                <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--hi)', marginTop: 8 }}>{it.description}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
