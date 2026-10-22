import FamilyIcon from './FamilyIcon.jsx';
import {useGame} from '../store.jsx';
import {CharacterIcon, InstitutionsIcon} from './InstitutionIcon.jsx';
import { haptic } from '../telegram.js';
import { Realm, Build, Swords, Crown, Mail, Heart, Shield, Eye, Cart, Scroll, Warehouse } from './Icons.jsx';

// هر آیتم index خودش رو جدا نگه می‌داره (نه ترتیب آرایه) چون همین index مستقیم
// به PAGES توی App.jsx اشاره می‌کنه — هر صفحهٔ جدید همین‌جا و اونجا اضافه شود
export const NAV_ITEMS = [
  { index: 0, Icon: Realm,  label: 'قلمرو', group: 'realm' },
  { index: 1, Icon: Build,  label: 'ساختمان‌ها', group: 'realm' },
  { index: 2, Icon: Swords, label: 'نیرو', group: 'realm' },
  { index: 3, Icon: Crown,  label: 'تاج‌وتخت', group: 'realm' },
  { index: 5, Icon: Heart,  label: 'دیپلماسی', group: 'world' },
];

// صفحه‌هایی که فقط از منوی کشویی/هدر قابل‌دسترسی‌اند (توی نوار پایین جا نمی‌شوند)
export const EXTRA_PAGES = [
  { index: 4, Icon: Mail, label: 'کلاغ‌ها', group: 'world' },
  { index: 6, Icon: Shield, label: 'پنل ادمین', adminOnly: true, group: 'admin' },
  { index: 7, Icon: Eye, label: 'جاسوسی', group: 'services' },
  { index: 8, Icon: Cart, label: 'تجارت', group: 'services' },
  { index: 9, Icon: Scroll, label: 'رول‌ها', group: 'world' },
  { index: 10, Icon: Warehouse, label: 'دارایی‌ها', group: 'realm' },
  { index: 11, Icon: FamilyIcon, label: 'خاندان و خانواده', group: 'character' },
  { index: 12, Icon: CharacterIcon, label: 'ساخت و ویرایش کاراکتر', group: 'character' },
  { index: 13, Icon: InstitutionsIcon, label: 'نهادها', group: 'services' },
  { index: 14, Icon: FamilyIcon, label: 'کاراکتر و سفر', group: 'character' },
  { index: 15, Icon: Cart, label: 'فروشگاه آیتم‌ها', group: 'services' },
  { index: 16, Icon: Scroll, label: 'تابلوی قراردادها', group: 'world' },
  { index: 17, Icon: Realm, label: 'زندگی در قلعه', group: 'world' },
  { index: 18, Icon: Scroll, label: 'روزنامه', group: 'world' },
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
