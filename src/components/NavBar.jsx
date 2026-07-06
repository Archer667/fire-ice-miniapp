import { haptic } from '../telegram.js';

const ITEMS = [
  { icon: '🏰', label: 'قلمرو' },
  { icon: '⚔️', label: 'لشکرکشی' },
  { icon: '🏆', label: 'تاج‌وتخت' },
  { icon: '🐦‍⬛', label: 'کلاغ‌ها' },
];

export default function NavBar({ tab, onChange }) {
  return (
    <div className="nav">
      {ITEMS.map((it, i) => (
        <div
          key={i}
          className={`nv ${tab === i ? 'on' : ''}`}
          onClick={() => { haptic(); onChange(i); }}
        >
          <div className="nv-ic">{it.icon}</div>
          {it.label}
        </div>
      ))}
    </div>
  );
}
