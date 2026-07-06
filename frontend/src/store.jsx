import { createContext, useContext, useState, useCallback } from 'react';

const Ctx = createContext(null);

export function GameProvider({ children }) {
  const [me, setMe] = useState(null);          // null = درحال بارگذاری
  const [toastMsg, setToastMsg] = useState('');
  const [show, setShow] = useState(false);

  const toast = useCallback((m) => {
    setToastMsg(m); setShow(true);
    setTimeout(() => setShow(false), 2600);
  }, []);

  return <Ctx.Provider value={{ me, setMe, toast, toastMsg, show }}>{children}</Ctx.Provider>;
}
export const useGame = () => useContext(Ctx);
