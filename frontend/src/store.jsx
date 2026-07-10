import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { api } from './api.js';

const Ctx = createContext(null);

export function GameProvider({ children }) {
  const [me, setMe] = useState(null);          // null = درحال بارگذاری
  const [toastMsg, setToastMsg] = useState('');
  const [show, setShow] = useState(false);
  const [unread, setUnread] = useState(0);

  const toast = useCallback((m) => {
    setToastMsg(m); setShow(true);
    setTimeout(() => setShow(false), 2600);
  }, []);

  const refreshUnread = useCallback(() => {
    api.ravensUnread().then(r => setUnread(r.count)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!me?.registered) return;
    refreshUnread();
    const id = setInterval(refreshUnread, 25000);
    return () => clearInterval(id);
  }, [me?.registered, refreshUnread]);

  return <Ctx.Provider value={{ me, setMe, toast, toastMsg, show, unread, refreshUnread }}>{children}</Ctx.Provider>;
}
export const useGame = () => useContext(Ctx);
