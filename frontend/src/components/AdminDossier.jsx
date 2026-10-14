import '../admin-dossiers.css';

export function dossierDate(value) {
  if (!value) return 'تاریخ ثبت نشده';
  const stamp = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  const date = new Date(stamp);
  return Number.isNaN(date.getTime()) ? 'تاریخ ثبت نشده' : date.toLocaleString('fa-IR', {
    timeZone: 'Asia/Tehran', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function AdminDossier({ title, date, place, people = [], kind, children }) {
  const names = [...new Set(people.filter(Boolean))];
  return <details className="card admin-dossier">
    <summary>
      <span className="admin-dossier-mark" aria-hidden="true">{kind === 'battle' ? '⚔' : '✒'}</span>
      <span className="admin-dossier-heading"><strong>{title}</strong>
        <span>{place || 'مکان ثبت نشده'}</span>
        <small>{names.join(' · ') || 'طرف‌های پرونده مشخص نشده‌اند'}</small>
        <time>{dossierDate(date)} · تهران</time>
      </span>
      <span className="admin-dossier-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="admin-dossier-body">{children}</div>
  </details>;
}
