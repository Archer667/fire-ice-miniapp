import { Build, Shield, Eye } from './Icons.jsx';
import { haptic } from '../telegram.js';
import { useGame } from '../store.jsx';

const ITEMS = [
  { id: 'construction', Icon: Build, label: 'ساخت‌وساز', ready: true },
  { id: 'barracks', Icon: Shield, label: 'پادگان', ready: false },
  { id: 'espionage', Icon: Eye, label: 'جاسوسی', ready: false },
];

export default function Drawer({ open, onClose, onOpenPage }) {
  const { toast } = useGame();
  return (
    <>
      <div className={`drawer-overlay ${open ? 'show' : ''}`} onClick={onClose} />
      <div className={`drawer ${open ? 'open' : ''}`}>
        <div className="drawer-title">فرمان‌های قلمرو</div>
        {ITEMS.map(({ id, Icon, label, ready }) => (
          <div key={id} className="drawer-item" onClick={() => {
            haptic();
            if (ready) { onOpenPage(id); } else { toast(`${label} — فاز بعدی`); onClose(); }
          }}>
            <div className="di"><Icon s={19} /></div>
            {label}
          </div>
        ))}
      </div>
    </>
  );
}
