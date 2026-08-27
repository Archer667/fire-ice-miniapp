import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Shield, Eye, Scroll, Plus, Close, Coin, Wood, Rock, Pick, Wheat, Wine, People, Warehouse, Swords } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import CastlePicker from '../components/CastlePicker.jsx';
import { MapFrame } from '../components/WesterosMap.jsx';
import ZoomPanMap from '../components/ZoomPanMap.jsx';
import { WARDEN_GROUPS, REGIONS_STATIC, TRADE_GOODS, TRADE_GOOD_NAMES, ROLEPLAY_CATEGORIES, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, ITEM_RARITY_HEX, WEAPON_NAMES, MAP_TERRAINS, castleLabel } from '../gamedata.js';

const NEW_CASTLE = '__new__';

const SPECIAL_MEDAL_PRESETS = [
  { key: 'season_champion', name: 'قهرمان فصل', icon: '🏆' },
  { key: 'realm_savior', name: 'ناجی قلمرو', icon: '🪽' },
  { key: 'immortal', name: 'نامیرا', icon: '♾️' },
  { key: 'golden_quill', name: 'صاحب قلم زرین', icon: '✒️' },
  { key: 'crown_enemy', name: 'دشمن تاج', icon: '🗡️' },
];

const MAP_KINDS = [
  { key: 'castle', label: 'قلعه' },
  { key: 'city',   label: 'شهر' },
  { key: 'ruin',   label: 'مخروبه' },
  { key: 'port',   label: 'بندر ⚓' },
];

// هر تب توضیح کوتاه و سطح دسترسی خودش را دارد تا ادمین تازه‌کار هم مسیر را گم نکند
const TAB_GROUPS = [
  {
    label: 'شروع و بازیکن‌ها',
    description: 'ورود بازیکن، منابع و مدیریت دسترسی‌ها',
    tabs: [
      { key: 'overview',   label: 'راهنمای پنل', description: 'کارهای روزانه و مسیر پیشنهادی' },
      { key: 'onboarding', label: 'خاندان‌ها', description: 'تخصیص بازیکن و مدیریت قلعه‌ها' },
      { key: 'resources',  label: 'منابع و لشکرها', description: 'ویرایش منابع و توقف لشکر', fullOnly: true },
      { key: 'admins',     label: 'ادمین‌ها', description: 'افزودن یا حذف ادمین محدود', fullOnly: true },
    ],
  },
  {
    label: 'داوری و ارتباط',
    description: 'صف‌هایی که بازیکن منتظر تصمیم یا پیام ادمین است',
    tabs: [
      { key: 'notifications', label: 'اعلان‌های ادمین', description: 'کارهای تازه و مهلت‌های نزدیک' },
      { key: 'war',         label: 'جنگ', description: 'لشکرکشی‌ها، کمین‌ها، نبردها و جاسوسی' },
      { key: 'roleplays',   label: 'رول‌ها', description: 'بررسی و اعلام نتیجهٔ سناریوهای بازیکنان' },
      { key: 'security_archive', label: 'آرشیو امنیتی', description: 'جست‌وجوی رول‌های دفاعی و امنیتی' },
      { key: 'rebellions',  label: 'شورش‌ها', description: 'بررسی رول و ثبت نتیجهٔ شورش' },
      { key: 'medals',      label: 'مدال‌ها', description: 'اعطای مدال روایی و ویژه' },
      { key: 'bot_messages', label: 'پیام بات', description: 'پیام مستقیم به همه یا چند بازیکن' },
      { key: 'rumor_admin', label: 'مدیریت توییت‌ها', description: 'دیدن نویسنده و حذف توییت' },
      { key: 'events',      label: 'رویداد همگانی', description: 'اعلام رویداد داخل صندوق بازی' },
    ],
  },
  {
    label: 'سیاست و جهان',
    description: 'اتحادها، مقام‌ها، رأی‌گیری و نقشه',
    tabs: [
      { key: 'alliances', label: 'اتحادها', description: 'مرور پیمان‌های بازیکنان' },
      { key: 'titles',    label: 'مقام‌ها', description: 'تعیین بالادست، والی و فرمانروا' },
      { key: 'polls',     label: 'رأی‌گیری', description: 'ساخت و بستن رأی‌گیری', fullOnly: true },
      { key: 'map',       label: 'نقشه', description: 'مدیریت نشانه‌ها و نوع زمین' },
    ],
  },
  {
    label: 'اقتصاد و تنظیمات',
    description: 'ابزارهای حساس و سراسری بازی',
    tabs: [
      { key: 'market',  label: 'بازار', description: 'بازار عمومی و بازار سیاه', fullOnly: true },
      { key: 'items',   label: 'آیتم‌ها', description: 'ساخت و اعطای آیتم', fullOnly: true },
      { key: 'balance', label: 'تعادل بازی', description: 'تغییر تولید و سقف ساختمان‌ها', fullOnly: true },
      { key: 'music', label: 'موسیقی بازی', description: 'فایل و تنظیمات موسیقی پس‌زمینه', fullOnly: true },
    ],
  },
];
const TABS = TAB_GROUPS.flatMap(g => g.tabs);
const TAB_BY_KEY = Object.fromEntries(TABS.map(t => [t.key, t]));

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
  const availGroups = TAB_GROUPS;
  const [tab, setTab] = useState('overview');

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

  const [warSubTab, setWarSubTab] = useState('campaigns'); // campaigns | ambushes | battles | espionage
  const [campaignsInfo, setCampaignsInfo] = useState(null);
  const [disbandBusyId, setDisbandBusyId] = useState(null);
  const [campaignLosses, setCampaignLosses] = useState({});
  const [ambushesList, setAmbushesList] = useState(null);
  const [ambushScores, setAmbushScores] = useState({});
  const [ambushQualityScores, setAmbushQualityScores] = useState({});
  const [ambushBusyId, setAmbushBusyId] = useState(null);
  const [warWindow, setWarWindow] = useState(null);
  const [warWindowBusy, setWarWindowBusy] = useState(false);
  const [eventTitle, setEventTitle] = useState('');
  const [eventDescription, setEventDescription] = useState('');
  const [eventBusy, setEventBusy] = useState(false);
  const [musicSettings, setMusicSettings] = useState(null);
  const [musicBusy, setMusicBusy] = useState(false);
  const [botMessage, setBotMessage] = useState('');
  const [botAudience, setBotAudience] = useState('all');
  const [botTargets, setBotTargets] = useState([]);
  const [botMessageBusy, setBotMessageBusy] = useState(false);
  const [botViaBot, setBotViaBot] = useState(true);
  const [botViaRaven, setBotViaRaven] = useState(false);
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
  const [seasonResetConfirm, setSeasonResetConfirm] = useState('');
  const [seasonResetBusy, setSeasonResetBusy] = useState(false);
  const [scoreResetConfirm, setScoreResetConfirm] = useState('');
  const [scoreResetBusy, setScoreResetBusy] = useState(false);

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
  const [resCaps, setResCaps] = useState(null);
  const [resPoints, setResPoints] = useState(null);
  const [resPopularity, setResPopularity] = useState(null);
  const [pointDelta, setPointDelta] = useState('');
  const [pointBusy, setPointBusy] = useState(false);
  const [popularityDelta, setPopularityDelta] = useState('');
  const [popularityBusy, setPopularityBusy] = useState(false);
  const [resBusy, setResBusy] = useState(false);
  const [resCampaigns, setResCampaigns] = useState(null);

  const [spyPending, setSpyPending] = useState(null);
  const [spyScores, setSpyScores] = useState({}); // missionId -> score string
  const [spyBusyId, setSpyBusyId] = useState(null);

  const [roleplayPending, setRoleplayPending] = useState(null);
  const [roleplayCategoryTab, setRoleplayCategoryTab] = useState('all');
  const [securityRoleplays, setSecurityRoleplays] = useState(null);
  const [securityQuery, setSecurityQuery] = useState('');
  const [securityPlayer, setSecurityPlayer] = useState([]);
  const [securitySearching, setSecuritySearching] = useState(false);
  const [battles, setBattles] = useState(null);
  const [roleplayResults, setRoleplayResults] = useState({}); // roleplayId -> result text
  const [roleplayVisibility, setRoleplayVisibility] = useState({}); // roleplayId -> 'participants' | 'all'
  const [roleplayOtherLords, setRoleplayOtherLords] = useState({}); // roleplayId -> [{tg_id, name}]
  const [roleplayWinners, setRoleplayWinners] = useState({}); // roleplayId -> winner tg_id
  const [roleplayLosses, setRoleplayLosses] = useState({}); // roleplayId -> {attacker:{troopId:n}, defender:{troopId:n}}
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
  const [balanceDrafts, setBalanceDrafts] = useState({});
  const [balanceBusyId, setBalanceBusyId] = useState(null);
  const [buildingAdminMode, setBuildingAdminMode] = useState('global');
  const [playerBuildingTarget, setPlayerBuildingTarget] = useState([]);
  const [playerBuildingData, setPlayerBuildingData] = useState(null);
  const [playerBuildingCastle, setPlayerBuildingCastle] = useState('');
  const [playerBuildingDrafts, setPlayerBuildingDrafts] = useState({});
  const [playerBuildingBusyId, setPlayerBuildingBusyId] = useState(null);
  const [rebellionSettings, setRebellionSettings] = useState(null);
  const [rebellionsList, setRebellionsList] = useState(null);
  const [rebellionSettingsBusy, setRebellionSettingsBusy] = useState(false);
  const [rebellionDrafts, setRebellionDrafts] = useState({});
  const [rebellionBusyId, setRebellionBusyId] = useState(null);
  const [adminNotifications, setAdminNotifications] = useState(null);
  const [notificationFilter, setNotificationFilter] = useState('unread');
  const [adminRumors, setAdminRumors] = useState(null);
  const [rumorDeleteBusy, setRumorDeleteBusy] = useState(null);
  const [cleanupPreview, setCleanupPreview] = useState(null);
  const [cleanupConfirm, setCleanupConfirm] = useState({});
  const [cleanupBusy, setCleanupBusy] = useState(null);

  const loadPendingPlayers = () => api.adminListPendingPlayers().then(setPendingPlayers).catch(e => toast(e.message));
  const loadRoster = () => api.adminListRoster().then(setRoster).catch(e => toast(e.message));
  const loadCampaigns = () => api.adminCampaigns().then(setCampaignsInfo).catch(e => toast(e.message));
  const loadAmbushes = () => api.adminAmbushes().then(setAmbushesList).catch(e => toast(e.message));
  const loadWarWindow = () => api.adminGetWarWindow().then(setWarWindow).catch(e => toast(e.message));
  const loadSpyPending = () => api.adminSpyPending().then(setSpyPending).catch(e => toast(e.message));
  const loadSpyResolved = () => api.adminSpyResolved().then(setSpyResolved).catch(e => toast(e.message));
  const loadRoleplayPending = () => api.adminRoleplayPending().then(setRoleplayPending).catch(e => toast(e.message));
  const loadSecurityRoleplays = async () => {
    setSecuritySearching(true);
    try { setSecurityRoleplays(await api.adminSecurityRoleplays(securityQuery.trim(), securityPlayer[0]?.tg_id || null)); }
    catch (e) { toast(e.message); setSecurityRoleplays([]); }
    setSecuritySearching(false);
  };
  const loadBattles = () => api.adminBattles().then(setBattles).catch(e => toast(e.message));
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
    setBalanceDrafts(Object.fromEntries(list.map(b => [b.id, {
      cost: Object.fromEntries(Object.keys(b.base_cost || {}).map(k => [k, String(b.cost?.[k] ?? b.base_cost[k])])),
      cost_step_percent: String(b.cost_step_percent ?? b.base_cost_step_percent ?? 15),
      produces: Object.fromEntries(Object.keys(b.base_produces || {}).map(k => [k, String(b.produces?.[k] ?? b.base_produces[k])])),
      cap_bonus: Object.fromEntries(Object.keys(b.base_cap_bonus || {}).map(k => [k, String(b.cap_bonus?.[k] ?? b.base_cap_bonus[k])])),
    }])));
  }).catch(e => toast(e.message));

  const loadAdminNotifications = () => api.adminNotifications().then(setAdminNotifications).catch(e => toast(e.message));
  const loadAdminRumors = () => api.adminRumors().then(setAdminRumors).catch(e => toast(e.message));
  const loadCleanupPreview = () => { if (isFull) api.adminCleanupPreview().then(setCleanupPreview).catch(e => toast(e.message)); };
  const loadRebellions = () => api.adminRebellions().then(setRebellionsList).catch(e => toast(e.message));
  const loadRebellionSettings = () => {
    if (!isFull) return;
    api.adminRebellionSettings().then(setRebellionSettings).catch(e => toast(e.message));
  };
  const setRebellionNumber = (key, value) => setRebellionSettings(prev => ({ ...prev, [key]: Number(value) }));
  const saveRebellionSettings = async () => {
    setRebellionSettingsBusy(true);
    try {
      const saved = await api.adminSaveRebellionSettings(rebellionSettings);
      setRebellionSettings(saved);
      toast('تنظیمات شورش ذخیره شد');
    } catch (e) { toast(e.message); }
    setRebellionSettingsBusy(false);
  };
  const resolveRebellion = async (row) => {
    const draft = rebellionDrafts[row.id] || {};
    if (!(draft.result || '').trim()) { toast('متن نتیجه شورش را بنویس'); return; }
    setRebellionBusyId(row.id);
    try {
      await api.adminResolveRebellion(row.id, {
        result: draft.result.trim(),
        popularity_delta: Number(draft.popularity_delta || 0),
        gold_delta: Number(draft.gold_delta || 0),
        food_delta: Number(draft.food_delta || 0),
        men_delta: Number(draft.men_delta || 0),
        outcome: draft.outcome || 'resolved',
      });
      toast('نتیجه شورش ثبت و برای بازیکن ارسال شد');
      loadRebellions();
    } catch (e) { toast(e.message); }
    setRebellionBusyId(null);
  };

  useEffect(() => {
    loadAdminNotifications();
    loadAdminRumors();
    loadCleanupPreview();
    loadPendingPlayers();
    loadRoster();
    loadCampaigns();
    loadAmbushes();
    loadWarWindow();
    loadSpyPending();
    loadSpyResolved();
    loadRoleplayPending();
    api.adminSecurityRoleplays().then(setSecurityRoleplays).catch(() => setSecurityRoleplays([]));
    loadBattles();
    loadAlliances();
    loadRebellions();
    loadRebellionSettings();
    loadMapData();
    if (isFull) { loadPolls(); loadAdmins(); loadMarket(); loadBlackMarket(); loadItems(); loadBalance(); api.adminMusicSettings().then(setMusicSettings).catch(e => toast(e.message)); }
    if (me.is_owner) loadResetPreview();
  }, []);

  useEffect(() => {
    loadMapOptions();
    resetCastlePicker();
    setEditingCastle(null);
  }, [mapRegion]);

  useEffect(() => {
    if (!playerBuildingTarget.length) {
      setPlayerBuildingData(null); setPlayerBuildingCastle(''); setPlayerBuildingDrafts({});
      return;
    }
    setPlayerBuildingData(null);
    api.adminPlayerBuildings(playerBuildingTarget[0].tg_id).then(data => {
      setPlayerBuildingData(data);
      const firstCastle = data.castles?.[0]?.castle || '';
      setPlayerBuildingCastle(firstCastle);
      setPlayerBuildingDrafts(Object.fromEntries(
        (data.castles || []).flatMap(castle => castle.buildings.map(b => [`${castle.castle}::${b.id}`, String(b.level)]))
      ));
    }).catch(e => toast(e.message));
  }, [playerBuildingTarget]);

  useEffect(() => {
    if (!resTarget.length) { setResValues(null); setResCaps(null); setResPoints(null); setResPopularity(null); setResCampaigns(null); return; }
    setResValues(null); setResCaps(null); setResPoints(null); setResPopularity(null); setPointDelta(''); setPopularityDelta(''); setResCampaigns(null);
    api.adminGetPlayerResources(resTarget[0].tg_id)
      .then(r => {
        setResValues(r.resources);
        setResCaps(r.resource_caps || {});
        setResPoints(r.points ?? 0);
        setResPopularity(r.popularity ?? 50);
      })
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

  const adjustPoints = async () => {
    if (!resTarget.length) return;
    const delta = Number(pointDelta);
    if (!Number.isInteger(delta) || delta === 0) { toast('مقدار افزایش یا کاهش امتیاز را وارد کن'); return; }
    setPointBusy(true);
    try {
      const result = await api.adminAdjustPlayerPoints(resTarget[0].tg_id, delta);
      setResPoints(result.points);
      setPointDelta('');
      haptic('medium');
      toast(`امتیاز «${resTarget[0].name}» به ${result.points.toLocaleString('fa-IR')} رسید`);
    } catch (e) { toast(e.message); }
    setPointBusy(false);
  };

  const adjustPopularity = async () => {
    if (!resTarget.length) return;
    const delta = Number(popularityDelta);
    if (!Number.isInteger(delta) || delta === 0) { toast('مقدار افزایش یا کاهش محبوبیت را وارد کن'); return; }
    setPopularityBusy(true);
    try {
      const result = await api.adminAdjustPlayerPopularity(resTarget[0].tg_id, delta);
      setResPopularity(result.popularity); setPopularityDelta(''); haptic('medium');
      toast(`محبوبیت «${resTarget[0].name}» به ${result.popularity.toLocaleString('fa-IR')} رسید`);
    } catch (e) { toast(e.message); }
    setPopularityBusy(false);
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
    if (!botViaBot && !botViaRaven) { toast('بات، کلاغ یا هر دو را انتخاب کن'); return; }
    if (botAudience === 'selected' && botTargets.length === 0) { toast('حداقل یک بازیکن را انتخاب کن'); return; }
    setBotMessageBusy(true);
    try {
      const res = await api.adminSendBotMessage(
        text,
        botAudience === 'all',
        botTargets.map(p => p.tg_id),
        botViaBot,
        botViaRaven,
      );
      haptic('medium');
      toast(`پیام برای ${(res.sent_to ?? 0).toLocaleString('fa-IR')} بازیکن ارسال شد`);
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
      const res = await api.adminDisbandCampaign(id);
      haptic('medium');
      toast(res.battle_dismissed ? 'لشکر منحل و نبرد مرتبط بسته شد؛ دیگر لشکرها آزاد شدند' : 'لشکر منحل شد و تمام هزینه‌هایش برگشت');
      if (resTarget.length) api.adminPlayerCampaigns(resTarget[0].tg_id).then(setResCampaigns).catch(() => {});
      loadCampaigns(); loadBattles(); loadRoleplayPending();
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
    if (roleplay?.category === 'war') {
      setTab('war'); setWarSubTab('battles');
      toast('نتیجه و تلفات جنگ فقط از پروندهٔ یکپارچهٔ نبرد ثبت می‌شود');
      return;
    }
    const winnerTgId = roleplayWinners[roleplayId] || null;
    if (roleplay?.category === 'war' && !winnerTgId) { toast('برندهٔ نبرد را مشخص کن'); return; }
    setRoleplayBusyId(roleplayId);
    try {
      const losses = roleplayLosses[roleplayId] || {};
      const res = await api.adminRespondRoleplay(roleplayId, result, visibility, otherLords, winnerTgId, losses.attacker || {}, losses.defender || {});
      haptic('medium');
      toast(visibility === 'all' ? `اعلامیه برای همهٔ بازیکنان (${(res.sent_to || 0).toLocaleString('fa-IR')} نفر) فرستاده شد` : 'نتیجهٔ رول برای بازیکن فرستاده شد');
      setRoleplayResults(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayVisibility(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayOtherLords(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayWinners(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      setRoleplayLosses(prev => { const n = { ...prev }; delete n[roleplayId]; return n; });
      loadRoleplayPending();
    } catch (e) { toast(e.message); }
    setRoleplayBusyId(null);
  };

  const chooseMusicFile = (file) => {
    if (!file) return;
    if (!file.type.startsWith('audio/')) { toast('فقط فایل صوتی انتخاب کن'); return; }
    if (file.size > 7 * 1024 * 1024) { toast('حجم موسیقی باید حداکثر ۷ مگابایت باشد'); return; }
    const reader = new FileReader();
    reader.onload = () => setMusicSettings(p => ({ ...(p || {}), audio_url: String(reader.result || ''), title: p?.title || file.name.replace(/\.[^.]+$/, '') }));
    reader.onerror = () => toast('خواندن فایل موسیقی ناموفق بود');
    reader.readAsDataURL(file);
  };

  const saveMusic = async () => {
    if (!musicSettings) return;
    setMusicBusy(true);
    try {
      const saved = await api.adminSaveMusicSettings({
        ...musicSettings, volume: Math.max(0, Math.min(100, Number(musicSettings.volume) || 0)),
      });
      setMusicSettings(saved); haptic('medium'); toast('تنظیمات موسیقی بازی ذخیره شد');
    } catch (e) { toast(e.message); }
    setMusicBusy(false);
  };

  const scoreAmbush = async (id) => {
    const coefficient = Number(ambushScores[id]);
    const ambushScore = Number(ambushQualityScores[id]);
    if (Number.isNaN(coefficient) || coefficient < 0 || coefficient > 10) { toast('ضریب باید بین صفر تا ۱۰ باشد'); return; }
    if (Number.isNaN(ambushScore) || ambushScore < 0 || ambushScore > 100) { toast('امتیاز کمین باید بین صفر تا ۱۰۰ باشد'); return; }
    setAmbushBusyId(id);
    try { await api.adminScoreAmbush(id, coefficient, ambushScore); haptic('medium'); toast('ضریب و امتیاز ثبت شد و کمین فعال شد'); loadAmbushes(); }
    catch (e) { toast(e.message); }
    setAmbushBusyId(null);
  };

  const reduceCampaign = async (campaign) => {
    const troops = campaignLosses[campaign.id] || {};
    if (!Object.values(troops).some(v => Number(v) > 0)) { toast('تلفات حداقل یک نیرو را وارد کن'); return; }
    setDisbandBusyId(campaign.id);
    try { await api.adminReduceCampaign(campaign.id, troops); toast('تلفات لشکر ثبت شد؛ چیزی به بازیکن برنگشت'); loadCampaigns(); if (resTarget.length) api.adminPlayerCampaigns(resTarget[0].tg_id).then(setResCampaigns); }
    catch (e) { toast(e.message); }
    setDisbandBusyId(null);
  };

  const destroyCampaign = async (id) => {
    if (!window.confirm('این لشکر کامل منهدم شود؟ هیچ نفر، سکه، سلاح یا ادواتی برنمی‌گردد.')) return;
    setDisbandBusyId(id);
    try { const res = await api.adminDestroyCampaign(id); toast(res.battle_dismissed ? 'لشکر منهدم و نبرد مرتبط بسته شد؛ دیگر لشکرها آزاد شدند' : 'لشکر کاملاً منهدم شد'); loadCampaigns(); loadBattles(); loadRoleplayPending(); if (resTarget.length) api.adminPlayerCampaigns(resTarget[0].tg_id).then(setResCampaigns); }
    catch (e) { toast(e.message); }
    setDisbandBusyId(null);
  };

  const resetSeason = async () => {
    if (seasonResetConfirm.trim() !== 'NEWSEASON') { toast('عبارت NEWSEASON را دقیق تایپ کن'); return; }
    if (!window.confirm('فصل تازه شروع شود؟ پیشرفت همه صفر می‌شود، اما بازیکن‌ها و قلعه‌هایشان باقی می‌مانند.')) return;
    setSeasonResetBusy(true);
    try {
      const res = await api.adminResetSeason(seasonResetConfirm.trim());
      haptic('medium'); toast(`فصل تازه شروع شد؛ ${res.players_reset ?? 0} بازیکن ریست شد`);
      setSeasonResetConfirm(''); loadRoster(); loadCampaigns(); loadMapData();
    } catch (e) { toast(e.message); }
    setSeasonResetBusy(false);
  };

  const resetScoreboard = async () => {
    if (scoreResetConfirm.trim() !== 'SCOREBOARD') { toast('عبارت SCOREBOARD را دقیق تایپ کن'); return; }
    if (!window.confirm('مبنای امتیاز همهٔ بازیکن‌ها از همین لحظه صفر شود؟')) return;
    setScoreResetBusy(true);
    try {
      const res = await api.adminResetScoreboard(scoreResetConfirm.trim());
      haptic('medium'); toast(`جدول امتیازات ${res.players_reset ?? 0} بازیکن صفر شد`);
      setScoreResetConfirm(''); loadRoster();
    } catch (e) { toast(e.message); }
    setScoreResetBusy(false);
  };

  const resolveBattle = async (battle) => {
    const id = battle.campaign_id;
    const result = (roleplayResults[id] || '').trim();
    const winner = roleplayWinners[id];
    if (result.length < 3) { toast('متن نتیجه خیلی کوتاه است'); return; }
    if (!winner) { toast('برندهٔ نبرد را مشخص کن'); return; }
    setRoleplayBusyId(id);
    try {
      const losses = roleplayLosses[id] || {};
      await api.adminResolveBattle(id, result, roleplayVisibility[id] || 'participants', winner, losses.attacker || {}, losses.defender || {}, losses.attackerEquipment || {}, losses.defenderEquipment || {}, losses.attackers || {}, losses.attackerEquipments || {}, losses.defenders || {}, losses.defenderEquipments || {});
      toast('نتیجهٔ نبرد ثبت و لشکرهای بازمانده آزاد شدند');
      loadBattles(); loadRoleplayPending(); loadCampaigns();
    } catch (e) { toast(e.message); }
    setRoleplayBusyId(null);
  };

  const dismissBattle = async (battle) => {
    if (!window.confirm(`نبرد «${battle.name}» منحل شود؟ نتیجه و برنده‌ای ثبت نمی‌شود و لشکرها آزاد می‌شوند.`)) return;
    setRoleplayBusyId(battle.campaign_id);
    try {
      await api.adminDismissBattle(battle.campaign_id);
      haptic('medium'); toast('نبرد منحل و لشکرهای درگیر آزاد شدند');
      loadBattles(); loadRoleplayPending(); loadCampaigns();
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

  const setBalanceDraft = (bid, section, key, value) => {
    setBalanceDrafts(prev => ({
      ...prev,
      [bid]: {
        ...prev[bid],
        [section]: key === null ? value : { ...(prev[bid]?.[section] || {}), [key]: value },
      },
    }));
  };

  const parseBalanceMap = (values, errorText) => {
    const out = {};
    for (const [key, value] of Object.entries(values || {})) {
      const n = parseInt(value, 10);
      if (isNaN(n) || n < 0) throw new Error(errorText);
      out[key] = n;
    }
    return out;
  };

  const saveBalance = async (b) => {
    const draft = balanceDrafts[b.id] || {};
    let payload;
    try {
      const step = Number(draft.cost_step_percent);
      if (!Number.isFinite(step) || step < 0 || step > 500) throw new Error('درصد رشد هزینه باید بین صفر تا ۵۰۰ باشد');
      payload = {
        building_id: b.id,
        cost: parseBalanceMap(draft.cost, 'هزینه‌ها باید عدد صحیح و غیرمنفی باشند'),
        cost_step_percent: step,
        produces: parseBalanceMap(draft.produces, 'مقدار تولید باید عدد صحیح و غیرمنفی باشد'),
        cap_bonus: parseBalanceMap(draft.cap_bonus, 'افزایش سقف باید عدد صحیح و غیرمنفی باشد'),
      };
    } catch (e) { toast(e.message); return; }
    setBalanceBusyId(b.id);
    try {
      await api.adminSetBuildingBalance(payload);
      haptic('medium');
      toast(`تنظیمات «${b.name}» ذخیره شد`);
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
      loadBalance();
    } catch (e) { toast(e.message); }
    setBalanceBusyId(null);
  };

  const savePlayerBuilding = async (row) => {
    if (!playerBuildingTarget.length || !playerBuildingCastle) return;
    const key = `${playerBuildingCastle}::${row.id}`;
    const level = parseInt(playerBuildingDrafts[key], 10);
    const maxLevel = row.max_level || playerBuildingData?.max_level || 30;
    if (isNaN(level) || level < 0 || level > maxLevel) {
      toast(`سطح باید بین صفر تا ${maxLevel.toLocaleString('fa-IR')} باشد`); return;
    }
    setPlayerBuildingBusyId(row.id);
    try {
      await api.adminSetPlayerBuilding(playerBuildingTarget[0].tg_id, row.id, playerBuildingCastle, level);
      haptic('medium');
      toast(level === 0 ? `«${row.name}» حذف شد` : `سطح «${row.name}» روی ${level.toLocaleString('fa-IR')} ثبت شد`);
      const data = await api.adminPlayerBuildings(playerBuildingTarget[0].tg_id);
      setPlayerBuildingData(data);
      setPlayerBuildingDrafts(Object.fromEntries(
        (data.castles || []).flatMap(castle => castle.buildings.map(b => [`${castle.castle}::${b.id}`, String(b.level)]))
      ));
    } catch (e) { toast(e.message); }
    setPlayerBuildingBusyId(null);
  };

  const deleteAdminRumor = async (row) => {
    if (!window.confirm(`توییتٔ «${row.text.slice(0, 60)}» حذف شود؟ محبوبیت کم‌شده برنمی‌گردد.`)) return;
    setRumorDeleteBusy(row.id);
    try {
      await api.adminDeleteRumor(row.id);
      setAdminRumors(prev => prev?.filter(x => x.id !== row.id));
      toast('توییت حذف شد');
    } catch (e) { toast(e.message); }
    setRumorDeleteBusy(null);
  };

  const runCleanup = async (category, token, label) => {
    if ((cleanupConfirm[category] || '').trim() !== token) {
      toast(`برای پاک‌سازی باید دقیقاً ${token} را بنویسی`);
      return;
    }
    if (!window.confirm(`تاریخچهٔ ${label} پاک شود؟ این کار برگشت‌ناپذیر است.`)) return;
    setCleanupBusy(category);
    try {
      const result = await api.adminCleanup(category, token);
      toast(`${result.deleted.toLocaleString('fa-IR')} مورد از ${label} پاک شد`);
      setCleanupConfirm(prev => ({ ...prev, [category]: '' }));
      loadCleanupPreview();
      if (category === 'rumors') loadAdminRumors();
    } catch (e) { toast(e.message); }
    setCleanupBusy(null);
  };

  const markNotificationRead = async (id) => {
    try {
      await api.adminReadNotification(id);
      setAdminNotifications(prev => prev?.map(x => x.id === id ? { ...x, read: true } : x));
    } catch (e) { toast(e.message); }
  };

  const markAllNotificationsRead = async () => {
    try {
      await api.adminReadAllNotifications();
      setAdminNotifications(prev => prev?.map(x => ({ ...x, read: true })));
      toast('همهٔ اعلان‌ها خوانده شدند');
    } catch (e) { toast(e.message); }
  };

  const openTab = (key) => {
    const target = TAB_BY_KEY[key];
    if (target?.fullOnly && !isFull) {
      toast('این بخش فقط برای ادمین کامل باز است');
      return;
    }
    haptic();
    setTab(key);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const tabBadge = (key) => {
    if (key === 'notifications') return adminNotifications?.filter(x => !x.read).length || 0;
    if (key === 'onboarding') return pendingPlayers?.length || 0;
    if (key === 'war') return (spyPending?.length || 0) + (battles?.length || 0) + (ambushesList?.filter(a => a.status === 'pending_score').length || 0);
    if (key === 'roleplays') return roleplayPending?.length || 0;
    if (key === 'rebellions') return rebellionsList?.filter(x => !['resolved', 'suppressed', 'player_won', 'rebels_won'].includes(x.status)).length || 0;
    return 0;
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
      <div className="admin-role-card up">
        <div>
          <strong>{isFull ? 'ادمین کامل' : 'ادمین محدود'}</strong>
          <small>{isFull
            ? 'به تنظیمات سراسری و ابزارهای حساس دسترسی داری.'
            : 'به داوری‌ها، بازیکن‌ها، نقشه، مدال و پیام‌رسانی دسترسی داری؛ تنظیمات حساس قفل‌اند.'}</small>
        </div>
        <span className={`admin-role-badge ${isFull ? 'full' : 'limited'}`}>{isFull ? 'دسترسی کامل' : 'دسترسی اجرایی'}</span>
      </div>

      <nav className="admin-nav" aria-label="بخش‌های پنل ادمین">
        {availGroups.map((g, gi) => (
          <section key={g.label} className={gi > 0 ? 'tabs-group' : ''}>
            <div className="tabs-group-heading up u1">
              <div className="tabs-group-label">{g.label}</div>
              <div className="tabs-group-description">{g.description}</div>
            </div>
            <div className="tabs admin-tabs up u1" role="tablist" aria-label={g.label}>
              {g.tabs.map(t => {
                const locked = t.fullOnly && !isFull;
                const count = tabBadge(t.key);
                return (
                  <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
                       aria-disabled={locked}
                       className={`rbtn tab admin-tab ${tab === t.key ? 'on' : ''} ${locked ? 'locked' : ''}`}
                       onClick={() => openTab(t.key)}>
                    <span>{t.label}{locked ? ' 🔒' : ''}</span>
                    <small>{locked ? 'فقط ادمین کامل' : t.description}</small>
                    {count > 0 && <b className="admin-tab-count">{count.toLocaleString('fa-IR')}</b>}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </nav>

      {tab !== 'overview' && TAB_BY_KEY[tab] && (
        <div className="admin-current-guide up u2">
          <strong>{TAB_BY_KEY[tab].label}</strong>
          <span>{TAB_BY_KEY[tab].description}</span>
          <button type="button" className="rbtn" onClick={() => openTab('overview')}>راهنمای پنل</button>
        </div>
      )}

      {tab === 'notifications' && (
        <>
          <div className="sect up u2">صندوق اعلان‌های مدیریتی</div>
          <div className="admin-notification-toolbar up u2">
            <div className="tabs" role="tablist" aria-label="فیلتر اعلان‌ها">
              <button type="button" className={`rbtn tab ${notificationFilter === 'unread' ? 'on' : ''}`}
                      onClick={() => setNotificationFilter('unread')}>
                خوانده‌نشده ({(adminNotifications?.filter(x => !x.read).length || 0).toLocaleString('fa-IR')})
              </button>
              <button type="button" className={`rbtn tab ${notificationFilter === 'all' ? 'on' : ''}`}
                      onClick={() => setNotificationFilter('all')}>همه</button>
            </div>
            <button type="button" className="btn ghost" disabled={!adminNotifications?.some(x => !x.read)}
                    onClick={markAllNotificationsRead}>همه را خواندم</button>
          </div>
          <div className="page-sub up u2" style={{ margin: '0 4px 12px', lineHeight: 1.9 }}>
            تلگرام فقط هشدار کوتاه می‌فرسته؛ جزئیات، مهلت و کار پیشنهادی هر پرونده این‌جا می‌مونه.
          </div>
          <div className="admin-notification-list up u3">
            {adminNotifications === null && <div className="loading">در حال گرفتن اعلان‌ها...</div>}
            {adminNotifications && adminNotifications.filter(x => notificationFilter === 'all' || !x.read).length === 0 && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)' }}>
                {notificationFilter === 'unread' ? 'اعلان خوانده‌نشده‌ای نداری' : 'هنوز اعلان مدیریتی ثبت نشده'}
              </div>
            )}
            {adminNotifications && adminNotifications
              .filter(x => notificationFilter === 'all' || !x.read)
              .map(n => {
                const deadline = n.deadline ? new Date(n.deadline) : null;
                const remainingMinutes = deadline ? Math.floor((deadline.getTime() - Date.now()) / 60000) : null;
                return (
                  <article key={n.id} className={`admin-notification-card ${n.read ? 'read' : ''} priority-${n.priority || 'normal'}`}>
                    <header>
                      <div><strong>{n.title}</strong><small>{new Date(n.created_at).toLocaleString('fa-IR')}</small></div>
                      <span>{({ urgent: 'فوری', high: 'مهم', normal: 'عادی' })[n.priority] || 'عادی'}</span>
                    </header>
                    <p>{n.detail}</p>
                    {(n.player_name || n.castle) && (
                      <div className="admin-notification-meta">
                        {n.player_name && <span>بازیکن: {n.player_name}</span>}
                        {n.castle && <span>قلعه: {castleLabel(n.castle)}</span>}
                      </div>
                    )}
                    {deadline && (
                      <div className={`admin-notification-deadline ${remainingMinutes !== null && remainingMinutes <= 120 ? 'near' : ''}`}>
                        مهلت: {deadline.toLocaleString('fa-IR')}
                        {remainingMinutes !== null && remainingMinutes > 0 ? ` · ${Math.ceil(remainingMinutes / 60).toLocaleString('fa-IR')} ساعت مانده` : ' · مهلت تمام شده'}
                      </div>
                    )}
                    {n.action && <div className="admin-notification-action"><b>کاری که باید بکنی:</b> {n.action}</div>}
                    {!n.read && <button type="button" className="btn ghost" onClick={() => markNotificationRead(n.id)}>دیدم؛ خوانده شد</button>}
                  </article>
                );
              })}
          </div>
        </>
      )}

      {tab === 'overview' && (
        <>
          <div className="sect up u2">از کجا شروع کنم؟</div>
          <div className="admin-help-card card up u2">
            <p>اگه تازه وارد این پنلی، کارها رو به همین ترتیب جلو ببر. عددِ روی هر تب یعنی چند مورد منتظر رسیدگیه.</p>
            <div className="admin-workflow">
              <button type="button" className="rbtn" onClick={() => openTab('onboarding')}>
                <b>۱. بازیکن‌های تازه</b><span>خاندان و قلعه‌شون رو مشخص کن</span>
              </button>
              <button type="button" className="rbtn" onClick={() => openTab('war')}>
                <b>۲. داوری‌ها</b><span>جاسوسی و رول‌های منتظر رو جواب بده</span>
              </button>
              <button type="button" className="rbtn" onClick={() => openTab('rebellions')}>
                <b>۳. شورش‌ها</b><span>مهلت‌ها و رول‌های شورش رو بررسی کن</span>
              </button>
              <button type="button" className="rbtn" onClick={() => openTab('bot_messages')}>
                <b>۴. اطلاع‌رسانی</b><span>در صورت نیاز پیام مستقیم بفرست</span>
              </button>
            </div>
          </div>
          <div className="admin-help-grid up u3">
            <div className="card">
              <strong>کارهای روزمره</strong>
              <p>خاندان‌ها، جنگ و رول‌ها، شورش‌ها و پیام بات. بازیکن در این بخش‌ها منتظر ادمینه.</p>
            </div>
            <div className="card">
              <strong>کارهای حساس</strong>
              <p>منابع، بازار، آیتم‌ها، تعادل و مدیریت ادمین فقط برای ادمین کامل بازه و روی کل بازی اثر می‌ذاره.</p>
            </div>
            <div className="card">
              <strong>پیام بات یا رویداد؟</strong>
              <p>«پیام بات» فقط به چت تلگرام می‌ره؛ «رویداد همگانی» داخل صندوق کلاغ‌های بازی هم ثبت می‌شه.</p>
            </div>
            <div className="card">
              <strong>قبل از تغییر بزرگ</strong>
              <p>اسم بازیکن، قلعه و اثر عملیات رو دوباره بخون. انتقال قلعه و ری‌استارت می‌تونه بازگشت‌ناپذیر باشه.</p>
            </div>
          </div>
        </>
      )}

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
          <div className="tabs up u1" role="tablist" aria-label="بخش‌های جنگ">
            {[
              { key: 'campaigns', label: 'لشکرکشی‌ها' },
              { key: 'ambushes', label: `کمین‌ها${ambushesList?.filter(a => a.status === 'pending_score').length ? ` (${ambushesList.filter(a => a.status === 'pending_score').length.toLocaleString('fa-IR')})` : ''}` },
              { key: 'battles', label: `نبردها${battles?.length ? ` (${battles.length.toLocaleString('fa-IR')})` : ''}` },
              { key: 'espionage', label: 'جاسوسی' },
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

          {warSubTab === 'ambushes' && <div className="up u2">
            <div className="page-sub" style={{ marginBottom: 12 }}>ضریب ۰ تا ۱۰، تلفات دشمن را مشخص می‌کند. امتیاز کمین ۰ تا ۱۰۰ کیفیت عقب‌نشینی است: مثلاً امتیاز ۸۰ یعنی ۲۰٪ نیروهای کمین‌گذار از بین می‌روند و ۸۰٪ با هزینه‌هایشان برمی‌گردند.</div>
            {ambushesList === null && <div className="loading">در حال بارگذاری کمین‌ها...</div>}
            {ambushesList && ambushesList.length === 0 && <div className="card" style={{ textAlign: 'center', color: 'var(--mid)' }}>کمینی ثبت نشده</div>}
            {(ambushesList || []).map(a => <div className="card" key={a.id} style={{ marginBottom: 10 }}>
              <div className="res"><div className="ic"><Eye s={16} /></div><div className="n">{a.player}<small>{castleLabel(a.origin_castle)} — {castleLabel(a.target_castle)} · {a.men_committed.toLocaleString('fa-IR')} نفر</small></div></div>
              <div style={{ fontSize: 12, color: 'var(--mid)', lineHeight: 1.9, whiteSpace: 'pre-wrap', margin: '10px 0' }}>{a.scenario}</div>
              <div style={{ fontSize: 11.5, marginBottom: 8 }}>نیروها: {a.troops.map(t => `${t.name} × ${t.count.toLocaleString('fa-IR')}`).join(' · ')}</div>
              {a.status === 'pending_score' ? <div className="grid2">
                <div><label className="f" style={{ marginTop: 0 }}>ضریب تلفات دشمن</label><input type="number" min="0" max="10" step="0.1" placeholder="۰ تا ۱۰" value={ambushScores[a.id] ?? ''} onChange={e => setAmbushScores(p => ({ ...p, [a.id]: e.target.value }))} /></div>
                <div><label className="f" style={{ marginTop: 0 }}>امتیاز کیفیت کمین</label><input type="number" min="0" max="100" placeholder="۰ تا ۱۰۰" value={ambushQualityScores[a.id] ?? ''} onChange={e => setAmbushQualityScores(p => ({ ...p, [a.id]: e.target.value }))} /></div>
                <button className="btn" disabled={ambushBusyId === a.id} onClick={() => scoreAmbush(a.id)}>ثبت و فعال‌سازی</button>
              </div> : <div className="notice-guide"><strong>{a.status === 'active' ? 'کمین فعال' : 'کمین مصرف‌شده'}</strong><span>ضریب {Number(a.coefficient || 0).toLocaleString('fa-IR')} · امتیاز {Number(a.ambush_score ?? 50).toLocaleString('fa-IR')}{a.casualties != null ? ` · ${a.casualties.toLocaleString('fa-IR')} تلفات به ${a.victim_name}` : ''}{a.ambusher_losses != null ? ` · ${a.ambusher_losses.toLocaleString('fa-IR')} تلفات کمین‌گذار` : ''}</span></div>}
            </div>)}
          </div>}

          {warSubTab === 'battles' && (
          <div className="up u2">
            <div className="page-sub" style={{ marginBottom: 12 }}>هر درگیری یک پرونده دارد؛ رول دو طرف، نیروها و ثبت نتیجه همه همین‌جاست. حتی اگر هیچ‌کس رول نداده باشد می‌توانی نتیجه را ثبت کنی.</div>
            {battles === null && <div className="loading">در حال بارگذاری نبردها...</div>}
            {battles && battles.length === 0 && <div className="card" style={{ textAlign: 'center', color: 'var(--mid)' }}>نبرد بازی نداریم</div>}
            {battles && battles.map(b => {
              return <div className="card" key={b.campaign_id} style={{ marginBottom: 12 }}>
                <div className="res"><div className="ic"><Swords s={16} /></div><div className="n">{b.name}<small>{b.attacker_name} در برابر {b.defender_name} · {castleLabel(b.location)}</small></div></div>
                <div className="notice-guide" style={{ marginTop: 10 }}><strong>زمان نبرد و ورود نیروها</strong><span>شروع: {b.started_at ? new Date(b.started_at).toLocaleString('fa-IR') : 'نامشخص'}{(b.battle_joins?.length ? b.battle_joins : [...(b.attacker_joins || []), ...(b.defender_joins || [])]).length ? `\n${(b.battle_joins?.length ? b.battle_joins : [...(b.attacker_joins || []), ...(b.defender_joins || [])]).map(j => `${j.player_name} · ${j.side === 'defender' ? 'مدافع' : 'مهاجم'}: ${new Date(j.joined_at).toLocaleString('fa-IR')}`).join('\n')}` : ''}</span></div>
                <div className="notice-guide" style={{ marginTop: 10 }}><strong>رول‌های جنگ</strong><span>{b.rolls.length ? b.rolls.map(r => `${r.player}: ${r.text}`).join('\n') : 'هیچ‌کدام از طرفین هنوز رول نفرستاده‌اند؛ داوری همچنان باز است.'}</span></div>
                <div className="sect" style={{ margin: '14px 0 7px' }}>نیروها و تلفات</div>
                <div className="notice-guide" style={{ marginBottom: 10 }}><strong>زیرساخت‌های دفاعی قلعه</strong><span>{b.defense_infrastructure?.length ? b.defense_infrastructure.map(x => `${x.name} سطح ${x.level.toLocaleString('fa-IR')}`).join(' · ') : 'زیرساخت دفاعی ساخته‌شده ندارد'}</span></div>
                {(b.attacker_armies || [b.attacker_army]).map((army, ai) => <div key={army.campaign_id} style={{ border: '1px solid var(--line)', borderRadius: 12, padding: 9, marginBottom: 9 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--danger)' }}>{army.player_name || `مهاجم ${ai + 1}`} · {army.men.toLocaleString('fa-IR')} نفر</div>
                  {army.troops.map(t => <div className="troop" key={`${army.campaign_id}-${t.id}`}><div className="tn">{t.name}<small>{t.count.toLocaleString('fa-IR')} حاضر</small></div><input type="number" min="0" max={t.count} placeholder="تلفات" value={roleplayLosses[b.campaign_id]?.attackers?.[army.campaign_id]?.[t.id] ?? ''} onChange={e => setRoleplayLosses(p => ({ ...p, [b.campaign_id]: { ...(p[b.campaign_id] || {}), attackers: { ...(p[b.campaign_id]?.attackers || {}), [army.campaign_id]: { ...(p[b.campaign_id]?.attackers?.[army.campaign_id] || {}), [t.id]: Math.max(0, Math.min(t.count, Number(e.target.value) || 0)) } } } }))} /></div>)}
                  {(army.equipment || []).map(e => <div className="troop" key={`${army.campaign_id}-e-${e.id}`}><div className="tn">{e.name}<small>{e.count.toLocaleString('fa-IR')} ادوات</small></div><input type="number" min="0" max={e.count} placeholder="منهدم" value={roleplayLosses[b.campaign_id]?.attackerEquipments?.[army.campaign_id]?.[e.id] ?? ''} onChange={ev => setRoleplayLosses(p => ({ ...p, [b.campaign_id]: { ...(p[b.campaign_id] || {}), attackerEquipments: { ...(p[b.campaign_id]?.attackerEquipments || {}), [army.campaign_id]: { ...(p[b.campaign_id]?.attackerEquipments?.[army.campaign_id] || {}), [e.id]: Math.max(0, Math.min(e.count, Number(ev.target.value) || 0)) } } } }))} /></div>)}
                </div>)}
                {(b.defender_armies || []).map((army, di) => <div key={army.campaign_id} style={{ border: '1px solid var(--line)', borderRadius: 12, padding: 9, marginBottom: 9 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--az2)' }}>{army.player_name || b.defender_name || `مدافع ${di + 1}`} · {army.men.toLocaleString('fa-IR')} نفر</div>
                  {army.troops.map(t => <div className="troop" key={`${army.campaign_id}-${t.id}`}><div className="tn">{t.name}<small>{t.count.toLocaleString('fa-IR')} حاضر</small></div><input type="number" min="0" max={t.count} placeholder="تلفات" value={roleplayLosses[b.campaign_id]?.defenders?.[army.campaign_id]?.[t.id] ?? ''} onChange={e => setRoleplayLosses(p => ({ ...p, [b.campaign_id]: { ...(p[b.campaign_id] || {}), defenders: { ...(p[b.campaign_id]?.defenders || {}), [army.campaign_id]: { ...(p[b.campaign_id]?.defenders?.[army.campaign_id] || {}), [t.id]: Math.max(0, Math.min(t.count, Number(e.target.value) || 0)) } } } }))} /></div>)}
                  {(army.equipment || []).map(e => <div className="troop" key={`${army.campaign_id}-e-${e.id}`}><div className="tn">{e.name}<small>{e.count.toLocaleString('fa-IR')} ادوات</small></div><input type="number" min="0" max={e.count} placeholder="منهدم" value={roleplayLosses[b.campaign_id]?.defenderEquipments?.[army.campaign_id]?.[e.id] ?? ''} onChange={ev => setRoleplayLosses(p => ({ ...p, [b.campaign_id]: { ...(p[b.campaign_id] || {}), defenderEquipments: { ...(p[b.campaign_id]?.defenderEquipments || {}), [army.campaign_id]: { ...(p[b.campaign_id]?.defenderEquipments?.[army.campaign_id] || {}), [e.id]: Math.max(0, Math.min(e.count, Number(ev.target.value) || 0)) } } } }))} /></div>)}
                </div>)}
                <label className="f">برنده</label><div className="grid2">{[...(b.attacker_armies || []).map(a => [a.tg_id, a.player_name]),...(b.defender_armies || []).map(a => [a.tg_id, a.player_name]),[b.defender_tg_id,b.defender_name]].filter(x => x[0]).filter((x,i,a) => a.findIndex(y => y[0] === x[0]) === i).map(([id,name]) => <button type="button" key={id} className={`rbtn pick ${roleplayWinners[b.campaign_id] === id ? 'sel' : ''}`} onClick={() => setRoleplayWinners(p => ({...p,[b.campaign_id]:id}))}><div className="n">{name}</div></button>)}</div>
                <label className="f">نتیجهٔ نبرد</label><textarea value={roleplayResults[b.campaign_id] || ''} onChange={e => setRoleplayResults(p => ({...p,[b.campaign_id]:e.target.value}))} placeholder="نتیجه و روایت نهایی جنگ..." />
                <div className="notice-guide" style={{ marginTop: 9 }}><strong>نتیجه عمومی است</strong><span>نام طرفین، برنده، محل، تلفات و نیروهای باقی‌مانده برای همه در بات و کلاغ ارسال می‌شود.</span></div>
                <button className="btn" style={{ marginTop: 12 }} disabled={roleplayBusyId === b.campaign_id} onClick={() => resolveBattle(b)}>{roleplayBusyId === b.campaign_id ? 'در حال ثبت...' : 'ثبت نتیجه و پایان نبرد'}</button>
                <button className="btn ghost" style={{ marginTop: 8, color: 'var(--danger)', borderColor: 'rgba(190,55,45,.45)' }} disabled={roleplayBusyId === b.campaign_id} onClick={() => dismissBattle(b)}>منحل‌کردن نبرد بدون نتیجه</button>
              </div>;
            })}
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

        </>
      )}

      {tab === 'security_archive' && (
          <div className="up u2">
            <div className="page-sub" style={{ marginBottom: 10 }}>
              رول‌های دفاعی و امنیتی نتیجه ندارند و همیشه در این آرشیو می‌مانند. با نام بازیکن یا بخشی از متن رول جست‌وجو کن.
            </div>
            <div className="card" style={{ marginBottom: 12 }}>
              <label className="f" style={{ marginTop: 0 }}>بازیکن (اختیاری)</label>
              <PlayerPicker value={securityPlayer} onChange={setSecurityPlayer} single placeholder="همهٔ بازیکن‌ها" />
              <label className="f">نام بازیکن یا عبارت داخل رول</label>
              <input value={securityQuery} onChange={e => setSecurityQuery(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') loadSecurityRoleplays(); }}
                     placeholder="مثلاً نگهبانان دروازه یا نام لرد..." />
              <div style={{ display: 'flex', gap: 7, marginTop: 10 }}>
                <button className="btn" disabled={securitySearching} onClick={loadSecurityRoleplays}>
                  {securitySearching ? 'در حال جست‌وجو...' : 'جست‌وجو در آرشیو'}
                </button>
                <button className="btn ghost" style={{ width: 'auto' }} onClick={() => {
                  setSecurityQuery(''); setSecurityPlayer([]); setSecuritySearching(true);
                  api.adminSecurityRoleplays().then(setSecurityRoleplays).catch(e => toast(e.message)).finally(() => setSecuritySearching(false));
                }}>پاک‌کردن فیلتر</button>
              </div>
            </div>
            {securityRoleplays === null && <div className="loading">در حال بارگذاری آرشیو...</div>}
            {securityRoleplays && securityRoleplays.length === 0 && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)' }}>رول امنیتی‌ای با این مشخصات پیدا نشد</div>
            )}
            {securityRoleplays && securityRoleplays.map(r => (
              <div className="card" key={r.id} style={{ marginBottom: 10 }}>
                <div className="res"><div className="ic"><Shield s={16} /></div><div className="n">{r.player}<small>{castleLabel(r.castle)} · {new Date(r.created_at).toLocaleString('fa-IR')}</small></div></div>
                <div style={{ marginTop: 10, whiteSpace: 'pre-wrap', fontSize: 12.5, lineHeight: 1.9, color: 'var(--mid)' }}>{r.text}</div>
              </div>
            ))}
          </div>
          )}

      {tab === 'roleplays' && (
          <>
          <div className="page-sub up u3">
            سناریوی هر بازیکن را بخوان و نتیجه‌اش را برایش بنویس؛ می‌توانی نتیجه را فقط برای شرکت‌کننده‌ها بفرستی یا به‌عنوان اعلامیهٔ عمومی برای همهٔ بازیکنان
          </div>
          <div className="tabs up u3" role="tablist" style={{ marginBottom: 10 }}>
            {[['all', 'همه'], ...Object.entries(ROLEPLAY_CATEGORIES).filter(([key]) => key !== 'security')].map(([key, label]) => {
              const count = (roleplayPending || []).filter(r => key === 'all' || r.category === key).length;
              return <button type="button" key={key} className={`rbtn tab ${roleplayCategoryTab === key ? 'on' : ''}`}
                onClick={() => setRoleplayCategoryTab(key)}>{label} ({count.toLocaleString('fa-IR')})</button>;
            })}
          </div>
          <div className="up u3">
            {(!roleplayPending || roleplayPending.filter(r => roleplayCategoryTab === 'all' || r.category === roleplayCategoryTab).length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>رول بررسی‌نشده‌ای نیست</div>
            )}
            {roleplayPending && roleplayPending.filter(r => roleplayCategoryTab === 'all' || r.category === roleplayCategoryTab).map(r => (
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
                  <div className="notice-guide" style={{ marginBottom: 10 }}>
                    <strong>داوری این رول در پروندهٔ نبرد انجام می‌شود</strong>
                    <span>برای جلوگیری از دو نتیجه و تلفات ناسازگار، نتیجهٔ جنگ از تب رول‌ها ثبت نمی‌شود.</span>
                    <button type="button" className="btn ghost" style={{ marginTop: 8 }} onClick={() => { setTab('war'); setWarSubTab('battles'); }}>رفتن به پرونده‌های نبرد</button>
                  </div>
                )}
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
                  <div style={{ display: 'none' }} aria-hidden="true">
                    <div style={{ margin: '10px 0', padding: 10, borderRadius: 12, border: '1px solid var(--line)' }}>
                      <div style={{ fontSize: 12, fontWeight: 800, marginBottom: 8 }}>نیروهای درگیر و ثبت تلفات</div>
                      <div style={{ fontSize: 11, color: 'var(--mid)', marginBottom: 8 }}>
                        عددی که برای هر نیرو می‌زنی از همان لشکر کم می‌شود. عدد را خالی یا صفر بگذار یعنی آن نیرو تلفاتی نداشته.
                      </div>
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--danger)', marginBottom: 6 }}>
                        مهاجم — {r.war.attacker_name} · {(r.war.attacker_army?.men || 0).toLocaleString('fa-IR')} نفر
                      </div>
                      {(r.war.attacker_army?.troops || []).map(t => (
                        <div className="troop" key={`a-${t.id}`}>
                          <div className="tn">{t.name}<small>{t.count.toLocaleString('fa-IR')} نفر حاضر</small></div>
                          <input type="number" min="0" max={t.count} placeholder="تلفات"
                            value={roleplayLosses[r.id]?.attacker?.[t.id] ?? ''}
                            onChange={e => setRoleplayLosses(prev => ({ ...prev, [r.id]: { ...(prev[r.id] || {}), attacker: { ...(prev[r.id]?.attacker || {}), [t.id]: Math.max(0, Math.min(t.count, Number(e.target.value) || 0)) } } }))} />
                        </div>
                      ))}
                      <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--az2)', margin: '10px 0 6px' }}>
                        مدافع — {r.war.defender_name} · {(r.war.defender_armies || []).reduce((s, a) => s + (a.men || 0), 0).toLocaleString('fa-IR')} نفر
                      </div>
                      {Object.values((r.war.defender_armies || []).flatMap(a => a.troops || []).reduce((m, t) => {
                        m[t.id] = m[t.id] ? { ...m[t.id], count: m[t.id].count + t.count } : { ...t }; return m;
                      }, {})).map(t => (
                        <div className="troop" key={`d-${t.id}`}>
                          <div className="tn">{t.name}<small>{t.count.toLocaleString('fa-IR')} نفر حاضر در دفاع</small></div>
                          <input type="number" min="0" max={t.count} placeholder="تلفات"
                            value={roleplayLosses[r.id]?.defender?.[t.id] ?? ''}
                            onChange={e => setRoleplayLosses(prev => ({ ...prev, [r.id]: { ...(prev[r.id] || {}), defender: { ...(prev[r.id]?.defender || {}), [t.id]: Math.max(0, Math.min(t.count, Number(e.target.value) || 0)) } } }))} />
                        </div>
                      ))}
                      {(!r.war.defender_armies || r.war.defender_armies.length === 0) && (
                        <div style={{ fontSize: 11, color: 'var(--low)' }}>هیچ لشکر دفاعیِ رسیده‌ای در این قلعه ثبت نشده.</div>
                      )}
                    </div>
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
                  </div>
                )}
                <div style={{ display: r.category === 'war' ? 'none' : 'block' }}>
                <label className="f" style={{ marginTop: 0 }}>نتیجه</label>
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
              </div>
            ))}
          </div>
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
          <div className="tabs up u1" role="tablist" aria-label="مدیریت ساختمان‌ها">
            <button type="button" role="tab" aria-selected={buildingAdminMode === 'global'}
                    className={`rbtn tab ${buildingAdminMode === 'global' ? 'on' : ''}`}
                    onClick={() => setBuildingAdminMode('global')}>تنظیمات سراسری</button>
            <button type="button" role="tab" aria-selected={buildingAdminMode === 'player'}
                    className={`rbtn tab ${buildingAdminMode === 'player' ? 'on' : ''}`}
                    onClick={() => setBuildingAdminMode('player')}>ساختمان‌های بازیکن</button>
          </div>

          {buildingAdminMode === 'global' && (
            <>
              <div className="sect up u2">هزینه و بازدهی همهٔ ساختمان‌ها</div>
              <div className="page-sub up u2" style={{ marginTop: -4, lineHeight: 1.9 }}>
                تغییرات این بخش سراسری است و روی ساخت‌های بعدیِ همهٔ بازیکن‌ها اثر می‌گذارد. هزینهٔ پایه برای سطح ۱ است؛
                درصد رشد تعیین می‌کند هزینهٔ هر سطح نسبت به سطح قبلی چقدر بیشتر شود. تولید و سقف هم به‌ازای هر سطح حساب می‌شوند.
              </div>
              {!balanceList && <div className="loading">در حال بارگذاری...</div>}
              {balanceList && balanceList.map(b => {
                const draft = balanceDrafts[b.id] || {};
                const busy = balanceBusyId === b.id;
                const typeName = b.type === 'economy' ? 'اقتصادی' : b.type === 'barracks' ? 'پادگان' : b.type === 'armory' ? 'کارگاه تسلیحات' : 'دفاعی';
                const preview = level => Object.entries(draft.cost || {}).map(([k, raw]) => {
                  const base = Math.max(0, parseInt(raw, 10) || 0);
                  const step = Math.max(0, Number(draft.cost_step_percent) || 0) / 100;
                  return `${RES_LABEL[k] || k}: ${Math.round(base * (1 + (level - 1) * step)).toLocaleString('fa-IR')}`;
                }).join(' · ');
                return (
                  <div className="card up u2" key={b.id} style={{ marginBottom: 12 }}>
                    <div className="res">
                      <div className="n">
                        {b.name}
                        <small>{typeName}{b.overridden ? ' · تنظیم سفارشی فعال است' : ' · تنظیمات پیش‌فرض بازی'}</small>
                      </div>
                    </div>

                    <div className="sect" style={{ margin: '14px 0 4px' }}>۱. هزینهٔ ساخت و ارتقا</div>
                    <div className="page-sub" style={{ margin: '0 0 9px', lineHeight: 1.8 }}>
                      هزینهٔ پایه همان هزینهٔ ساخت سطح ۱ است. ارتقاهای بعدی با درصد رشد زیر محاسبه می‌شوند.
                    </div>
                    <div className="grid2">
                      {Object.keys(b.base_cost || {}).map(k => (
                        <div key={k}>
                          <label className="f" style={{ marginTop: 0 }}>{RES_LABEL[k] || k} برای سطح ۱ <small style={{ color: 'var(--low)' }}>(پیش‌فرض {b.base_cost[k]})</small></label>
                          <input type="number" min="0" value={draft.cost?.[k] ?? ''}
                                 onChange={e => setBalanceDraft(b.id, 'cost', k, e.target.value)} />
                        </div>
                      ))}
                      <div>
                        <label className="f" style={{ marginTop: 0 }}>رشد هزینه در هر سطح <small style={{ color: 'var(--low)' }}>(درصد)</small></label>
                        <input type="number" min="0" max="500" step="0.5" value={draft.cost_step_percent ?? ''}
                               onChange={e => setBalanceDraft(b.id, 'cost_step_percent', null, e.target.value)} />
                      </div>
                    </div>
                    <div className="notice-guide" style={{ marginTop: 9 }}>
                      <strong>پیش‌نمایش هزینه با عددهای فعلی</strong>
                      <span>سطح ۱: {preview(1) || 'بدون هزینه'}<br />سطح ۲: {preview(2) || 'بدون هزینه'}<br />سطح ۱۰: {preview(10) || 'بدون هزینه'}</span>
                    </div>

                    <div className="sect" style={{ margin: '16px 0 4px' }}>۲. بازدهی هر سطح</div>
                    <div className="page-sub" style={{ margin: '0 0 9px', lineHeight: 1.8 }}>
                      تولید روزانه و افزایش سقف ذخیره برای هر یک سطح ساختمان است؛ سطح ۵ پنج برابر عدد ثبت‌شده اثر دارد.
                    </div>
                    {(Object.keys(b.base_produces || {}).length > 0 || Object.keys(b.base_cap_bonus || {}).length > 0) ? (
                      <div className="grid2">
                        {Object.keys(b.base_produces || {}).map(k => (
                          <div key={`produce-${k}`}>
                            <label className="f" style={{ marginTop: 0 }}>تولید روزانهٔ {RES_LABEL[k] || k} <small style={{ color: 'var(--low)' }}>(پیش‌فرض {b.base_produces[k]})</small></label>
                            <input type="number" min="0" value={draft.produces?.[k] ?? ''}
                                   onChange={e => setBalanceDraft(b.id, 'produces', k, e.target.value)} />
                          </div>
                        ))}
                        {Object.keys(b.base_cap_bonus || {}).map(k => (
                          <div key={`cap-${k}`}>
                            <label className="f" style={{ marginTop: 0 }}>افزایش سقف {RES_LABEL[k] || k} <small style={{ color: 'var(--low)' }}>(پیش‌فرض {b.base_cap_bonus[k]})</small></label>
                            <input type="number" min="0" value={draft.cap_bonus?.[k] ?? ''}
                                   onChange={e => setBalanceDraft(b.id, 'cap_bonus', k, e.target.value)} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="notice-guide">
                        <strong>بازدهی منبع ندارد</strong>
                        <span>این ساختمان تولید یا سقف انبار اضافه نمی‌کند و کارکردش نظامی، دفاعی یا بازکردن قابلیت است.</span>
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
                      <button className="btn" style={{ width: 'auto', padding: '8px 16px', fontSize: 11.5 }} disabled={busy} onClick={() => saveBalance(b)}>
                        {busy ? 'در حال ذخیره...' : 'ذخیرهٔ تنظیمات ساختمان'}
                      </button>
                      {b.overridden && (
                        <button className="btn ghost" style={{ width: 'auto', padding: '8px 16px', fontSize: 11.5 }} disabled={busy} onClick={() => resetBalance(b)}>
                          بازگشت کامل به پیش‌فرض
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {buildingAdminMode === 'player' && (
            <>
              <div className="sect up u2">مدیریت ساختمان‌های یک بازیکن</div>
              <div className="page-sub up u2" style={{ marginTop: -4, lineHeight: 1.9 }}>
                این بخش فقط ساختمان‌های بازیکن انتخاب‌شده را تغییر می‌دهد. سطح صفر یعنی حذف ساختمان؛ سطح ۱ یعنی ساخت اولیه.
                ثبت مستقیم سطح، هر ساخت یا ارتقای درحال‌انجامِ همان ساختمان را لغو می‌کند.
              </div>
              <div className="card up u2">
                <label className="f" style={{ marginTop: 0 }}>بازیکن</label>
                <PlayerPicker value={playerBuildingTarget} onChange={setPlayerBuildingTarget} single placeholder="بازیکن را انتخاب کن..." />
                {playerBuildingTarget.length > 0 && !playerBuildingData && <div className="loading">در حال گرفتن ساختمان‌ها...</div>}
                {playerBuildingData && (
                  <>
                    <label className="f">قلعهٔ موردنظر</label>
                    <select value={playerBuildingCastle} onChange={e => setPlayerBuildingCastle(e.target.value)}>
                      {playerBuildingData.castles.map(castle => (
                        <option key={castle.castle} value={castle.castle}>{castle.castle}{castle.home ? ' · قلعهٔ اصلی' : ''}</option>
                      ))}
                    </select>
                    <div className="notice-guide">
                      <strong>تغییر مستقیم سطح</strong>
                      <span>منابع بازیکن کم یا زیاد نمی‌شود. این ابزار برای اصلاح وضعیت، جایزه، جریمه یا رفع خطای ادمینی است.</span>
                    </div>
                  </>
                )}
              </div>

              {playerBuildingData && playerBuildingData.castles.find(c => c.castle === playerBuildingCastle)?.buildings.map(row => {
                const key = `${playerBuildingCastle}::${row.id}`;
                const busy = playerBuildingBusyId === row.id;
                const typeName = row.type === 'economy' ? 'اقتصادی' : row.type === 'barracks' ? 'پادگان' : row.type === 'armory' ? 'کارگاه تسلیحات' : 'دفاعی';
                return (
                  <div className="card up u3" key={row.id} style={{ marginBottom: 9 }}>
                    <div className="res">
                      <div className="n">
                        {row.name}
                        <small>
                          {typeName} · سطح فعلی {row.level.toLocaleString('fa-IR')}
                          {row.upgrade_to ? ` · درحال ارتقا به سطح ${row.upgrade_to.toLocaleString('fa-IR')}` : ''}
                          {row.requires_port ? ' · فقط قلعهٔ بندری' : ''}
                        </small>
                      </div>
                    </div>
                    <div className="grid2" style={{ marginTop: 10, alignItems: 'end' }}>
                      <div>
                        <label className="f" style={{ marginTop: 0 }}>سطح جدید (۰ تا {row.max_level || playerBuildingData.max_level})</label>
                        <input type="number" min="0" max={row.max_level || playerBuildingData.max_level}
                               value={playerBuildingDrafts[key] ?? String(row.level)}
                               onChange={e => setPlayerBuildingDrafts(prev => ({ ...prev, [key]: e.target.value }))} />
                      </div>
                      <button className="btn" disabled={busy} onClick={() => savePlayerBuilding(row)}>
                        {busy ? 'در حال ثبت...' : 'ثبت سطح'}
                      </button>
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                      <button className="btn ghost" style={{ width: 'auto', padding: '7px 10px', fontSize: 10 }}
                              onClick={() => setPlayerBuildingDrafts(prev => ({ ...prev, [key]: '0' }))}>حذف (سطح صفر)</button>
                      <button className="btn ghost" style={{ width: 'auto', padding: '7px 10px', fontSize: 10 }}
                              onClick={() => setPlayerBuildingDrafts(prev => ({ ...prev, [key]: '1' }))}>ساخت سطح ۱</button>
                      <button className="btn ghost" style={{ width: 'auto', padding: '7px 10px', fontSize: 10 }}
                              onClick={() => setPlayerBuildingDrafts(prev => ({ ...prev, [key]: String(row.max_level || playerBuildingData.max_level) }))}>حداکثر</button>
                    </div>
                  </div>
                );
              })}
            </>
          )}
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
                <div style={{ marginBottom: 14, padding: 12, borderRadius: 12, border: '1px solid var(--line)', background: 'rgba(255,255,255,.025)' }}>
                  <div className="res" style={{ marginBottom: 8 }}>
                    <div className="n">امتیاز بازیکن<small>امتیاز فعلی: {(resPoints ?? 0).toLocaleString('fa-IR')}</small></div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input type="number" value={pointDelta} placeholder="مثلاً ۱۰۰ یا ۵۰-"
                           style={{ margin: 0, flex: 1 }} onChange={e => setPointDelta(e.target.value)} />
                    <button className="btn" style={{ width: 'auto', padding: '10px 16px' }} disabled={pointBusy} onClick={adjustPoints}>
                      {pointBusy ? '...' : 'اعمال'}
                    </button>
                  </div>
                  <div className="page-sub" style={{ marginTop: 7 }}>عدد مثبت امتیاز اضافه می‌کند و عدد منفی از امتیاز کم می‌کند؛ امتیاز زیر صفر نمی‌رود.</div>
                </div>
                <div style={{ marginBottom: 14, padding: 12, borderRadius: 12, border: '1px solid var(--line)', background: 'rgba(255,255,255,.025)' }}>
                  <div className="res" style={{ marginBottom: 8 }}>
                    <div className="n">محبوبیت بازیکن<small>محبوبیت فعلی: {(resPopularity ?? 50).toLocaleString('fa-IR')} از ۱۰۰</small></div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input type="number" value={popularityDelta} placeholder="مثلاً ۱۰ یا ۵-"
                           style={{ margin: 0, flex: 1 }} onChange={e => setPopularityDelta(e.target.value)} />
                    <button className="btn" style={{ width: 'auto', padding: '10px 16px' }} disabled={popularityBusy} onClick={adjustPopularity}>
                      {popularityBusy ? '...' : 'اعمال'}
                    </button>
                  </div>
                  <div className="page-sub" style={{ marginTop: 7 }}>مقدار مثبت محبوبیت را بیشتر و مقدار منفی آن را کمتر می‌کند؛ نتیجه همیشه بین صفر تا صد می‌ماند.</div>
                </div>
                <div className="page-sub" style={{ margin: '4px 4px 12px', lineHeight: 1.9 }}>
                  عددِ سمت راست موجودی فعلیه و زیرش سقف واقعی بازیکن نوشته شده؛ این سقف از ساختمان‌های همهٔ قلعه‌هاش حساب می‌شه.
                </div>
                {PLAYER_RES.map(({ key, label, Icon }) => {
                  const value = Number(resValues[key] ?? 0);
                  const cap = Number(resCaps?.[key] ?? 0);
                  const overCap = cap > 0 && value > cap;
                  return (
                    <div className="troop" key={key} style={{ alignItems: 'center' }}>
                      <div className="tn"><Icon s={14} /> {label}</div>
                      <div style={{ width: 130, maxWidth: '48%' }}>
                        <input type="number" min="0" value={value}
                               aria-label={`${label}؛ سقف ${cap.toLocaleString('fa-IR')}`}
                               style={{ margin: 0, borderColor: overCap ? 'var(--danger)' : undefined }}
                               onChange={e => setResValues({ ...resValues, [key]: Math.max(0, +e.target.value || 0) })} />
                        <div style={{ marginTop: 4, textAlign: 'center', fontSize: 9.5, color: overCap ? 'var(--danger)' : 'var(--low)' }}>
                          {value.toLocaleString('fa-IR')} از {cap.toLocaleString('fa-IR')}
                          {overCap ? ' · بیشتر از سقف' : ''}
                        </div>
                      </div>
                    </div>
                  );
                })}
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
                    {c.active && <div style={{ padding: 10, border: '1px solid var(--line)', borderRadius: 12, marginBottom: 9 }}>
                      <div style={{ fontSize: 11.5, fontWeight: 800, marginBottom: 6 }}>ثبت تلفات مستقیم (بدون بازپرداخت)</div>
                      {c.troops.map(t => <div className="troop" key={t.id}>
                        <div className="tn">{t.name}<small>{t.count.toLocaleString('fa-IR')} حاضر</small></div>
                        <input type="number" min="0" max={t.count} placeholder="تلفات" value={campaignLosses[c.id]?.[t.id] || ''}
                          onChange={e => setCampaignLosses(prev => ({ ...prev, [c.id]: { ...(prev[c.id] || {}), [t.id]: Math.max(0, Math.min(t.count, Number(e.target.value) || 0)) } }))} />
                      </div>)}
                      <button className="btn ghost" disabled={disbandBusyId === c.id} onClick={() => reduceCampaign(c)}>ثبت کاهش نیرو</button>
                    </div>}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--low)' }}>
                        {c.active ? (c.arrived ? 'رسیده به مقصد' : 'در راه') : 'لغوشده'}
                      </div>
                      {c.active && (<div style={{ display: 'flex', gap: 7 }}>
                        <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11 }}
                                disabled={disbandBusyId === c.id} onClick={() => disbandCampaign(c.id)}>
                          {disbandBusyId === c.id ? 'در حال انحلال...' : 'منحل کن'}
                        </button>
                        <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11, color: 'var(--danger)' }}
                          disabled={disbandBusyId === c.id} onClick={() => destroyCampaign(c.id)}>انهدام کامل</button>
                      </div>)}
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

      {tab === 'rebellions' && (
        <>
          <div className="sect up u2">شورش‌های بازیکنان</div>
          {!rebellionsList && <div className="loading">در حال بارگذاری...</div>}
          {rebellionsList && rebellionsList.length === 0 && <div className="empty">هنوز شورشی ثبت نشده است.</div>}
          {rebellionsList && rebellionsList.map(row => {
            const d = rebellionDrafts[row.id] || {};
            const active = ['awaiting_roleplay', 'roleplay_submitted', 'expired'].includes(row.status);
            return (
              <div className="card up u2" key={row.id} style={{ marginBottom: 10 }}>
                <div style={{ fontWeight: 900 }}>🔥 {row.player_name} — {row.castle || 'بدون قلعه'}</div>
                <div className="page-sub" style={{ marginTop: 5 }}>
                  محبوبیت {row.popularity.toLocaleString('fa-IR')} · شانس {row.chance.toLocaleString('fa-IR')}٪ · تاس {row.roll.toLocaleString('fa-IR')} · وضعیت {row.status}
                </div>
                <div className="page-sub">مهلت: {new Date(row.deadline).toLocaleString('fa-IR')}</div>
                {row.roleplay_text && (
                  <div style={{ marginTop: 10, padding: 10, background: 'rgba(255,255,255,.05)', borderRadius: 10 }}>
                    <b>رول بازیکن:</b><div style={{ whiteSpace: 'pre-wrap', marginTop: 5 }}>{row.roleplay_text}</div>
                  </div>
                )}
                {row.result && <div style={{ marginTop: 8 }}>نتیجه: {row.result}</div>}
                {active && (
                  <>
                    <label className="f">نتیجه شورش</label>
                    <textarea rows={4} value={d.result || ''} onChange={e => setRebellionDrafts(p => ({ ...p, [row.id]: { ...d, result: e.target.value } }))}
                              placeholder="نتیجه داوری و اتفاقی که در قلمرو افتاد..." />
                    <div className="grid2">
                      <div><label className="f">تغییر محبوبیت (+ پاداش / − جریمه)</label><input type="number" value={d.popularity_delta || ''} onChange={e => setRebellionDrafts(p => ({ ...p, [row.id]: { ...d, popularity_delta: e.target.value } }))} /></div>
                      <div><label className="f">تغییر سکهٔ خزانه</label><input type="number" value={d.gold_delta || ''} onChange={e => setRebellionDrafts(p => ({ ...p, [row.id]: { ...d, gold_delta: e.target.value } }))} /></div>
                      <div><label className="f">تغییر غلهٔ انبار</label><input type="number" value={d.food_delta || ''} onChange={e => setRebellionDrafts(p => ({ ...p, [row.id]: { ...d, food_delta: e.target.value } }))} /></div>
                      <div><label className="f">تغییر جمعیت قلمرو</label><input type="number" value={d.men_delta || ''} onChange={e => setRebellionDrafts(p => ({ ...p, [row.id]: { ...d, men_delta: e.target.value } }))} /></div>
                    </div>
                    <label className="f">وضعیت نهایی</label>
                    <select value={d.outcome || 'resolved'} onChange={e => setRebellionDrafts(p => ({ ...p, [row.id]: { ...d, outcome: e.target.value } }))}>
                      <option value="resolved">شورش پایان یافت</option>
                      <option value="suppressed">شورش سرکوب شد</option>
                      <option value="negotiated">با مذاکره پایان یافت</option>
                      <option value="rebels_won">شورشیان پیروز شدند</option>
                    </select>
                    <button className="btn" style={{ marginTop: 12 }} disabled={rebellionBusyId === row.id} onClick={() => resolveRebellion(row)}>
                      {rebellionBusyId === row.id ? 'در حال ثبت...' : 'ثبت نتیجه و ارسال به بازیکن'}
                    </button>
                  </>
                )}
              </div>
            );
          })}

          {isFull && rebellionSettings && (
            <>
              <div className="sect up u2">تنظیمات سراسری شورش</div>
              <div className="card up u2">
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
                  <input type="checkbox" checked={rebellionSettings.enabled} onChange={e => setRebellionSettings(p => ({ ...p, enabled: e.target.checked }))} />
                  سیستم شورش فعال باشد
                </label>
                <div className="grid2">
                  <div><label className="f">حد امن محبوبیت</label><input type="number" value={rebellionSettings.safe_popularity} onChange={e => setRebellionNumber('safe_popularity', e.target.value)} /></div>
                  <div><label className="f">شروع خطر زیاد</label><input type="number" value={rebellionSettings.high_risk_popularity} onChange={e => setRebellionNumber('high_risk_popularity', e.target.value)} /></div>
                  <div><label className="f">شورش قطعی زیر</label><input type="number" value={rebellionSettings.guaranteed_popularity} onChange={e => setRebellionNumber('guaranteed_popularity', e.target.value)} /></div>
                  <div><label className="f">مهلت رول (ساعت)</label><input type="number" value={rebellionSettings.roleplay_hours} onChange={e => setRebellionNumber('roleplay_hours', e.target.value)} /></div>
                  <div><label className="f">دوره آرامش (ساعت)</label><input type="number" value={rebellionSettings.cooldown_hours} onChange={e => setRebellionNumber('cooldown_hours', e.target.value)} /></div>
                  <div><label className="f">مصرف استاندارد غله برای هر ۱۰۰ نفر</label><input type="number" value={rebellionSettings.base_food_per_100_men} onChange={e => setRebellionNumber('base_food_per_100_men', e.target.value)} /></div>
                  <div><label className="f">جریمه نبود غله</label><input type="number" value={rebellionSettings.starvation_popularity} onChange={e => setRebellionNumber('starvation_popularity', e.target.value)} /></div>
                  <div><label className="f">شانس شروع بازه ۴۰–۵۰</label><input type="number" value={rebellionSettings.chance_low_start} onChange={e => setRebellionNumber('chance_low_start', e.target.value)} /></div>
                  <div><label className="f">افزایش شانس هر پله</label><input type="number" value={rebellionSettings.chance_low_step} onChange={e => setRebellionNumber('chance_low_step', e.target.value)} /></div>
                  <div><label className="f">شانس شروع بازه ۳۰–۴۰</label><input type="number" value={rebellionSettings.chance_high_start} onChange={e => setRebellionNumber('chance_high_start', e.target.value)} /></div>
                  <div><label className="f">افزایش شانس شدید</label><input type="number" value={rebellionSettings.chance_high_step} onChange={e => setRebellionNumber('chance_high_step', e.target.value)} /></div>
                  <div><label className="f">هزینه غذای ضیافت</label><input type="number" value={rebellionSettings.feast_food_cost} onChange={e => setRebellionNumber('feast_food_cost', e.target.value)} /></div>
                  <div><label className="f">هزینه شراب ضیافت</label><input type="number" value={rebellionSettings.feast_wine_cost} onChange={e => setRebellionNumber('feast_wine_cost', e.target.value)} /></div>
                  <div><label className="f">محبوبیت ضیافت</label><input type="number" value={rebellionSettings.feast_popularity_gain} onChange={e => setRebellionNumber('feast_popularity_gain', e.target.value)} /></div>
                </div>

                <label className="f">جیره استاندارد بازیکنان</label>
                <select value={rebellionSettings.default_ration} onChange={e => setRebellionSettings(p => ({ ...p, default_ration: e.target.value }))}>
                  {Object.entries(rebellionSettings.ration_levels || {}).map(([key, level]) => <option key={key} value={key}>{level.label}</option>)}
                </select>
                <div className="sect" style={{ marginTop: 16 }}>اثر نرخ مالیات</div>
                <div className="page-sub" style={{ marginBottom: 10, lineHeight: 1.8 }}>
                  آستانهٔ پایه برای محبوبیت ۵۰ محاسبه می‌شود. با هر پله تغییر محبوبیت، آستانهٔ مالیات سنگین هم به اندازهٔ تعیین‌شده جابه‌جا می‌شود؛ بالاتر از آستانه، به ازای هر پله مالیات جریمهٔ اضافه اعمال می‌شود.
                </div>
                <div className="grid2" style={{ marginBottom: 10 }}>
                  <div><label className="f">آستانهٔ پایه مالیات سنگین</label><input type="number" value={rebellionSettings.tax_overage_start ?? 20} onChange={e => setRebellionNumber('tax_overage_start', e.target.value)} /></div>
                  <div><label className="f">هر چند محبوبیت یک پله؟</label><input type="number" min="1" value={rebellionSettings.tax_popularity_step ?? 5} onChange={e => setRebellionNumber('tax_popularity_step', e.target.value)} /></div>
                  <div><label className="f">تغییر آستانه در هر پله محبوبیت</label><input type="number" value={rebellionSettings.tax_limit_per_step ?? 1} onChange={e => setRebellionNumber('tax_limit_per_step', e.target.value)} /></div>
                  <div><label className="f">هر چند درصد مالیات اضافه یک پله؟</label><input type="number" min="1" value={rebellionSettings.tax_overage_step ?? 5} onChange={e => setRebellionNumber('tax_overage_step', e.target.value)} /></div>
                  <div><label className="f">جریمه محبوبیت هر پله اضافه</label><input type="number" value={rebellionSettings.tax_overage_popularity ?? -1} onChange={e => setRebellionNumber('tax_overage_popularity', e.target.value)} /></div>
                </div>
                {(rebellionSettings.tax_bands || []).map((band, index) => (
                  <div className="grid2" key={index} style={{ marginBottom: 8 }}>
                    <div><label className="f">تا نرخ مالیات</label><input type="number" value={band.max}
                      onChange={e => setRebellionSettings(p => ({ ...p, tax_bands: p.tax_bands.map((b, i) => i === index ? { ...b, max: Number(e.target.value) } : b) }))} /></div>
                    <div><label className="f">تغییر محبوبیت روزانه</label><input type="number" value={band.popularity}
                      onChange={e => setRebellionSettings(p => ({ ...p, tax_bands: p.tax_bands.map((b, i) => i === index ? { ...b, popularity: Number(e.target.value) } : b) }))} /></div>
                  </div>
                ))}
                <div className="sect" style={{ marginTop: 16 }}>سطح‌های سهم غله</div>
                {Object.entries(rebellionSettings.ration_levels || {}).map(([key, level]) => (
                  <div className="grid2" key={key} style={{ marginBottom: 8 }}>
                    <div><label className="f">{level.label} — ضریب مصرف</label><input type="number" step="0.05" value={level.multiplier}
                      onChange={e => setRebellionSettings(p => ({ ...p, ration_levels: { ...p.ration_levels, [key]: { ...level, multiplier: Number(e.target.value) } } }))} /></div>
                    <div><label className="f">اثر محبوبیت</label><input type="number" value={level.popularity}
                      onChange={e => setRebellionSettings(p => ({ ...p, ration_levels: { ...p.ration_levels, [key]: { ...level, popularity: Number(e.target.value) } } }))} /></div>
                  </div>
                ))}

                <div className="sect" style={{ marginTop: 16 }}>اثر نتیجه جنگ</div>
                <div className="grid2">
                  {Object.entries(rebellionSettings.war_popularity || {}).map(([key, value]) => (
                    <div key={key}><label className="f">{key}</label><input type="number" value={value}
                      onChange={e => setRebellionSettings(p => ({ ...p, war_popularity: { ...p.war_popularity, [key]: Number(e.target.value) } }))} /></div>
                  ))}
                </div>
                <button className="btn" style={{ marginTop: 16 }} disabled={rebellionSettingsBusy} onClick={saveRebellionSettings}>
                  {rebellionSettingsBusy ? 'در حال ذخیره...' : 'ذخیره تنظیمات شورش'}
                </button>
              </div>
            </>
          )}
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

      {tab === 'music' && isFull && (
        <>
          <div className="sect up u2">موسیقی پس‌زمینهٔ بازی</div>
          <div className="page-sub up u2" style={{ marginTop: -10, lineHeight: 1.9 }}>
            فایل برای همهٔ بازیکن‌ها پخش می‌شود. مرورگر ممکن است بار اول تا لمس دکمهٔ نت اجازهٔ پخش خودکار ندهد؛ هر بازیکن هم می‌تواند موسیقی را برای خودش قطع کند.
          </div>
          {!musicSettings ? <div className="loading">در حال بارگذاری تنظیمات موسیقی...</div> : <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>فایل موسیقی</label>
            <input type="file" accept="audio/*" onChange={e => chooseMusicFile(e.target.files?.[0])} />
            <div className="page-sub" style={{ marginTop: 7 }}>MP3، OGG یا M4A تا حداکثر ۷ مگابایت. فایل داخل دیتابیس بازی نگه‌داری می‌شود.</div>
            <label className="f">یا لینک مستقیم موسیقی</label>
            <input dir="ltr" value={musicSettings.audio_url?.startsWith('data:') ? '' : (musicSettings.audio_url || '')}
                   onChange={e => setMusicSettings(p => ({ ...p, audio_url: e.target.value }))} placeholder="https://.../music.mp3" />
            {musicSettings.audio_url && <audio controls loop={musicSettings.loop} src={musicSettings.audio_url} style={{ width: '100%', marginTop: 12 }} />}
            <label className="f">نام قطعه</label>
            <input value={musicSettings.title || ''} maxLength={80} onChange={e => setMusicSettings(p => ({ ...p, title: e.target.value }))} placeholder="مثلاً: نغمهٔ والریا" />
            <label className="f">حجم پیش‌فرض — {Number(musicSettings.volume || 0).toLocaleString('fa-IR')}٪</label>
            <input type="range" min="0" max="100" value={musicSettings.volume ?? 35} onChange={e => setMusicSettings(p => ({ ...p, volume: Number(e.target.value) }))} />
            <div className="grid2" style={{ marginTop: 12 }}>
              <label className="check"><input type="checkbox" checked={!!musicSettings.enabled} onChange={e => setMusicSettings(p => ({ ...p, enabled: e.target.checked }))} /> فعال برای بازیکن‌ها</label>
              <label className="check"><input type="checkbox" checked={!!musicSettings.loop} onChange={e => setMusicSettings(p => ({ ...p, loop: e.target.checked }))} /> تکرار پیوسته</label>
              <label className="check"><input type="checkbox" checked={!!musicSettings.autoplay} onChange={e => setMusicSettings(p => ({ ...p, autoplay: e.target.checked }))} /> تلاش برای پخش خودکار</label>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
              <button className="btn" disabled={musicBusy} onClick={saveMusic}>{musicBusy ? 'در حال ذخیره...' : 'ذخیره و اعمال برای همه'}</button>
              <button className="btn ghost" disabled={musicBusy} onClick={() => setMusicSettings(p => ({ ...p, enabled: false, audio_url: '' }))}>پاک‌کردن فایل؛ سپس ذخیره</button>
            </div>
          </div>}
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

      {tab === 'rumor_admin' && (
        <>
          <div className="sect up u2">مدیریت توییت‌ها</div>
          <div className="page-sub up u2" style={{ margin: '-8px 4px 12px', lineHeight: 1.9 }}>
            توییت برای بازیکن‌ها ناشناسه، ولی ادمین برای رسیدگی به تخلف نویسندهٔ واقعی رو می‌بینه. حذف توییت، محبوبیتی که قبلاً کم شده رو برنمی‌گردونه.
          </div>
          <div className="admin-rumor-list up u3">
            {adminRumors === null && <div className="loading">در حال گرفتن توییت‌ها...</div>}
            {adminRumors && adminRumors.length === 0 && <div className="card" style={{ textAlign: 'center', color: 'var(--mid)' }}>توییت‌ای وجود نداره</div>}
            {adminRumors && adminRumors.map(row => (
              <article className="admin-rumor-card card" key={row.id}>
                <header>
                  <div><b>نویسنده: {row.author_name}</b><small>شناسه: {row.author_tg_id}</small></div>
                  <time>{new Date(row.created_at).toLocaleString('fa-IR')}</time>
                </header>
                <div className="admin-rumor-target">علیه: {row.target_name} · شناسه {row.target_tg_id}</div>
                <p>{row.text}</p>
                <footer>
                  <span>👍 {row.likes.toLocaleString('fa-IR')} · 👎 {row.dislikes.toLocaleString('fa-IR')}</span>
                  <button type="button" className="btn ghost" disabled={rumorDeleteBusy === row.id} onClick={() => deleteAdminRumor(row)}>
                    {rumorDeleteBusy === row.id ? 'در حال حذف...' : 'حذف توییت'}
                  </button>
                </footer>
              </article>
            ))}
          </div>
        </>
      )}

      {tab === 'bot_messages' && (
        <>
          <div className="sect up u2">ارسال پیام به بازیکن‌ها</div>
          <div className="page-sub up u2" style={{ marginTop: -10 }}>
            مشخص کن پیام در چت خصوصی بات، اطلاعیه‌های کلاغ، یا هر دو دیده شود.
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
            <label className="f">مسیر ارسال</label>
            <div className="grid2">
              <button type="button" className={`rbtn pick ${botViaBot ? 'sel' : ''}`} onClick={() => setBotViaBot(v => !v)}>
                <div className="n">بات تلگرام</div><div className="c">پیام خصوصی داخل بات</div>
              </button>
              <button type="button" className={`rbtn pick ${botViaRaven ? 'sel' : ''}`} onClick={() => setBotViaRaven(v => !v)}>
                <div className="n">کلاغ</div><div className="c">داخل اطلاعیه‌های بازی</div>
              </button>
            </div>
            <label className="f">متن پیام</label>
            <textarea value={botMessage} onChange={e => setBotMessage(e.target.value)} maxLength={4000}
                      rows={6} placeholder="پیامی که بات مستقیماً برای بازیکن می‌فرستد..." />
            <button className="btn" style={{ marginTop: 14 }} disabled={botMessageBusy} onClick={sendBotMessage}>
              {botMessageBusy
                ? 'در حال ارسال...'
                : botAudience === 'all'
                  ? 'ارسال پیام به همهٔ بازیکنان'
                  : `ارسال پیام به ${botTargets.length.toLocaleString('fa-IR')} بازیکن`}
            </button>
          </div>
        </>
      )}

      {tab === 'admins' && isFull && (
        <>
          <div className="sect up u2">مدیریت ادمین‌ها</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>افزودن ادمین محدود (داوری، بازیکن‌ها، نقشه، مدال و پیام‌رسانی)</label>
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

          <div className="sect up u3">پاک‌سازی داده‌های قدیمی</div>
          <div className="page-sub up u3" style={{ margin: '-8px 4px 12px', lineHeight: 1.9 }}>
            این ابزارها برای سبک‌کردن دیتابیس‌اند و حساب، منابع، نقشه و قلعه‌های بازیکن‌ها رو پاک نمی‌کنن. موارد فعال و پرونده‌های منتظر داوری هم محافظت می‌شن.
          </div>
          <div className="admin-cleanup-grid up u3">
            {[
              { key: 'messages', token: 'MESSAGES', label: 'پیام‌ها و اطلاعیه‌ها', note: 'تمام نامه‌های خصوصی و اطلاعیه‌های داخل کلاغ‌ها' },
              { key: 'rumors', token: 'RUMORS', label: 'توییت‌ها', note: 'تمام توییت‌ها و واکنش‌های آن‌ها' },
              { key: 'campaigns', token: 'CAMPAIGNS', label: 'لشکرکشی‌های بسته', note: 'فقط تاریخچه؛ لشکر فعال حذف نمی‌شه' },
              { key: 'reports', token: 'REPORTS', label: 'گزارش‌های حل‌شده', note: 'جاسوسی و رول داوری‌شده؛ پروندهٔ باز محفوظ می‌مونه' },
            ].map(item => (
              <div className="card admin-cleanup-card" key={item.key}>
                <header><b>{item.label}</b><span>{(cleanupPreview?.[item.key] || 0).toLocaleString('fa-IR')} مورد</span></header>
                <p>{item.note}</p>
                <label className="f">برای تایید بنویس: <code>{item.token}</code></label>
                <input value={cleanupConfirm[item.key] || ''} onChange={e => setCleanupConfirm(prev => ({ ...prev, [item.key]: e.target.value }))}
                       placeholder={item.token} dir="ltr" />
                <button type="button" className="btn ghost" disabled={cleanupBusy === item.key || (cleanupConfirm[item.key] || '').trim() !== item.token}
                        onClick={() => runCleanup(item.key, item.token, item.label)}>
                  {cleanupBusy === item.key ? 'در حال پاک‌سازی...' : `پاک‌کردن ${item.label}`}
                </button>
              </div>
            ))}
          </div>
          {cleanupPreview?.protected && (
            <div className="admin-cleanup-protected up u3">
              محافظت‌شده: {cleanupPreview.protected.active_campaigns.toLocaleString('fa-IR')} لشکر فعال · {cleanupPreview.protected.pending_spy.toLocaleString('fa-IR')} جاسوسی منتظر · {cleanupPreview.protected.pending_roleplays.toLocaleString('fa-IR')} رول منتظر
            </div>
          )}

          {me.is_owner && (
            <>
              <div className="sect up u3" style={{ color: 'var(--danger)' }}>منطقهٔ خطر — فقط صاحب بازی</div>
              <div className="card up u3" style={{ borderColor: '#9c6b20' }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>شروع فصل تازه بدون حذف بازیکن‌ها</div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 8, lineHeight: 1.9 }}>
                  منابع، ساختمان‌ها، نیروها، مدال‌ها، محبوبیت و تاریخچهٔ فصل پاک و از مقدار آغازین شروع می‌شوند.
                  حساب بازیکن، خاندان، اقلیم، قلعهٔ اصلی و قلعه‌های فتح‌شده سر جای خود می‌مانند.
                </div>
                <label className="f">برای تایید بنویس: <code>NEWSEASON</code></label>
                <input value={seasonResetConfirm} onChange={e => setSeasonResetConfirm(e.target.value)} placeholder="NEWSEASON" dir="ltr" />
                <button className="btn ghost" disabled={seasonResetConfirm.trim() !== 'NEWSEASON' || seasonResetBusy} onClick={resetSeason}>
                  {seasonResetBusy ? 'در حال شروع فصل...' : 'شروع فصل تازه'}
                </button>
              </div>
              <div className="card up u3" style={{ borderColor: '#9c6b20' }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>ریست فقط جدول امتیازات</div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 8, lineHeight: 1.9 }}>
                  امتیاز همه از همین لحظه صفر می‌شود؛ منابع، ساختمان‌ها، نیروها، مقام‌ها و مالکیت قلعه‌ها تغییر نمی‌کنند.
                </div>
                <label className="f">برای تایید بنویس: <code>SCOREBOARD</code></label>
                <input value={scoreResetConfirm} onChange={e => setScoreResetConfirm(e.target.value)} placeholder="SCOREBOARD" dir="ltr" />
                <button className="btn ghost" disabled={scoreResetConfirm.trim() !== 'SCOREBOARD' || scoreResetBusy} onClick={resetScoreboard}>
                  {scoreResetBusy ? 'در حال ریست...' : 'ریست جدول امتیازات'}
                </button>
              </div>
              <div className="card up u3" style={{ borderColor: 'var(--danger)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--danger)' }}>ری‌استارت کامل بازی</div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 8, lineHeight: 1.9 }}>
                  همهٔ بازیکن‌های غیرادمین حذف می‌شوند و باید از نو ثبت‌نام کنند؛ تاریخچهٔ لشکرکشی‌ها، جاسوسی‌ها،
                  پیام‌ها، رول‌ها، شورش‌ها و تاس‌های شورش، توییت‌ها، اتحادها، رای‌گیری‌ها و کاروان‌ها پاک می‌شود.
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

