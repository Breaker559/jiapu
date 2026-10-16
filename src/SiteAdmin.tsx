import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, FolderHeart, RefreshCw, Search, ShieldCheck, UserPlus, Users } from 'lucide-react';
import { json } from './api';
import { Button, Empty, Modal } from './components';
import { roleNames } from './types';

type Registration = {enabled:boolean; environment_allowed:boolean; version:number};
type Overview = {users:number; admins:number; families:number; recent_registrations:number; registration:Registration};
type Account = {
 id:string; name:string; email:string; admin:boolean; registered_at:string|null; last_login_at:string|null;
 family_count:number; families:{id:string; name:string; role:string}[];
};
type Directory = {items:Account[]; total:number; page:number; pages:number; page_size:number};
const dateFormat = new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const dateLabel = (value:string|null) => value ? dateFormat.format(new Date(value)) : '未记录';

export default function SiteAdmin({onRegistrationChange}:{onRegistrationChange:(enabled:boolean)=>void}) {
 const [overview,setOverview]=useState<Overview|null>(null),[directory,setDirectory]=useState<Directory|null>(null);
 const [overviewError,setOverviewError]=useState(''),[listError,setListError]=useState(''),[settingError,setSettingError]=useState('');
 const [overviewLoading,setOverviewLoading]=useState(true),[listLoading,setListLoading]=useState(true),[saving,setSaving]=useState(false);
 const [draft,setDraft]=useState(''),[query,setQuery]=useState(''),[role,setRole]=useState('all'),[page,setPage]=useState(1),[pageSize,setPageSize]=useState(20),[revision,setRevision]=useState(0);
 const [selected,setSelected]=useState<Account|null>(null),[message,setMessage]=useState('');
 useEffect(()=>{
  let cancelled=false;setOverviewLoading(true);setOverviewError('');
  json('/admin/overview').then(data=>{if(!cancelled)setOverview(data);}).catch(error=>{if(!cancelled){setOverview(null);setOverviewError(error.message);}}).finally(()=>{if(!cancelled)setOverviewLoading(false);});
  return()=>{cancelled=true;};
 },[revision]);
 useEffect(()=>{
  let cancelled=false;setListLoading(true);setListError('');
  const params=new URLSearchParams({q:query,role,page:String(page),page_size:String(pageSize)});
  json('/admin/users?'+params).then(data=>{if(!cancelled)setDirectory(data);}).catch(error=>{if(!cancelled){setDirectory(null);setListError(error.message);}}).finally(()=>{if(!cancelled)setListLoading(false);});
  return()=>{cancelled=true;};
 },[query,role,page,pageSize,revision]);
 const refresh=()=>{setRevision(n=>n+1);setMessage('');setSettingError('');};
 const toggleRegistration=async()=>{
  if(!overview||saving||overviewLoading)return;
  setSaving(true);setSettingError('');setMessage('');
  try{
   const config:Registration=await json('/admin/registration','PUT',{enabled:!overview.registration.enabled,version:overview.registration.version});
   setOverview(value=>value?{...value,registration:config}:value);onRegistrationChange(config.enabled);
   setMessage(config.enabled?'已开放公开注册':'已关闭公开注册，已有账号仍可登录，家族邀请仍可使用');
  }catch(error:any){setSettingError(error.message);}finally{setSaving(false);}
 };
 const metrics = [
  {label:'注册账号',value:overview?.users,icon:Users},
  {label:'站点管理员',value:overview?.admins,icon:ShieldCheck},
  {label:'家族空间',value:overview?.families,icon:FolderHeart},
  {label:'近 7 天注册',value:overview?.recent_registrations,icon:UserPlus},
 ];
 return <div className="site-admin">
  <div className="page-heading"><div><span className="eyebrow">SITE ADMINISTRATION</span><h1>站点管理</h1><p>查看全站账号、所属家族与注册情况。</p></div><Button variant="secondary" disabled={saving||overviewLoading||listLoading} onClick={refresh}><RefreshCw size={16}/>刷新数据</Button></div>
  {overviewError&&<div className="error-box" role="alert">{overviewError}<button onClick={refresh}>重试</button></div>}
  <div className="admin-metrics" aria-label="站点概况" aria-busy={overviewLoading}>{metrics.map(metric=><div className="admin-metric" key={metric.label}><metric.icon size={20}/><span>{metric.label}</span><strong>{overviewLoading?'…':metric.value??'—'}</strong></div>)}</div>
  {overview&&<section className="admin-registration" aria-labelledby="registration-heading">
   <div><h2 id="registration-heading">公开注册 <span className={'admin-badge '+(overview.registration.enabled?'is-admin':'')}>{overview.registration.enabled?'已开放':'已关闭'}</span></h2><p>{overview.registration.environment_allowed?'开放后，访客可注册账号并创建自己的家族空间。':'部署配置已关闭注册。如需开放，请先将服务器 QINPU_ALLOW_REGISTRATION 设置为 1 并重启。'}</p></div>
   <Button variant="secondary" loading={saving} disabled={saving||overviewLoading||!overview.registration.environment_allowed} onClick={()=>void toggleRegistration()}>{overview.registration.enabled?'关闭公开注册':'开放公开注册'}</Button>
  </section>}
  {settingError&&<div className="error-box" role="alert">{settingError}<button disabled={saving} onClick={refresh}>刷新设置</button></div>}
  {message&&<p className="success-text" role="status">{message}</p>}
  <section className="admin-directory" aria-labelledby="accounts-heading">
   <div className="admin-directory-heading"><h2 id="accounts-heading">账号目录</h2><span>仅站点管理员可见</span></div>
   <form className="admin-filters" role="search" onSubmit={e=>{e.preventDefault();setQuery(draft.trim());setPage(1);}}>
    <label className="admin-search"><Search size={17}/><input aria-label="搜索账号姓名或邮箱" placeholder="搜索姓名或邮箱" value={draft} maxLength={100} onChange={e=>setDraft(e.target.value)}/></label>
    <Button type="submit" variant="secondary">搜索</Button>
    <select aria-label="筛选站点角色" value={role} onChange={e=>{setRole(e.target.value);setPage(1);}}><option value="all">全部角色</option><option value="admin">站点管理员</option><option value="user">普通账号</option></select>
    {query&&<button type="button" className="text-link" onClick={()=>{setDraft('');setQuery('');setPage(1);}}>清除搜索</button>}
   </form>
   <div aria-live="polite" aria-busy={listLoading}>
    {listLoading?<p className="admin-state">正在加载账号…</p>:listError?<div className="error-box" role="alert">{listError}<button onClick={refresh}>重试</button></div>:directory?.items.length?<>
     <p className="admin-scroll-hint">左右滑动表格，查看时间与账号详情</p>
     <div className="admin-table-scroll" tabIndex={0} role="region" aria-label="注册账号列表，可横向滚动">
      <table className="admin-table"><thead><tr><th scope="col">账号</th><th scope="col">站点角色</th><th scope="col">所属家族</th><th scope="col">注册时间</th><th scope="col">最近登录</th><th scope="col">详情</th></tr></thead>
       <tbody>{directory.items.map(account=><tr key={account.id}>
        <td><strong className="admin-account-name">{account.name}</strong><span className="admin-email">{account.email}</span></td>
        <td><span className={'admin-badge '+(account.admin?'is-admin':'')}>{account.admin?'站点管理员':'普通账号'}</span></td>
        <td>{account.family_count} 个家族</td><td>{dateLabel(account.registered_at)}</td><td>{dateLabel(account.last_login_at)}</td>
        <td><button className="text-link" aria-label={'查看账号 '+account.email} onClick={()=>setSelected(account)}>查看<ChevronRight size={14}/></button></td>
       </tr>)}</tbody>
      </table>
     </div>
    </>:<Empty icon={Users} title="没有找到账号" description="试试其他姓名、邮箱或角色。"/>}
   </div>
   <div className="admin-pagination"><span>{!listLoading&&directory&&!listError?`共 ${directory.total} 个账号 · 第 ${directory.page} / ${directory.pages} 页`:'账号目录'}</span><div className="button-row">
    <select aria-label="每页账号数" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1);}}><option value={20}>每页 20 个</option><option value={50}>每页 50 个</option><option value={100}>每页 100 个</option></select>
    <Button variant="secondary small" disabled={listLoading||!!listError||!directory||directory.page<=1} onClick={()=>setPage((directory?.page||1)-1)}><ChevronLeft size={15}/>上一页</Button>
    <Button variant="secondary small" disabled={listLoading||!!listError||!directory||directory.page>=directory.pages} onClick={()=>setPage((directory?.page||1)+1)}>下一页<ChevronRight size={15}/></Button>
   </div></div>
  </section>
  <p className="admin-note">时间按北京时间显示。历史账号未记录的注册或登录时间显示为“未记录”，最近登录将在下次登录后更新。</p>
  {selected&&<Modal title="账号详情" subtitle="账号资料与家族成员身份" onClose={()=>setSelected(null)}>
   <div className="modal-body admin-account-detail">
    <h3>{selected.name}</h3><p className="admin-detail-email">{selected.email}</p>
    <dl><div><dt>站点角色</dt><dd>{selected.admin?'站点管理员':'普通账号'}</dd></div><div><dt>注册时间</dt><dd>{dateLabel(selected.registered_at)}</dd></div><div><dt>最近登录</dt><dd>{dateLabel(selected.last_login_at)}</dd></div></dl>
    <h3>所属家族 · {selected.family_count}</h3>
    {selected.families.length?<ul className="admin-family-list">{selected.families.map(family=><li key={family.id}><FolderHeart size={18}/><strong>{family.name}</strong><span>{roleNames[family.role]||family.role}</span></li>)}</ul>:<p className="muted">该账号尚未加入家族。</p>}
   </div><div className="modal-footer"><Button variant="secondary" onClick={()=>setSelected(null)}>关闭详情</Button></div>
  </Modal>}
 </div>;
}
