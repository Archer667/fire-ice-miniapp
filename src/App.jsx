import { useEffect, useState } from 'react';
import { useGame } from './store.jsx';
import { initTelegram, getTelegramUser } from './telegram.js';
import Onboarding from './pages/Onboarding.jsx';
import Dashboard from './pages/Dashboard.jsx';
import War from './pages/War.jsx';
import Leaderboard from './pages/Leaderboard.jsx';
import Chat from './pages/Chat.jsx';
import NavBar from './components/NavBar.jsx';
import Toast from './components/Toast.jsx';

const PAGES = [Dashboard, War, Leaderboard, Chat];

export default function App() {
  const { player, setPlayer } = useGame();
  const [tab, setTab] = useState(0);
  const [tgName, setTgName] = useState('');

  useEffect(() => {
    initTelegram();
    const u = getTelegramUser();
    if (u?.firstName) setTgName(u.firstName); // اسم واقعی از تلگرام
  }, []);

  const Page = PAGES[tab];

  return (
    <div className="app">
      {!player ? (
        <Onboarding defaultName={tgName} onDone={setPlayer} />
      ) : (
        <>
          <div className="pages">
            <div className="page" key={tab}>
              <Page goTo={setTab} />
            </div>
          </div>
          <NavBar tab={tab} onChange={setTab} />
        </>
      )}
      <Toast />
    </div>
  );
}
