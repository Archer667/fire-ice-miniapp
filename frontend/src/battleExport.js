const fa = value => Number(value || 0).toLocaleString('fa-IR');
const divider = '꧁─꩜༺᪥༻꩜─꧂';
export function battleTime(real, internal) {
  if (real && Number.isFinite(Date.parse(real))) return new Date(real).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' }) + ' (به وقت تهران)';
  return internal ? String(internal).replace('T', ' ') + ' (زمان داخلی بازی؛ ساعت واقعی ثبت نشده)' : 'نامشخص';
}
// Narrative scale only; campaign travel times and game timers stay unchanged.
export function arrivalDelay(b, j) {
  const parseUtc = value => value ? Date.parse(/[zZ]$|[+-]\d{2}:?\d{2}$/.test(value) ? value : value + 'Z') : NaN;
  const realStart = parseUtc(b.started_at_real), realJoin = parseUtc(j.joined_at_real);
  const useReal = Number.isFinite(realStart) && Number.isFinite(realJoin);
  const start = useReal ? realStart : parseUtc(b.started_at);
  const joined = useReal ? realJoin : parseUtc(j.joined_at);
  if (!Number.isFinite(start) || !Number.isFinite(joined)) return 'تأخیر نامشخص';
  const minutes = Math.floor(Math.max(0, joined - start) / 60000 * 18);
  if (!minutes) return joined <= start ? 'بدون تأخیر به نبرد رسید' : 'با کمتر از یک دقیقه تأخیر به نبرد رسید';
  const hours = Math.floor(minutes / 60), remainder = minutes % 60;
  const duration = [hours ? `${fa(hours)} ساعت` : '', remainder ? `${fa(remainder)} دقیقه` : ''].filter(Boolean).join(' و ');
  return `با ${duration} تأخیر به نبرد رسید`;
}
export function arrivalText(b) {
  const rows = b.battle_joins?.length ? b.battle_joins : [...(b.attacker_joins || []), ...(b.defender_joins || [])];
  const dated = rows.filter(j => j.joined_at && Number.isFinite(Date.parse(j.joined_at))).sort((a, z) => Date.parse(a.joined_at) - Date.parse(z.joined_at));
  return [b.started_at ? `شروع نبرد: ${battleTime(b.started_at_real, b.started_at)}` : '', ...dated.map(j => `لشکر ${j.player_name || 'بی‌نام'} — ${b.multi_party ? 'طرف مستقل' : j.side === 'defender' ? 'مدافع' : 'مهاجم'}: ${battleTime(j.joined_at_real, j.joined_at)} | ${arrivalDelay(b, j)}`)].filter(Boolean).join('\n') || 'زمان ورود نیروها ثبت نشده است.';
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
  const defenders = b.defender_armies || [];
  const participants = new Map();
  for (const [armies, title] of [[attackers, 'مهاجم'], [defenders, 'مدافع']]) {
    for (const army of armies) {
      const key = army.tg_id != null ? `id:${army.tg_id}` : `name:${army.player_name || army.campaign_id}`;
      if (!participants.has(key)) participants.set(key, { armies: [], name: army.player_name || 'بی‌نام', sides: new Set() });
      participants.get(key).armies.push(army); participants.get(key).sides.add(title);
    }
  }
  // Count actual players, not armies: several armies owned by two players
  // must not turn a duel into a multiplayer report.
  const individual = participants.size > 2 ? `\n\n${divider}\n\nآمار هر لرد و لیدی\n\n` + [...participants.values()].map(p => side(p.armies, p.name, '👤', [...p.sides].join(' / '))).join('\n\n') : '';
  if (b.multi_party && b.parties?.length) {
    const armies = [...attackers, ...defenders];
    const parties = b.parties.map(p => side(armies.filter(a => a.tg_id === p.tg_id), p.player_name, '👤', 'طرف مستقل') +
      `\nدرگیر با: ${p.hostile_to.map(id => b.parties.find(x => x.tg_id === id)?.player_name || id).join('، ') || 'ندارد'}` +
      `\nپیمان صلح با: ${p.peace_with.map(id => b.parties.find(x => x.tg_id === id)?.player_name || id).join('، ') || 'ندارد'}`).join(`\n\n${divider}\n\n`);
    return `⚔️ نبرد چندطرفهٔ ${b.location || b.name || 'نامشخص'}\n📍 محل نبرد: ${b.location || 'نامشخص'}\n\n${divider}\n\n${parties}\n\n${divider}\n\n🗺 شرایط نبرد:\n${conditions.trim() || 'توسط ادمین اعلام می‌شود.'}\n\n${divider}\n\n⏳ زمان ارسال سناریو: ${deadline.trim() || 'مهلت توسط ادمین اعلام می‌شود.'}\nلردها و لیدی‌ها به زمان رسیدن نیروها توجه کنن.`;
  }
  return `⚔️ نبرد ${b.location || b.name || 'نامشخص'}\n📍 محل نبرد: ${b.location || 'نامشخص'}\n\n${divider}\n\n${side(attackers, b.attacker_name, '🗡', 'مهاجمین')}\n\n🆚\n${side(b.defender_armies || [], b.defender_name, '🛡', 'مدافعین')}${individual}\n\n${divider}\n\n🗺 شرایط نبرد:\n${conditions.trim() || 'توسط ادمین اعلام می‌شود.'}\n\n${divider}\n\n⏳ زمان ارسال سناریو: ${deadline.trim() || 'مهلت توسط ادمین اعلام می‌شود.'}\nلردها و لیدی‌ها به زمان رسیدن نیروها توجه کنن.`;
}
