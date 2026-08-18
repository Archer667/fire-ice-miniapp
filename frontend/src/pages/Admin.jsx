import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Shield, Eye, Scroll, Plus, Close, Coin, Wood, Rock, Pick, Wheat, Wine, People, Warehouse, Swords } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import CastlePicker from '../components/CastlePicker.jsx';
import { MapFrame } from '../components/WesterosMap.jsx';
import ZoomPanMap from '../components/ZoomPanMap.jsx';
import { WARDEN_GROUPS, REGIONS_STATIC, TRADE_GOODS, TRADE_GOOD_NAMES, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, ITEM_RARITY_HEX, WEAPON_NAMES, MAP_TERRAINS, castleLabel } from '../gamedata.js';

const NEW_CASTLE = '__new__';

const SPECIAL_MEDAL_PRESETS = [
  { key: 'season_champion', name: 'قهرمان فصل', icon: '🏆' },
  { key: 'realm_savior', name: 'ناجی قلمرو', icon: '🛡️' },
  { key: 'immortal', name: 'نامیرا', icon: '♾️' },
  { key: 'golden_quill', name: 'صاحب قلم زرین', icon: '✒️' },
  { key: 'crown_enemy', name: 'دشمن تاج', icon: '⚔️' },
];

const MAP_KINDS = [
  { key: 'castle', label: 'قلعه' },
  { key: 'city',   label: 'شهر' },
  { key: 'ruin',   label: 'مخروبه' },
  { key: 'port',   label: 'بندر ⚓' },
];

// دسته‌های تب‌ها فقط برای نمایشِ گروه‌بندی‌شده‌ترِ نوار تب‌هاست
const TAB_GROUPS = [
  {
    label: 'بازیکن‌ها',
    tabs: [
      { key: 'onboarding', label: 'خاندان‌ها' },
      { key: 'resources',  label: 'منابع و لشکرها', fullOnly: true },
      { key: 'admins',     label: 'ادمین‌ها', fullOnly: true },
    ],
  },
  {
    label: 'رویدادها',
    tabs: [
      { key: 'war',       label: 'جنگ و رول‌ها' },
      { key: 'alliances', label: 'اتحادها' },
      { key: 'titles',    label: 'مقام‌ها' },
      { key: 'polls',     label: 'رای‌گیری', fullOnly: true },
      { key: 'events', label: 'ایونت' },
    ],
  },
  {
    label: 'ابزارهای ادمین',
    tabs: [
      { key: 'medals',       label: 'مدال‌ها' },
      { key: 'bot_messages', label: 'پیام بات' },
    ],
  },
  {
    label: 'دنیای بازی',
    tabs: [
      { key: 'map',     label: 'نقشه' },
      { key: 'market',  label: 'بازار', fullOnly: true },
      { key: 'items',   label: 'آیتم‌ها', fullOnly: true },
      { key: 'balance', label: 'تعادل بازی', fullOnly: true },
    ],
  },
];
const TABS = TAB_GROUPS.flatMap(g => g.tabs);

const PLAYER_RES = [
  { key: 'gold',  label: 'طلا',  Icon: Coin },
  { key: 'wood',  label: 'چوب',  Icon: Wood },
  { key: 'stone', label: 'سنگ',  Icon: Rock },
  { key: 'iron',  label: 'آهن',  Icon: Pick },
  { key: 'food',  label: 'غذا',  Icon: Wheat },
  { key: 'wine',  label: 'شراب', Icon: Wine },
  { key: 'men',   label: 'نیروی انسانی', Icon: People },
  ...Object.entries(WEAPON_NAMES).map(([key, label]) => ({ key, label, Icon: Swords })),
];
const RES_LABEL = Object.fromEntries(PLAYER_RES.map(r => [r.key, r.label]));

export default function Admin() {
  const { me, toast } = useGame();
  const isFull = me.admin_role === 'full';
  const availGroups = TAB_GROUPS.map(g => ({ ...g, tabs: g.tabs.filter(t => !t.fullOnly || isFull) })).filter(g => g.tabs.length);
  const [tab, setTab] = useState('onboarding');

  const [pendingPlayers, setPendingPlayers] = useState(null);
  const [roster, setRoster] = useState(null);
  const [assignRegion, setAssignRegion] = useState({}); // tg_id -> regionId
  const [assignCastle, setAssignCastle] = useState({}); // tg_id -> castle name
  const [assignBusyId, setAssignBusyId] = useState(null);
  const [unassignBusyId, setUnassignBusyId] = useState(null);
  const [deletePendingBusyId, setDeletePendingBusyId] = useState(null);
  const [reassignOpenId, setReassignOpenId] = useState(null);
  const [addCastleOpenId, setAddCastleOpenId] = useState(null);
  const [addCastleValue, setAddCastleValue] = useState([]); // CastlePicker می‌خواد آرایه باشه — همیشه حداکثر یک‌دونه
  const [addCastleBusyId, setAddCastleBusyId] = useState(null);
  const [removeCastleBusyKey, setRemoveCastleBusyKey] = useState(null); // `${tgId}:${castle}`

  const [warSubTab, setWarSubTab] = useState('campaigns'); // 'campaigns' | 'espionage' | 'roleplay'
  const [campaignsInfo, setCampaignsInfo] = useState(null);
  const [disbandBusyId, setDisbandBusyId] = useState(null);
  const [warWindow, setWarWindow] = useState(null);
  const [warWindowBusy, setWarWindowBusy] = useState(false);
  const [eventTitle, setEventTitle] = useState('');
  const [eventDescription, setEventDescription] = useState('');
  const [eventBusy, setEventBusy] = useState(false);
  const [botMessage, setBotMessage] = useState('');
  const [botAudience, setBotAudience] = useState('all');
  const [botTargets, setBotTargets] = useState([]);
  const [botMessageBusy, setBotMessageBusy] = useState(false);
  const [medalTarget, setMedalTarget] = useState([]);
  const [medalTier, setMedalTier] = useState('bronze');
  const [medalReason, setMedalReason] = useState('');
  const [medalBusy, setMedalBusy] = useState(false);
  const [specialMedalTarget, setSpecialMedalTarget] = useState([]);
  const [specialMedalPreset, setSpecialMedalPreset] = useState('season_champion');
  const [specialMedalName, setSpecialMedalName] = useState('');
  const [specialMedalIcon, setSpecialMedalIcon] = useState('');
  const [specialMedalTier, setSpecialMedalTier] = useState('gold');
  const [specialMedalReason, setSpecialMedalReason] = useState('');
  const [specialMedalBusy, setSpecialMedalBusy] = useState(false);
  const [alliancesList, setAlliancesList] = useState(null);
  const [dissolveBusyId, setDissolveBusyId] = useState(null);
  const [spyResolved, setSpyResolved] = useState(null);
  const [spyResultsView, setSpyResultsView] = useState('pending'); // 'pending' | 'resolved'
  const [overlordTarget, setOverlordTarget] = useState([]);
  const [overlordRegion, setOverlordRegion] = useState('north');
  const [wardenTarget, setWardenTarget] = useState([]);
  const [wardenGroup, setWardenGroup] = useState('south');
  const [kingTarget, setKingTarget] = useState([]);
  const [epithetTarget, setEpithetTarget] = useState([]);
  const [epithetText, setEpithetText] = useState('');
  const [pollQuestion, setPollQuestion] = useState('');
  const [pollOptions, setPollOptions] = useState(['', '']);
  const [pollEligible, setPollEligible] = useState([]);
  const [polls, setPolls] = useState(null);
  const [admins, setAdmins] = useState(null);
  const [newAdminTarget, setNewAdminTarget] = useState([]);
  const [resetPreview, setResetPreview] = useState(null);
  const [resetConfirmText, setResetConfirmText] = useState('');
  const [resetBusy, setResetBusy] = useState(false);

  const [mapRegion, setMapRegion] = useState('north');
  const [mapData, setMapData] = useState(null);
  const [mapError, setMapError] = useState(false);
  const [mapOptions, setMapOptions] = useState(null);
  const [pendingPin, setPendingPin] = useState(null); // {x,y}
  const [pickName, setPickName] = useState('');
  const [castleQuery, setCastleQuery] = useState('');
  const [castleResultsOpen, setCastleResultsOpen] = useState(false);
  const [newCastleName, setNewCastleName] = useState('');
  const [pinKind, setPinKind] = useState('castle');
  const [pinTerrain, setPinTerrain] = useState('land');
  const [editingCastle, setEditingCastle] = useState(null);
  const [editKind, setEditKind] = useState('castle');
  const [editTerrain, setEditTerrain] = useState('land');

  const [marketListings, setMarketListings] = useState(null);
  const [marketResource, setMarketResource] = useState(TRADE_GOODS[0]);
  const [marketQty, setMarketQty] = useState('');
  const [marketPrice, setMarketPrice] = useState('');
  const [blackListings, setBlackListings] = useState(null);
  const [blackResource, setBlackResource] = useState(TRADE_GOODS[0]);
  const [blackQty, setBlackQty] = useState('');
  const [blackPrice, setBlackPrice] = useState('');
  const [blackHours, setBlackHours] = useState('6');

  const [resTarget, setResTarget] = useState([]);
  const [resValues, setResValues] = useState(null);
  const [resBusy, setResBusy] = useState(false);
  const [resCampaigns, setResCampaigns] = useState(null);

  const [spyPending, setSpyPending] = useState(null);
  const [spyScores, setSpyScores] = useState({}); // missionId -> score string
  const [spyBusyId, setSpyBusyId] = useState(null);

  const [roleplayPending, setRoleplayPending] = useState(null);
  const [roleplayResults, setRoleplayResults] = useState({}); // roleplayId -> result text
  const [roleplayVisibility, setRoleplayVisibility] = useState({}); // roleplayId -> 'participants' | 'all'
  const [roleplayOtherLords, setRoleplayOtherLords] = useState({}); // roleplayId -> [{tg_id, name}]
  const [roleplayWinners, setRoleplayWinners] = useState({}); // roleplayId -> winner tg_id
  const [roleplayBusyId, setRoleplayBusyId] = useState(null);

  const [itemsList, setItemsList] = useState(null);
  const [itemName, setItemName] = useState('');
  const [itemType, setItemType] = useState(Object.keys(ITEM_TYPES)[0]);
  const [itemDuration, setItemDuration] = useState(Object.keys(ITEM_DURATIONS)[0]);
  const [itemDurationHours, setItemDurationHours] = useState('24');
  const [itemDescription, setItemDescription] = useState('');
  const [itemBusy, setItemBusy] = useState(false);
  const [grantOpenId, setGrantOpenId] = useState(null);
  const [grantTarget, setGrantTarget] = useState([]);
  const [grantColor, setGrantColor] = useState(Object.keys(ITEM_RARITY_COLORS)[0]);
  const [grantBusy, setGrantBusy] = useState(false);

  const [balanceList, setBalanceList] = useState(null);
  const [balanceDrafts, setBalanceDrafts] = useState({}); // buildingId -> { resourceKey: stringValue }
  const [balanceBusyId, setBalanceBusyId] = useState(null);

  const loadPendingPlayers = () => api.adminListPendingPlayers().then(setPendingPlayers).catch(e => toast(e.message));
  const loadRoster = () => api.adminListRoster().then(setRoster).catch(e => toast(e.message));
  const loadCampaigns = () => api.adminCampaigns().then(setCampaignsInfo).catch(e => toast(e.message));
  const loadWarWindow = () => api.adminGetWarWindow().then(setWarWindow).catch(e => toast(e.message));
  const loadSpyPending = () => api.adminSpyPending().then(setSpyPending).catch(e => toast(e.message));
  const loadSpyResolved = () => api.adminSpyResolved().then(setSpyResolved).catch(e => toast(e.message));
  const loadRoleplayPending = () => api.adminRoleplayPending().then(setRoleplayPending).catch(e => toast(e.message));
  const loadAlliances = () => api.adminListAlliances().then(setAlliancesList).catch(e => toast(e.message));
  const loadPolls = () => api.polls().then(setPolls).catch(e => toast(e.message));
  const loadAdmins = () => api.adminListAdmins().then(setAdmins).catch(e => toast(e.message));
  const loadResetPreview = () => api.adminResetGamePreview().then(setResetPreview).catch(e => toast(e.message));
  const loadMapData = () => { setMapError(false); api.map().then(setMapData).catch(e => { toast(e.message); setMapError(true); }); };
  const loadMapOptions = () => api.adminMapOptions(mapRegion).then(setMapOptions).catch(e => toast(e.message));
  const loadMarket = () => api.adminMarketList().then(setMarketListings).catch(e => toast(e.message));
  const loadBlackMarket = () => api.adminBlackMarketList().then(setBlackListings).catch(e => toast(e.message));
  const loadItems = () => api.adminListItems().then(setItemsList).catch(e => toast(e.message));
  const loadBalance = () => api.adminGetBuildingBalance().then(list => {
    setBalanceList(list);
    setBalanceDrafts(prev => {
      const next = { ...prev };
      for (const b of list) {
        if (next[b.id]) continue;
        next[b.id] = {
          ...Object.fromEntries(Object.keys(b.base_produces).map(k => [k, String(b.produces[k] ?? '')])),
          ...Object.fromEntries(Object.keys(b.base_cap_bonus).map(k => [k, String(b.cap_bonus[k] ?? '')])),
        };
      }
      return next;
    });
  }).catch(e => toast(e.message));

  useEffect(() => {
    loadPendingPlayers();
    loadRoster();
    loadCampaigns();
    loadWarWindow();
    loadSpyPending();
    loadSpyResolved();
    loadRoleplayPending();
    loadAlliances();
    loadMapData();
    if (isFull) { loadPolls(); loadAdmins(); loadMarket(); loadBlackMarket(); loadItems(); loadBalance(); }
    if (me.is_owner) loadResetPreview();
  }, []);

  useEffect(() => {
    loadMapOptions();
    resetCastlePicker();
    setEditingCastle(null);
  }, [mapRegion]);

  useEffect(() => {
    if (!resTarget.length) { setResValues(null); setResCampaigns(null); return; }
    setResValues(null); setResCampaigns(null);
    api.adminGetPlayerResources(resTarget[0].tg_id)
      .then(r => setResValues(r.resources))
      .catch(e => { toast(e.message); setResTarget([]); });
    api.adminPlayerCampaigns(resTarget[0].tg_id).then(setResCampaigns).catch(e => toast(e.message));
  }, [resTarget]);

  const filteredCastleOptions = (mapOptions || []).filter(o =>
    !castleQuery.trim() || o.name.includes(castleQuery.trim())
  );

  const pickCastle = (name) => {
    haptic();
    setPickName(name); setCastleQuery(name); setCastleResultsOpen(false);
    const o = (mapOptions || []).find(o => o.name === name);
    setPinKind(o?.kind || 'castle');
    setPinTerrain(o?.terrain || 'land');
  };
  const pickNewCastle = () => {
    haptic();
    setPickName(NEW_CASTLE); setNewCastleName(castleQuery.trim()); setCastleResultsOpen(false);
    setPinKind('castle'); setPinTerrain('land');
  };

  const resetCastlePicker = () => {
    setPendingPin(null); setPickName(''); setCastleQuery(''); setCastleResultsOpen(false);
    setNewCastleName(''); setPinKind('castle'); setPinTerrain('land');
  };

  const addMapCastle = async () => {
    if (!pendingPin) return;
    if (!pickName) { toast('یک قلعه/شهر را انتخاب کن'); return; }
    const body = { region: mapRegion, x: pendingPin.x, y: pendingPin.y, kind: pinKind, terrain: pinTerrain };
    if (pickName === NEW_CASTLE) {
      if (!newCastleName.trim()) { toast('نام قلعه/شهر تازه را بنویس'); return; }
      body.new_name = newCastleName.trim();
    } else {
      body.name = pickName;
    }
    try {
      await api.adminAddMapCastle(body);
      haptic('medium');
      toast('قلعه/شهر به نقشه اضافه شد');
      resetCastlePicker();
      loadMapData(); loadMapOptions();
    } catch (e) { toast(e.message); }
  };

  const deleteMapCastle = async (name) => {
    try {
      await api.adminDeleteMapCastle(name);
      haptic('medium');
      toast(`نشانهٔ «${name}» از نقشه حذف شد`);
      loadMapData(); loadMapOptions();
    } catch (e) { toast(e.message); }
  };

  const startEditMapCastle = (c) => {
    haptic();
    setEditingCastle(c.name); setEditKind(c.kind || 'castle'); setEditTerrain(c.terrain || 'land');
  };
  const cancelEditMapCastle = () => setEditingCastle(null);
  const saveEditMapCastle = async () => {
    try {
      await api.adminEditMapCastle(editingCastle, { kind: editKind, terrain: editTerrain });
      haptic('medium');
      toast(`نشانهٔ «${editingCastle}» به‌روزرسانی شد`);
      setEditingCastle(null);
      loadMapData();
    } catch (e) { toast(e.message); }
  };

  const setMarketListing = async () => {
    const qty = parseInt(marketQty, 10), price = parseInt(marketPrice, 10);
    if (!Number.isFinite(qty) || qty < 0 || !Number.isFinite(price) || price <= 0) {
      toast('مقدار و قیمت را درست وارد کن'); return;
    }
    try {
      await api.adminMarketSet({ resource: marketResource, qty, price });
      haptic('medium');
      toast(`بازار وستروس برای «${TRADE_GOOD_NAMES[marketResource]}» به‌روز شد`);
      setMarketQty(''); setMarketPrice('');
      loadMarket();
    } catch (e) { toast(e.message); }
  };

  const deleteMarketListing = async (resource) => {
    try {
      await api.adminMarketDelete(resource);
      haptic('medium');
      toast(`«${TRADE_GOOD_NAMES[resource]}» از بازار وستروس برداشته شد`);
      loadMarket();
    } catch (e) { toast(e.message); }
  };

  const createBlackMarketListing = async () => {
    const qty = parseInt(blackQty, 10), price = parseInt(blackPrice, 10), hours = parseInt(blackHours, 10);
    if (!Number.isFinite(qty) || qty <= 0 || !Number.isFinite(price) || price <= 0 || !Number.isFinite(hours) || hours <= 0) {
      toast('مقدار، قیمت و مدت را درست وارد کن'); return;
    }
    try {
      await api.adminBlackMarketCreate({ resource: blackResource, qty, price, hours });
      haptic('medium');
      toast(`جنس تازه به بازار سیاه اضافه شد`);
      setBlackQty(''); setBlackPrice(''); setBlackHours('6');
      loadBlackMarket();
    } catch (e) { toast(e.message); }
  };

  const deleteBlackMarketListing = async (id) => {
    try {
      await api.adminBlackMarketDelete(id);
      haptic('medium');
      toast('از بازار سیاه برداشته شد');
      loadBlackMarket();
    } catch (e) { toast(e.message); }
  };

  const saveResources = async () => {
    if (!resTarget.length || !resValues) return;
    setResBusy(true);
    try {
      await api.adminSetPlayerResources(resTarget[0].tg_id, resValues);
      haptic('medium');
      toast(`منابع «${resTarget[0].name}» به‌روزرسانی شد`);
    } catch (e) { toast(e.message); }
    setResBusy(false);
  };

  const toggleWarWindow = async () => {
    if (!warWindow) return;
    setWarWindowBusy(true);
    try {
      const res = await api.adminSetWarWindow(!warWindow.open);
      haptic('medium');
      toast(res.open ? 'پنجرهٔ لشکرکشی برای همه باز شد' : 'پنجرهٔ لشکرکشی برای همه بسته شد');
      loadWarWindow();
    } catch (e) { toast(e.message); }
    setWarWindowBusy(false);
  };

  const sendEvent = async () => {
    if (!eventTitle.trim() || !eventDescription.trim()) { toast('عنوان و توضیحِ رویداد را بنویس'); return; }
    setEventBusy(true);
    try {
      await api.adminAnnounceEvent(eventTitle.trim(), eventDescription.trim());
      haptic('medium');
      toast('رویداد برای همهٔ بازیکنان با کلاغ فرستاده شد');
      setEventTitle(''); setEventDescription('');
    } catch (e) { toast(e.message); }
    setEventBusy(false);
  };

  const sendBotMessage = async () => {
    const text = botMessage.trim();
    if (!text) { toast('متن پیام را بنویس'); return; }
    if (botAudience === 'selected' && botTargets.length === 0) { toast('حداقل یک بازیکن را انتخاب کن'); return; }
    setBotMessageBusy(true);
    try {
      const res = await api.adminSendBotMessage(
        text,
        botAudience === 'all',
        botTargets.map(p => p.tg_id),
      );
      haptic('medium');
      toast(`پیام بات برای ${(res.sent_to ?? 0).toLocaleString('fa-IR')} بازیکن ارسال شد`);
      setBotMessage('');
      setBotTargets([]);
    } catch (e) { toast(e.message); }
    setBotMessageBusy(false);
  };

  const awardStoryteller = async () => {
    if (!medalTarget.length) { toast('یک بازیکن انتخاب کن'); return; }
    setMedalBusy(true);
    try {
      await api.adminAwardStoryteller(medalTarget[0].tg_id, medalTier, medalReason.trim());
      haptic('medium'); toast('مدال راوی قلمرو اعطا شد');
      setMedalTarget([]); setMedalReason('');
    } catch (e) { toast(e.message); }
    setMedalBusy(false);
  };

  const awardSpecialMedal = async () => {
    if (!specialMedalTarget.length) { toast('بازیکن دریافت‌کننده را انتخاب کن'); return; }
    const preset = SPECIAL_MEDAL_PRESETS.find(m => m.key === specialMedalPreset);
    const medalName = specialMedalPreset === 'custom' ? specialMedalName.trim() : preset?.name;
    const medalIcon = specialMedalIcon.trim() || preset?.icon || '🏅';
    if (!medalName) { toast('نام مدال را بنویس'); return; }
    setSpecialMedalBusy(true);
    try {
      await api.adminAwardSpecialMedal(specialMedalTarget[0].tg_id, {
        name: medalName, icon: medalIcon, tier: specialMedalTier,
        reason: specialMedalReason.trim(),
      });
      haptic('medium'); toast('مدال ویژهٔ ادمین اعطا شد');
      setSpecialMedalTarget([]); setSpecialMedalName(''); setSpecialMedalIcon('');
      setSpecialMedalReason('');
    } catch (e) { toast(e.message); }
    setSpecialMedalBusy(false);
  };

  const resetGame = async () => {
    if (resetConfirmText.trim() !== 'RESET') { toast('عبارت RESET را دقیقاً همون‌جوری تایپ کن'); return; }
    if (!window.confirm('مطمئنی؟ این کار بازگشت‌ناپذیره — همهٔ بازیکن‌های غیرادمین حذف می‌شن و تاریخچهٔ بازی پاک می‌شه.')) return;
    setResetBusy(true);
    try {
      const res = await api.adminResetGame(resetConfirmText.trim());
      haptic('medium');
      toast(`بازی ری‌استارت شد — ${(res.players_deleted ?? 0).toLocaleString('fa-IR')} بازیکن حذف شد`);
      setResetConfirmText('');
      loadResetPreview();
      // ری‌استارت این‌ها رو کامل خالی می‌کنه (لشکرکشی، جاسوسی، رول، اتحاد، رای‌گیری) —
      // بدونِ رفرشِ همه‌شون، پنل ادمین تا رفرشِ دستیِ صفحه دادهٔ حذف‌شده نشون می‌ده
      loadPendingPlayers(); loadRoster(); loadCampaigns(); loadMapData();
      loadSpyPending(); loadSpyResolved(); loadRoleplayPending(); loadAlliances(); loadPolls();
    } catch (e) { toast(e.message); }
    setResetBusy(false);
  };

  const disbandCampaign = async (id) => {
    setDisbandBusyId(id);
    try {
      await api.adminDisbandCampaign(id);
      haptic('medium');
      toast('لشکر منحل شد و نفراتش به خانه برگشتند');
      if (resTarget.length) api.adminPlayerCampaigns(resTarget[0].tg_id).then(setResCampaigns).catch(() => {});
      loadCampaigns();
    } catch (e) { toast(e.message); }
    setDisbandBusyId(null);
  };

  const scoreSpy = async (missionId) => {
    const raw = spyScores[missionId];
    const score = Number(raw);
    if (raw === undefined || raw === '' || Number.isNaN(score) || score < 0 || score > 100) {
      toast('امتیاز جاسوسی باید عددی بین ۰ تا ۱۰۰ باشد'); return;
    }
    setSpyBusyId(missionId);
    try {
      const res = await api.adminScoreSpy(missionId, score);
      haptic('medium');
      toast(res.success ? 'نتیجه ثبت شد — جاسوسی موفق بود' : 'نتیجه ثبت شد — جاسوس دستگیر شد');
      setSpyScores(prev => { const n = { ...prev }; delete n[missionId]; return n; });
      loadSpyPending();
      loadSpyResolved();
    } catch (e) { toast(e.message); }
    setSpyBusyId(null);
  };

  const dissolveAlliance = async (id) => {
    setDissolveBusyId(id);
    try {
      await api.adminDissolveAlliance(id);
      haptic('medium');
      toast('پیمان منحل شد و به هر دو طرف اطلاع داده شد');
      loadAlliances();
    } catch (e) { toast(e.message); }
    setDissolveBusyId(null);
  };

  const respondRoleplay = async (roleplayId) => {
    const result = (roleplayResults[roleplayId] || '').trim();
    if (result.length < 3) { toast('متن نتیجه خیلی کوتاه است'); return; }
    const visibility = roleplayVisibility[roleplayId] || 'participants';
    const otherLords = (roleplayOtherLords[roleplayId] || []).map(p => p.tg_id);
    const roleplay = roleplayPending?.find(r => r.id === roleplayId);
    const winnerTgId = roleplayWinners[roleplayId] || null;
    if (roleplay?.category === 'war' && !winnerTgId) { toast('برندهٔ نبرد را مشخص کن'); return; }
    setRoleplayBusyId(roleplayId);
    try {
      const res = await api.adminRespondRoleplay(roleplayId, result, visibility, otherLords, winnerTgId);
      haptic('medium');
      toast(visibility === 'all' ? `اعلامیه برای همهٔ بازیکنان (${(res.sent_to || 0).toLocaleString('fa-IR')} نفر) فرستاده شد` : 'نتیجهٔ رول برای بازیکن فرستاده شد');
      setRoleplayResults(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayVisibility(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayOtherLords(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayWinners(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      loadRoleplayPending();
    } catch (e) { toast(e.message); }
    setRoleplayBusyId(null);
  };

  const setOverlord = async () => {
    if (!overlordTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    try {
      await api.adminSetOverlord(overlordRegion, overlordTarget[0].tg_id);
      haptic('medium');
      toast('بالادستی تعیین شد');
      setOverlordTarget([]);
    } catch (e) { toast(e.message); }
  };

  const setWarden = async () => {
    if (!wardenTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    try {
      await api.adminSetWarden(wardenGroup, wardenTarget[0].tg_id);
      haptic('medium');
      toast('والی تعیین شد');
      setWardenTarget([]);
    } catch (e) { toast(e.message); }
  };

  const setKing = async () => {
    if (!kingTarget.length) { toast('یک والی را انتخاب کن'); return; }
    try {
      await api.adminSetKing(kingTarget[0].tg_id);
      haptic('medium');
      toast('پادشاه/ملکه تعیین شد');
      setKingTarget([]);
    } catch (e) { toast(e.message); }
  };

  const setEpithet = async () => {
    if (!epithetTarget.length || !epithetText.trim()) { toast('لرد و عنوان را مشخص کن'); return; }
    try {
      await api.adminSetEpithet(epithetTarget[0].tg_id, epithetText.trim());
      haptic('medium');
      toast('عنوان ثبت شد');
      setEpithetTarget([]); setEpithetText('');
    } catch (e) { toast(e.message); }
  };

  const createPoll = async () => {
    const opts = pollOptions.map(o => o.trim()).filter(Boolean);
    if (!pollQuestion.trim() || opts.length < 2 || !pollEligible.length) {
      toast('سوال، حداقل دو گزینه، و حداقل یک واجد شرایط لازم است'); return;
    }
    try {
      await api.adminCreatePoll(pollQuestion.trim(), opts, pollEligible.map(p => p.tg_id));
      haptic('medium');
      toast('رای‌گیری ساخته شد');
      setPollQuestion(''); setPollOptions(['', '']); setPollEligible([]);
      loadPolls();
    } catch (e) { toast(e.message); }
  };

  const closePoll = async (id) => {
    try { await api.adminClosePoll(id); haptic(); toast('رای‌گیری بسته شد'); loadPolls(); }
    catch (e) { toast(e.message); }
  };

  const deletePoll = async (id) => {
    try { await api.adminDeletePoll(id); haptic(); toast('رای‌گیری حذف شد'); loadPolls(); }
    catch (e) { toast(e.message); }
  };

  const addAdmin = async () => {
    if (!newAdminTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    try {
      await api.adminAddAdmin(newAdminTarget[0].tg_id);
      haptic('medium');
      toast('ادمین محدود اضافه شد');
      setNewAdminTarget([]);
      loadAdmins();
    } catch (e) { toast(e.message); }
  };

  const removeAdmin = async (tgId) => {
    try { await api.adminRemoveAdmin(tgId); haptic(); toast('ادمین حذف شد'); loadAdmins(); }
    catch (e) { toast(e.message); }
  };

  const assignHouse = async (tgId) => {
    const current = roster?.find(p => p.tg_id === tgId) || pendingPlayers?.find(p => p.tg_id === tgId);
    const regionId = assignRegion[tgId] || current?.region || Object.keys(REGIONS_STATIC)[0];
    const castle = assignCastle[tgId];
    if (!castle) { toast('یک قلعه انتخاب کن'); return; }
    setAssignBusyId(tgId);
    try {
      const res = await api.adminAssignHouse(tgId, regionId, castle);
      haptic('medium');
      toast(res.moved ? 'خاندان و قلعه جابه‌جا شد — کلاغی برایش رفت' : 'خاندان و قلعه تعیین شد — کلاغی برایش رفت');
      setAssignCastle(prev => { const n = { ...prev }; delete n[tgId]; return n; });
      setReassignOpenId(null);
      loadPendingPlayers(); loadRoster(); loadMapData();
    } catch (e) { toast(e.message); }
    setAssignBusyId(null);
  };

  const unassignHouse = async (tgId) => {
    setUnassignBusyId(tgId);
    try {
      await api.adminUnassignHouse(tgId);
      haptic('medium');
      toast('خاندان و قلعه از این بازیکن گرفته شد');
      loadPendingPlayers(); loadRoster(); loadMapData();
    } catch (e) { toast(e.message); }
    setUnassignBusyId(null);
  };

  const addCastle = async (tgId) => {
    const castle = addCastleValue[0];
    if (!castle) { toast('یک قلعه انتخاب کن'); return; }
    setAddCastleBusyId(tgId);
    try {
      const res = await api.adminAddCastle(tgId, castle);
      haptic('medium');
      toast(res.captured_from ? `قلعه از «${res.captured_from}» گرفته شد و به این بازیکن اضافه شد` : 'قلعهٔ اضافه به این بازیکن داده شد');
      setAddCastleValue([]);
      setAddCastleOpenId(null);
      // فتحِ قلعه ممکنه صاحبِ قبلی رو بی‌خاندان کنه (اگه تنها قلعه‌اش بوده) — پس باید
      // لیستِ در-انتظار هم دوباره لود بشه، نه فقط roster
      loadRoster(); loadPendingPlayers(); loadMapData();
    } catch (e) { toast(e.message); }
    setAddCastleBusyId(null);
  };

  const removeCastle = async (tgId, castle) => {
    setRemoveCastleBusyKey(`${tgId}:${castle}`);
    try {
      await api.adminRemoveCastle(tgId, castle);
      haptic('medium');
      toast(`قلعهٔ «${castle}» از این بازیکن گرفته شد`);
      loadRoster(); loadMapData();
    } catch (e) { toast(e.message); }
    setRemoveCastleBusyKey(null);
  };

  const deletePendingPlayer = async (tgId, name) => {
    if (!window.confirm(`درخواستِ ثبت‌نامِ «${name}» کاملاً پاک بشه؟ این کار برگشت‌ناپذیره.`)) return;
    setDeletePendingBusyId(tgId);
    try {
      await api.adminDeletePendingPlayer(tgId);
      haptic('medium');
      toast('درخواست ثبت‌نام حذف شد');
      loadPendingPlayers();
    } catch (e) { toast(e.message); }
    setDeletePendingBusyId(null);
  };

  const toggleReassign = (tgId) => {
    haptic();
    setReassignOpenId(prev => prev === tgId ? null : tgId);
    setAssignCastle(prev => ({ ...prev, [tgId]: '' }));
  };

  const toggleAddCastle = (tgId) => {
    haptic();
    setAddCastleOpenId(prev => prev === tgId ? null : tgId);
    setAddCastleValue([]);
  };

  const createItem = async () => {
    if (!itemName.trim()) { toast('نام آیتم را بنویس'); return; }
    if (itemDuration === 'temporary' && (!itemDurationHours || +itemDurationHours <= 0)) {
      toast('برای آیتم موقتی، مدت (ساعت) را مشخص کن'); return;
    }
    setItemBusy(true);
    try {
      await api.adminCreateItem({
        name: itemName.trim(), type: itemType, duration: itemDuration,
        duration_hours: itemDuration === 'temporary' ? +itemDurationHours : null,
        description: itemDescription.trim(),
      });
      haptic('medium');
      toast('آیتم ساخته شد');
      setItemName(''); setItemDescription(''); setItemDurationHours('24');
      loadItems();
    } catch (e) { toast(e.message); }
    setItemBusy(false);
  };

  const deleteItem = async (id) => {
    try { await api.adminDeleteItem(id); haptic(); toast('آیتم حذف شد'); loadItems(); }
    catch (e) { toast(e.message); }
  };

  const openGrant = (id) => {
    haptic();
    setGrantOpenId(prev => prev === id ? null : id);
    setGrantTarget([]); setGrantColor(Object.keys(ITEM_RARITY_COLORS)[0]);
  };

  const grantItem = async (id) => {
    if (!grantTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    setGrantBusy(true);
    try {
      await api.adminGrantItem(id, grantTarget[0].tg_id, grantColor);
      haptic('medium');
      toast(`آیتم به «${grantTarget[0].name}» داده شد`);
      setGrantOpenId(null); setGrantTarget([]);
      loadItems();
    } catch (e) { toast(e.message); }
    setGrantBusy(false);
  };

  const setBalanceDraft = (bid, key, value) => {
    setBalanceDrafts(prev => ({ ...prev, [bid]: { ...prev[bid], [key]: value } }));
  };

  const saveBalance = async (b) => {
    const draft = balanceDrafts[b.id] || {};
    const produces = {};
    for (const k of Object.keys(b.base_produces)) {
      const n = parseInt(draft[k], 10);
      if (isNaN(n) || n < 0) { toast('مقدارها باید عدد صحیح و غیرمنفی باشند'); return; }
      produces[k] = n;
    }
    const capBonus = {};
    for (const k of Object.keys(b.base_cap_bonus)) {
      const n = parseInt(draft[k], 10);
      if (isNaN(n) || n < 0) { toast('مقدارها باید عدد صحیح و غیرمنفی باشند'); return; }
      capBonus[k] = n;
    }
    setBalanceBusyId(b.id);
    try {
      await api.adminSetBuildingBalance({ building_id: b.id, produces, cap_bonus: capBonus });
      haptic('medium');
      toast(`بازدهی «${b.name}» ذخیره شد`);
      loadBalance();
    } catch (e) { toast(e.message); }
    setBalanceBusyId(null);
  };

  const resetBalance = async (b) => {
    setBalanceBusyId(b.id);
    try {
      await api.adminResetBuildingBalance(b.id);
      haptic();
      toast(`«${b.name}» به مقدار پیش‌فرض برگشت`);
      setBalanceDrafts(prev => { const next = { ...prev }; delete next[b.id]; return next; });
      loadBalance();
    } catch (e) { toast(e.message); }
    setBalanceBusyId(null);
  };

  if (!me.admin_role) {
    return (
      <>
        <div className="page-title up">پنل ادمین</div>
        <div className="card up u1" style={{ textAlign: 'center', color: 'var(--mid)' }}>دسترسی نداری</div>
      </>
    );
  }

  return (
    <>
      <div className="page-title up">پنل ادمین</div>
      <div className="page-sub up">{isFull ? 'ادمین کامل' : 'ادمین محدود — فقط لشکرکشی‌ها، رول‌ها، جاسوسی و مقام‌ها'}</div>

      {availGroups.map((g, gi) => (
        <div key={g.label} className={gi > 0 ? 'tabs-group' : ''}>
          <div className="tabs-group-label up u1">{g.label}</div>
          <div className="tabs up u1" role="tablist" aria-label={g.label}>
            {g.tabs.map(t => (
              <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
                   className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
                   onClick={() => { haptic(); setTab(t.key); }}>{t.label}</button>
            ))}
          </div>
        </div>
      ))}

      {tab === 'onboarding' && (
        <>
          <div className="sect up u2">بازیکن‌های منتظر تخصیص خاندان</div>
          <div className="page-sub up u2" style={{ marginTop: -10 }}>
            این‌ها فقط اسم‌نویسی کرده‌اند — اقلیم (خاندان) و قلعه‌شان را دستی مشخص کن تا وارد بازی شوند
          </div>
          <div className="up u2">
            {(!pendingPlayers || pendingPlayers.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>فعلاً کسی منتظر نیست</div>
            )}
            {pendingPlayers && pendingPlayers.map(p => {
              const regionId = assignRegion[p.tg_id] || Object.keys(REGIONS_STATIC)[0];
              const region = REGIONS_STATIC[regionId];
              const castleOptions = [...region.castles.map(n => ({ n, port: false })), ...region.ports.map(n => ({ n, port: true }))];
              return (
                <div className="card" key={p.tg_id} style={{ marginBottom: 10 }}>
                  <div className="res">
                    <div className="ic"><Shield s={16} /></div>
                    <div className="n">{p.name}<small>{p.title} · {p.gender === 'lady' ? 'لیدی' : 'لرد'}</small></div>
                  </div>
                  {p.requested_castles && p.requested_castles.length > 0 && (
                    <div style={{ margin: '2px 0 12px' }}>
                      <div className="page-sub" style={{ margin: '0 4px 6px' }}>درخواستِ خودِ بازیکن (به‌ترتیب اولویت):</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {p.requested_castles.map((rc, i) => (
                          <button type="button" key={rc.name}
                                  className="rbtn" disabled={rc.occupied || !rc.region}
                                  style={{
                                    width: 'auto', padding: '6px 10px', fontSize: 11.5, borderRadius: 999,
                                    border: '1px solid rgba(160,195,255,0.18)',
                                    color: rc.occupied ? 'var(--mid)' : 'var(--az2)',
                                    opacity: rc.occupied ? 0.6 : 1,
                                  }}
                                  onClick={() => {
                                    haptic();
                                    setAssignRegion(prev => ({ ...prev, [p.tg_id]: rc.region }));
                                    setAssignCastle(prev => ({ ...prev, [p.tg_id]: rc.name }));
                                  }}>
                            {(i + 1).toLocaleString('fa-IR')}. {castleLabel(rc.name)}{rc.occupied ? ' (اشغال‌شده)' : ''}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <label className="f">اقلیم (خاندان)</label>
                  <select value={regionId} onChange={e => {
                    setAssignRegion(prev => ({ ...prev, [p.tg_id]: e.target.value }));
                    setAssignCastle(prev => ({ ...prev, [p.tg_id]: '' }));
                  }}>
                    {Object.entries(REGIONS_STATIC).map(([rid, r]) => <option key={rid} value={rid}>{r.name}</option>)}
                  </select>
                  <label className="f">قلعه</label>
                  <select value={assignCastle[p.tg_id] || ''} onChange={e => setAssignCastle(prev => ({ ...prev, [p.tg_id]: e.target.value }))}>
                    <option value="" disabled>انتخاب کن...</option>
                    {castleOptions.map(c => <option key={c.n} value={c.n}>{castleLabel(c.n)}{c.port ? ' ⚓ بندر' : ''}</option>)}
                  </select>
                  <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                    <button className="btn" style={{ flex: 1 }} disabled={assignBusyId === p.tg_id} onClick={() => assignHouse(p.tg_id)}>
                      {assignBusyId === p.tg_id ? 'در حال ثبت...' : 'تخصیص خاندان و قلعه'}
                    </button>
                    <button className="btn ghost" style={{ width: 'auto', padding: '0 14px', color: 'var(--danger)' }}
                            disabled={deletePendingBusyId === p.tg_id} onClick={() => deletePendingPlayer(p.tg_id, p.name)}>
                      {deletePendingBusyId === p.tg_id ? '...' : 'حذف درخواست'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="sect up u3">خاندان‌های موجود در بازی</div>
          <div className="page-sub up u3" style={{ marginTop: -10 }}>
            هر بازیکنِ خاندان‌دار — می‌توانی از خاندانش خارجش کنی یا به خاندان/قلعهٔ دیگری منتقلش کنی
          </div>
          <div className="up u3">
            {(!roster || roster.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز کسی خاندانی ندارد</div>
            )}
            {roster && roster.map(p => {
              const regionId = assignRegion[p.tg_id] || p.region || Object.keys(REGIONS_STATIC)[0];
              const region = REGIONS_STATIC[regionId];
              const castleOptions = [...region.castles.map(n => ({ n, port: false })), ...region.ports.map(n => ({ n, port: true }))];
              return (
                <div className="card" key={p.tg_id} style={{ marginBottom: 10 }}>
                  <div className="res">
                    <div className="ic"><Shield s={16} /></div>
                    <div className="n">{p.name}<small>{p.region_name} · {castleLabel(p.castle)}{p.is_port ? ' ⚓' : ''}</small></div>
                  </div>
                  {p.castles && p.castles.length > 0 && (
                    <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {p.castles.map(c => (
                        <span key={c} className="rbtn" style={{
                          width: 'auto', padding: '4px 8px', fontSize: 11, borderRadius: 999, display: 'flex',
                          alignItems: 'center', gap: 5, border: '1px solid rgba(160,195,255,0.18)',
                        }}>
                          {castleLabel(c)} — پایگاهِ دوم
                          <button type="button" aria-label={`پس‌گرفتن ${c}`}
                                  disabled={removeCastleBusyKey === `${p.tg_id}:${c}`}
                                  onClick={() => removeCastle(p.tg_id, c)}
                                  style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: 0 }}>
                            <Close s={11} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                    <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }}
                            disabled={unassignBusyId === p.tg_id} onClick={() => unassignHouse(p.tg_id)}>
                      {unassignBusyId === p.tg_id ? 'در حال حذف...' : 'حذف از خاندان'}
                    </button>
                    <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }} onClick={() => toggleReassign(p.tg_id)}>
                      انتقال به خاندان دیگر
                    </button>
                    <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }} onClick={() => toggleAddCastle(p.tg_id)}>
                      افزودن قلعه
                    </button>
                  </div>
                  {reassignOpenId === p.tg_id && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(160,195,255,0.07)' }}>
                      <label className="f" style={{ marginTop: 0 }}>اقلیم (خاندان) تازه</label>
                      <select value={regionId} onChange={e => {
                        setAssignRegion(prev => ({ ...prev, [p.tg_id]: e.target.value }));
                        setAssignCastle(prev => ({ ...prev, [p.tg_id]: '' }));
                      }}>
                        {Object.entries(REGIONS_STATIC).map(([rid, r]) => <option key={rid} value={rid}>{r.name}</option>)}
                      </select>
                      <label className="f">قلعهٔ تازه</label>
                      <select value={assignCastle[p.tg_id] || ''} onChange={e => setAssignCastle(prev => ({ ...prev, [p.tg_id]: e.target.value }))}>
                        <option value="" disabled>انتخاب کن...</option>
                        {castleOptions.map(c => <option key={c.n} value={c.n}>{castleLabel(c.n)}{c.port ? ' ⚓ بندر' : ''}</option>)}
                      </select>
                      <button className="btn" style={{ marginTop: 14 }} disabled={assignBusyId === p.tg_id} onClick={() => assignHouse(p.tg_id)}>
                        {assignBusyId === p.tg_id ? 'در حال ثبت...' : 'انتقال'}
                      </button>
                    </div>
                  )}
                  {addCastleOpenId === p.tg_id && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(160,195,255,0.07)' }}>
                      <div className="page-sub" style={{ margin: '0 0 8px' }}>
                        قلعهٔ اضافه — پایگاهِ دومِ کاملِ این بازیکن؛ از هر اقلیمی می‌تونه باشه. اگه الان دستِ بازیکنِ
                        دیگری باشد (چه قلعهٔ اصلی‌اش چه اضافه‌اش)، خودکار به‌عنوانِ غنیمتِ جنگ ازش گرفته می‌شود.
                      </div>
                      <CastlePicker value={addCastleValue} onChange={setAddCastleValue} max={1} />
                      <button className="btn" style={{ marginTop: 14 }} disabled={addCastleBusyId === p.tg_id} onClick={() => addCastle(p.tg_id)}>
                        {addCastleBusyId === p.tg_id ? 'در حال ثبت...' : 'افزودن'}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {tab === 'war' && (
        <>
          <div className="tabs up u1" role="tablist" aria-label="بخش‌های جنگ و رول‌ها">
            {[
              { key: 'campaigns', label: 'لشکرکشی‌ها' },
              { key: 'espionage', label: 'جاسوسی' },
              { key: 'roleplay',  label: 'رول‌ها' },
            ].map(t => (
              <button type="button" key={t.key} role="tab" aria-selected={warSubTab === t.key}
                   className={`rbtn tab ${warSubTab === t.key ? 'on' : ''}`}
                   onClick={() => { haptic(); setWarSubTab(t.key); }}>{t.label}</button>
            ))}
          </div>

          {warSubTab === 'campaigns' && (
          <div className="up u2">
            <div className="card" style={{ marginBottom: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700 }}>
                  پنجرهٔ لشکرکشی: {warWindow ? (warWindow.open ? 'باز' : 'بسته') : '...'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--mid)', marginTop: 4 }}>
                  وقتی بسته باشد هیچ بازیکنی نمی‌تواند فرمان گسیل تازه بدهد؛ لشکرهای در راه دست‌نخورده می‌مانند
                </div>
              </div>
              <button className="btn" style={{ width: 'auto', flexShrink: 0, padding: '10px 18px', fontSize: 12.5 }}
                      disabled={!warWindow || warWindowBusy} onClick={toggleWarWindow}>
                {warWindowBusy ? '...' : warWindow?.open ? 'بستن' : 'باز کردن'}
              </button>
            </div>
            {(!campaignsInfo || campaignsInfo.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز لشکرکشی‌ای ثبت نشده</div>
            )}
            {campaignsInfo && campaignsInfo.map(s => (
              <div className="card" key={s.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Shield s={16} /></div>
                  <div className="n">
                    {s.player} — {s.name}
                    <small>
                      {s.op_name} · {s.from} ← {s.to} · {s.gold_cost.toLocaleString('fa-IR')} طلا ·{' '}
                      {s.men_committed.toLocaleString('fa-IR')} نفر · توان {s.power.toLocaleString('fa-IR')} ·{' '}
                      {s.food_per_day.toLocaleString('fa-IR')} غله/روز ·{' '}
                      {s.travel_minutes.toLocaleString('fa-IR')} دقیقه سفر
                    </small>
                  </div>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', margin: '8px 0' }}>
                  نیروها: {s.troops.length ? s.troops.map(t => `${t.name} × ${t.count.toLocaleString('fa-IR')}`).join(' · ') : '—'}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--low)' }}>
                    {s.active ? (s.arrived ? 'رسیده به مقصد' : 'در راه') : 'لغوشده'}
                  </div>
                  {s.active && isFull && (
                    <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11, color: 'var(--danger)' }}
                            disabled={disbandBusyId === s.id} onClick={() => disbandCampaign(s.id)}>
                      {disbandBusyId === s.id ? 'در حال انحلال...' : 'منحل کن'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          )}

          {warSubTab === 'espionage' && (
          <>
          <div className="grid2 up u2" role="radiogroup" aria-label="نمای جاسوسی">
            <button type="button" role="radio" aria-checked={spyResultsView === 'pending'}
                    className={`rbtn pick ${spyResultsView === 'pending' ? 'sel' : ''}`}
                    onClick={() => { haptic(); setSpyResultsView('pending'); }}>
              <div className="n">در انتظار بررسی</div>
            </button>
            <button type="button" role="radio" aria-checked={spyResultsView === 'resolved'}
                    className={`rbtn pick ${spyResultsView === 'resolved' ? 'sel' : ''}`}
                    onClick={() => { haptic(); setSpyResultsView('resolved'); }}>
              <div className="n">بررسی‌شده‌ها</div>
            </button>
          </div>

          {spyResultsView === 'pending' && (
          <>
          <div className="page-sub up u3">
            نقشهٔ هر بازیکن را بخوان و بر اساس هوشمندی و منطقی‌بودنش امتیاز جاسوسی (۰ تا ۱۰۰) بده — همان امتیاز مستقیماً شانس موفقیتش می‌شود
          </div>
          <div className="up u3">
            {(!spyPending || spyPending.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>سناریوی بررسی‌نشده‌ای نیست</div>
            )}
            {spyPending && spyPending.map(m => (
              <div className="card" key={m.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Eye s={16} /></div>
                  <div className="n">
                    {m.player}
                    <small>{m.origin} ← {m.target} · {m.arrived ? 'رسیده به مقصد' : 'در راه'}</small>
                  </div>
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.8, margin: '10px 0', color: 'var(--mid)' }}>{m.scenario}</div>
                <div className="buy-row">
                  <input type="number" min="0" max="100" placeholder="۰-۱۰۰"
                         value={spyScores[m.id] ?? ''}
                         onChange={e => setSpyScores(prev => ({ ...prev, [m.id]: e.target.value }))} />
                  <button className="btn" disabled={spyBusyId === m.id} onClick={() => scoreSpy(m.id)}>
                    {spyBusyId === m.id ? 'در حال ثبت...' : 'ثبت امتیاز و اعلام نتیجه'}
                  </button>
                </div>
              </div>
            ))}
          </div>
          </>
          )}

          {spyResultsView === 'resolved' && (
          <div className="up u3">
            {(!spyResolved || spyResolved.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز جاسوسی‌ای بررسی نشده</div>
            )}
            {spyResolved && spyResolved.map(m => (
              <div className="card" key={m.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Eye s={16} /></div>
                  <div className="n">
                    {m.player}
                    <small>{m.target} · امتیاز {m.admin_score.toLocaleString('fa-IR')} · {m.success ? 'موفق' : 'دستگیر شد'}</small>
                  </div>
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.8, margin: '10px 0', color: 'var(--mid)' }}>{m.scenario}</div>
              </div>
            ))}
          </div>
          )}
          </>
          )}

          {warSubTab === 'roleplay' && (
          <>
          <div className="page-sub up u3">
            سناریوی هر بازیکن را بخوان و نتیجه‌اش را برایش بنویس؛ می‌توانی نتیجه را فقط برای شرکت‌کننده‌ها بفرستی یا به‌عنوان اعلامیهٔ عمومی برای همهٔ بازیکنان
          </div>
          <div className="up u3">
            {(!roleplayPending || roleplayPending.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>رول بررسی‌نشده‌ای نیست</div>
            )}
            {roleplayPending && roleplayPending.map(r => (
              <div className="card" key={r.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Scroll s={16} /></div>
                  <div className="n">
                    {r.player}
                    <small>{r.category_name} · {castleLabel(r.castle)}</small>
                  </div>
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.8, margin: '10px 0', color: 'var(--mid)' }}>{r.text}</div>
                {r.category === 'war' && (
                  r.sibling ? (
                    <div style={{ margin: '0 0 10px', padding: 10, borderRadius: 12, background: 'rgba(77,163,255,0.08)', border: '1px solid rgba(96,178,255,0.2)' }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--az2)', marginBottom: 4 }}>سناریوی طرف مقابل ({r.sibling.player})</div>
                      <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--mid)' }}>{r.sibling.text}</div>
                    </div>
                  ) : (
                    <div style={{ margin: '0 0 10px', fontSize: 11, color: 'var(--low)' }}>طرف مقابل هنوز سناریویش را نفرستاده — نتیجه برای هر دو طرف فرستاده می‌شود</div>
                  )
                )}
                {r.category === 'war' && r.war && (
                  <>
                    <label className="f" style={{ marginTop: 0 }}>برندهٔ نبرد</label>
                    <div className="grid2" role="radiogroup" aria-label="برندهٔ نبرد">
                      <button type="button" role="radio" aria-checked={roleplayWinners[r.id] === r.war.attacker_tg_id}
                              className={`rbtn pick ${roleplayWinners[r.id] === r.war.attacker_tg_id ? 'sel' : ''}`}
                              onClick={() => setRoleplayWinners(prev => ({ ...prev, [r.id]: r.war.attacker_tg_id }))}>
                        <div className="n">{r.war.attacker_name}</div>
                        <div className="c">مهاجم — پیروزی در حمله</div>
                      </button>
                      <button type="button" role="radio" disabled={!r.war.defender_tg_id}
                              aria-checked={roleplayWinners[r.id] === r.war.defender_tg_id}
                              className={`rbtn pick ${roleplayWinners[r.id] === r.war.defender_tg_id ? 'sel' : ''}`}
                              onClick={() => r.war.defender_tg_id && setRoleplayWinners(prev => ({ ...prev, [r.id]: r.war.defender_tg_id }))}>
                        <div className="n">{r.war.defender_name}</div>
                        <div className="c">مدافع — دفاع موفق از {castleLabel(r.war.target_castle)}</div>
                      </button>
                    </div>
                  </>
                )}
                <label className="f" style={{ marginTop: r.category === 'war' ? 12 : 0 }}>نتیجه</label>
                <textarea value={roleplayResults[r.id] ?? ''}
                          onChange={e => setRoleplayResults(prev => ({ ...prev, [r.id]: e.target.value }))}
                          placeholder="نتیجهٔ این رول چه شد..." />
                <label className="f">این رول بین این لرد و چه لردهای دیگری بوده؟ (اختیاری)</label>
                <PlayerPicker value={roleplayOtherLords[r.id] || []}
                              onChange={(v) => setRoleplayOtherLords(prev => ({ ...prev, [r.id]: v }))} />
                <label className="f">این نتیجه برای چه کسانی نمایش داده شود؟</label>
                <div className="grid2" role="radiogroup" aria-label="نمایش نتیجه">
                  <button type="button" role="radio" aria-checked={(roleplayVisibility[r.id] || 'participants') === 'participants'}
                          className={`rbtn pick ${(roleplayVisibility[r.id] || 'participants') === 'participants' ? 'sel' : ''}`}
                          onClick={() => setRoleplayVisibility(prev => ({ ...prev, [r.id]: 'participants' }))}>
                    <div className="n">شرکت‌کننده‌ها</div>
                    <div className="c">{r.category === 'war' ? 'هر دو طرف نبرد' : 'فقط همین بازیکن'}</div>
                  </button>
                  <button type="button" role="radio" aria-checked={roleplayVisibility[r.id] === 'all'}
                          className={`rbtn pick ${roleplayVisibility[r.id] === 'all' ? 'sel' : ''}`}
                          onClick={() => setRoleplayVisibility(prev => ({ ...prev, [r.id]: 'all' }))}>
                    <div className="n">همهٔ بازیکنان</div>
                    <div className="c">اعلامیهٔ عمومی</div>
                  </button>
                </div>
                <button className="btn" style={{ marginTop: 14 }} disabled={roleplayBusyId === r.id} onClick={() => respondRoleplay(r.id)}>
                  {roleplayBusyId === r.id ? 'در حال ارسال...' : 'ارسال نتیجه'}
                </button>
              </div>
            ))}
          </div>
          </>
          )}
        </>
      )}

      {tab === 'alliances' && (
        <>
          <div className="sect up u2">اتحادهای بازی</div>
          <div className="page-sub up u2" style={{ marginTop: -10 }}>
            همهٔ پیمان‌های پیشنهادشده بین بازیکنان — پیمان‌های برقرار را در صورت نیاز می‌توانی زورکی منحل کنی
          </div>
          <div className="up u2">
            {(!alliancesList || alliancesList.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز پیمانی بسته نشده</div>
            )}
            {alliancesList && alliancesList.map(a => (
              <div className="card" key={a.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Scroll s={16} /></div>
                  <div className="n">
                    {a.from} ← {a.to}
                    <small>{a.type_name}{a.name ? ` · «${a.name}»` : ''} · {a.public ? 'عمومی' : 'خصوصی'}</small>
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--low)' }}>
                    {{ pending: 'در انتظار پاسخ', accepted: 'برقرار', rejected: 'رد شده', dissolved: 'منحل‌شده' }[a.status] || a.status}
                  </div>
                  {a.status === 'accepted' && isFull && (
                    <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11, color: 'var(--danger)' }}
                            disabled={dissolveBusyId === a.id} onClick={() => dissolveAlliance(a.id)}>
                      {dissolveBusyId === a.id ? 'در حال انحلال...' : 'منحل کن'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'map' && (
        <>
          <div className="sect up u2">افزودن قلعه/شهر به نقشه</div>
          <div className="card up u2">
            <div className="page-sub" style={{ margin: '0 4px 10px' }}>روی نقطهٔ خالی از نقشه کلیک کن تا قلعه/شهر تازه‌ای همان‌جا اضافه شود</div>
            {mapError && (
              <div style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5, margin: '10px 0' }}>
                نقشه بارگذاری نشد — <button type="button" className="rbtn" style={{ width: 'auto', display: 'inline', color: 'var(--az2)', cursor: 'pointer', textDecoration: 'underline' }} onClick={loadMapData}>تلاش دوباره</button>
              </div>
            )}
            {mapData && (() => {
              const r = mapData.regions.find(x => x.id === mapRegion);
              if (!r) return null;
              const coords = r.coords || {};
              return (
                <div className="mapview" style={{ marginTop: 4 }}>
                  <ZoomPanMap>
                    <MapFrame region={r} coords={coords} pin={null}
                              onFrameClick={(x, y) => { haptic(); setPendingPin({ x, y }); }} />
                  </ZoomPanMap>
                </div>
              );
            })()}
            <label className="f">اقلیم</label>
            <select value={mapRegion} onChange={e => setMapRegion(e.target.value)}>
              {Object.entries(REGIONS_STATIC).map(([rid, r]) => <option key={rid} value={rid}>{r.name}</option>)}
            </select>
            {pendingPin && (
              <div style={{ marginTop: 12 }}>
                <label className="f" style={{ marginTop: 0 }}>این نقطه کدام قلعه/شهر است؟</label>
                <div className="ppicker">
                  <input
                    value={castleQuery}
                    onChange={e => { setCastleQuery(e.target.value); setPickName(''); setCastleResultsOpen(true); }}
                    onFocus={() => setCastleResultsOpen(true)}
                    placeholder={mapOptions === null ? 'در حال بارگذاری قلعه/شهرهای این اقلیم...' : 'اسم قلعه یا شهر را جست‌وجو کن...'}
                  />
                  {castleResultsOpen && (
                    <div className="ppicker-results">
                      {mapOptions === null ? (
                        <div className="ppicker-empty">در حال بارگذاری...</div>
                      ) : (
                        <>
                          {filteredCastleOptions.length === 0 && (
                            <div className="ppicker-empty">
                              {mapOptions.length === 0 ? 'همهٔ قلعه/شهرهای این اقلیم روی نقشه جا گرفته‌اند' : 'موردی پیدا نشد'}
                            </div>
                          )}
                          {filteredCastleOptions.map(o => (
                            <button type="button" className="rbtn ppicker-row" key={o.name} onClick={() => pickCastle(o.name)}>
                              <span>{castleLabel(o.name)}{o.kind === 'port' ? ' ⚓ بندر' : ''}</span>
                            </button>
                          ))}
                          <button type="button" className="rbtn ppicker-row" onClick={pickNewCastle} style={{ color: 'var(--az2)' }}>
                            + قلعه/شهر کاملاً جدید{castleQuery.trim() ? `: «${castleQuery.trim()}»` : '...'}
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
                {pickName && pickName !== NEW_CASTLE && (
                  <div className="page-sub" style={{ margin: '8px 4px 0' }}>انتخاب شد: <b style={{ color: 'var(--az2)' }}>{castleLabel(pickName)}</b></div>
                )}
                {pickName === NEW_CASTLE && (
                  <>
                    <label className="f">نام تازه</label>
                    <input value={newCastleName} onChange={e => setNewCastleName(e.target.value)} placeholder="مثلاً: هارتزهیل" />
                  </>
                )}
                {pickName && (
                  <>
                    <label className="f">نوع آیکن روی نقشه</label>
                    <div className="grid2">
                      {MAP_KINDS.map(k => (
                        <div key={k.key} className={`pick ${pinKind === k.key ? 'sel' : ''}`}
                             onClick={() => { haptic(); setPinKind(k.key); }}>
                          <div className="n">{k.label}</div>
                        </div>
                      ))}
                    </div>
                    <label className="f">نوع زمین (تعیین‌کنندهٔ ساخت کشتی/بندر)</label>
                    <div className="grid2">
                      {MAP_TERRAINS.map(t => (
                        <div key={t.key} className={`pick ${pinTerrain === t.key ? 'sel' : ''}`}
                             onClick={() => { haptic(); setPinTerrain(t.key); }}>
                          <div className="n">{t.label}</div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                  <button className="btn" style={{ padding: 11 }} onClick={addMapCastle}>افزودن به نقشه</button>
                  <button className="btn ghost" style={{ padding: 11 }} onClick={resetCastlePicker}>انصراف</button>
                </div>
              </div>
            )}
          </div>

          {mapData && (() => {
            const r = mapData.regions.find(x => x.id === mapRegion);
            if (!r) return null;
            const placedNames = new Set(Object.keys(r.coords || {}));
            const placed = r.castles.filter(c => placedNames.has(c.name));
            if (!placed.length) return null;
            return (
              <>
                <div className="sect up u3">نشانه‌های ثبت‌شدهٔ این اقلیم</div>
                <div className="region-castles up u3">
                  {placed.map(c => (
                    <div key={c.name}>
                      <div className="rc">
                        <span>{castleLabel(c.name)}<small style={{ color: 'var(--low)' }}> · {MAP_KINDS.find(k => k.key === c.kind)?.label || c.kind} · {MAP_TERRAINS.find(t => t.key === c.terrain)?.label || 'صرفاً خشکی'}</small></span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          {c.owner ? <span className="own">{c.owner.name}</span> : <span className="empty">بدون لرد</span>}
                          <button className="btn ghost" style={{ width: 'auto', padding: '6px 10px', fontSize: 11 }}
                                  onClick={() => startEditMapCastle(c)}>ادیت</button>
                          <button className="btn ghost" style={{ width: 'auto', padding: '6px 10px', fontSize: 11 }}
                                  onClick={() => deleteMapCastle(c.name)}>حذف</button>
                        </div>
                      </div>
                      {editingCastle === c.name && (
                        <div style={{ padding: '10px 4px 16px' }}>
                          <label className="f">نوع آیکن روی نقشه</label>
                          <div className="grid2">
                            {MAP_KINDS.map(k => (
                              <div key={k.key} className={`pick ${editKind === k.key ? 'sel' : ''}`}
                                   onClick={() => { haptic(); setEditKind(k.key); }}>
                                <div className="n">{k.label}</div>
                              </div>
                            ))}
                          </div>
                          <label className="f">نوع زمین (تعیین‌کنندهٔ ساخت کشتی/بندر)</label>
                          <div className="grid2">
                            {MAP_TERRAINS.map(t => (
                              <div key={t.key} className={`pick ${editTerrain === t.key ? 'sel' : ''}`}
                                   onClick={() => { haptic(); setEditTerrain(t.key); }}>
                                <div className="n">{t.label}</div>
                              </div>
                            ))}
                          </div>
                          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                            <button className="btn" style={{ padding: 11 }} onClick={saveEditMapCastle}>ذخیره</button>
                            <button className="btn ghost" style={{ padding: 11 }} onClick={cancelEditMapCastle}>انصراف</button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            );
          })()}
        </>
      )}

      {tab === 'titles' && (
        <>
          <div className="sect up u2">تعیین بالادستی</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>اقلیم</label>
            <select value={overlordRegion} onChange={e => setOverlordRegion(e.target.value)}>
              {Object.entries(REGIONS_STATIC).map(([rid, r]) => <option key={rid} value={rid}>{r.name}</option>)}
            </select>
            <label className="f">لرد (باید اهل همین اقلیم باشد — معمولاً برندهٔ رای‌گیری)</label>
            <PlayerPicker value={overlordTarget} onChange={setOverlordTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={setOverlord}>ثبت بالادستی</button>
          </div>

          <div className="sect up u2">تعیین والی</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>والی‌نشین</label>
            <select value={wardenGroup} onChange={e => setWardenGroup(e.target.value)}>
              {Object.entries(WARDEN_GROUPS).map(([gid, g]) => <option key={gid} value={gid}>{g.name}</option>)}
            </select>
            <label className="f">لرد (باید الان بالادستی یکی از اقلیم‌های این والی‌نشین باشد)</label>
            <PlayerPicker value={wardenTarget} onChange={setWardenTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={setWarden}>ثبت والی</button>
          </div>

          <div className="sect up u3">تعیین پادشاه/ملکه</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>لرد (باید الان یکی از سه والی باشد)</label>
            <PlayerPicker value={kingTarget} onChange={setKingTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={setKing}>ثبت پادشاه/ملکه</button>
          </div>

          <div className="sect up u3">تعیین عنوان (لقب)</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>لرد</label>
            <PlayerPicker value={epithetTarget} onChange={setEpithetTarget} single />
            <label className="f">عنوان تازه</label>
            <input value={epithetText} onChange={e => setEpithetText(e.target.value)} placeholder="مثلاً: شکنندهٔ زنجیرها" />
            <button className="btn" style={{ marginTop: 14 }} onClick={setEpithet}>ثبت عنوان</button>
          </div>
        </>
      )}

      {tab === 'items' && isFull && (
        <>
          <div className="sect up u2">ساخت آیتم تازه</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>نام آیتم</label>
            <input value={itemName} onChange={e => setItemName(e.target.value)} maxLength={60} placeholder="مثلاً «شمشیر فولاد والریایی»" />
            <label className="f">نوع</label>
            <select value={itemType} onChange={e => setItemType(e.target.value)}>
              {Object.entries(ITEM_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <label className="f">مدت</label>
            <select value={itemDuration} onChange={e => setItemDuration(e.target.value)}>
              {Object.entries(ITEM_DURATIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            {itemDuration === 'temporary' && (
              <>
                <label className="f">مدت (ساعت)</label>
                <input type="number" min="1" value={itemDurationHours} onChange={e => setItemDurationHours(e.target.value)} />
              </>
            )}
            <label className="f">توضیح (اختیاری)</label>
            <textarea value={itemDescription} onChange={e => setItemDescription(e.target.value)} placeholder="این آیتم چه می‌کند..." />
            <button className="btn" style={{ marginTop: 14 }} disabled={itemBusy} onClick={createItem}>
              {itemBusy ? 'در حال ساخت...' : 'ساخت آیتم'}
            </button>
          </div>

          <div className="sect up u3">آیتم‌های ساخته‌شده</div>
          <div className="up u3">
            {(!itemsList || itemsList.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز آیتمی نساخته‌ای</div>
            )}
            {itemsList && itemsList.map(it => (
              <div className="card" key={it.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Warehouse s={16} /></div>
                  <div className="n">
                    {it.name}
                    <small>
                      {it.type_name} · {it.duration_name}{it.duration_hours ? ` (${it.duration_hours.toLocaleString('fa-IR')} ساعت)` : ''} ·{' '}
                      {it.grant_count.toLocaleString('fa-IR')} بار داده‌شده
                    </small>
                  </div>
                </div>
                {it.description && <div style={{ fontSize: 12, color: 'var(--mid)', margin: '8px 0' }}>{it.description}</div>}
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                  <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }} onClick={() => openGrant(it.id)}>
                    افزودن به یک لرد
                  </button>
                  <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }} onClick={() => deleteItem(it.id)}>
                    حذف آیتم
                  </button>
                </div>
                {grantOpenId === it.id && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(160,195,255,0.07)' }}>
                    <label className="f" style={{ marginTop: 0 }}>لرد</label>
                    <PlayerPicker value={grantTarget} onChange={setGrantTarget} single />
                    <label className="f">میزان خاص‌بودن (رنگ)</label>
                    <div className="grid2">
                      {Object.entries(ITEM_RARITY_COLORS).map(([k, v]) => (
                        <div key={k} className={`pick ${grantColor === k ? 'sel' : ''}`}
                             style={{ borderColor: grantColor === k ? ITEM_RARITY_HEX[k] : undefined }}
                             onClick={() => { haptic(); setGrantColor(k); }}>
                          <div className="n" style={{ color: ITEM_RARITY_HEX[k] }}>{v}</div>
                        </div>
                      ))}
                    </div>
                    <button className="btn" style={{ marginTop: 14 }} disabled={grantBusy} onClick={() => grantItem(it.id)}>
                      {grantBusy ? 'در حال افزودن...' : 'افزودن به دارایی‌های این لرد'}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'balance' && isFull && (
        <>
          <div className="sect up u2">بازدهی و سقفِ ساختمان‌ها</div>
          <div className="page-sub up u2" style={{ marginTop: -4 }}>
            هر مقداری اینجا تغییر بدی، سراسری روی همهٔ بازیکن‌ها اثر می‌ذاره — این‌ها مقدارِ افزوده به‌ازای هر سطحِ همان ساختمانه
          </div>
          {!balanceList && <div className="loading">در حال بارگذاری...</div>}
          {balanceList && balanceList.map(b => {
            const draft = balanceDrafts[b.id] || {};
            const busy = balanceBusyId === b.id;
            return (
              <div className="card up u2" key={b.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="n">
                    {b.name}
                    {b.overridden && <small style={{ color: 'var(--az)' }}>سفارشی — با پیش‌فرض کد فرق دارد</small>}
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 10 }}>
                  {Object.keys(b.base_produces).map(k => (
                    <div key={k} style={{ minWidth: 110 }}>
                      <label className="f" style={{ marginTop: 0, fontSize: 11 }}>{RES_LABEL[k] || k} / روز <small style={{ color: 'var(--low)' }}>(پیش‌فرض {b.base_produces[k]})</small></label>
                      <input type="number" min="0" value={draft[k] ?? ''} onChange={e => setBalanceDraft(b.id, k, e.target.value)} />
                    </div>
                  ))}
                  {Object.keys(b.base_cap_bonus).map(k => (
                    <div key={k} style={{ minWidth: 110 }}>
                      <label className="f" style={{ marginTop: 0, fontSize: 11 }}>سقفِ {RES_LABEL[k] || k} <small style={{ color: 'var(--low)' }}>(پیش‌فرض {b.base_cap_bonus[k]})</small></label>
                      <input type="number" min="0" value={draft[k] ?? ''} onChange={e => setBalanceDraft(b.id, k, e.target.value)} />
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
                  <button className="btn" style={{ width: 'auto', padding: '8px 16px', fontSize: 11.5 }} disabled={busy} onClick={() => saveBalance(b)}>
                    {busy ? '...' : 'ذخیره'}
                  </button>
                  {b.overridden && (
                    <button className="btn ghost" style={{ width: 'auto', padding: '8px 16px', fontSize: 11.5 }} disabled={busy} onClick={() => resetBalance(b)}>
                      بازگشت به پیش‌فرض
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </>
      )}

      {tab === 'market' && isFull && (
        <>
          <div className="sect up u2">بازار وستروس</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>کالا</label>
            <select value={marketResource} onChange={e => setMarketResource(e.target.value)}>
              {TRADE_GOODS.map(g => <option key={g} value={g}>{TRADE_GOOD_NAMES[g]}</option>)}
            </select>
            <label className="f">حجم موجود</label>
            <input type="number" min="0" value={marketQty} onChange={e => setMarketQty(e.target.value)} placeholder="مثلاً: ۳۰۰" />
            <label className="f">قیمت (طلا به‌ازای هر واحد)</label>
            <input type="number" min="1" value={marketPrice} onChange={e => setMarketPrice(e.target.value)} placeholder="مثلاً: ۵" />
            <button className="btn" style={{ marginTop: 14 }} onClick={setMarketListing}>ثبت/به‌روزرسانی در بازار</button>
          </div>
          <div className="up u2">
            {(!marketListings || marketListings.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز کالایی در بازار وستروس نیست</div>
            )}
            {marketListings && marketListings.map(m => (
              <div className="res" key={m.resource}>
                <div className="n">{TRADE_GOOD_NAMES[m.resource] || m.resource}
                  <small>{m.qty.toLocaleString('fa-IR')} واحد · {m.price.toLocaleString('fa-IR')} طلا · پایه {m.base_price.toLocaleString('fa-IR')}</small>
                </div>
                <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }}
                        onClick={() => deleteMarketListing(m.resource)}>حذف</button>
              </div>
            ))}
          </div>

          <div className="sect up u3">افزودن به بازار سیاه</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>کالا</label>
            <select value={blackResource} onChange={e => setBlackResource(e.target.value)}>
              {TRADE_GOODS.map(g => <option key={g} value={g}>{TRADE_GOOD_NAMES[g]}</option>)}
            </select>
            <label className="f">حجم</label>
            <input type="number" min="1" value={blackQty} onChange={e => setBlackQty(e.target.value)} placeholder="مثلاً: ۴۰" />
            <label className="f">قیمت (طلا به‌ازای هر واحد)</label>
            <input type="number" min="1" value={blackPrice} onChange={e => setBlackPrice(e.target.value)} placeholder="مثلاً: ۵" />
            <label className="f">مدت (ساعت)</label>
            <input type="number" min="1" value={blackHours} onChange={e => setBlackHours(e.target.value)} />
            <button className="btn" style={{ marginTop: 14 }} onClick={createBlackMarketListing}>افزودن به بازار سیاه</button>
          </div>
          <div className="up u3">
            {(!blackListings || blackListings.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز جنسی در بازار سیاه نیست</div>
            )}
            {blackListings && blackListings.map(m => (
              <div className="res" key={m.id}>
                <div className="n">{TRADE_GOOD_NAMES[m.resource] || m.resource}
                  <small>{m.qty.toLocaleString('fa-IR')} واحد · {m.price.toLocaleString('fa-IR')} طلا · {Math.floor(m.expires_in_minutes / 60).toLocaleString('fa-IR')} ساعت مانده</small>
                </div>
                <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }}
                        onClick={() => deleteBlackMarketListing(m.id)}>حذف</button>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'resources' && isFull && (
        <>
          <div className="sect up u2">ویرایش منابع بازیکن</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>بازیکن</label>
            <PlayerPicker value={resTarget} onChange={setResTarget} single />
            {resTarget.length > 0 && !resValues && (
              <div className="page-sub" style={{ margin: '10px 4px' }}>در حال بارگذاری منابع...</div>
            )}
            {resValues && (
              <>
                {PLAYER_RES.map(({ key, label, Icon }) => (
                  <div className="troop" key={key}>
                    <div className="tn"><Icon s={14} /> {label}</div>
                    <input type="number" min="0" value={resValues[key] ?? 0}
                           onChange={e => setResValues({ ...resValues, [key]: Math.max(0, +e.target.value || 0) })} />
                  </div>
                ))}
                <button className="btn" style={{ marginTop: 14 }} disabled={resBusy} onClick={saveResources}>
                  {resBusy ? 'در حال ثبت...' : 'ثبت منابع تازه'}
                </button>
              </>
            )}
          </div>

          {resTarget.length > 0 && (
            <>
              <div className="sect up u3">لشکرهای «{resTarget[0].name}»</div>
              <div className="up u3">
                {resCampaigns === null && <div className="page-sub" style={{ margin: '0 4px' }}>در حال بارگذاری...</div>}
                {resCampaigns && resCampaigns.length === 0 && (
                  <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>این بازیکن لشکری ندارد</div>
                )}
                {resCampaigns && resCampaigns.map(c => (
                  <div className="card" key={c.id} style={{ marginBottom: 10 }}>
                    <div className="res">
                      <div className="ic"><Swords s={16} /></div>
                      <div className="n">
                        {c.name}
                        <small>
                          {c.op_name} · {castleLabel(c.from)} ← {castleLabel(c.to)} · توان {c.power.toLocaleString('fa-IR')} ·{' '}
                          {c.men_committed.toLocaleString('fa-IR')} نفر
                        </small>
                      </div>
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--mid)', margin: '8px 0' }}>
                      نیروها: {c.troops.length ? c.troops.map(t => `${t.name} × ${t.count.toLocaleString('fa-IR')}`).join(' · ') : '—'}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--low)' }}>
                        {c.active ? (c.arrived ? 'رسیده به مقصد' : 'در راه') : 'لغوشده'}
                      </div>
                      {c.active && (
                        <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11, color: 'var(--danger)' }}
                                disabled={disbandBusyId === c.id} onClick={() => disbandCampaign(c.id)}>
                          {disbandBusyId === c.id ? 'در حال انحلال...' : 'منحل کن'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {tab === 'polls' && isFull && (
        <>
          <div className="sect up u2">رای‌گیری تازه</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>سوال</label>
            <textarea value={pollQuestion} onChange={e => setPollQuestion(e.target.value)} placeholder="مثلاً: والی جنوب چه کسی باشد؟" />
            <label className="f">گزینه‌ها</label>
            {pollOptions.map((opt, i) => (
              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                <input value={opt} onChange={e => setPollOptions(pollOptions.map((o, j) => j === i ? e.target.value : o))}
                       placeholder={`گزینهٔ ${(i + 1).toLocaleString('fa-IR')}`} />
                {pollOptions.length > 2 && (
                  <button className="btn ghost" style={{ width: 44, padding: 0, flexShrink: 0 }}
                          onClick={() => setPollOptions(pollOptions.filter((_, j) => j !== i))}><Close s={14} /></button>
                )}
              </div>
            ))}
            <button className="btn ghost" style={{ padding: 10, fontSize: 12 }} onClick={() => setPollOptions([...pollOptions, ''])}>
              <Plus s={14} /> افزودن گزینه
            </button>
            <label className="f">چه کسانی حق رای دارند</label>
            <PlayerPicker value={pollEligible} onChange={setPollEligible} />
            <button className="btn" style={{ marginTop: 14 }} onClick={createPoll}>ساخت رای‌گیری</button>
          </div>

          <div className="sect up u3">رای‌گیری‌های موجود</div>
          <div className="up u3">
            {(!polls || polls.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>رای‌گیری‌ای ساخته نشده</div>
            )}
            {polls && polls.map(p => (
              <div className="card poll" key={p.id}>
                <div className="poll-q">
                  {p.question}
                  <span className={`poll-status ${p.status}`}>{p.status === 'open' ? 'باز' : 'بسته'}</span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginBottom: 8 }}>
                  {p.total_votes.toLocaleString('fa-IR')} رای — {p.options.join(' · ')}
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  {p.status === 'open' && (
                    <button className="btn ghost" style={{ padding: 10, fontSize: 12, flex: 1 }} onClick={() => closePoll(p.id)}>بستن رای‌گیری</button>
                  )}
                  <button className="btn ghost" style={{ padding: 10, fontSize: 12, flex: 1, color: 'var(--danger)' }} onClick={() => deletePoll(p.id)}>حذف رای‌گیری</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'events' && (
        <>
          <div className="sect up u2">اعلام رویداد به همهٔ بازیکنان</div>
          <div className="page-sub up u2" style={{ marginTop: -10 }}>
            توضیح یک اتفاق در طول بازی؛ این متن با کلاغ برای همه فرستاده می‌شود و در اطلاعیه‌ها می‌ماند.
          </div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>عنوان رویداد</label>
            <input value={eventTitle} onChange={e => setEventTitle(e.target.value)} maxLength={80}
                   placeholder="مثلاً: جشن پیروزی زمستان" />
            <label className="f">توضیحات</label>
            <textarea value={eventDescription} onChange={e => setEventDescription(e.target.value)} maxLength={1500}
                      rows={5} placeholder="شرح رویداد، قوانین و زمان آن..." />
            <button className="btn" style={{ marginTop: 14 }} disabled={eventBusy} onClick={sendEvent}>
              {eventBusy ? 'در حال ارسال...' : 'ارسال رویداد به همهٔ بازیکنان'}
            </button>
          </div>
        </>
      )}

      {tab === 'medals' && (
        <>
          <div className="sect up u2">مدال‌ها و نتایج نبرد</div>
          <div className="page-sub up u2" style={{ marginTop: -10 }}>
            مدال «راوی قلمرو» را دستی اعطا کن یا نتیجهٔ جنگ را برای محاسبهٔ مدال‌های رزمی ثبت کن.
          </div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>اعطای دستی مدال «راوی قلمرو»</label>
            <PlayerPicker value={medalTarget} onChange={setMedalTarget} single placeholder="بازیکن را انتخاب کن..." />
            <select value={medalTier} onChange={e => setMedalTier(e.target.value)} style={{ marginTop: 10 }}>
              <option value="bronze">برنز — قصه‌گو</option>
              <option value="silver">نقره — وقایع‌نگار</option>
              <option value="gold">طلا — زبان تاریخ</option>
            </select>
            <input value={medalReason} onChange={e => setMedalReason(e.target.value)} maxLength={200}
                   placeholder="دلیل اعطا (اختیاری)" style={{ marginTop: 10 }} />
            <button className="btn" style={{ marginTop: 12 }} disabled={medalBusy} onClick={awardStoryteller}>
              {medalBusy ? 'در حال ثبت...' : 'اعطای مدال'}
            </button>
          </div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>اعطای مدال ویژهٔ ادمین</label>
            <PlayerPicker value={specialMedalTarget} onChange={setSpecialMedalTarget} single placeholder="بازیکن را انتخاب کن..." />
            <label className="f">انتخاب مدال</label>
            <select value={specialMedalPreset} onChange={e => { setSpecialMedalPreset(e.target.value); setSpecialMedalIcon(''); }}>
              {SPECIAL_MEDAL_PRESETS.map(m => <option key={m.key} value={m.key}>{m.icon} {m.name}</option>)}
              <option value="custom">مدال با نام دلخواه</option>
            </select>
            {specialMedalPreset === 'custom' && (
              <input value={specialMedalName} onChange={e => setSpecialMedalName(e.target.value)}
                     maxLength={60} placeholder="نام دلخواه مدال" style={{ marginTop: 10 }} />
            )}
            <div className="grid2" style={{ marginTop: 10 }}>
              <input value={specialMedalIcon} onChange={e => setSpecialMedalIcon(e.target.value)} maxLength={8}
                     placeholder={SPECIAL_MEDAL_PRESETS.find(m => m.key === specialMedalPreset)?.icon || 'نشان، مثلاً 👑'} />
              <select value={specialMedalTier} onChange={e => setSpecialMedalTier(e.target.value)}>
                <option value="bronze">برنز</option>
                <option value="silver">نقره</option>
                <option value="gold">طلا</option>
              </select>
            </div>
            <input value={specialMedalReason} onChange={e => setSpecialMedalReason(e.target.value)} maxLength={300}
                   placeholder="دلیل اعطا (اختیاری)" style={{ marginTop: 10 }} />
            <button className="btn" style={{ marginTop: 12 }} disabled={specialMedalBusy} onClick={awardSpecialMedal}>
              {specialMedalBusy ? 'در حال ثبت...' : 'اعطای مدال ویژه'}
            </button>
          </div>
        </>
      )}

      {tab === 'bot_messages' && (
        <>
          <div className="sect up u2">ارسال پیام مستقیم از طرف بات تلگرام</div>
          <div className="page-sub up u2" style={{ marginTop: -10 }}>
            پیام فقط در چت خصوصی تلگرام فرستاده می‌شود و داخل صندوق کلاغ‌های بازی ذخیره نمی‌شود.
          </div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>گیرندگان</label>
            <select value={botAudience} onChange={e => { setBotAudience(e.target.value); setBotTargets([]); }}>
              <option value="all">همهٔ بازیکنان</option>
              <option value="selected">بازیکنان مشخص</option>
            </select>
            {botAudience === 'selected' && (
              <div style={{ marginTop: 12 }}>
                <PlayerPicker value={botTargets} onChange={setBotTargets} placeholder="نام لرد یا قلعه را جست‌وجو کن..." />
              </div>
            )}
            <label className="f">متن پیام بات</label>
            <textarea value={botMessage} onChange={e => setBotMessage(e.target.value)} maxLength={4000}
                      rows={6} placeholder="پیامی که بات مستقیماً برای بازیکن می‌فرستد..." />
            <button className="btn" style={{ marginTop: 14 }} disabled={botMessageBusy} onClick={sendBotMessage}>
              {botMessageBusy
                ? 'در حال ارسال...'
                : botAudience === 'all'
                  ? 'ارسال پیام بات به همهٔ بازیکنان'
                  : `ارسال پیام بات به ${botTargets.length.toLocaleString('fa-IR')} بازیکن`}
            </button>
          </div>
        </>
      )}

      {tab === 'admins' && isFull && (
        <>
          <div className="sect up u2">مدیریت ادمین‌ها</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>افزودن ادمین محدود (فقط لشکرکشی‌ها، رول‌ها، جاسوسی و مقام‌ها)</label>
            <PlayerPicker value={newAdminTarget} onChange={setNewAdminTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={addAdmin}>افزودن ادمین</button>
          </div>
          <div className="card up u2">
            {(!admins || admins.length === 0) && (
              <div style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>ادمینی نیست</div>
            )}
            {admins && admins.map(a => (
              <div className="res" key={a.tg_id}>
                <div className="ic"><Shield s={16} /></div>
                <div className="n">{a.name || a.tg_id}<small>{a.role === 'full' ? 'ادمین کامل' : 'ادمین محدود'}{a.castle ? ` · ${castleLabel(a.castle)}` : ''}</small></div>
                {a.role === 'limited' && (
                  <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }} onClick={() => removeAdmin(a.tg_id)}>حذف</button>
                )}
              </div>
            ))}
          </div>

          {me.is_owner && (
            <>
              <div className="sect up u3" style={{ color: 'var(--danger)' }}>منطقهٔ خطر — فقط صاحب بازی</div>
              <div className="card up u3" style={{ borderColor: 'var(--danger)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--danger)' }}>ری‌استارت کامل بازی</div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 8, lineHeight: 1.9 }}>
                  همهٔ بازیکن‌های غیرادمین حذف می‌شوند و باید از نو ثبت‌نام کنند؛ تاریخچهٔ لشکرکشی‌ها، جاسوسی‌ها،
                  پیام‌ها، رول‌ها، شایعات، اتحادها، رای‌گیری‌ها و کاروان‌ها پاک می‌شود.
                  <br />
                  دست‌نخورده می‌ماند: قلعه‌های ثبت‌شده روی نقشه، آیتم‌ها و بازارهایی که خودت ساخته‌ای، و حساب/پیشرفت خودِ ادمین‌ها.
                  <br />این کار بازگشت‌ناپذیر است.
                </div>
                {resetPreview && (
                  <div style={{ fontSize: 12, color: 'var(--hi)', marginTop: 10, fontWeight: 700 }}>
                    {resetPreview.non_admin_players.toLocaleString('fa-IR')} بازیکن حذف می‌شود · {resetPreview.admins_kept.toLocaleString('fa-IR')} ادمین می‌ماند
                  </div>
                )}
                <label className="f">برای تایید، عبارت RESET را تایپ کن</label>
                <input value={resetConfirmText} onChange={e => setResetConfirmText(e.target.value)} placeholder="RESET" style={{ direction: 'ltr', textAlign: 'center' }} />
                <button className="btn" style={{ marginTop: 14, background: 'linear-gradient(160deg, #b3271b, #690000 60%, #4a0000)' }}
                        disabled={resetConfirmText.trim() !== 'RESET' || resetBusy} onClick={resetGame}>
                  {resetBusy ? 'در حال ری‌استارت...' : 'ری‌استارت کامل بازی'}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
