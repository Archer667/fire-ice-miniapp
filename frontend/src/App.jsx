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

function DebugBanner() {
  const tg = window.Telegram?.WebApp;
  const info = [
    'platform=' + tg?.platform,
    'version=' + tg?.version,
    'initDataLen=' + (tg?.initData?.length ?? 'undefined'),
  ].join(' | ');
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 99999,
      background: '#ff0', color: '#000', fontSize: 11, padding: '4px 6px',
      wordBreak: 'break-all', fontFamily: 'monospace', direction: 'ltr', textAlign: 'left',
    }}>
      DEBUG: {info}
    </div>
  );
}

export default function App() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState(0);

  useEffect(() => {
    initTelegram();
    api.me().then(setMe).catch(e => { toast(e.message); setMe({ registered: false }); });
  }, []);

  if (me === null) {
    return <div className="shell"><DebugBanner /><div className="loading">کلاغ‌ها در راه‌اند...</div></div>;
  }

  const Page = PAGES[tab];
  return (
    <div className="shell">
      <DebugBanner />
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
