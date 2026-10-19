import assert from 'node:assert/strict';
import { battleExportText, arrivalText, arrivalDelay } from './src/battleExport.js';
const b = { location: 'ریورران', attacker_armies: [{player_name:'الف', troops:[{id:'spear',count:385},{id:'ship',count:2}], equipment:[{count:12}]}], defender_armies:[{player_name:'ب',troops:[{id:'spear',count:1172}]}] };
const out=battleExportText(b,['ship'],'هوای صاف','تا دو ظهر');
assert.ok(out.includes('۳۸۵ سرباز')); assert.ok(out.includes('۱٬۱۷۲ سرباز')); assert.ok(out.includes('۲ کشتی')); assert.ok(out.includes('۱۲ ادوات جنگی')); assert.ok(out.includes('فاقد ادوات جنگی')); assert.ok(out.includes('تا دو ظهر'));
assert.ok(!out.includes('undefined'));
const joins=arrivalText({...b,battle_joins:[{player_name:'دوم',joined_at:'2026-09-14T12:00:00Z'},{player_name:'اول',joined_at:'2026-09-14T08:00:00Z'}]});
assert.ok(joins.indexOf('اول') < joins.indexOf('دوم'));
assert.ok(battleExportText({...b,attacker_armies:[],attacker_army:b.attacker_armies[0]},['ship']).includes('۰ سرباز'));
console.log('Battle export totals, ships, empty sides, ordering and custom text passed');

const multi={...b,attacker_armies:[{...b.attacker_armies[0],tg_id:1},{tg_id:1,player_name:'الف',troops:[{id:'spear',count:15}],equipment:[]}],defender_armies:[{...b.defender_armies[0],tg_id:2},{tg_id:3,player_name:'ج',troops:[{id:'ship',count:5}]}]};
const individual=battleExportText(multi,['ship']);
assert.ok(individual.includes('آمار هر لرد و لیدی')); assert.ok(individual.includes('۴۰۰ سرباز'));
assert.equal(individual.split('👤 مهاجم: الف').length,2);
assert.ok(!battleExportText({...multi,defender_armies:[multi.defender_armies[0]]},['ship']).includes('آمار هر لرد و لیدی'));
const wall=arrivalText({started_at:'2026-09-12T17:00:00',started_at_real:'2026-09-14T20:58:00Z'});
assert.ok(wall.includes('تهران'));assert.ok(!wall.includes('ثبت نشده'));
console.log('Per-player aggregation and wall-clock display passed');

const start={started_at_real:'2026-09-14T21:00:00Z',started_at:'2026-09-12T18:43:59'};
assert.equal(arrivalDelay(start,{joined_at_real:'2026-09-14T21:10:00Z'}),'با ۳ ساعت تأخیر به نبرد رسید');
assert.equal(arrivalDelay(start,{joined_at_real:'2026-09-14T21:05:00Z'}),'با ۱ ساعت و ۳۰ دقیقه تأخیر به نبرد رسید');
assert.equal(arrivalDelay(start,{joined_at_real:'2026-09-14T21:00:00Z'}),'بدون تأخیر به نبرد رسید');
assert.equal(arrivalDelay(start,{joined_at_real:'2026-09-14T20:59:00Z'}),'بدون تأخیر به نبرد رسید');
assert.equal(arrivalDelay({},{}),'تأخیر نامشخص');
assert.equal(arrivalDelay(start,{joined_at:'2026-09-12T18:53:59'}),'با ۳ ساعت تأخیر به نبرد رسید');
assert.ok(arrivalText({...start,battle_joins:[{player_name:'دانل',joined_at:'2026-09-12T18:53:59',joined_at_real:'2026-09-14T21:10:00Z'}]}).includes('(به وقت تهران) | با ۳ ساعت تأخیر به نبرد رسید'));
console.log('Narrative arrival delays passed');

const detailedBattle={name:'آزمون',location:'روکزرست',attacker_armies:[
 {tg_id:1,name:'نیزه‌های شمال',player_name:'الف',troops:[{id:'spear',name:'نیزه‌دار',count:123},{id:'ship',name:'کشتی جنگی',count:4}],equipment:[{id:'ram',name:'دژکوب',count:3}]},
 {tg_id:1,name:'تیراندازان شمال',player_name:'الف',troops:[{id:'archer',name:'کماندار',count:80}],equipment:[]}
],defender_armies:[{tg_id:2,name:'دفاع قلعه',player_name:'ب',troops:[{id:'guard',name:'نگهبان',count:50}],equipment:[]}]};
const summary=battleExportText(detailedBattle,['ship'],'شرایط ویژه','مهلت نهایی');
const full=battleExportText(detailedBattle,['ship'],'شرایط ویژه','مهلت نهایی',{detailed:true});
assert(!summary.includes('نیزه‌دار:'));assert(full.includes('نیزه‌دار: ۱۲۳ نفر'));
assert(full.includes('کشتی جنگی: ۴ فروند'));assert(full.includes('دژکوب: ۳ دستگاه'));
assert(full.includes('کماندار: ۸۰ نفر'));assert(full.includes('نگهبان: ۵۰ نفر'));
assert(full.includes('۲۰۳ سرباز'));assert(!full.includes('۲۰۷ سرباز'));
assert(full.includes('بدون ادوات جنگی'));assert(full.includes('شرایط ویژه'));assert(full.includes('مهلت نهایی'));
const parties=battleExportText({...detailedBattle,multi_party:true,parties:[{tg_id:1,player_name:'الف',hostile_to:[2],peace_with:[]},{tg_id:2,player_name:'ب',hostile_to:[1],peace_with:[]}]},['ship'],'','',{detailed:true});
assert(parties.includes('طرف مستقل'));assert(parties.includes('کشتی جنگی: ۴ فروند'));assert(parties.includes('نگهبان: ۵۰ نفر'));
console.log('Summary/detail separation, per-army unit counts, ships, equipment and independent parties passed');
