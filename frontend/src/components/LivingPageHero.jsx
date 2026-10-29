export default function LivingPageHero({ kind, eyebrow, title, subtitle, badges = [], art, compact = false, children }) {
  const style = art ? { '--living-art': `url("${art}")` } : undefined;
  return <header className={`living-hero living-hero-${kind} ${compact ? 'living-hero-compact' : ''}`} style={style}>
    <div className="living-hero-frame" />
    <div className="living-hero-copy">
      <div className="living-hero-eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      <p>{subtitle}</p>
      {!!badges.length && <div className="living-hero-badges">{badges.filter(Boolean).map((badge, index) => <span key={index}>{badge}</span>)}</div>}
      {children}
    </div>
  </header>;
}
