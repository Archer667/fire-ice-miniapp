export default function ResourceRow({ r }) {
  const pct = Math.round((r.val / r.max) * 100);
  return (
    <div className="res-row">
      <div className="res-ic">{r.icon}</div>
      <div className="res-name">{r.name}</div>
      <div className="res-track">
        <div className="res-fill" style={{ width: pct + '%', background: r.color }} />
      </div>
      <div className="res-num">
        {r.val.toLocaleString('fa-IR')}/{r.max.toLocaleString('fa-IR')}
      </div>
    </div>
  );
}
