import { useEffect, useRef, useState } from 'react';
import { haptic } from '../telegram.js';
import { Menu, Mail, Coin, Wood, Rock, Pick } from './Icons.jsx';
import { useGame } from '../store.jsx';

const TICKER_RES = [
  { key: 'gold',  Icon: Coin },
  { key: 'wood',  Icon: Wood },
  { key: 'stone', Icon: Rock },
  { key: 'iron',  Icon: Pick },
];

export default function Header({ onOpenMenu, onOpenRavens }) {
  const { me, unread } = useGame();
  const [ravenAttention, setRavenAttention] = useState(false);
  const previousUnread = useRef(0);

  useEffect(() => {
    const shouldAnimate = unread > 0 && (previousUnread.current === 0 || unread > previousUnread.current);
    previousUnread.current = unread;
    if (!shouldAnimate) return;
    setRavenAttention(true);
    const timer = setTimeout(() => setRavenAttention(false), 2600);
    return () => clearTimeout(timer);
  }, [unread]);
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
      <button className={`ravens-icon ${ravenAttention ? 'needs-attention' : ''}`}
              onClick={() => { haptic(); setRavenAttention(false); onOpenRavens?.(); }}
              aria-label={unread > 0 ? `کلاغ‌ها؛ ${unread.toLocaleString('fa-IR')} مورد تازه` : 'کلاغ‌ها'}>
        <Mail s={14} />
        {unread > 0 && <span className="raven-count badge">{unread > 99 ? '۹۹+' : unread.toLocaleString('fa-IR')}</span>}
      </button>
    </div>
  );
}
