const fa = value => Number(value || 0).toLocaleString('fa-IR');
const divider = '꧁─꩜༺᪥༻꩜─꧂';
export function arrivalText(b) {
  const rows = b.battle_joins?.length ? b.battle_joins : [...(b.attacker_joins || []), ...(b.defender_joins || [])];
  const dated = rows.filter(j => j.joined_at && Number.isFinite(Date.parse(j.joined_at))).sort((a, z) => Date.parse(a.joined_at) - Date.parse(z.joined_at));
  const date = value => new Date(value).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' });
  return [b.started_at && Number.isFinite(Date.parse(b.started_at)) ? `شروع نبرد: ${date(b.started_at)} (به وقت تهران)` : '', ...dated.map(j => `لشکر ${j.player_name || 'بی‌نام'} — ${j.side === 'defender' ? 'مدافع' : 'مهاجم'}: ${date(j.joined_at)} (به وقت تهران)`)].filter(Boolean).join('\n') || 'زمان ورود نیروها ثبت نشده است.';
}
export function battleExportText(b, navalIds, conditions = arrivalText(b), deadline = '') {
  const side = (armies, fallback, icon, title) => {
    const names = [...new Set(armies.map(a => a.player_name).filter(Boolean))];
    let men = 0, ships = 0, equipment = 0;
    for (const a of armies) {
      // Naval units are vessels, not soldiers; never add them to the headcount.
      men += (a.troops || []).filter(t => !navalIds.includes(t.id)).reduce((n, t) => n + Number(t.count || 0), 0);
      ships += (a.troops || []).filter(t => navalIds.includes(t.id)).reduce((n, t) => n + Number(t.count || 0), 0);
      equipment += (a.equipment || []).reduce((n, t) => n + Number(t.count || 0), 0);
    }
    return `${icon} ${title}: ${names.join(' - ') || fallback || 'بدون نیرو'}\n\n⚔ آمار ارتش: ${fa(men)} سرباز\n☄ ادوات جنگی: ${equipment ? `${fa(equipment)} ادوات جنگی` : 'فاقد ادوات جنگی'}\n🚢 آمار کشتی‌ها: ${ships ? `${fa(ships)} کشتی` : 'فاقد کشتی'}`;
  };
  const attackers = b.attacker_armies ?? (b.attacker_army ? [b.attacker_army] : []);
  return `⚔️ نبرد ${b.location || b.name || 'نامشخص'}\n\n${divider}\n\n${side(attackers, b.attacker_name, '🗡', 'مهاجمین')}\n\n🆚\n${side(b.defender_armies || [], b.defender_name, '🛡', 'مدافعین')}\n\n${divider}\n\n🗺 شرایط نبرد:\n${conditions.trim() || 'توسط ادمین اعلام می‌شود.'}\n\n${divider}\n\n⏳ زمان ارسال سناریو: ${deadline.trim() || 'مهلت توسط ادمین اعلام می‌شود.'}\nلردها و لیدی‌ها به زمان رسیدن نیروها توجه کنن.`;
}
