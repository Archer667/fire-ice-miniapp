import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Close } from './Icons.jsx';
import { castleLabel, CASTLE_EN_NAMES } from '../gamedata.js';

/** لیستِ مرورپذیر برای انتخابِ چندتایی از قلعه/شهرهای بازی، به‌ترتیبِ اولویت — برای
 * درخواستِ خاندان موقع ثبت‌نام، چون خاندانِ اول‌اولویتِ بازیکن ممکنه از قبل
 * اشغال شده باشه و ادمین لازمه بدونه بعدی‌هاش چی‌ان. جست‌وجو هم می‌شه کرد، ولی
 * بدونِ تایپ‌کردن هم همهٔ قلعه‌ها (با اسمِ خاندانشون) دیده می‌شن. */
export default function CastlePicker({ value, onChange, max = 5, placeholder = 'اسم قلعه یا شهر را جست‌وجو کن، یا از لیست انتخاب کن...' }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(null);

  useEffect(() => {
    api.map().then(data => {
      const list = [];
      for (const r of data.regions) {
        for (const c of r.castles) {
          list.push({ name: c.name, region_name: r.name, occupied: !!c.owner, house: c.house || null });
        }
      }
      list.sort((a, b) => a.name.localeCompare(b.name, 'fa'));
      setAll(list);
    }).catch(() => setAll([]));
  }, []);

  const q = query.trim().toLowerCase();
  const results = (all || [])
    .filter(c => !value.includes(c.name))
    .filter(c => q.length === 0 || c.name.includes(q) || (CASTLE_EN_NAMES[c.name] || '').toLowerCase().includes(q));

  const pick = (name) => {
    if (value.length >= max) return;
    haptic();
    onChange([...value, name]);
    setQuery('');
    setOpen(false);
  };
  const remove = (name) => { haptic(); onChange(value.filter(v => v !== name)); };

  return (
    <div className="ppicker">
      {value.length > 0 && (
        <div className="ppicker-chips">
          {value.map((name, i) => (
            <span className="ppicker-chip" key={name}>
              {(i + 1).toLocaleString('fa-IR')}. {castleLabel(name)}
              <button type="button" aria-label={`حذف ${name}`} onClick={() => remove(name)}><Close s={11} /></button>
            </span>
          ))}
        </div>
      )}
      {value.length < max && (
        <>
          <input
            value={query}
            onChange={e => { setQuery(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            placeholder={all === null ? 'در حال بارگذاری قلعه‌ها...' : placeholder}
          />
          {open && (
            <div className="ppicker-results">
              {results.length === 0 ? (
                <div className="ppicker-empty">موردی پیدا نشد</div>
              ) : results.map(c => (
                <button type="button" className="rbtn ppicker-row" key={c.name} onClick={() => pick(c.name)}>
                  <span>{castleLabel(c.name)}{c.house ? ` · خاندان ${c.house}` : ''}</span>
                  <small>{c.region_name}{c.occupied ? ' · قبلاً گرفته شده' : ''}</small>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
