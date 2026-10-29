import LivingPageHero from './LivingPageHero.jsx';

export const PAGE_PRESENTATION = [
  {slug:'realm', core:true, title:'قلمرو', art:'/buildings/art/treasury.webp'},
  {slug:'buildings', core:true, title:'ساختمان‌ها', art:'/buildings/art/wall-stone.webp'},
  {slug:'war', core:true, title:'نیرو', art:'/maps/westros1.webp'},
  {slug:'throne', core:true, title:'تاج‌وتخت', art:'/institutions/art/faith.webp'},
  {slug:'ravens', title:'کلاغ‌ها', eyebrow:'نامه‌ها و خبرهای قلمرو', subtitle:'پیام‌ها، شایعه‌ها و اعلامیه‌هایی که مسیر داستان را عوض می‌کنند.', art:'/buildings/art/watchtower.webp'},
  {slug:'diplomacy', core:true, title:'دیپلماسی', art:'/buildings/art/market.webp'},
  {slug:'admin', title:'پنل مدیریت', eyebrow:'فرماندهی سامانه', subtitle:'رسیدگی به جهان، بازیکنان، داوری‌ها و تنظیمات از یک مرکز فرماندهی.', art:'/institutions/art/citadel.webp'},
  {slug:'espionage', title:'جاسوسی', eyebrow:'سایه‌ها خبر می‌آورند', subtitle:'شبکه‌ها را مستقر کن، گزارش‌ها را دنبال کن و پرسش‌های اطلاعاتی بفرست.', art:'/institutions/art/faceless.webp'},
  {slug:'trade', title:'تجارت', eyebrow:'راه‌ها به خزانه می‌رسند', subtitle:'بازار، کاروان‌ها و جریان کالا میان قلعه‌های وستروس.', art:'/buildings/art/market.webp'},
  {slug:'roleplay', title:'رول‌ها', eyebrow:'روایت زندهٔ قلمرو', subtitle:'داستان شخصیتت، سناریوها و پرونده‌های در انتظار داوری.', art:'/institutions/art/citadel.webp'},
  {slug:'assets', title:'دارایی‌ها', eyebrow:'آنچه زیر پرچمت گرد آمده', subtitle:'قلعه‌ها، منابع، نیروها، ادوات و آیتم‌های خاندان.', art:'/buildings/art/warehouse.webp'},
  {slug:'family', title:'خاندان و خانواده', eyebrow:'نامی که پس از تو می‌ماند', subtitle:'فرزندان، پیوندها و سرنوشت نسل بعدی خاندان.', art:'/buildings/art/village.webp'},
  {slug:'profile', title:'کاراکتر', eyebrow:'چهرهٔ تو در این جهان', subtitle:'مشخصات، تصویر و گذشته‌ای که دیگران از شخصیتت می‌بینند.', art:'/institutions/art/faith.webp'},
  {slug:'institutions', title:'نهادها', eyebrow:'قدرت بیرون از دیوار قلعه', subtitle:'بانک، سیتادل، انجمن‌ها و سازمان‌هایی که بر جهان اثر می‌گذارند.', art:'/institutions/art/bank.webp'},
  {slug:'travel', title:'کاراکتر و سفر', eyebrow:'هر جاده داستانی تازه دارد', subtitle:'محل اقامت، همراهان، درخواست ورود و مسیر سفر شخصیت.', art:'/maps/westros1.webp'},
  {slug:'store', title:'فروشگاه آیتم‌ها', eyebrow:'کالاهای کمیاب وستروس', subtitle:'فروش قطعی، مزایده‌ها و سفارش‌هایی که منتظر تأیید هستند.', art:'/buildings/art/goods_warehouse.webp'},
  {slug:'notifications', title:'صندوق اعلان', eyebrow:'هیچ فرمانی را از دست نده', subtitle:'خبرها، پاسخ‌ها و رویدادهای مهم حساب در یک صندوق مرتب.', art:'/buildings/art/watchtower.webp'},
  {slug:'contracts', title:'تابلوی قراردادها', eyebrow:'مُهر بزن؛ عهد ببند', subtitle:'پیشنهادها و قراردادهایی که به دنبال همراه یا مجری هستند.', art:'/buildings/art/treasury.webp'},
  {slug:'castle-life', title:'زندگی در قلعه', eyebrow:'پشت دیوارها چه می‌گذرد', subtitle:'رفت‌وآمد، رویدادها و زندگی روزمرهٔ ساکنان قلعه.', art:'/buildings/art/village.webp'},
  {slug:'newspaper', title:'روزنامه', eyebrow:'وقایع وستروس', subtitle:'خبرهای رسمی و روایت رخدادهایی که همه درباره‌شان حرف می‌زنند.', art:'/institutions/art/citadel.webp'},
  {slug:'guide', core:true, title:'راهنمای بازی', art:'/institutions/art/citadel.webp'},
  {slug:'support', title:'پشتیبانی', eyebrow:'صدایت به ما می‌رسد', subtitle:'تیکت‌های فنی، رول و سناریوی نبرد را بفرست و پاسخ را همین‌جا بگیر.', art:'/institutions/art/watch.webp'},
];

export function presentationFor(index) {
  return PAGE_PRESENTATION[index] || PAGE_PRESENTATION[0];
}

export default function LivingScreen({ index, children }) {
  const page = presentationFor(index);
  return <section className={`living-screen living-screen-${page.slug} ${page.core ? 'living-screen-core' : 'living-screen-secondary'}`} data-living-page={page.slug} style={{'--screen-art':`url("${page.art}")`}}>
    {!page.core && <LivingPageHero kind={page.slug} eyebrow={page.eyebrow} title={page.title} subtitle={page.subtitle} art={page.art} compact />}
    <div className="living-screen-body">{children}</div>
  </section>;
}
