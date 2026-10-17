const ORDINALS = ['اول', 'دوم', 'سوم', 'چهارم', 'پنجم', 'ششم', 'هفتم', 'هشتم', 'نهم', 'دهم'];

export function seasonTitle(number, name = '') {
  const label = ORDINALS[number - 1] || Number(number).toLocaleString('fa-IR', { useGrouping: false });
  return `والریا : سیزن ${label}${name.trim() ? ` — ${name.trim()}` : ''}`;
}
