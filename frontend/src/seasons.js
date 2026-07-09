// هر دوره ۳۰ روزه = دقیقاً دو چرخهٔ ۱۵روزهٔ فصلی؛ بازی درست وسط زمستانِ دوم تمام می‌شود
export const CYCLE_DAYS = 15;

export const SEASONS = {
  spring: { name: 'بهار', from: '#34d399', to: '#22c55e' },
  summer: { name: 'تابستان', from: '#fbbf24', to: '#f59e0b' },
  autumn: { name: 'پاییز', from: '#fb923c', to: '#ea580c' },
  winter: { name: 'زمستان', from: '#38bdf8', to: '#4da3ff' },
};

export function seasonOf(day) {
  const dayInCycle = ((day - 1) % CYCLE_DAYS) + 1;
  if (dayInCycle <= 4) return 'spring';
  if (dayInCycle <= 8) return 'summer';
  if (dayInCycle <= 12) return 'autumn';
  return 'winter';
}

export function dayInCycleOf(day) {
  return ((day - 1) % CYCLE_DAYS) + 1;
}
