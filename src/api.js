// وقتی Backend آماده شد، فقط این فایل عوض می‌شود — بقیه اپ دست نمی‌خورد

const MOCK_LEADERBOARD = [
  { rank: 1, sigil: '🐉', name: 'دنریس تارگرین',  pts: 2380 },
  { rank: 2, sigil: '🦁', name: 'تایوین لنیستر',   pts: 2140 },
  { rank: 3, sigil: '🌹', name: 'مارگری تایرل',    pts: 1990 },
  { rank: 4, sigil: '🐺', name: 'تو',              pts: 1820, me: true },
  { rank: 5, sigil: '🦌', name: 'استنیس باراتیون', pts: 1765 },
  { rank: 6, sigil: '🦑', name: 'یارا گریجوی',     pts: 1610 },
  { rank: 7, sigil: '☀️', name: 'اوبرین مارتل',    pts: 1495 },
  { rank: 8, sigil: '🦅', name: 'لیسا ارین',       pts: 1320 },
];

const MOCK_MESSAGES = [
  { who: '🦁 تایوین لنیستر', text: 'لنیستر همیشه بدهی‌اش را می‌پردازد. شمال هم استثنا نیست.', me: false },
  { who: '🐉 دنریس تارگرین', text: 'با آتش و خون پس می‌گیرم آنچه از آنِ من است.', me: false },
  { who: '🌹 مارگری تایرل', text: 'شاید بهتر باشد به‌جای شمشیر، سرِ میز مذاکره بنشینیم؟', me: false },
  { who: '🦑 یارا گریجوی', text: 'آنچه مرده است هرگز نمی‌میرد ⚓', me: false },
];

export async function fetchLeaderboard() {
  return MOCK_LEADERBOARD;
}

export async function fetchMessages() {
  return MOCK_MESSAGES;
}

export async function submitScenario(data) {
  console.log('scenario =>', data);
  return { ok: true };
}
