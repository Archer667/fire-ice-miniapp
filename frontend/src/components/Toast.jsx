import { useGame } from '../store.jsx';
export default function Toast() {
  const { toastMsg, show, tweetAlert, dismissTweetAlert } = useGame();
  let start = 0;
  return <><div className={`tweet-alert ${tweetAlert ? 'show' : ''}`} onClick={dismissTweetAlert}
    onTouchStart={e => { start = e.touches[0].clientY; }} onTouchEnd={e => { if (Math.abs(e.changedTouches[0].clientY - start) > 20) dismissTweetAlert(); }}>
    {tweetAlert}<small>برای بستن، لمس یا به بالا/کنار بکش</small>
  </div><div className={`toast ${show ? 'show' : ''}`}>{toastMsg}</div></>;
}
