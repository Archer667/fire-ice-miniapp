import {Swords,Shield} from './Icons.jsx';
export default function InstitutionIcon({kind='institutions',s=24}) {
  if(kind==='golden-company')return <Swords s={s}/>;
  if(kind==='watch')return <Shield s={s}/>;
  const url=`url(/institutions/${kind}.svg)`;
  return <span aria-hidden="true" style={{display:'inline-block',flexShrink:0,width:s,height:s,verticalAlign:'middle',backgroundColor:'currentColor',maskImage:url,WebkitMaskImage:url,maskSize:'contain',WebkitMaskSize:'contain',maskRepeat:'no-repeat',WebkitMaskRepeat:'no-repeat'}}/>;
}
export const CharacterIcon=props=><InstitutionIcon {...props} kind="character"/>;
export const InstitutionsIcon=props=><InstitutionIcon {...props} kind="institutions"/>;
export const INSTITUTIONS=[
  {id:'bank',name:'بانک آهنین براووس',description:'وام، اقساط و ضمانت',icon:'bank'},
  {id:'citadel',name:'سیتادل',description:'پژوهش و درمان کاراکتر',icon:'citadel'},
  {id:'golden-company',name:'گروه طلایی',description:'قرارداد و اعزام مزدور',icon:'golden-company'},
  {id:'alchemists',name:'صنف کیمیاگران',description:'سفارش ساخت و سناریوی تولید',icon:'alchemists'},
  {id:'faceless',name:'بی‌چهره‌ها',description:'سفارش مأموریت و ارسال سناریو',icon:'faceless'},
  {id:'faith',name:'ایمان هفت',description:'مراسم، میانجی‌گری و حمایت مذهبی',icon:'faith'},
  {id:'watch',name:'نگهبانان شب',description:'مأموریت‌های دیوار و پشتیبانی',icon:'watch'},
];
