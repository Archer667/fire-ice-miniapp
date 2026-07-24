import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Close } from './Icons.jsx';

/** جست‌وجو و انتخابِ چندتایی از قلعه/شهرهای بازی، به‌ترتیبِ اولویت — برای
 * درخواستِ خاندان موقع ثبت‌نام، چون خاندانِ اول‌اولویتِ بازیکن ممکنه از قبل
 * اشغال شده باشه و ادمین لازمه بدونه بعدی‌هاش چی‌ان */
export default function CastlePicker({ value, onChange, max = 5, placeholder = 'اسم قلعه یا شهر را جست‌وجو کن...' }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(null);

  useEffect(() => {
    api.map().then(data => {
      const list = [];
      for (const r of data.regions) {
        for (const c of r.castles) {
          list.push({ name: c.name, region_name: r.name, occupied: !!c.owner });
        }
      }
      setAll(list);
    }).catch(() => setAll([]));
  }, []);

  const q = query.trim();
  const results = (all || [])
    .filter(c => !value.includes(c.name))
    .filter(c => q.length >= 1 && c.name.includes(q))
    .slice(0, 20);

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
              {(i + 1).toLocaleString('fa-IR')}. {name}
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
          {open && q.length >= 1 && (
            <div className="ppicker-results">
              {results.length === 0 ? (
                <div className="ppicker-empty">موردی پیدا نشد</div>
              ) : results.map(c => (
                <button type="button" className="rbtn ppicker-row" key={c.name} onClick={() => pick(c.name)}>
                  <span>{c.name}</span>
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
