const tg = window.Telegram?.WebApp;

export function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.setHeaderColor('#060913');
  tg.setBackgroundColor('#060913');
}

export const getInitData = () => tg?.initData || '';
export const getTgUser = () => tg?.initDataUnsafe?.user || null;
export const haptic = (t = 'light') => tg?.HapticFeedback?.impactOccurred?.(t);
