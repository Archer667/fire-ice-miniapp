// The picture follows completed levels and the currently configured maximum.
export function wallArtStage(level, maxLevel) {
  const maximum = Number(maxLevel);
  const completed = Math.max(0, Number(level) || 0);
  if (!Number.isFinite(maximum) || maximum <= 0) return 1;
  if (completed * 3 >= maximum * 2) return 3;
  if (completed * 3 >= maximum) return 2;
  return 1;
}
const BUILDING_ART = new Set(['lumber_mill', 'stone_mine', 'iron_mine', 'gold_mine', 'market', 'village', 'farm', 'ranch', 'winery', 'warehouse', 'goods_warehouse', 'treasury', 'weapon_warehouse', 'camp_sword', 'camp_spear', 'camp_archer', 'camp_lcav', 'camp_hcav', 'armory_sword', 'armory_spear', 'armory_archer', 'armory_lcav', 'armory_hcav', 'siege_workshop', 'port', 'watchtower']);
const WALL_ART = ['wall-wood', 'wall-mixed', 'wall-stone'];
export function buildingArt(row) {
  const id = row.id === 'wall' ? WALL_ART[wallArtStage(row.level, row.max_level) - 1] : row.id;
  return row.id === 'wall' || BUILDING_ART.has(id) ? `/buildings/art/${id}.webp` : null;
}
