import { haptic } from '../telegram.js';
import { Keep, Map, Swords, Crown, Mail } from './Icons.jsx';

const ITEMS = [
  { Icon: Keep,   label: 'قلمرو' },
  { Icon: Map,    label: 'نقشه' },
  { Icon: Swords, label: 'لشکرکشی' },
  { Icon: Crown,  label: 'تاج‌وتخت' },
  { Icon: Mail,   label: 'کلاغ‌ها' },
];

export default function NavBar({ tab, onChange, unread = 0 }) {
  return (
    <div className="nav">
      {ITEMS.map(({ Icon, label }, i) => (
        <div key={i} className={`nv ${tab === i ? 'on' : ''}`}
             onClick={() => { haptic(); onChange(i); }}>
          {i === 4 && unread > 0 && <span className="dot badge" />}
          <Icon />
          {label}
        </div>
      ))}
    </div>
  );
}
