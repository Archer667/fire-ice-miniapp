import { haptic } from '../telegram.js';
import { Keep, Build, Map, Swords, Crown, Mail, Heart, Shield } from './Icons.jsx';

// آیکن‌های ردیف پایین — تا اینجا محدود نگه داشته می‌شود که شلوغ نشود
export const NAV_ITEMS = [
  { Icon: Keep,   label: 'قلمرو' },
  { Icon: Build,  label: 'ساختمان‌ها' },
  { Icon: Map,    label: 'نقشه' },
  { Icon: Swords, label: 'لشکرکشی' },
  { Icon: Crown,  label: 'تاج‌وتخت' },
  { Icon: Mail,   label: 'کلاغ‌ها' },
];
const RAVENS_INDEX = NAV_ITEMS.length - 1;

// صفحه‌هایی که فقط از منوی کشویی/دستورها قابل‌دسترسی‌اند (توی نوار پایین جا نمی‌شوند)
export const EXTRA_PAGES = [
  { index: 6, Icon: Heart, label: 'دیپلماسی' },
  { index: 7, Icon: Shield, label: 'پنل ادمین', adminOnly: true },
];

export const PAGE_TITLES = [...NAV_ITEMS.map(i => i.label), ...EXTRA_PAGES.map(p => p.label)];

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
