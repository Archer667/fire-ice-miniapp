import { haptic } from '../telegram.js';
import { Realm, Build, Swords, Crown, Mail, Heart, Shield, Eye, Cart, Scroll, Warehouse } from './Icons.jsx';

// هر آیتم index خودش رو جدا نگه می‌داره (نه ترتیب آرایه) چون همین index مستقیم
// به PAGES توی App.jsx اشاره می‌کنه — هر صفحهٔ جدید همین‌جا و اونجا اضافه شود
export const NAV_ITEMS = [
  { index: 0, Icon: Realm,  label: 'قلمرو' },
  { index: 1, Icon: Build,  label: 'ساختمان‌ها' },
  { index: 2, Icon: Swords, label: 'نیروها/لشکرکشی' },
  { index: 3, Icon: Crown,  label: 'تاج‌وتخت' },
  { index: 5, Icon: Heart,  label: 'دیپلماسی' },
];

// صفحه‌هایی که فقط از منوی کشویی/هدر قابل‌دسترسی‌اند (توی نوار پایین جا نمی‌شوند)
export const EXTRA_PAGES = [
  { index: 4, Icon: Mail,   label: 'کلاغ‌ها' },
  { index: 6, Icon: Shield, label: 'پنل ادمین', adminOnly: true },
  { index: 7, Icon: Eye,    label: 'جاسوسی' },
  { index: 8, Icon: Cart,   label: 'تجارت' },
  { index: 9, Icon: Scroll, label: 'رول‌ها' },
  { index: 10, Icon: Warehouse, label: 'دارایی‌ها' },
];

export default function NavBar({ tab, onChange }) {
  return (
    <nav className="nav" aria-label="ناوبری اصلی">
      {NAV_ITEMS.map(({ index, Icon, label }) => (
        <button key={index} type="button" className={`rbtn nv ${tab === index ? 'on' : ''}`}
             aria-current={tab === index ? 'page' : undefined}
             onClick={() => { haptic(); onChange(index); }}>
          <Icon />
          {label}
        </button>
      ))}
    </nav>
  );
}
