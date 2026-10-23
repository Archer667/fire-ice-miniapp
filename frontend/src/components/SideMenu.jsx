import {canOpenPage} from '../characterAccess.js';
import { haptic } from '../telegram.js';
import { Close } from './Icons.jsx';
import { NAV_ITEMS, EXTRA_PAGES } from './NavBar.jsx';
import { useGame } from '../store.jsx';
import { castleLabel } from '../gamedata.js';

export default function SideMenu({ open, tab, onChange, onClose }) {
  const { me, toast } = useGame();
  const pages = [...NAV_ITEMS, ...EXTRA_PAGES]
    .filter(p => (!p.adminOnly || me?.admin_role) && canOpenPage(me, p.index));
  const groups = [
    ['realm', 'قلمرو و فرماندهی', '♜'],
    ['world', 'جهان و داستان', '✦'],
    ['services', 'بازار و خدمات', '⚖'],
    ['character', 'کاراکتر و خاندان', '♛'],
    ['admin', 'مدیریت', 'V'],
  ];
  return (
    <>
      <div className={`sidemenu-overlay ${open ? 'show' : ''}`} onClick={onClose} aria-hidden="true" />
      <div className={`sidemenu ${open ? 'open' : ''}`} role="dialog" aria-modal="true" aria-label="منو" aria-hidden={!open} inert={open?undefined:''}>
        <div className="sidemenu-head">
          <div className="sidemenu-brand" aria-hidden="true"><b>V</b><span>VALYRIA</span></div>
          <div className={`ava sidemenu-avatar ${me?.profile_image ? 'has-image' : ''}`}>
            {me?.profile_image ? <img src={me.profile_image} alt="" /> : me?.name?.charAt(0)}
          </div>
          <div className="sidemenu-identity">
            <div className="nm" style={{ fontSize: 14 }}>{me?.name}</div>
            <div className="hs" style={{ fontSize: 10.5 }}>{me?.castle ? castleLabel(me.castle) : 'مسافر قلمرو'}</div>
          </div>
          <button className="sidemenu-close" onClick={onClose} aria-label="بستن"><Close s={17} /></button>
        </div>

        <div className="sidemenu-scroll" tabIndex={0} aria-label="بخش‌های بازی">
        {groups.map(([key, title, emblem]) => {
          const items = pages.filter(p => p.group === key);
          const active = items.some(p => p.index === tab);
          return items.length > 0 && <details className={`sidemenu-group ${active ? 'is-active' : ''}`} data-group={key} key={key} defaultOpen={active || key === 'realm'} onToggle={event => {
            if (event.currentTarget.open) requestAnimationFrame(() => event.currentTarget.scrollIntoView({ block: 'nearest', behavior: 'smooth' }));
          }}>
            <summary><i className="sidemenu-group-emblem" aria-hidden="true">{emblem}</i><span>{title}</span><small>{items.length.toLocaleString('fa-IR')}</small></summary>
            <div className="sidemenu-list">{items.map(({ index, Icon, label }) => (
              <button type="button" key={index} className={`rbtn sidemenu-item ${tab === index ? 'on' : ''}`}
                   aria-current={tab === index ? 'page' : undefined}
                   onClick={() => { haptic(); onChange(index); onClose(); }}>
                <span className="sidemenu-item-icon"><Icon s={18} /></span><span>{label}</span><i className="sidemenu-item-mark" aria-hidden="true" />
              </button>
            ))}</div>
          </details>;
        })}

        <div className="sidemenu-list sidemenu-help">
          <span className="sidemenu-help-title">همراهی در مسیر</span>
          <button type="button" className="rbtn sidemenu-item" onClick={() => { toast('راهنما — به‌زودی'); onClose(); }}>راهنمای بازی</button>
          <button type="button" className="rbtn sidemenu-item" onClick={() => { toast('پشتیبانی — به‌زودی'); onClose(); }}>پشتیبانی</button>
        </div>
        </div>
      </div>
    </>
  );
}
