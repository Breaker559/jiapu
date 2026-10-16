import { useEffect, useId, useRef, useState } from 'react';
import { ArrowRight, ChevronDown, KeyRound, LoaderCircle, LogOut } from 'lucide-react';

type Props = {
 user?: {name:string; email:string; admin:boolean};
 demo:boolean;
 onPassword:()=>void;
 onLogout:()=>Promise<void>|void;
};

export default function AccountMenu({user,demo,onPassword,onLogout}:Props) {
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(false);
 const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),menu=useRef<HTMLDivElement>(null);
 const menuId=useId();
 const close=(restoreFocus=false)=>{setOpen(false);if(restoreFocus)trigger.current?.focus();};
 useEffect(()=>{
  if(!open)return;
  menu.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
  const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
  const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();setOpen(false);trigger.current?.focus();}};
  document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);
  return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};
 },[open]);
 return <div className="account-menu" ref={root} onBlur={event=>{if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget as Node))setOpen(false);}}>
  <button ref={trigger} className={'account-trigger '+(open?'is-open':'')} aria-label="账号菜单" title="账号菜单" aria-haspopup="menu" aria-expanded={open} aria-controls={open?menuId:undefined}
   onClick={()=>setOpen(value=>!value)} onKeyDown={event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();setOpen(true);}}}>
   <span className="top-avatar">{demo?'访':user?.name.slice(-1)}</span><ChevronDown size={12}/>
  </button>
  {open&&<div className="account-popover">
   <div className="account-menu-identity"><strong>{demo?'体验访客':user?.name}</strong><span>{demo?'正在浏览虚构示例':user?.email}</span><small>{demo?'创建账号，保存自己的家族记忆':user?.admin?'站点管理员':'个人账号'}</small></div>
   <div id={menuId} ref={menu} role="menu" aria-label="账号操作" onKeyDown={event=>{
    const items=Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')||[]);
    const index=items.indexOf(document.activeElement as HTMLButtonElement);
    if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)&&items.length){
     event.preventDefault();
     const next=event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;
     items[next].focus();
    }
   }}>
    {!demo&&<button role="menuitem" disabled={busy} onClick={()=>{close(true);onPassword();}}><KeyRound size={17}/><span>修改密码</span></button>}
    <button role="menuitem" disabled={busy} className={demo?'':'account-logout'} onClick={async()=>{if(busy)return;setBusy(true);try{await onLogout();close();}finally{setBusy(false);}}}>
     {busy?<LoaderCircle size={17} className="spin"/>:demo?<ArrowRight size={17}/>:<LogOut size={17}/>}<span>{demo?'创建我的家谱':busy?'正在退出…':'退出登录'}</span>
    </button>
   </div>
  </div>}
 </div>;
}
