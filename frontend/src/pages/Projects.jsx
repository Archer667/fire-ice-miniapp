import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import '../projects.css';
import { useGame } from '../store.jsx';

const LABELS = { gold: 'طلا', wood: 'چوب', stone: 'سنگ', iron: 'آهن', food: 'غذا', wine: 'شراب' };
const STATUS = { pending: 'منتظر تأیید ادمین', scheduled: 'زمان‌بندی‌شده', funding: 'در حال جذب سرمایه', active: 'در حال اجرا', completed: 'تکمیل‌شده', rejected: 'ردشده', unfunded: 'جذب سرمایه ناموفق', failed: 'شکست‌خورده', reserving: 'در حال رزرو آورده' };
const number = v => Number(v || 0).toLocaleString('fa-IR', { maximumFractionDigits: 8 });
const money = b => Object.entries(b || {}).filter(([, v]) => v !== 0).map(([k, v]) => `${number(v)} ${LABELS[k] || k}`).join(' + ') || '۰';
const mult = (b, q) => Object.fromEntries(Object.entries(b || {}).map(([k, v]) => [k, v * q]));
const difference = (a, b) => Object.fromEntries(Object.keys(LABELS).map(k => [k, (a?.[k] || 0) - (b?.[k] || 0)]));
const isoDate = s => s && new Date(/[Zz]|[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z');
const date = s => s ? isoDate(s).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran', dateStyle: 'medium', timeStyle: 'short' }) + ' (تهران)' : 'پس از تأیید ادمین';
const initial = () => ({ request_id: crypto.randomUUID(), kind: 'shared', name: '', goal: '', description: '', budget: { gold: 1000, wood: 200 }, total_shares: 100, owner_shares: 30, period_return: { gold: 200, wood: 100 }, period_hours: 24, period_count: 10, accepted_terms: false });

function Modal({ title, children, close }) {
  const ref = useRef(null);
  useEffect(() => { ref.current.showModal(); }, []);
  return <dialog ref={ref} className="project-dialog" onCancel={close} onClick={e => { if (e.target === ref.current) close(); }}>
    <div className="project-dialog-head"><h2>{title}</h2><button type="button" className="btn ghost" onClick={close} aria-label="بستن پنجره">×</button></div>
    {children}
  </dialog>;
}

function Resources({ title, values, change }) {
  return <fieldset className="project-fieldset"><legend>{title}</legend><div className="project-resource-grid">
    {Object.entries(LABELS).map(([key, label]) => <label className="f" key={key}>{label}<input type="number" inputMode="numeric" min="0" max="1000000000" step="1" value={values[key] || ''} placeholder="۰" onChange={e => change({ ...values, [key]: Number(e.target.value) })} /></label>)}
  </div></fieldset>;
}

function Economics({ project, shares, title }) {
  const perShare = project.share_return || mult(project.period_return, 1 / project.total_shares);
  const cost = project.share_cost || mult(project.budget, 1 / project.total_shares);
  const income = mult(perShare, shares);
  const total = mult(income, project.period_count);
  const investment = mult(cost, shares);
  return <div className="project-economics"><strong>{title}</strong><dl>
    <dt>آورده</dt><dd>{money(investment)}</dd>
    <dt>دریافتی هر دوره</dt><dd>{money(income)}</dd>
    <dt>دریافتی کل در صورت موفقیت</dt><dd>{money(total)}</dd>
    <dt>خالص هر منبع پس از کسر آورده</dt><dd>{money(difference(total, investment))}</dd>
  </dl></div>;
}

export default function Projects({ admin = false }) {
  const { me, setMe, toast } = useGame();
  const [rows, setRows] = useState(null);
  const [rules, setRules] = useState(null);
  const [error, setError] = useState('');
  const [mine, setMine] = useState(false);
  const [status, setStatus] = useState('all');
  const [create, setCreate] = useState(false);
  const [form, setForm] = useState(initial);
  const [terms, setTerms] = useState(false);
  const [selected, setSelected] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [purchaseKey, setPurchaseKey] = useState(() => crypto.randomUUID());
  const [purchaseAccepted, setPurchaseAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState(null);
  const [clock, setClock] = useState(Date.now());
  const busyRef = useRef(false);
  const load = async () => {
    try { const data = await (admin ? api.adminProjects() : api.projects(mine)); setRows(data); setError(''); }
    catch (e) { setError(e.message); }
  };
  useEffect(() => { api.projectRules().then(setRules).catch(e => setError(e.message)); }, []);
  useEffect(() => { load(); const timer = setInterval(() => { load(); setClock(Date.now()); }, 15000); return () => clearInterval(timer); }, [admin, mine]);
  const run = async action => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await action(); await load(); if (!admin) await api.me().then(setMe); }
    catch (e) { toast(e.message); }
    finally { busyRef.current = false; setBusy(false); }
  };
  const field = (key, value) => setForm(prev => ({ ...prev, [key]: value, request_id: crypto.randomUUID() }));
  const selectedProject = rows?.find(p => p.id === selected?.id) || selected;
  const previewValid = form.total_shares > 0 && Object.values(form.budget).some(v => v > 0) && Object.values(form.budget).every(v => v >= 0 && v % form.total_shares === 0);
  const ownerShares = form.kind === 'personal' ? form.total_shares : form.owner_shares;
  const submit = e => {
    e.preventDefault();
    if (!previewValid) { toast('هر منبع بودجه باید بر تعداد سهام بخش‌پذیر باشد'); return; }
    run(async () => {
      try { await api.submitProject({ ...form, owner_shares: ownerShares }); }
      catch (error) {
        if (error.status >= 400 && error.status < 500) setForm(prev => ({ ...prev, request_id: crypto.randomUUID() }));
        throw error;
      }
      toast('طرح ثبت شد و آوردهٔ شما رزرو شد'); setCreate(false); setForm(initial()); setMine(true);
    });
  };
  const openProject = p => {
    setSelected(p); setQuantity(1); setPurchaseKey(crypto.randomUUID()); setPurchaseAccepted(false);
    const local = new Date(Date.now() + 3600000); local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
    setReview({ publish_at: local.toISOString().slice(0, 16), funding_hours: 48, max_shares_per_player: '', reason: '', notification_terms: p.notification_terms || rules?.terms || '' });
  };
  const decide = action => run(async () => {
    if (review.reason.trim().length < 3) throw new Error('دلیل تصمیم را بنویس');
    if (action === 'fail' && !window.confirm('شکست پروژه ثبت شود؟ اصل سرمایه بازنمی‌گردد و تمام پرداخت‌های آینده متوقف می‌شوند.')) return;
    const payload = action === 'approve' ? { ...review, publish_at: new Date(review.publish_at).toISOString(), funding_hours: Number(review.funding_hours), max_shares_per_player: review.max_shares_per_player ? Number(review.max_shares_per_player) : null } : { reason: review.reason };
    await api.decideProject(selectedProject.id, action, payload); toast('تصمیم ثبت شد'); setSelected(null);
  });

  return <section className="projects" dir="rtl">
    <div className="project-toolbar"><h2>{admin ? 'مدیریت پروژه‌ها' : 'پروژه‌های قلمرو'}</h2>
      {!admin && !me.admin_role && <button className="btn" disabled={!rules || busy} onClick={() => setCreate(true)}>＋ طرح پروژه</button>}
    </div>
    <p className="page-sub">{admin ? 'طرح را بررسی کن، زمان عرضه را مشخص کن و پروژه‌های در حال اجرا را مدیریت کن.' : 'سرمایه‌گذاری در طرح‌های تأییدشده؛ بازده دوره‌ای با ریسک شکست پروژه.'}</p>
    <div className="project-toolbar">
      {!admin && <label className="project-check"><input type="checkbox" checked={mine} onChange={e => setMine(e.target.checked)} />پروژه‌های من</label>}
      <label className="f">وضعیت<select value={status} onChange={e => setStatus(e.target.value)}><option value="all">همه</option>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <button className="btn ghost" onClick={load}>تازه‌سازی</button>
      <button className="btn ghost" disabled={!rules} onClick={() => setTerms(true)}>شرایط سرمایه‌گذاری</button>
    </div>
    {error && <p role="alert" className="project-error">{error}</p>}
    {rows === null && !error && <div className="loading">دریافت پروژه‌ها...</div>}
    {rows && !rows.filter(p => status === 'all' || p.status === status).length && <div className="empty">پروژه‌ای در این فهرست نیست.</div>}
    <div className="project-grid">{rows?.filter(p => status === 'all' || p.status === status).map(p => <article className="card project-card" key={p.id}>
      <div className="project-toolbar"><span className={`project-status ${p.status}`}>{STATUS[p.status]}</span><small>{p.kind === 'personal' ? 'شخصی' : 'مشترک'}</small></div>
      <h3>{p.name}</h3><p className="page-sub">طراح: {p.owner_name}{p.is_owner ? ' — شما' : ''}</p><p>{p.goal}</p>
      <progress max={p.total_shares} value={p.sold_shares} aria-label="سهام تأمین‌شده" />
      <div className="project-toolbar"><small>{number(p.sold_shares)} از {number(p.total_shares)} سهم تأمین شده</small>{p.my_shares > 0 && <strong>{number(p.my_shares)} سهم شما</strong>}</div>
      <dl><dt>بهای هر سهم</dt><dd>{money(p.share_cost)}</dd><dt>دریافتی هر سهم / {number(p.period_hours)} ساعت</dt><dd>{money(p.share_return)}</dd></dl>
      {p.status === 'funding' && <small>پایان خرید: {date(p.funding_deadline)}</small>}
      {p.status === 'scheduled' && <small>عرضه: {date(p.publish_at)}</small>}
      {p.status === 'active' && <small>پرداخت بعدی: {date(p.next_payout_at)}</small>}
      <button className="btn ghost" onClick={() => openProject(p)}>{admin ? 'بررسی و مدیریت' : 'جزئیات و سرمایه‌گذاری'}</button>
    </article>)}</div>

    {create && <Modal title="طرح پروژهٔ تازه" close={() => !busy && setCreate(false)}>
      <form onSubmit={submit}>
        <fieldset disabled={busy} className="project-fieldset">
          <label className="f">نوع پروژه<select value={form.kind} onChange={e => field('kind', e.target.value)}><option value="shared">مشترک — با سرمایه‌گذار</option><option value="personal">شخصی — تمام سرمایه با خودم</option></select></label>
          <label className="f">نام پروژه<input required minLength={3} maxLength={80} value={form.name} onChange={e => field('name', e.target.value)} /></label>
          <label className="f">چشم‌انداز و هدف<textarea required minLength={10} maxLength={250} value={form.goal} onChange={e => field('goal', e.target.value)} /></label>
          <label className="f">توضیح و شیوهٔ رسیدن به هدف<textarea required minLength={20} maxLength={600} value={form.description} onChange={e => field('description', e.target.value)} /></label>
          <Resources title="کل بودجهٔ موردنیاز" values={form.budget} change={v => field('budget', v)} />
          <div className="project-resource-grid"><label className="f">تعداد کل سهام<input required type="number" min="1" max="10000" step="1" value={form.total_shares} onChange={e => field('total_shares', Number(e.target.value))} /></label>
          <label className="f">سهام اولیهٔ شما<input required type="number" disabled={form.kind === 'personal'} min="1" max={form.total_shares - (form.kind === 'shared' ? 1 : 0)} step="1" value={ownerShares} onChange={e => field('owner_shares', Number(e.target.value))} /></label></div>
          {!previewValid && <p className="project-error">مقدار هر منبع بودجه باید بر تعداد کل سهام بخش‌پذیر باشد.</p>}
          <p>بهای هر سهم: <strong>{previewValid ? money(mult(form.budget, 1 / form.total_shares)) : '—'}</strong></p>
          <p>آوردهٔ شما: <strong>{previewValid ? money(mult(form.budget, ownerShares / form.total_shares)) : '—'}</strong></p>
          <p>آوردهٔ سرمایه‌گذاران: <strong>{previewValid ? money(mult(form.budget, (form.total_shares - ownerShares) / form.total_shares)) : '—'}</strong></p>
          <Resources title="خروجی کل پروژه در هر دوره" values={form.period_return} change={v => field('period_return', v)} />
          <div className="project-resource-grid"><label className="f">فاصلهٔ پرداخت‌ها (ساعت)<input required type="number" min="1" max="720" value={form.period_hours} onChange={e => field('period_hours', Number(e.target.value))} /></label>
          <label className="f">تعداد دوره‌ها<input required type="number" min="1" max="365" value={form.period_count} onChange={e => field('period_count', Number(e.target.value))} /></label></div>
          <p>طول اجرا: {number(form.period_hours * form.period_count)} ساعت — اولین پرداخت یک دوره پس از شروع اجرا.</p>
          {previewValid && <><Economics project={form} shares={1} title="محاسبات هر سهم" /><Economics project={form} shares={ownerShares} title={`محاسبات شما — ${number(ownerShares)} سهم`} /></>}
          <button type="button" className="btn ghost" onClick={() => setTerms(true)}>مطالعهٔ شرایط سرمایه‌گذاری</button>
          <label className="project-check"><input required type="checkbox" checked={form.accepted_terms} onChange={e => field('accepted_terms', e.target.checked)} />شرایط رزرو، جریمه و شکست پروژه را خواندم و می‌پذیرم.</label>
          <button className="btn" disabled={!previewValid || !form.accepted_terms}>{busy ? 'در حال ثبت...' : 'ثبت درخواست و رزرو آوردهٔ من'}</button>
        </fieldset>
      </form>
    </Modal>}

    {selectedProject && selected && <Modal title={selectedProject.name} close={() => !busy && setSelected(null)}>
      <span className={`project-status ${selectedProject.status}`}>{STATUS[selectedProject.status]}</span>
      <p>طراح: <strong>{selectedProject.owner_name}</strong> — {number(selectedProject.owner_shares)} سهم ({number(selectedProject.owner_shares / selectedProject.total_shares * 100)}٪)</p>
      <h3>هدف</h3><p>{selectedProject.goal}</p><h3>شیوهٔ اجرا</h3><p className="project-pre">{selectedProject.description}</p>
      <dl><dt>بودجهٔ کل</dt><dd>{money(selectedProject.budget)}</dd><dt>آوردهٔ طراح</dt><dd>{money(mult(selectedProject.share_cost, selectedProject.owner_shares))}</dd>
      <dt>آوردهٔ موردنیاز سرمایه‌گذاران</dt><dd>{money(mult(selectedProject.share_cost, selectedProject.total_shares - selectedProject.owner_shares))}</dd>
      <dt>سهام کل / باقی‌مانده</dt><dd>{number(selectedProject.total_shares)} / {number(selectedProject.remaining_shares)}</dd>
      <dt>دوره‌های پرداخت</dt><dd>{number(selectedProject.period_count)} نوبت، هر {number(selectedProject.period_hours)} ساعت</dd>
      <dt>طول اجرا</dt><dd>{number(selectedProject.period_hours * selectedProject.period_count)} ساعت</dd>
      <dt>دوره‌های پرداخت‌شده</dt><dd>{number(selectedProject.paid_periods)}</dd><dt>زمان عرضه</dt><dd>{date(selectedProject.publish_at)}</dd>
      {selectedProject.funding_deadline && <><dt>مهلت جذب سرمایه</dt><dd>{date(selectedProject.funding_deadline)}</dd></>}
      <dt>سقف خرید هر بازیکن</dt><dd>{selectedProject.max_shares_per_player ? `${number(selectedProject.max_shares_per_player)} سهم` : 'بدون محدودیت'}</dd></dl>
      <Economics project={selectedProject} shares={1} title="هر سهم" />
      {(selectedProject.my_shares > 0 || admin) && <Economics project={selectedProject} shares={admin ? selectedProject.owner_shares : selectedProject.my_shares} title={admin ? 'محاسبات طراح' : 'محاسبات سهام شما'} />}
      {selectedProject.my_shares > 0 && <p>دریافتی پرداخت‌شدهٔ شما: <strong>{money(selectedProject.my_received)}</strong></p>}
      {selectedProject.reason && <p className="project-pre">دلیل تصمیم ادمین: {selectedProject.reason}</p>}
      {selectedProject.notification_terms && <><h3>متن شرایط اعلام‌شده</h3><p className="project-pre">{selectedProject.notification_terms}</p></>}
      <button className="btn ghost" onClick={() => setTerms(true)}>قوانین ثابت سرمایه‌گذاری</button>
      {!admin && selectedProject.is_owner && <p className="page-sub">شما طراح این پروژه هستید؛ خرید سهم برای طراح مجاز نیست.</p>}
      {!admin && !me.admin_role && selectedProject.can_buy && clock < isoDate(selectedProject.funding_deadline).getTime() && <form onSubmit={e => { e.preventDefault(); run(async () => {
        if (!purchaseAccepted) throw new Error('شرایط سرمایه‌گذاری را بپذیر');
        await api.buyProjectShares(selectedProject.id, { shares: quantity, request_id: purchaseKey }); toast('سهام خریداری شد'); setSelected(null);
      }); }}>
        <label className="f">تعداد سهم<input required disabled={busy} type="number" min="1" max={Math.min(selectedProject.remaining_shares, selectedProject.max_shares_per_player ? selectedProject.max_shares_per_player - selectedProject.my_shares : selectedProject.remaining_shares)} value={quantity} onChange={e => { setQuantity(Number(e.target.value)); setPurchaseKey(crypto.randomUUID()); }} /></label>
        <Economics project={selectedProject} shares={quantity} title="پیش‌نمایش این خرید" />
        <label className="project-check"><input type="checkbox" required checked={purchaseAccepted} onChange={e => setPurchaseAccepted(e.target.checked)} />قوانین ثابت و ریسک ازدست‌رفتن سرمایه را می‌پذیرم.</label>
        <button className="btn" disabled={busy || !purchaseAccepted}>{busy ? 'در حال خرید...' : `خرید ${number(quantity)} سهم`}</button>
      </form>}
      {admin && review && ['pending', 'active'].includes(selectedProject.status) && <div className="project-review">
        <h3>تصمیم ادمین</h3><label className="f">دلیل تصمیم<textarea minLength={3} maxLength={500} value={review.reason} disabled={busy} onChange={e => setReview({ ...review, reason: e.target.value })} /></label>
        {selectedProject.status === 'pending' && <>
          <label className="f">زمان عرضه (به وقت دستگاه شما)<input type="datetime-local" value={review.publish_at} disabled={busy} onChange={e => setReview({ ...review, publish_at: e.target.value })} /></label>
          <label className="f">فرصت جذب سرمایه از زمان عرضه (ساعت)<input type="number" min="1" max="720" value={review.funding_hours} disabled={busy} onChange={e => setReview({ ...review, funding_hours: e.target.value })} /></label>
          {selectedProject.kind === 'shared' && <label className="f">حداکثر مجموع سهام هر بازیکن — خالی یعنی نامحدود<input type="number" min="1" max="10000" value={review.max_shares_per_player} disabled={busy} onChange={e => setReview({ ...review, max_shares_per_player: e.target.value })} /></label>}
          <label className="f">شرایط سرمایه‌گذاری در اعلان<textarea rows="7" minLength={10} maxLength={1000} value={review.notification_terms} disabled={busy} onChange={e => setReview({ ...review, notification_terms: e.target.value })} /></label>
          <p className="page-sub">این متن در کلاغ و بات نمایش داده می‌شود؛ قوانین واقعی پرداخت و بازپرداخت را تغییر نمی‌دهد.</p>
          <button className="btn ghost" disabled={busy} onClick={() => setReview({ ...review, notification_terms: rules.terms })}>بازگرداندن متن پیش‌فرض</button>
          <div className="project-toolbar"><button className="btn" disabled={busy} onClick={() => decide('approve')}>تأیید و زمان‌بندی اعلان</button><button className="btn ghost" disabled={busy} onClick={() => decide('reject')}>رد درخواست و بازپرداخت</button></div>
        </>}
        {selectedProject.status === 'active' && <button className="btn" disabled={busy} onClick={() => decide('fail')}>اعلام شکست پروژه</button>}
      </div>}
      {admin && selectedProject.members && <><h3>سهام‌داران</h3>{selectedProject.members.map(m => <p key={m.tg_id}>{m.name} — {number(m.shares)} سهم</p>)}</>}
    </Modal>}
    {terms && rules && <Modal title="شرایط سرمایه‌گذاری" close={() => setTerms(false)}><p className="project-pre">{rules.terms}</p><p>در محاسبات، طلا و هر منبع جدا ارزیابی می‌شوند؛ برای منابع متفاوت، درصد سود تجمیعی ساختگی نمایش داده نمی‌شود.</p><button className="btn" onClick={() => setTerms(false)}>متوجه شدم</button></Modal>}
  </section>;
}
