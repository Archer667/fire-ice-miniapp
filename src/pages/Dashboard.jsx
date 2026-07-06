import { useGame } from '../store.jsx';
import ResourceRow from '../components/ResourceRow.jsx';
import { haptic } from '../telegram.js';

const STATS = [
  { ic: '⚔️', val: '۸۵۰', lab: 'سپاه' },
  { ic: '⭐', val: '۸۵', lab: 'اعتبار' },
  { ic: '🏰', val: '۳', lab: 'قلعه' },
  { ic: '🤝', val: '۲', lab: 'اتحاد' },
];

export default function Dashboard({ goTo }) {
  const { player, resources, day, toast } = useGame();
  const pct = Math.round((day / 30) * 100);

  const act = (msg) => { haptic(); toast(msg); };

  return (
    <div className="scroll">
      <div className="season-bar rise">
        <div className="season-icon">❄️</div>
        <div className="season-info">
          <div className="season-name">زمستان نزدیک است</div>
          <div className="season-day">روز {day.toLocaleString('fa-IR')} از ۳۰ · دوره‌ی نخست</div>
          <div className="season-track">
            <div className="season-fill" style={{ width: pct + '%' }} />
          </div>
        </div>
      </div>

      <div className="hero rise d1">
        <div className="avatar">{player.name.charAt(0)}</div>
        <div className="p-name">{player.name}</div>
        <div className="p-house">{player.house.sigil} خاندان {player.house.name} · {player.house.seat}</div>
        <div className="p-rank">🏆 رتبه ۴ از ۹۸ لرد</div>
      </div>

      <div className="stats rise d2">
        {STATS.map((s, i) => (
          <div className="stat" key={i}>
            <div className="s-ic">{s.ic}</div>
            <div className="s-val grad-text">{s.val}</div>
            <div className="s-lab">{s.lab}</div>
          </div>
        ))}
      </div>

      <div className="glass rise d3">
        <div className="sec-title">خزانه و انبار</div>
        {Object.values(resources).map((r, i) => <ResourceRow key={i} r={r} />)}
      </div>

      <div className="acts rise d4">
        <div className="act" onClick={() => { haptic(); goTo(1); }}>
          <div className="a-ic">⚔️</div>لشکرکشی
        </div>
        <div className="act" onClick={() => act('🕵️ سناریوی جاسوسی به‌زودی...')}>
          <div className="a-ic">🕵️</div>جاسوسی
        </div>
        <div className="act" onClick={() => act('🤝 پیشنهاد اتحاد ارسال شد')}>
          <div className="a-ic">🤝</div>دیپلماسی
        </div>
        <div className="act" onClick={() => act('🏗️ به صف ساخت افزوده شد')}>
          <div className="a-ic">🏗️</div>ساخت‌وساز
        </div>
      </div>
    </div>
  );
}
