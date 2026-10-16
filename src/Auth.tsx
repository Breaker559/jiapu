import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, Eye, EyeOff, GitFork, Image, LockKeyhole, Moon, ShieldCheck } from 'lucide-react';
import { json, setCsrf } from './api';
import { Button, Field, Logo } from './components';

type Mode = 'login' | 'setup' | 'register' | 'join' | 'recover';
export default function Auth({initialized,registrationEnabled,onLogin,onDemo}:{initialized:boolean;registrationEnabled:boolean;onLogin:(result:any)=>void;onDemo:()=>void}){
 const [mode,setMode]=useState<Mode>(initialized?'login':'setup');
 const [v,setV]=useState({email:'',password:'',confirm:'',name:'',family_name:'',demo:true,code:'',recovery:''});
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[show,setShow]=useState(false),[newRecovery,setNewRecovery]=useState('');
 const set=(key:keyof typeof v,value:string|boolean)=>setV(old=>({...old,[key]:value}));
 const switchMode=(next:Mode)=>{setMode(next);setError('');setNewRecovery('');setShow(false);setV(old=>({...old,password:'',confirm:'',recovery:''}));};
 const titles={login:'很高兴再次见到你',setup:'创建你的家族空间',register:'注册你的家谱账号',join:'加入家人的邀请',recover:'恢复账号'};
 const descriptions={login:'登录后，继续整理你们的家族记忆。',setup:'先创建管理员账号，开始记录第一段故事。',register:'创建账号和独立家族空间，邀请家人一起记录。',join:'输入邀请码。已有账号请填写原来的邮箱和密码。',recover:'使用创建账号时保存的恢复码重设密码。'};
 const labels={login:'登录家谱',setup:'创建并进入家谱',register:'注册并创建家族',join:'加入家族',recover:'重设密码'};
 const submit=async(e:FormEvent)=>{
  e.preventDefault();if(busy)return;setError('');
  if(mode==='register'&&v.password!==v.confirm){setError('两次输入的密码不一致');return;}
  setBusy(true);
  try{
   const credentials={email:v.email,password:v.password};
   const data=mode==='login'?credentials:mode==='recover'?{...credentials,recovery:v.recovery}:mode==='register'?{...credentials,name:v.name,family_name:v.family_name}:mode==='join'?{...credentials,name:v.name.trim()||'家族成员',code:v.code}:{...credentials,name:v.name,demo:v.demo};
   const result=await json('/'+mode,'POST',data);
   if(mode==='recover'){setNewRecovery(result.recovery);setV(old=>({...old,password:'',confirm:'',recovery:''}));}
   else{setCsrf(result.csrf);onLogin(result);}
  }catch(e:any){setError(e.message);}finally{setBusy(false);}
 };
 return <main className="auth-page">
  <section className="auth-story"><Logo/><div className="auth-intro"><span className="eyebrow">家人的故事，值得好好收藏</span><h1>从一个名字，<br/>连接一家人的记忆。</h1><p>记下走过的路，留下相聚的时光。<br/>和家人一起，让故事继续。</p><div className="auth-tree"><div className="auth-person first"><span>祖辈</span><i/></div><div className="auth-connector"/><div className="auth-generation"><div className="auth-person"><span>父母</span><i/></div><div className="auth-person"><span>家人</span><i/></div></div><div className="auth-connector short"/><div className="auth-generation"><div className="auth-person green"><span>我们</span><i/></div><div className="auth-person"><span>下一代</span><i/></div></div></div><div className="auth-features"><span><GitFork size={18}/>清晰世系</span><span><Image size={18}/>家族相册</span><span><Moon size={18}/>阳历 · 农历</span></div></div><p className="auth-bottom"><ShieldCheck size={15}/>本地保存与服务器部署，数据由你掌握。</p></section>
  <section className="auth-panel"><div className="auth-card">
   <div className="auth-mobile-logo"><Logo/></div>
   <span className="eyebrow">欢迎来到家谱</span>
   {initialized&&registrationEnabled&&<div className="auth-mode-switch" role="group" aria-label="登录或注册"><button type="button" aria-pressed={mode==='login'} disabled={busy} onClick={()=>switchMode('login')}>登录</button><button type="button" aria-pressed={mode==='register'} disabled={busy} onClick={()=>switchMode('register')}>注册账号</button></div>}
   <h2>{titles[mode]}</h2><p>{descriptions[mode]}</p>
   {newRecovery?<div className="recovery-box"><strong>密码已更新。请保存新的恢复码：</strong><code>{newRecovery}</code><p>旧恢复码与已登录会话已失效。</p><Button type="button" onClick={()=>switchMode('login')}>返回登录</Button></div>:<form onSubmit={submit}>
    {(mode==='setup'||mode==='register'||mode==='join')&&<Field label="你的称呼"><input required value={v.name} onChange={e=>set('name',e.target.value)} placeholder="家人如何称呼你" autoComplete="name" maxLength={50}/></Field>}
    <Field label="登录邮箱" hint={mode==='register'?'用于登录，不发送验证邮件；请核对邮箱并保存注册后的恢复码。':undefined}><input required type="email" maxLength={200} value={v.email} onChange={e=>set('email',e.target.value)} placeholder="name@example.com" autoComplete="username"/></Field>
    {mode==='register'&&<Field label="家族名称"><input required maxLength={60} value={v.family_name} onChange={e=>set('family_name',e.target.value)} placeholder="例如：张氏家族"/></Field>}
    {mode==='join'&&<Field label="家族邀请码"><input required value={v.code} onChange={e=>set('code',e.target.value)} placeholder="粘贴家族所有者给你的邀请码"/></Field>}
    {mode==='recover'&&<Field label="账号恢复码"><input required value={v.recovery} onChange={e=>set('recovery',e.target.value)} autoComplete="off"/></Field>}
    <Field label={mode==='recover'?'设置新密码':'密码'} hint={mode==='setup'?'至少 10 个字符；邮箱用作登录名，本地使用无需邮件服务。':undefined}><div className="password-input"><input required type={show?'text':'password'} value={v.password} onChange={e=>set('password',e.target.value)} minLength={10} maxLength={128} placeholder="至少 10 个字符" autoComplete={mode==='login'||mode==='join'?'current-password':'new-password'}/><button type="button" className="icon-button" aria-label={show?'隐藏密码':'显示密码'} onClick={()=>setShow(!show)}>{show?<EyeOff size={17}/>:<Eye size={17}/>}</button></div></Field>
    {mode==='register'&&<Field label="确认密码"><input required type={show?'text':'password'} minLength={10} maxLength={128} autoComplete="new-password" value={v.confirm} onChange={e=>set('confirm',e.target.value)} placeholder="再输入一次密码"/></Field>}
    {mode==='setup'&&<label className="check-line"><input type="checkbox" checked={v.demo} onChange={e=>set('demo',e.target.checked)}/>创建一份可编辑的示例家族（虚构资料）</label>}
    {error&&<div className="error-box" role="alert">{error}</div>}
    <Button type="submit" loading={busy} variant="full">{labels[mode]}<ArrowRight size={17}/></Button>
   </form>}
   <div className="auth-links">
    {mode!=='join'&&<button disabled={busy} onClick={()=>switchMode('join')}>我有家族邀请码</button>}
    {mode!=='login'&&initialized&&<button disabled={busy} onClick={()=>switchMode('login')}>已有账号，去登录</button>}
    {mode==='login'&&<button disabled={busy} onClick={()=>switchMode('recover')}>忘记密码</button>}
    {mode!=='setup'&&!initialized&&<button disabled={busy} onClick={()=>switchMode('setup')}>创建管理员</button>}
   </div>
   <div className="auth-divider"><span>先了解一下</span></div><Button variant="secondary full" disabled={busy} onClick={onDemo}>浏览示例家族<ArrowRight size={16}/></Button>
   <p className="auth-privacy"><LockKeyhole size={13}/>各家族资料独立，受邀成员按权限访问。</p>
  </div></section>
 </main>;
}
