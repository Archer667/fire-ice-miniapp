import { haptic } from '../telegram.js';
import { Keep, Build, Map, Swords, Crown, Mail } from './Icons.jsx';

export const NAV_ITEMS = [
  { Icon: Keep,   label: 'قلمرو' },
  { Icon: Build,  label: 'ساختمان‌ها' },
  { Icon: Map,    label: 'نقشه' },
  { Icon: Swords, label: 'لشکرکشی' },
  { Icon: Crown,  label: 'تاج‌وتخت' },
  { Icon: Mail,   label: 'کلاغ‌ها' },
];
const RAVENS_INDEX = NAV_ITEMS.length - 1;

export default function NavBar({ tab, onChange, unread = 0 }) {
  return (
    <div className="nav">
      {NAV_ITEMS.map(({ Icon, label }, i) => (
        <div key={i} className={`nv ${tab === i ? 'on' : ''}`}
             onClick={() => { haptic(); onChange(i); }}>
          {i === RAVENS_INDEX && unread > 0 && <span className="dot badge" />}
          <Icon />
          {label}
        </div>
      ))}
    </div>
  );
}
