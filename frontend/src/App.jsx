import { useEffect, useState } from 'react';
import { useGame } from './store.jsx';
import { initTelegram, haptic } from './telegram.js';
import { api } from './api.js';
import Onboarding from './pages/Onboarding.jsx';
import Dashboard from './pages/Dashboard.jsx';
import MapPage from './pages/MapPage.jsx';
import War from './pages/War.jsx';
import Leaderboard from './pages/Leaderboard.jsx';
import Ravens from './pages/Ravens.jsx';
import Construction from './pages/Construction.jsx';
import NavBar from './components/NavBar.jsx';
import Toast from './components/Toast.jsx';
import Drawer from './components/Drawer.jsx';
import { Menu, Back } from './components/Icons.jsx';

const PAGES = [Dashboard, MapPage, War, Leaderboard, Ravens];
const EXTRA_PAGES = { construction: Construction };

export default function App() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState(0);
  const [extra, setExtra] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    initTelegram();
    api.me().then(setMe).catch(e => { toast(e.message); setMe({ registered: false }); });
  }, []);

  if (me === null) {
    return <div className="shell"><div className="loading">کلاغ‌ها در راه‌اند...</div></div>;
  }

  const Page = PAGES[tab];
  const ExtraPage = extra ? EXTRA_PAGES[extra] : null;

  return (
    <div className="shell">
      {me.registered && (
        <button className="menu-btn" onClick={() => { haptic(); setDrawerOpen(true); }}>
          <Menu />
        </button>
      )}
      {!me.registered ? (
        <Onboarding />
      ) : ExtraPage ? (
        <div className="view" key={extra}>
          <div className="back" onClick={() => setExtra(null)}><Back /> بازگشت</div>
          <ExtraPage />
        </div>
      ) : (
        <>
          <div className="view" key={tab}><Page goTo={setTab} /></div>
          <NavBar tab={tab} onChange={setTab} />
        </>
      )}
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}
              onOpenPage={(id) => { setExtra(id); setDrawerOpen(false); }} />
      <Toast />
    </div>
  );
}
