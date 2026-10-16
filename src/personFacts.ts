import type { Entry, FamilyDate } from './types';

export function todayInShanghai(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
 const value=(type:string)=>parts.find(p=>p.type===type)!.value;
 return `${value('year')}-${value('month')}-${value('day')}`;
}

function solarDate(value:FamilyDate|undefined,info:any):string|undefined{
 if(info?.solar)return info.solar;
 if(value?.calendar!=='lunar'&&value?.year&&value.month&&value.day)return `${String(value.year).padStart(4,'0')}-${String(value.month).padStart(2,'0')}-${String(value.day).padStart(2,'0')}`;
}
function displayDate(value:FamilyDate|undefined,info:any){
 if(!value||![value.year,value.month,value.day].some(Boolean))return value?.original?'日期待考（有原记载）':'日期不详';
 if(value.calendar==='lunar')return info?.label||`农历 ${value.year?value.year+'年':''}${value.leap?'闰':''}${value.month?value.month+'月':''}${value.day?value.day+'日':''}`;
 const full=solarDate(value,info);
 if(full)return (value.approximate?'约 ':'')+full.replaceAll('-','.');
 return (value.approximate?'约 ':'')+(value.year?value.year+'年':'')+(value.month?value.month+'月':'')+(value.day?value.day+'日':'');
}

export function birthPresentation(person:Entry){
 const value=person.data.birth as FamilyDate|undefined,info=person.birth_info;
 const lunar=value?.calendar==='lunar';
 const primary=displayDate(value,info);
 const alternate=lunar?info?.solar:info?.lunar;
 return {label:lunar?'农历生日':'阳历生日',primary,secondary:alternate?`${lunar?'阳历':'农历'} ${alternate}`:'',original:value?.original||''};
}

export function personFacts(person:Entry,today=todayInShanghai()){
 const {birth,death}=person.data as {birth?:FamilyDate;death?:FamilyDate};
 const living=person.data.living!==false;
 const start=solarDate(birth,person.birth_info),end=living?today:solarDate(death,person.death_info);
 let age='待考';
 if(start&&end){
  if(end<start)age='日期待核对';
  else{
   const years=Number(end.slice(0,4))-Number(start.slice(0,4))-(end.slice(5)<start.slice(5)?1:0);
   const approximate=birth?.approximate||(!living&&death?.approximate);
   age=(approximate?'约 ':'')+(years===0?'不足1岁':`${years}${living&&!approximate?'周岁':'岁'}`);
  }
 }else if(birth?.year&&birth.calendar!=='lunar'&&(living||(death?.year&&death.calendar!=='lunar'))){
  const year=living?Number(today.slice(0,4)):death!.year!;
  if(year<birth.year)age='日期待核对';
  else age=`约 ${year-birth.year} 岁`;
 }
 return {gender:person.data.gender==='male'?'男':person.data.gender==='female'?'女':'性别未注明',living,birth:displayDate(birth,person.birth_info),death:living?undefined:displayDate(death,person.death_info),age,ageLabel:living?'年龄':'享年',ageTitle:living?`截至 ${today}，按阳历周岁计算；仅有年份时标为估算`:'按出生至去世日期计算；仅有年份时标为估算'};
}
