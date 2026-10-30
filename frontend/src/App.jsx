import {canOpenPage} from './characterAccess.js';
import './styles/living-pages.css';
import './styles/living-system.css';
import './styles/living-responsive.css';
import './styles/ui-coherence.css';
import Notifications from './pages/Notifications.jsx';
import CharacterProfile from './pages/CharacterProfile.jsx';
import { lazy, Suspense, useEffect, useState } from 'react';
import { useGame } from './store.jsx';
import { initTelegram } from './telegram.js';
import { api } from './api.js';
import Onboarding from './pages/Onboarding.jsx';
import Pending from './pages/Pending.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Buildings from './pages/Buildings.jsx';
import Leaderboard from './pages/Leaderboard.jsx';
import Ravens from './pages/Ravens.jsx';
import Espionage from './pages/Espionage.jsx';
import Roleplay from './pages/Roleplay.jsx';
import Assets from './pages/Assets.jsx';
import ItemStore from './pages/ItemStore.jsx';
import Family from './pages/Family.jsx';
import CharacterTravel from './pages/CharacterTravel.jsx';
import Support from './pages/Support.jsx';
import Header from './components/Header.jsx';
import SideMenu from './components/SideMenu.jsx';
import NavBar from './components/NavBar.jsx';
import Toast from './components/Toast.jsx';
import BackgroundMusic from './components/BackgroundMusic.jsx';
import { syncGameClock } from './gameClock.js';
import LivingScreen, { presentationFor } from './components/LivingScreen.jsx';

const War = lazy(() => import('./pages/War.jsx'));
const Diplomacy = lazy(() => import('./pages/Diplomacy.jsx'));
const Admin = lazy(() => import('./pages/Admin.jsx'));
const Trade = lazy(() => import('./pages/Trade.jsx'));
const Institutions = lazy(() => import('./pages/Institutions.jsx'));
const PlayerGuide = lazy(() => import('./pages/PlayerGuide.jsx'));
const Contracts = lazy(() => import('./pages/SocialWorld.jsx'));
const CastleLife = lazy(() => import('./pages/SocialWorld.jsx').then(module => ({default: module.CastleLife})));
const Newspaper = lazy(() => import('./pages/SocialWorld.jsx').then(module => ({default: module.Newspaper})));

// ترتیب باید با NAV_ITEMS + EXTRA_PAGES در NavBar.jsx یکی باشد — هر صفحهٔ
// جدید همین‌جا و آنجا اضافه شود
const PAGES = [Dashboard, Buildings, War, Leaderboard, Ravens, Diplomacy, Admin, Espionage, Trade, Roleplay, Assets, Family, CharacterProfile, Institutions, CharacterTravel, ItemStore, Notifications, Contracts, CastleLife, Newspaper, PlayerGuide, Support];
const RAVENS_INDEX = 16;
const ADMIN_INDEX = 6;

export default function App() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [pauseState, setPauseState] = useState(null);
  useEffect(() => {
    const onStatus = e => setPauseState(e.detail);
    window.addEventListener('game-status', onStatus);
    const refresh = () => api.gameStatus().then(syncGameClock).catch(() => {});
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => { clearInterval(timer); window.removeEventListener('game-status', onStatus); };
  }, []);

  useEffect(() => {
    initTelegram();
    api.me().then(setMe).catch(e => { toast(e.message); setMe({ registered: false }); });
  }, []);

  // ادمین‌ها بازیکن نیستند و عمداً قلعه/اقلیم ندارند. بک‌اند برای جلوگیری از
  // ورودشان به صفحات بازیکنی pending برمی‌گرداند؛ پس به‌جای نمایش صفحهٔ
  // «منتظر تأیید»، مستقیماً پنل مدیریت را باز می‌کنیم.
  useEffect(() => {
    if (me?.admin_role && me?.pending) setTab(ADMIN_INDEX);
  }, [me?.admin_role, me?.pending]);

  useEffect(() => {
    const onDeath = () => api.me().then(setMe).catch(() => {});
    window.addEventListener('player-dead', onDeath);
    return () => window.removeEventListener('player-dead', onDeath);
  }, []);

  if (me === null) {
    return <div className="shell"><div className="loading">کلاغ‌ها در راه‌اند...</div></div>;
  }

  if (me.is_dead) {
    return <div className="shell" dir="rtl"><div className="card death-screen">
      <div style={{ fontSize: 48 }}>⚔️</div><h1>کشته شد</h1>
      <p>{me.name}، داستان این شخصیت به پایان رسید.</p>
      <p>{me.death_reason}</p><p>برای درخواست شخصیت تازه، ادمین باید «حذف از خاندان» را انجام دهد.</p>
      <button className="btn ghost" onClick={() => api.me().then(setMe).catch(e => toast(e.message))}>بررسی وضعیت</button>
    </div><Toast /></div>;
  }
  const Page = !canOpenPage(me, tab) ? CharacterTravel : PAGES[tab];
  const presentation = presentationFor(tab);
  const showPauseBanner = Boolean(pauseState?.paused && me.registered && !me.pending && !me.admin_role && tab !== ADMIN_INDEX);
  return (
    <div className={`shell living-shell living-shell-${presentation.slug} ${showPauseBanner ? 'game-paused' : ''}`}>
      {showPauseBanner && <aside className="game-pause-banner" role="status"><strong>⏸ بازی موقتاً متوقف شده است</strong><p>{tab === 15 ? 'فروشگاه آیتم‌ها و مزایده‌ها با زمان واقعی فعال‌اند. اعتبار زمانی آیتم‌ها همچنان از ساعت بازی پیروی می‌کند.' : 'مشاهدهٔ صفحات آزاد است؛ زمان بازی، تولید، مصرف و محاسبات دوره‌ای متوقف‌اند. فروشگاه آیتم‌ها با زمان واقعی فعال می‌ماند.'}</p><p>دلیل توقف: {pauseState.reason}</p></aside>}
      {!me.registered ? (
        <Onboarding />
      ) : (
        <>
          <Header onOpenMenu={() => setMenuOpen(true)} onOpenRavens={() => setTab(RAVENS_INDEX)} />
          <div className={`view living-view living-view-${presentation.slug}`} key={tab}>
            {me.pending && !me.admin_role && ![ADMIN_INDEX,16].includes(tab) ? <Pending goTo={setTab} /> : <Suspense fallback={<div className="loading">در حال آماده‌کردن صفحه…</div>}><LivingScreen index={tab}><Page goTo={setTab} /></LivingScreen></Suspense>}
          </div>
          <SideMenu open={menuOpen} tab={tab} onChange={setTab} onClose={() => setMenuOpen(false)} />
          <NavBar tab={tab} onChange={setTab} />
          <BackgroundMusic />
        </>
      )}
      <Toast />
    </div>
  );
}
