// اتصال به Telegram Mini App SDK
// وقتی داخل تلگرام اجرا شود، اطلاعات واقعی کاربر را می‌گیرد
// وقتی در مرورگر معمولی باز شود، حالت توسعه (mock) فعال می‌شود

const tg = window.Telegram?.WebApp;

export function initTelegram() {
  if (!tg) return null;
  tg.ready();          // به تلگرام بگو اپ آماده است
  tg.expand();         // تمام‌صفحه شو
  tg.setHeaderColor('#0a0e1a');
  tg.setBackgroundColor('#0a0e1a');
  return tg;
}

export function getTelegramUser() {
  const u = tg?.initDataUnsafe?.user;
  if (!u) return null;
  return {
    id: u.id,
    firstName: u.first_name || '',
    username: u.username || '',
  };
}

// لرزش لمسی (Haptic) — فقط داخل تلگرام کار می‌کند
export function haptic(type = 'light') {
  tg?.HapticFeedback?.impactOccurred?.(type);
}
