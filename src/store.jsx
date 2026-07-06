import { createContext, useContext, useState, useCallback } from 'react';

// ---- دیتای اولیه (بعداً از Backend می‌آید) ----
export const HOUSES = [
  { id: 'stark',     name: 'استارک',   sigil: '🐺', seat: 'وینترفل · شمال' },
  { id: 'lannister', name: 'لنیستر',   sigil: '🦁', seat: 'کسترلی‌راک' },
  { id: 'targaryen', name: 'تارگرین',  sigil: '🐉', seat: 'دراگون‌استون' },
  { id: 'baratheon', name: 'باراتیون', sigil: '🦌', seat: 'استورمز اند' },
  { id: 'tyrell',    name: 'تایرل',    sigil: '🌹', seat: 'های‌گاردن' },
  { id: 'greyjoy',   name: 'گریجوی',   sigil: '🦑', seat: 'پایک' },
];

const GameCtx = createContext(null);

export function GameProvider({ children }) {
  const [player, setPlayer] = useState(null); // { name, house }
  const [resources, setResources] = useState({
    gold:  { val: 1250, max: 2000, icon: '🪙', name: 'طلا',           color: 'linear-gradient(90deg,#ffd54f,#ff8f00)' },
    food:  { val: 500,  max: 2000, icon: '🌾', name: 'غذا',           color: 'linear-gradient(90deg,#aed581,#558b2f)' },
    men:   { val: 800,  max: 1000, icon: '🧑‍🌾', name: 'نیروی انسانی', color: 'linear-gradient(90deg,#81d4fa,#0288d1)' },
    iron:  { val: 150,  max: 500,  icon: '⛏️', name: 'آهن',           color: 'linear-gradient(90deg,#b0bec5,#546e7a)' },
    wood:  { val: 325,  max: 500,  icon: '🪵', name: 'چوب',           color: 'linear-gradient(90deg,#bcaaa4,#6d4c41)' },
  });
  const [day] = useState(18);
  const [toastMsg, setToastMsg] = useState('');
  const [toastVisible, setToastVisible] = useState(false);

  const toast = useCallback((msg) => {
    setToastMsg(msg);
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 2400);
  }, []);

  // خرج کردن طلا — منبع حقیقت واحد؛ همه صفحات خودکار آپدیت می‌شوند
  const spendGold = useCallback((amount) => {
    let ok = false;
    setResources(prev => {
      if (prev.gold.val < amount) return prev;
      ok = true;
      return { ...prev, gold: { ...prev.gold, val: prev.gold.val - amount } };
    });
    return ok;
  }, []);

  const value = { player, setPlayer, resources, spendGold, day, toast, toastMsg, toastVisible };
  return <GameCtx.Provider value={value}>{children}</GameCtx.Provider>;
}

export const useGame = () => useContext(GameCtx);
