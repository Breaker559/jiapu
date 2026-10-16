import { Children, cloneElement, isValidElement, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { X, LoaderCircle, ChevronDown, CalendarDays, Moon, Sun, Search, ArrowRight, Sprout } from 'lucide-react';
import { json } from './api';
import type { Entry, FamilyDate } from './types';
import { initials } from './types';

export function Logo({small=false}:{small?:boolean}) { return <div className={'brand '+(small?'small':'')}><span className="brand-icon"><Sprout size={25}/></span><span>家谱<small>JIAPU</small></span></div>; }
export function Avatar({person,fid,size='md',onClick}:{person:Entry;fid:string;size?:string;onClick?:()=>void}) {
 const [bad,setBad]=useState(false);const d=person.data;
 useEffect(()=>setBad(false),[d.avatar]);
 return <span onClick={onClick} className={`avatar ${size} ${d.gender==='female'?'rose':d.gender==='male'?'sage':'slate'}`}>{d.avatar&&!bad?<img alt={d.name} src={`/api/families/${fid}/media/${d.avatar}/avatar?person=${person.id}&v=${person.version}`} onError={()=>setBad(true)}/>:initials(d.name)}</span>;
}
export function Button({children,loading=false,variant='',...props}:any){return <button className={`button ${variant}`} disabled={loading||props.disabled} {...props}>{loading?<LoaderCircle size={17} className="spin"/>:null}{children}</button>;}
export function Modal({title,subtitle,children,onClose,wide=false}:{title:string;subtitle?:string;children:ReactNode;onClose:()=>void;wide?:boolean}){
 const ref=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  const prev=document.activeElement as HTMLElement;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';
  const timer=setTimeout(()=>ref.current?.querySelector<HTMLElement>('input,select,textarea,button')?.focus(),40);
  const key=(e:KeyboardEvent)=>{
   if(e.key==='Escape')onClose();
   if(e.key==='Tab'){
    const els=Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')||[]).filter(x=>x.offsetParent!==null);
    if(!els.length)return;const first=els[0],last=els[els.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
   }
  };document.addEventListener('keydown',key);
  return()=>{clearTimeout(timer);document.body.style.overflow=overflow;document.removeEventListener('keydown',key);prev?.focus();};
 },[]);
 return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div ref={ref} className={'modal '+(wide?'wide':'')} role="dialog" aria-modal="true" aria-label={title}><div className="modal-head"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div><button className="icon-button" aria-label="关闭" onClick={onClose}><X size={21}/></button></div>{children}</div></div>;
}
export function Field({label,children,hint}:{label:string;children:ReactNode;hint?:string}){
 const id=useId();
 const labelled=(nodes:ReactNode):ReactNode=>Children.map(nodes,node=>{
  if(!isValidElement(node))return node;
  const el=node as React.ReactElement<any>;
  if(['input','textarea','select'].includes(String(el.type)))return cloneElement(el,{'aria-label':el.props['aria-label']||label,'aria-describedby':hint?id:undefined});
  if(el.type==='label')return el;
  return el.props.children?cloneElement(el,{},labelled(el.props.children)):el;
 });
 return <div className="field"><span>{label}</span>{labelled(children)}{hint&&<small id={id}>{hint}</small>}</div>;
}
export function Empty({icon:Icon=Sprout,title,description,action}:{icon?:any;title:string;description?:string;action?:ReactNode}){return <div className="empty"><span className="empty-icon"><Icon size={29}/></span><h3>{title}</h3><p>{description}</p>{action}</div>;}
export function SearchBox({value,onChange,placeholder='搜索姓名、别名、房支…'}:{value:string;onChange:(v:string)=>void;placeholder?:string}){return <div className="search-box"><Search size={18}/><input aria-label={placeholder} placeholder={placeholder} value={value} onChange={e=>onChange(e.target.value)}/>{value&&<button className="icon-button" aria-label="清空搜索" onClick={()=>onChange('')}><X size={14}/></button>}</div>;}
export function DateField({label,value={},onChange}:{label:string;value:FamilyDate;onChange:(d:FamilyDate)=>void}){
 const [info,setInfo]=useState<any>(null);const [error,setError]=useState('');
 useEffect(()=>{let live=true;const t=setTimeout(()=>{json('/dates/convert','POST',value).then(x=>{if(live){setInfo(x);setError('');}}).catch(e=>{if(live){setInfo(null);setError(e.message);}});},250);return()=>{live=false;clearTimeout(t);};},[JSON.stringify(value)]);
 const set=(k:string,v:any)=>onChange({...value,[k]:v});
 return <div className="date-field"><div className="date-label"><span>{label}</span><div className="segmented small"><button type="button" className={(value.calendar||'solar')==='solar'?'active':''} onClick={()=>onChange({...value,calendar:'solar',leap:false})}><Sun size={13}/>阳历</button><button type="button" className={value.calendar==='lunar'?'active':''} onClick={()=>onChange({...value,calendar:'lunar'})}><Moon size={13}/>农历</button></div></div><div className="date-inputs"><input type="number" aria-label={label+'年份'} placeholder="年份不详" min="1" max="9999" value={value.year||''} onChange={e=>set('year',e.target.value?Number(e.target.value):null)}/><select aria-label={label+'月份'} value={value.month||''} onChange={e=>set('month',e.target.value?Number(e.target.value):null)}><option value="">月不详</option>{Array.from({length:12},(_,i)=><option key={i} value={i+1}>{i+1} 月</option>)}</select><select aria-label={label+'日期'} value={value.day||''} onChange={e=>set('day',e.target.value?Number(e.target.value):null)}><option value="">日不详</option>{Array.from({length:value.calendar==='lunar'?30:31},(_,i)=><option key={i} value={i+1}>{i+1} 日</option>)}</select></div><div className="date-options">{value.calendar==='lunar'&&<label><input type="checkbox" checked={value.leap||false} onChange={e=>set('leap',e.target.checked)}/>闰月</label>}<label><input type="checkbox" checked={value.approximate||false} onChange={e=>set('approximate',e.target.checked)}/>约数 / 日期待考</label></div>{error?<small className="error-text">{error}</small>:info&&<small className="date-conversion"><CalendarDays size={13}/>{value.calendar==='lunar'?(info.solar?`阳历 ${info.solar}`:info.note):(info.lunar?`农历 ${info.lunar}`:info.note)}</small>}</div>;
}
export function SectionTitle({title,subtitle,action}:{title:string;subtitle?:string;action?:ReactNode}){return <div className="section-title"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>;}
export function TextLink({children,onClick}:{children:ReactNode;onClick:()=>void}){return <button className="text-link" onClick={onClick}>{children}<ArrowRight size={15}/></button>;}
