import { haptic } from '../telegram.js';
import { Close } from './Icons.jsx';
import { NAV_ITEMS, EXTRA_PAGES } from './NavBar.jsx';
import { useGame } from '../store.jsx';

export default function SideMenu({ open, tab, onChange, onClose }) {
  const { me, toast } = useGame();
  return (
    <>
      <div className={`sidemenu-overlay ${open ? 'show' : ''}`} onClick={onClose} />
      <div className={`sidemenu ${open ? 'open' : ''}`}>
        <div className="sidemenu-head">
          <div className="ava" style={{ width: 44, height: 44, fontSize: 18 }}>{me?.name?.charAt(0)}</div>
          <div>
            <div className="nm" style={{ fontSize: 14 }}>{me?.name}</div>
            <div className="hs" style={{ fontSize: 10.5 }}>{me?.castle}</div>
          </div>
          <button className="sidemenu-close" onClick={onClose} aria-label="بستن"><Close s={17} /></button>
        </div>

        <div className="sidemenu-list">
          {[...NAV_ITEMS, ...EXTRA_PAGES]
            .filter(p => !p.adminOnly || me?.admin_role)
            .sort((a, b) => a.index - b.index)
            .map(({ index, Icon, label }) => (
              <div key={index} className={`sidemenu-item ${tab === index ? 'on' : ''}`}
                   onClick={() => { haptic(); onChange(index); onClose(); }}>
                <Icon s={18} /> {label}
              </div>
            ))}
        </div>

        <div className="sidemenu-list">
          <div className="sidemenu-item" onClick={() => { toast('راهنما — به‌زودی'); onClose(); }}>راهنمای بازی</div>
          <div className="sidemenu-item" onClick={() => { toast('پشتیبانی — به‌زودی'); onClose(); }}>پشتیبانی</div>
        </div>
      </div>
    </>
  );
}
