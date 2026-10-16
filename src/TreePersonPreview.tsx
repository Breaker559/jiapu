import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowUpRight, Camera, GitFork, X } from 'lucide-react';
import { Avatar } from './components';
import type { Entry } from './types';
import { personFacts } from './personFacts';

type Props={person:Entry;today:string;media:Entry[];fid:string;anchor:DOMRect;hasRelations:boolean;onClose:()=>void;onEnter:()=>void;onLeave:()=>void;onRelations:()=>void;onOpen:()=>void;onPhoto:(p:Entry)=>void};
export default function TreePersonPreview({person,today,media,fid,anchor,hasRelations,onClose,onEnter,onLeave,onRelations,onOpen,onPhoto}:Props){
 const [tab,setTab]=useState('overview'),[position,setPosition]=useState({top:12,left:12});
 const ref=useRef<HTMLDivElement>(null),uid=useId();
 const tabs=[['overview','概览'],['photos','照片'],['bio','生平']];
 const photos=media.filter(m=>m.data.person_ids?.includes(person.id)||m.id===person.data.avatar);
 const facts=personFacts(person,today);
 useLayoutEffect(()=>{
  const box=ref.current!.getBoundingClientRect(),width=window.innerWidth,height=window.innerHeight;
  const left=anchor.right+12+box.width<=width-12?anchor.right+12:anchor.left-box.width-12>=12?anchor.left-box.width-12:Math.max(12,(width-box.width)/2);
  setPosition({left,top:Math.max(12,Math.min(anchor.top,height-box.height-12))});
 },[anchor]);
 useEffect(()=>{const close=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.stopPropagation();onClose();}};document.addEventListener('keydown',close);return()=>document.removeEventListener('keydown',close);},[onClose]);
 return createPortal(<div ref={ref} className="tree-person-preview" role="dialog" aria-label={`${person.data.name}资料预览`} style={position} onPointerEnter={onEnter} onPointerLeave={onLeave}>
  <header><Avatar person={person} fid={fid} size="lg"/><div><small>人物速览</small><h3>{person.data.name}</h3></div><button className="icon-button" aria-label="关闭人物预览" onClick={onClose}><X size={17}/></button></header>
  <div className="person-preview-tabs" role="tablist" aria-label="人物预览内容">{tabs.map(([key,title],i)=><button key={key} id={`${uid}-${key}`} role="tab" aria-selected={tab===key} aria-controls={`${uid}-panel`} tabIndex={tab===key?0:-1} onClick={()=>setTab(key)} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;setTab(tabs[next][0]);document.getElementById(`${uid}-${tabs[next][0]}`)?.focus();}}}>{title}{key==='photos'&&<small>{photos.length}</small>}</button>)}</div>
  <div className="person-preview-content" role="tabpanel" id={`${uid}-panel`} aria-labelledby={`${uid}-${tab}`} tabIndex={0}>
   {tab==='overview'&&<dl>{[
    ['性别',facts.gender],[facts.ageLabel,facts.age],
    ['阳历出生',person.birth_info?.solar||'尚未记录'],['农历出生',person.birth_info?.lunar||'尚未记录'],
    ...(!person.data.living?[['去世日期',person.death_info?.label||'尚未记录']]:[]),
    ['出生地',person.data.birthplace||'尚未记录'],['别名',person.data.aliases||'尚未记录'],
   ].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
   {tab==='photos'&&(photos.length?<div className="person-preview-photos">{photos.slice(0,6).map(m=><button key={m.id} onClick={()=>onPhoto(m)} aria-label={`查看照片：${m.data.title||'家族照片'}`}><img loading="lazy" alt={m.data.title||'家族照片'} src={`/api/families/${fid}/media/${m.id}/thumb?v=${m.version}`}/></button>)}</div>:<div className="person-preview-empty"><Camera size={24}/><p>还没有关联照片</p></div>)}
   {tab==='bio'&&<div className="person-preview-bio"><p>{person.data.bio||'尚未记录生平，可进入完整档案补充。'}</p>{person.data.source&&<small>资料来源：{person.data.source}</small>}</div>}
  </div>
  <footer><button className="preview-relations-action" disabled={!hasRelations} onClick={onRelations}><GitFork size={15}/>亲属关系</button><button onClick={onOpen}>完整档案<ArrowUpRight size={14}/></button></footer>
 </div>,document.body);
}
