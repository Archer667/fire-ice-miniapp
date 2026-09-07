let snapshot = null;
let receivedAt = 0;
export function syncGameClock(state) {
  snapshot = state;
  receivedAt = performance.now();
  window.dispatchEvent(new CustomEvent('game-status', { detail: state }));
}
export function gameNow() {
  if (!snapshot) return Date.now();
  return Date.parse(snapshot.game_now) + (snapshot.paused ? 0 : performance.now() - receivedAt);
}
