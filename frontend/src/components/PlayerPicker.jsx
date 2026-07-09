import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Close } from './Icons.jsx';

export default function PlayerPicker({ value, onChange, placeholder = 'اسم لرد یا قلعه را جست‌وجو کن...', single = false }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    clearTimeout(timer.current);
    if (query.trim().length < 2) { setResults([]); return; }
    timer.current = setTimeout(() => {
      api.searchPlayers(query.trim())
        .then(rows => setResults(rows.filter(r => !value.some(v => v.tg_id === r.tg_id))))
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(timer.current);
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
              <i onClick={() => remove(p.tg_id)}><Close s={11} /></i>
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
          {results.length === 0 ? (
            <div className="ppicker-empty">لردی با این مشخصات پیدا نشد</div>
          ) : results.map(p => (
            <div className="ppicker-row" key={p.tg_id} onClick={() => pick(p)}>
              <span>{p.name}</span>
              <small>{p.castle} · {p.region_name}</small>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
