import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Close } from './Icons.jsx';
import { castleLabel } from '../gamedata.js';

export default function PlayerPicker({ value, onChange, placeholder = 'نام، یوزرنیم، آیدی یا قلعه را جست‌وجو کن...', single = false }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const timer = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setError('');
    clearTimeout(timer.current);
    if (query.trim().length < 2) { setResults([]); setLoading(false); return; }
    setResults([]); setLoading(true);
    timer.current = setTimeout(() => {
      api.searchPlayers(query.trim(), { signal: controller.signal })
        .then(rows => { if (!cancelled) setResults(rows.filter(r => !value.some(v => v.tg_id === r.tg_id))); })
        .catch(e => { if (!cancelled && e.name !== 'AbortError') { setResults([]); setError('جست‌وجو انجام نشد؛ دوباره تلاش کن'); } })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 180);
    return () => { cancelled = true; controller.abort(); clearTimeout(timer.current); };
  }, [query, value]);

  const pick = (p) => {
    haptic();
    onChange(single ? [p] : [...value, p]);
    setQuery('');
    setResults([]);
    setOpen(false);
  };
  const remove = (tgId) => { haptic(); onChange(value.filter(v => v.tg_id !== tgId)); };

  return (
    <div className="ppicker">
      {value.length > 0 && (
        <div className="ppicker-chips">
          {value.map(p => (
            <span className="ppicker-chip" key={p.tg_id}>
              {p.name}
              <button type="button" aria-label={`حذف ${p.name}`} onClick={() => remove(p.tg_id)}><Close s={11} /></button>
            </span>
          ))}
        </div>
      )}
      <input
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
      />
      {open && query.trim().length >= 2 && (
        <div className="ppicker-results">
          {loading || error || results.length === 0 ? (
            <div className="ppicker-empty">{loading ? 'در حال جست‌وجو…' : error || 'لردی با این مشخصات پیدا نشد'}</div>
          ) : results.map(p => (
            <button type="button" className="rbtn ppicker-row" key={p.tg_id} onClick={() => pick(p)}>
              <span>{p.name}</span>
              <small>{p.telegram_username ? `@${p.telegram_username.replace(/^@/, '')} · ` : ''}{castleLabel(p.castle)} · {p.region_name}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
