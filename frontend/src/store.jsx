import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { api } from './api.js';

const Ctx = createContext(null);

export function GameProvider({ children }) {
  const [me, setMe] = useState(null);          // null = درحال بارگذاری
  const [seasonBranding, setSeasonBranding] = useState({ number: 1, name: '', revision: 0, title: 'والریا' });
  useEffect(() => {
    let active = true;
    const refresh = () => {
      if (document.hidden) return;
      api.seasonBranding().then(value => { if (active) setSeasonBranding(current => value.revision >= current.revision ? value : current); }).catch(() => {});
    };
    refresh();
    const timer = setInterval(refresh, 60000);
    document.addEventListener('visibilitychange', refresh);
    return () => { active = false; clearInterval(timer); document.removeEventListener('visibilitychange', refresh); };
  }, []);
  useEffect(() => { document.title = seasonBranding.title; }, [seasonBranding.title]);
  const [toastMsg, setToastMsg] = useState('');
  const [show, setShow] = useState(false);
  const [unread, setUnread] = useState(0);
  const [unreadBreakdown, setUnreadBreakdown] = useState({ announcements: 0, messages: 0, rumors: 0 });
  const [tweetAlert, setTweetAlert] = useState(null);
  const lastTweetId = useRef(null);
  const lastMessageId = useRef(null);
  const alertTimer = useRef(null);

  const showGreenAlert = useCallback((message) => {
    if (alertTimer.current) clearTimeout(alertTimer.current);
    setTweetAlert(message);
    alertTimer.current = setTimeout(() => setTweetAlert(null), 5000);
  }, []);

  const toast = useCallback((m) => {
    setToastMsg(m); setShow(true);
    setTimeout(() => setShow(false), 2600);
  }, []);

  const refreshUnread = useCallback(() => {
    api.ravensUnread().then(r => {
      if (r.rumors > 0 && r.latest_rumor_id && r.latest_rumor_id !== lastTweetId.current) {
        lastTweetId.current = r.latest_rumor_id;
        showGreenAlert(`توییت جدید دربارهٔ ${r.latest_rumor_target || 'یکی از لردها'}`);
      }
      if (r.messages > 0 && r.latest_message_id && r.latest_message_id !== lastMessageId.current) {
        lastMessageId.current = r.latest_message_id;
        showGreenAlert(`نامهٔ جدید از ${r.latest_message_from || 'یکی از بازیکنان'}`);
      }
      setUnread(r.count || 0);
      setUnreadBreakdown({
        announcements: r.announcements || 0,
        messages: r.messages || 0,
        rumors: r.rumors || 0,
      });
    }).catch(() => {});
  }, [showGreenAlert]);

  useEffect(() => {
    if (!me?.registered) return;
    refreshUnread();
    const id = setInterval(refreshUnread, 25000);
    return () => clearInterval(id);
  }, [me?.registered, refreshUnread]);

  return <Ctx.Provider value={{ me, setMe, seasonBranding, setSeasonBranding, toast, toastMsg, show, unread, unreadBreakdown, refreshUnread, tweetAlert, dismissTweetAlert: () => setTweetAlert(null) }}>{children}</Ctx.Provider>;
}
export const useGame = () => useContext(Ctx);
