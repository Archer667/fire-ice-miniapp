import assert from 'node:assert/strict';
import { battleExportText, arrivalText } from './src/battleExport.js';
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
