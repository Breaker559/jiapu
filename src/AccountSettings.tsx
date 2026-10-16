import { useState } from 'react';
import { json, setCsrf } from './api';
import { Button, Field, Modal } from './components';

export default function AccountSettings({user,onClose,onSaved}:{user:{name:string;email:string};onClose:()=>void;onSaved:(result:any)=>void}){
 const [current,setCurrent]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 return <Modal title="账号设置" subtitle="管理你自己的登录密码。" onClose={()=>{if(!busy)onClose();}}>
  <form onSubmit={async e=>{
   e.preventDefault();if(busy)return;setError('');
   if(password!==confirm){setError('两次输入的新密码不一致');return;}
   setBusy(true);
   try{const result=await json('/account/password','POST',{current_password:current,new_password:password});setCsrf(result.csrf);onSaved(result);}
   catch(e:any){setError(e.message);}finally{setBusy(false);}
  }}>
   <div className="modal-body">
    <div className="account-identity"><strong>{user.name}</strong><span>{user.email}</span></div>
    <Field label="当前密码"><input required type="password" autoComplete="current-password" maxLength={128} value={current} onChange={e=>setCurrent(e.target.value)}/></Field>
    <Field label="新密码" hint="至少 10 个字符；修改后其他设备需要重新登录。"><input required type="password" autoComplete="new-password" minLength={10} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)}/></Field>
    <Field label="确认新密码"><input required type="password" autoComplete="new-password" minLength={10} maxLength={128} value={confirm} onChange={e=>setConfirm(e.target.value)}/></Field>
    {error&&<div className="error-box" role="alert">{error}</div>}
   </div>
   <div className="modal-footer"><Button type="button" variant="secondary" disabled={busy} onClick={onClose}>取消</Button><Button type="submit" loading={busy}>保存新密码</Button></div>
  </form>
 </Modal>;
}
