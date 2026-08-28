import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { api } from './api.js';

const Ctx = createContext(null);

export function GameProvider({ children }) {
  const [me, setMe] = useState(null);          // null = درحال بارگذاری
  const [toastMsg, setToastMsg] = useState('');
  const [show, setShow] = useState(false);
  const [unread, setUnread] = useState(0);
  const [unreadBreakdown, setUnreadBreakdown] = useState({ announcements: 0, messages: 0, rumors: 0 });
  const [tweetAlert, setTweetAlert] = useState(null);
  const lastTweetId = useRef(null);

  const toast = useCallback((m) => {
    setToastMsg(m); setShow(true);
    setTimeout(() => setShow(false), 2600);
  }, []);

  const refreshUnread = useCallback(() => {
    api.ravensUnread().then(r => {
      if (r.rumors > 0 && r.latest_rumor_id && r.latest_rumor_id !== lastTweetId.current) {
        lastTweetId.current = r.latest_rumor_id;
        setTweetAlert(`توییت جدید دربارهٔ ${r.latest_rumor_target || 'یکی از لردها'}`);
        setTimeout(() => setTweetAlert(null), 5000);
      }
      setUnread(r.count || 0);
      setUnreadBreakdown({
        announcements: r.announcements || 0,
        messages: r.messages || 0,
        rumors: r.rumors || 0,
      });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!me?.registered) return;
    refreshUnread();
    const id = setInterval(refreshUnread, 25000);
    return () => clearInterval(id);
  }, [me?.registered, refreshUnread]);

  return <Ctx.Provider value={{ me, setMe, toast, toastMsg, show, unread, unreadBreakdown, refreshUnread, tweetAlert, dismissTweetAlert: () => setTweetAlert(null) }}>{children}</Ctx.Provider>;
}
export const useGame = () => useContext(Ctx);
