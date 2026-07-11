import { haptic } from '../telegram.js';
import { Keep, Build, Swords, Crown, Mail, Heart, Shield, Eye } from './Icons.jsx';

// هر آیتم index خودش رو جدا نگه می‌داره (نه ترتیب آرایه) چون همین index مستقیم
// به PAGES توی App.jsx اشاره می‌کنه — هر صفحهٔ جدید همین‌جا و اونجا اضافه شود
export const NAV_ITEMS = [
  { index: 0, Icon: Keep,   label: 'قلمرو' },
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
];

export default function NavBar({ tab, onChange }) {
  return (
    <div className="nav">
      {NAV_ITEMS.map(({ index, Icon, label }) => (
        <div key={index} className={`nv ${tab === index ? 'on' : ''}`}
             onClick={() => { haptic(); onChange(index); }}>
          <Icon />
          {label}
        </div>
      ))}
    </div>
  );
}
