import { haptic } from '../telegram.js';
import { Menu, Mail, Coin, Wood, Rock, Pick } from './Icons.jsx';
import { PAGE_TITLES } from './NavBar.jsx';
import { useGame } from '../store.jsx';

const TICKER_RES = [
  { key: 'gold',  Icon: Coin },
  { key: 'wood',  Icon: Wood },
  { key: 'stone', Icon: Rock },
  { key: 'iron',  Icon: Pick },
];

export default function Header({ tab, onOpenMenu, onOpenRavens }) {
  const { me, unread } = useGame();
  const title = PAGE_TITLES[tab] || 'وستروس';
  return (
    <div className="header">
      <button className="hamburger" onClick={() => { haptic(); onOpenMenu(); }} aria-label="منو">
        <Menu s={20} />
      </button>
      <div className="header-title">{title}</div>
      <div className="header-spacer" />
      {me?.resources && (
        <div className="header-ticker">
          {TICKER_RES.map(({ key, Icon }) => (
            <span key={key}>
              <Icon s={12} />
              {(me.resources[key] ?? 0).toLocaleString('fa-IR')}
            </span>
          ))}
        </div>
      )}
      <button className="ravens-icon" onClick={() => { haptic(); onOpenRavens?.(); }} aria-label="کلاغ‌ها">
        <Mail s={14} />
        {unread > 0 && <span className="dot badge" />}
      </button>
    </div>
  );
}
