import FamilyIcon from './FamilyIcon.jsx';
import {useGame} from '../store.jsx';
import {CharacterIcon, InstitutionsIcon} from './InstitutionIcon.jsx';
import { haptic } from '../telegram.js';
import { Realm, Build, Swords, Crown, Mail, Heart, Shield, Eye, Cart, Scroll, Warehouse } from './Icons.jsx';

// هر آیتم index خودش رو جدا نگه می‌داره (نه ترتیب آرایه) چون همین index مستقیم
// به PAGES توی App.jsx اشاره می‌کنه — هر صفحهٔ جدید همین‌جا و اونجا اضافه شود
export const NAV_ITEMS = [
  { index: 0, Icon: Realm,  label: 'قلمرو' },
  { index: 1, Icon: Build,  label: 'ساختمان‌ها' },
  { index: 2, Icon: Swords, label: 'نیرو' },
  { index: 3, Icon: Crown,  label: 'تاج‌وتخت' },
  { index: 5, Icon: Heart,  label: 'دیپلماسی' },
];

// صفحه‌هایی که فقط از منوی کشویی/هدر قابل‌دسترسی‌اند (توی نوار پایین جا نمی‌شوند)
export const EXTRA_PAGES = [
  { index: 16, Icon: Mail, label: 'صندوق اعلان' },
  { index: 4, Icon: Mail,   label: 'کلاغ‌ها' },
  { index: 6, Icon: Shield, label: 'پنل ادمین', adminOnly: true },
  { index: 7, Icon: Eye,    label: 'جاسوسی' },
  { index: 8, Icon: Cart,   label: 'تجارت' },
  { index: 9, Icon: Scroll, label: 'رول‌ها' },
  { index: 10, Icon: Warehouse, label: 'دارایی‌ها' },
  { index: 11, Icon: FamilyIcon, label: 'خاندان و خانواده' },
  { index: 12, Icon: CharacterIcon, label: 'ساخت و ویرایش کاراکتر' },
  { index: 13, Icon: InstitutionsIcon, label: 'نهادها' },
  { index: 14, Icon: FamilyIcon, label: 'کاراکتر و سفر' },
  { index: 15, Icon: Cart, label: 'فروشگاه آیتم‌ها' },
];

export default function NavBar({ tab, onChange }) {
  const {me}=useGame();
  const items=me?.landless?[EXTRA_PAGES.find(p=>p.index===14),EXTRA_PAGES.find(p=>p.index===11),NAV_ITEMS.find(p=>p.index===3),EXTRA_PAGES.find(p=>p.index===4)]:NAV_ITEMS;
  return (
    <nav className="nav" aria-label="ناوبری اصلی">
      {items.map(({ index, Icon, label }) => (
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
