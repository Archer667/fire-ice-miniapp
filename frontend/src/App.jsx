import { useEffect, useState } from 'react';
import { useGame } from './store.jsx';
import { initTelegram } from './telegram.js';
import { api } from './api.js';
import Onboarding from './pages/Onboarding.jsx';
import Dashboard from './pages/Dashboard.jsx';
import MapPage from './pages/MapPage.jsx';
import War from './pages/War.jsx';
import Leaderboard from './pages/Leaderboard.jsx';
import Ravens from './pages/Ravens.jsx';
import NavBar from './components/NavBar.jsx';
import Toast from './components/Toast.jsx';

const PAGES = [Dashboard, MapPage, War, Leaderboard, Ravens];

export default function App() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState(0);

  useEffect(() => {
    initTelegram();
    api.me().then(setMe).catch(e => { toast(e.message); setMe({ registered: false }); });
  }, []);

  if (me === null) {
    return <div className="shell"><div className="loading">کلاغ‌ها در راه‌اند...</div></div>;
  }

  const Page = PAGES[tab];
  return (
    <div className="shell">
      {!me.registered ? (
        <Onboarding />
      ) : (
        <>
          <div className="view" key={tab}><Page goTo={setTab} /></div>
          <NavBar tab={tab} onChange={setTab} />
        </>
      )}
      <Toast />
    </div>
  );
}
