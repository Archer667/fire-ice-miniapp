import { useEffect, useState } from 'react';
import { useGame } from './store.jsx';
import { initTelegram } from './telegram.js';
import { api } from './api.js';
import Onboarding from './pages/Onboarding.jsx';
import Pending from './pages/Pending.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Buildings from './pages/Buildings.jsx';
import War from './pages/War.jsx';
import Leaderboard from './pages/Leaderboard.jsx';
import Ravens from './pages/Ravens.jsx';
import Diplomacy from './pages/Diplomacy.jsx';
import Admin from './pages/Admin.jsx';
import Espionage from './pages/Espionage.jsx';
import Trade from './pages/Trade.jsx';
import Roleplay from './pages/Roleplay.jsx';
import Assets from './pages/Assets.jsx';
import Rumors from './pages/Rumors.jsx';
import Header from './components/Header.jsx';
import SideMenu from './components/SideMenu.jsx';
import NavBar from './components/NavBar.jsx';
import Toast from './components/Toast.jsx';

// ترتیب باید با NAV_ITEMS + EXTRA_PAGES در NavBar.jsx یکی باشد — هر صفحهٔ
// جدید همین‌جا و آنجا اضافه شود
const PAGES = [Dashboard, Buildings, War, Leaderboard, Ravens, Diplomacy, Admin, Espionage, Trade, Roleplay, Assets, Rumors];
const RAVENS_INDEX = 4;
const ADMIN_INDEX = 6;

export default function App() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

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
          <Header onOpenMenu={() => setMenuOpen(true)} onOpenRavens={() => setTab(RAVENS_INDEX)} />
          <div className="view" key={tab}>
            {me.pending && tab !== ADMIN_INDEX ? <Pending goTo={setTab} /> : <Page goTo={setTab} />}
          </div>
          <SideMenu open={menuOpen} tab={tab} onChange={setTab} onClose={() => setMenuOpen(false)} />
          <NavBar tab={tab} onChange={setTab} />
        </>
      )}
      <Toast />
    </div>
  );
}
