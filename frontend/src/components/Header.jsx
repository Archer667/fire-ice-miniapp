import { haptic } from '../telegram.js';
import { Menu } from './Icons.jsx';
import { NAV_ITEMS } from './NavBar.jsx';

export default function Header({ tab, onOpenMenu }) {
  const title = NAV_ITEMS[tab]?.label || 'وستروس';
  return (
    <div className="header">
      <button className="hamburger" onClick={() => { haptic(); onOpenMenu(); }} aria-label="منو">
        <Menu s={20} />
      </button>
      <div className="header-title">{title}</div>
      <div className="header-spacer" />
    </div>
  );
}
