import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Send, Plus, Back, Eye, ThumbsUp, ThumbsDown } from '../components/Icons.jsx';
import { RUMOR_GOLD_COST, RUMOR_POPULARITY_DAMAGE } from '../gamedata.js';
import PlayerPicker from '../components/PlayerPicker.jsx';

const SYSTEM_TG_ID = 0;

const NOTICE_META = {
  war:       { icon: '⚔️', label: 'جنگ و لشکرکشی' },
  trade:     { icon: '🛒', label: 'کاروان و تجارت' },
  building:  { icon: '🏗️', label: 'ساخت‌وساز' },
  daily:     { icon: '🎁', label: 'جایزهٔ روزانه' },
  diplomacy: { icon: '🤝', label: 'پیمان و اتحاد' },
  rebellion: { icon: '🔥', label: 'شورش' },
  espionage: { icon: '👁️', label: 'جاسوسی' },
  roleplay:  { icon: '📜', label: 'رول و نتیجه' },
  reward:    { icon: '🏅', label: 'پاداش و مدال' },
  event:     { icon: '📣', label: 'رویداد' },
  general:   { icon: '🔔', label: 'اطلاعیهٔ بازی' },
};

function noticeMeta(message) {
  if (message?.kind && message.kind !== 'general' && NOTICE_META[message.kind]) return NOTICE_META[message.kind];
  const text = message?.text || message?.last_text || '';
  if (/شورش/.test(text)) return NOTICE_META.rebellion;
  if (/لشکر|نبرد|حمله|محاصره|غارت/.test(text)) return NOTICE_META.war;
  if (/کاروان|تجارت|بازار/.test(text)) return NOTICE_META.trade;
  if (/ساختمان|ساخت‌وساز|ارتقا/.test(text)) return NOTICE_META.building;
  if (/جایزه.{0,3}روزانه/.test(text)) return NOTICE_META.daily;
  if (/پیمان|اتحاد|هم‌پیمان/.test(text)) return NOTICE_META.diplomacy;
  if (/جاسوس/.test(text)) return NOTICE_META.espionage;
  if (/رول|سناریو|نتیجه/.test(text)) return NOTICE_META.roleplay;
  if (/مدال|آیتم|پاداش/.test(text)) return NOTICE_META.reward;
  if (/رویداد|ایونت/.test(text)) return NOTICE_META.event;
  return NOTICE_META.general;
}

function timeAgo(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 60) return `${min.toLocaleString('fa-IR')} دقیقه پیش`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h.toLocaleString('fa-IR')} ساعت پیش`;
  return `${Math.floor(h / 24).toLocaleString('fa-IR')} روز پیش`;
}

export default function Ravens() {
  const { me, setMe, toast, refreshUnread, unreadBreakdown } = useGame();
  const [inbox, setInbox] = useState(null);
  const [tab, setTab] = useState('announcements');
  const [openWith, setOpenWith] = useState(null);   // {tg_id, name}
  const [thread, setThread] = useState([]);
  const [text, setText] = useState('');
  const [composeTargets, setComposeTargets] = useState([]);
  const [composing, setComposing] = useState(false);
  const [rumors, setRumors] = useState(null);
  const [composingTweet, setComposingTweet] = useState(false);
  const [tweetTarget, setTweetTarget] = useState([]);
  const [tweetText, setTweetText] = useState('');
  const [tweetBusy, setTweetBusy] = useState(false);

  const loadInbox = () => api.inbox().then(setInbox).catch(e => { toast(e.message); setInbox([]); });
  const loadRumors = () => api.listRumors().then(setRumors).catch(e => { toast(e.message); setRumors([]); });
  useEffect(() => { loadInbox(); }, []);
  useEffect(() => {
    if (tab !== 'rumors') return;
    if (rumors === null) loadRumors();
    api.markRumorsSeen().then(refreshUnread).catch(() => {});
  }, [tab]);

  const sendTweet = async () => {
    const text = tweetText.trim();
    if (!tweetTarget.length) { toast('یک لرد را هدف بگیر'); return; }
    if (text.length < 10) { toast('متن توییت را کمی بیشتر بنویس'); return; }
    if ((me.resources?.gold || 0) < RUMOR_GOLD_COST) { toast('طلای کافی برای انتشار این توییت نداری'); return; }
    setTweetBusy(true);
    try {
      await api.sendRumor(tweetTarget[0].tg_id, text);
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, gold: me.resources.gold - RUMOR_GOLD_COST } });
      toast(`توییت علیه «${tweetTarget[0].name}» منتشر شد`);
      setTweetTarget([]); setTweetText(''); setComposingTweet(false);
      setRumors(null); loadRumors();
    } catch (e) { toast(e.message); }
    setTweetBusy(false);
  };

  const reactRumor = async (rumorId, reaction) => {
    const r = rumors.find(x => x.id === rumorId);
    const next = r?.my_reaction === reaction ? null : reaction;
    try {
      const updated = await api.reactRumor(rumorId, next);
      haptic();
      setRumors(prev => prev.map(x => x.id === rumorId ? updated : x));
    } catch (e) { toast(e.message); }
  };

  const openThread = async (m) => {
    haptic();
    setOpenWith({ tg_id: m.with_tg_id, name: m.with_name });
    try {
      setThread(await api.thread(m.with_tg_id));
      refreshUnread();
    } catch (e) { toast(e.message); }
  };

  const send = async () => {
    const t = text.trim();
    if (!t) return;
    const toTgIds = composing ? composeTargets.map(p => p.tg_id) : [openWith.tg_id];
    if (!toTgIds.length) { toast('حداقل یک گیرنده انتخاب کن'); return; }
    try {
      await api.sendRaven(toTgIds, t);
      haptic('medium');
      if (!composing) setThread(prev => [...prev, { mine: true, text: t }]);
      setText('');
      if (composing) {
        setComposing(false); setComposeTargets([]);
        toast(toTgIds.length > 1 ? `کلاغ برای ${toTgIds.length.toLocaleString('fa-IR')} لرد پر کشید` : 'کلاغ پر کشید');
        loadInbox();
      }
    } catch (e) { toast(e.message); }
  };

  /* ---------- نمای گفتگو ---------- */
  if (openWith || composing) return (
    <>
      <button type="button" className="rbtn back up" style={{ width: 'auto' }}
              onClick={() => { setOpenWith(null); setComposing(false); setComposeTargets([]); loadInbox(); }}>
        <Back s={15} /> بازگشت به صندوق نامه
      </button>
      {composing ? (
        <>
          <div className="page-title up">کلاغ تازه</div>
          <div className="page-sub up">یک یا چند لرد را جست‌وجو و انتخاب کن — کلاغ راهش را بلد است</div>
          <div className="card up u1">
            <label className="f" style={{ marginTop: 0 }}>گیرنده(ها)</label>
            <PlayerPicker value={composeTargets} onChange={setComposeTargets} />
          </div>
        </>
      ) : (
        <div className="page-title up">{openWith.tg_id === SYSTEM_TG_ID ? "اطلاعیه‌های بازی" : openWith.name}</div>
      )}
      <div className="thread up u1" style={{ marginTop: 12 }}>
        {thread.map((m, i) => {
          if (openWith?.tg_id === SYSTEM_TG_ID) {
            const meta = noticeMeta(m);
            const [noticeTitle, ...noticeBody] = (m.text || '').split('\n');
            return (
              <article key={i} className="notice-message">
                <header><span>{meta.icon}</span><strong>{meta.label}</strong>{m.at && <time>{timeAgo(m.at)}</time>}</header>
                {m.kind === 'battle' ? (
                  <div><strong style={{ display: 'block', color: 'var(--text)', marginBottom: 7 }}>{noticeTitle}</strong>{noticeBody.join('\n')}</div>
                ) : <div>{m.text}</div>}
              </article>
            );
          }
          return <div key={i} className={`tmsg ${m.mine ? 'mine' : 'theirs'}`}>{m.text}</div>;
        })}
      </div>
      <div className="composer up u2">
        <input value={text} onChange={e => setText(e.target.value)}
               onKeyDown={e => e.key === 'Enter' && send()} placeholder="نامه‌ات را بنویس..." />
        <button type="button" aria-label="ارسال" onClick={send}><Send s={18} /></button>
      </div>
    </>
  );

  /* ---------- صندوق نامه ---------- */
  if (!inbox) return <div className="loading">کلاغ‌ها در راه‌اند...</div>;

  const announcements = inbox.filter(m => m.with_tg_id === SYSTEM_TG_ID);
  const personal = inbox.filter(m => m.with_tg_id !== SYSTEM_TG_ID);
  const rows = tab === 'announcements' ? announcements : personal;

  return (
    <>
      <div className="page-title up">کلاغ‌ها</div>
      <div className="page-sub up">نامه‌های خصوصی و رخدادهای بازی</div>

      <div className="tabs up u1" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'announcements'}
                className={`rbtn tab ${tab === 'announcements' ? 'on' : ''}`} onClick={() => { haptic(); setTab('announcements'); }}>
          اطلاعیه‌ها
          {unreadBreakdown.announcements > 0 && <span className="raven-tab-count">{unreadBreakdown.announcements.toLocaleString('fa-IR')}</span>}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'messages'}
                className={`rbtn tab ${tab === 'messages' ? 'on' : ''}`} onClick={() => { haptic(); setTab('messages'); }}>
          پیام‌ها
          {unreadBreakdown.messages > 0 && <span className="raven-tab-count">{unreadBreakdown.messages.toLocaleString('fa-IR')}</span>}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'rumors'}
                className={`rbtn tab ${tab === 'rumors' ? 'on' : ''}`} onClick={() => { haptic(); setTab('rumors'); }}>
          توییت‌ها
          {unreadBreakdown.rumors > 0 && <span className="raven-tab-count">{unreadBreakdown.rumors.toLocaleString('fa-IR')}</span>}
        </button>
      </div>

      {tab === 'announcements' && (
        <div className="notice-guide up u2">
          <strong>اینجا سابقهٔ اتفاق‌های مهم بازی می‌مونه</strong>
          <span>⚔️ جنگ · 🔥 شورش · 🏗️ ساخت · 🛒 کاروان · 🤝 پیمان · 🎁 جایزه</span>
        </div>
      )}

      {tab !== 'rumors' && (
        <div className="up u2">
          {rows.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
              {tab === 'announcements' ? 'هنوز اطلاعیه‌ای نیامده' : 'هنوز کلاغی برایت نیامده — تو اولین نامه را بفرست'}
            </div>
          )}
          {rows.map((m, i) => (
            <button type="button" key={i} className="rbtn mailrow" onClick={() => openThread(m)}>
              <div className="mava">{m.with_tg_id === SYSTEM_TG_ID ? noticeMeta(m).icon : m.with_name.charAt(0)}</div>
              <div className="mt">
                <div className="mn">{m.with_tg_id === SYSTEM_TG_ID ? "اطلاعیه‌های بازی" : m.with_name}{m.unread > 0 && <span className="dot" />}</div>
                <div className="ms">{m.last_text}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {tab === 'rumors' && (
        <div className="up u2">
          {composingTweet && (
            <div className="card tweet-composer">
              <div className="sect" style={{ marginTop: 0 }}>توییت تازه</div>
              <label className="f">هدف توییت</label>
              <PlayerPicker value={tweetTarget} onChange={setTweetTarget} single />
              <label className="f">متن توییت</label>
              <textarea value={tweetText} onChange={e => setTweetText(e.target.value)} maxLength={400}
                        placeholder="دربارهٔ این لرد چه توییتی منتشر می‌کنی؟" />
              <div className="page-sub" style={{ margin: '9px 4px 0', lineHeight: 1.8 }}>
                هزینه: <b style={{ color: 'var(--az2)' }}>{RUMOR_GOLD_COST.toLocaleString('fa-IR')} طلا</b> ·
                {' '}اثر: <b style={{ color: 'var(--danger)' }}>−{RUMOR_POPULARITY_DAMAGE.toLocaleString('fa-IR')} محبوبیت هدف</b>
              </div>
              <div className="tweet-composer-actions">
                <button type="button" className="btn" disabled={tweetBusy} onClick={sendTweet}>
                  {tweetBusy ? 'در حال انتشار...' : 'انتشار توییت'}
                </button>
                <button type="button" className="btn ghost" onClick={() => { setComposingTweet(false); setTweetTarget([]); setTweetText(''); }}>انصراف</button>
              </div>
            </div>
          )}
          {rumors === null && <div className="loading">در حال بارگذاری...</div>}
          {rumors && rumors.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز توییت‌ای پخش نشده</div>
          )}
          {rumors && rumors.map(r => (
            <div className="card" key={r.id} style={{ marginBottom: 10 }}>
              <div className="res">
                <div className="ic"><Eye s={16} /></div>
                <div className="n">
                  علیه {r.target}
                  <small>{r.mine ? 'از طرف تو' : 'توییت‌سازش ناشناس مانده'} · {timeAgo(r.created_at)}</small>
                </div>
              </div>
              <div style={{ fontSize: 12.5, lineHeight: 1.8, color: 'var(--hi)', marginTop: 8 }}>{r.text}</div>
              {r.mine ? (
                <div style={{ display: 'flex', gap: 14, marginTop: 10, fontSize: 11.5, color: 'var(--mid)' }}>
                  <span><ThumbsUp s={14} /> {r.likes.toLocaleString('fa-IR')}</span>
                  <span><ThumbsDown s={14} /> {r.dislikes.toLocaleString('fa-IR')}</span>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button type="button" className={`rbtn reaction-btn ${r.my_reaction === 'like' ? 'on' : ''}`}
                          style={{ width: 'auto' }} onClick={() => reactRumor(r.id, 'like')}>
                    <ThumbsUp s={14} /> {r.likes.toLocaleString('fa-IR')}
                  </button>
                  <button type="button" className={`rbtn reaction-btn ${r.my_reaction === 'dislike' ? 'on' : ''}`}
                          style={{ width: 'auto' }} onClick={() => reactRumor(r.id, 'dislike')}>
                    <ThumbsDown s={14} /> {r.dislikes.toLocaleString('fa-IR')}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'messages' && (
        <button type="button" className="fab" aria-label="کلاغ تازه" onClick={() => { haptic(); setComposing(true); setThread([]); }}>
          <Plus s={22} />
        </button>
      )}
      {tab === 'rumors' && !composingTweet && (
        <button type="button" className="fab" aria-label="توییت تازه" onClick={() => { haptic(); setComposingTweet(true); }}>
          <Plus s={22} />
        </button>
      )}
    </>
  );
}

