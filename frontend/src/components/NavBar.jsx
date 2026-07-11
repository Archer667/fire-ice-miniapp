import { haptic } from '../telegram.js';
import { Keep, Build, Map, Swords, Crown, Mail, Heart, Shield } from './Icons.jsx';

// هر آیتم index خودش رو جدا نگه می‌داره (نه ترتیب آرایه) چون همین index مستقیم
// به PAGES توی App.jsx اشاره می‌کنه — هر صفحهٔ جدید همین‌جا و اونجا اضافه شود
export const NAV_ITEMS = [
  { index: 0, Icon: Keep,   label: 'قلمرو' },
  { index: 2, Icon: Map,    label: 'نقشه' },
  { index: 3, Icon: Swords, label: 'لشکرکشی' },
  { index: 4, Icon: Crown,  label: 'تاج‌وتخت' },
  { index: 5, Icon: Mail,   label: 'کلاغ‌ها' },
];
const RAVENS_INDEX = 5;

// صفحه‌هایی که فقط از منوی کشویی/دستورها قابل‌دسترسی‌اند (توی نوار پایین جا نمی‌شوند)
export const EXTRA_PAGES = [
  { index: 1, Icon: Build,  label: 'ساختمان‌ها' },
  { index: 6, Icon: Heart,  label: 'دیپلماسی' },
  { index: 7, Icon: Shield, label: 'پنل ادمین', adminOnly: true },
];

export default function NavBar({ tab, onChange, unread = 0 }) {
  return (
    <div className="nav">
      {NAV_ITEMS.map(({ index, Icon, label }) => (
        <div key={index} className={`nv ${tab === index ? 'on' : ''}`}
             onClick={() => { haptic(); onChange(index); }}>
          {index === RAVENS_INDEX && unread > 0 && <span className="dot badge" />}
          <Icon />
          {label}
        </div>
      ))}
    </div>
  );
}
