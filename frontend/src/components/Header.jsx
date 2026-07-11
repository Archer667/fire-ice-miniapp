import { haptic } from '../telegram.js';
import { Menu, Coin, Wood, Rock, Pick } from './Icons.jsx';
import { useGame } from '../store.jsx';

const TICKER_RES = [
  { key: 'gold',  Icon: Coin },
  { key: 'wood',  Icon: Wood },
  { key: 'stone', Icon: Rock },
  { key: 'iron',  Icon: Pick },
];

export default function Header({ onOpenMenu }) {
  const { me } = useGame();
  return (
    <div className="header">
      <button className="hamburger" onClick={() => { haptic(); onOpenMenu(); }} aria-label="منو">
        <Menu s={20} />
      </button>
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
    </div>
  );
}
