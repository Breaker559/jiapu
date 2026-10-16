import { useState } from 'react';
import { Button, Field, SectionTitle } from './components';
import { json } from './api';
import type { Entry, Family } from './types';
import { isParentRelation } from './types';
import { relationPairLabel } from './kinship';
import { DEFAULT_TERMS, EVERYDAY_TERMS, kinshipTerm } from './kinshipTerms';
import type { KinshipKey, KinshipTerms } from './kinshipTerms';

const basic:KinshipKey[]=['father','mother','son','daughter','husband','wife'];
const pairFields:KinshipKey[]=['marriage','past_marriage'];
const fieldNames:Partial<Record<KinshipKey,string>>={marriage:'夫妻关系名称',past_marriage:'过往婚姻关系名称'};
const advanced:KinshipKey[]=['adoptive_father','adoptive_mother','adoptive_son','adoptive_daughter','step_father','step_mother','step_son','step_daughter','former_husband','former_wife','partner','former_partner','coparent','parent','child','spouse','adoptive_parent','adoptive_child','step_parent','step_child','former_spouse','other','legacy_partner'];
const allKeys=Object.keys(DEFAULT_TERMS) as KinshipKey[];

export default function KinshipSettings({family,records,demo,refresh,previewRelations,onApplied}:{family:Family;records:Entry[];demo:boolean;refresh:()=>Promise<void>;previewRelations?:Entry[];onApplied?:()=>void}) {
 const [draft,setDraft]=useState<KinshipTerms>({...family.kinship_terms});
 const [version,setVersion]=useState<number>(family.kinship_version||0);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 const owner=family.role==='owner'&&!demo,canPreview=owner||demo;
 const terms=Object.fromEntries(Object.entries(draft).filter(([,v])=>v?.trim()).map(([key,v])=>[key,v!.trim()])) as KinshipTerms;
 const changed=allKeys.filter(key=>kinshipTerm(key,terms)!==kinshipTerm(key,family.kinship_terms));
 const people=records.filter(r=>r.kind==='person');
 const samples=(previewRelations||records.filter(r=>r.kind==='relation')).slice(0,4);
 const loadSaved=()=>{setDraft({...family.kinship_terms});setVersion(family.kinship_version||0);setError('');setMessage('已载入保存的称谓');};
 const field=(key:KinshipKey)=><Field key={key} label={fieldNames[key]||`${DEFAULT_TERMS[key]}的称谓`} hint={key.startsWith('adoptive_')||key.startsWith('step_')||key.startsWith('former_')?'留空跟随基础称谓':'留空使用默认叫法'}><input maxLength={12} value={draft[key]||''} placeholder={kinshipTerm(key,{...terms,[key]:undefined})} disabled={!canPreview||busy} onChange={e=>{setDraft({...draft,[key]:e.target.value});setError('');setMessage('');}}/></Field>;
 return <section className="settings-panel panel kinship-settings">
  <SectionTitle title="家族统一称谓" subtitle="修改一次，图谱、人物档案和关系查询一起更新。"/>
  <p className="muted kinship-explainer">例如把“子”改成“儿子”，本家族所有对应称谓都会采用新叫法。可一次修改多项，保存后统一生效。</p>
  <div className="button-row kinship-presets"><Button variant="secondary small" disabled={!canPreview||busy} onClick={()=>{setDraft({});setMessage('已填入家谱简写，保存后生效');setError('');}}>恢复默认简写</Button><Button variant="secondary small" disabled={!canPreview||busy} onClick={()=>{setDraft({...EVERYDAY_TERMS});setMessage('已填入日常称呼，保存后生效');setError('');}}>使用日常称呼</Button><Button variant="secondary small" disabled={busy} onClick={loadSaved}>载入已保存设置</Button></div>
  <form onSubmit={async e=>{
   e.preventDefault();if(!owner)return;setBusy(true);setError('');setMessage('');
   try{const result=await json(`/families/${family.id}/kinship`,'PUT',{terms,version});setVersion(result.version);setDraft(result.terms);await refresh();setMessage('称谓已统一更新，本家族所有页面均使用新叫法。');onApplied?.();}
   catch(e:any){setError(e.message);}finally{setBusy(false);}
  }}>
   <h3 className="kinship-group-title">双人关系名称</h3><p className="muted kinship-explainer">两人之间的连线显示“夫妻”等关系名称。</p>
   <div className="kinship-fields">{pairFields.map(field)}</div>
   <h3 className="kinship-group-title">人物称谓</h3><p className="muted kinship-explainer">“夫 / 妻”用于人物档案和关系查询中的个人称谓；孩子分支显示“子 / 女”。</p>
   <div className="kinship-fields">{basic.map(field)}</div>
   <details className="kinship-advanced"><summary>更多称谓：收养、继亲、伴侣与未注明性别</summary><p className="muted">未单独填写的养、继称谓，会随基础称谓生成；在这里填写可以指定独立叫法。</p><div className="kinship-fields">{advanced.map(field)}</div></details>
   <div className="kinship-live-preview"><h3>实时预览</h3>{samples.length?samples.map(r=><div key={r.id}><span>{people.find(p=>p.id===r.data.from_id)?.data.name}{isParentRelation(r.data.type)?' → ':' ↔ '}{people.find(p=>p.id===r.data.to_id)?.data.name}</span><strong>{relationPairLabel(r,people,r.data.from_id,terms)}</strong></div>):<p>{kinshipTerm('father',terms)} → {kinshipTerm('son',terms)}　 ·　{kinshipTerm('mother',terms)} → {kinshipTerm('daughter',terms)}</p>}</div>
   <p className="kinship-change-count">{changed.length?`${changed.length} 项称谓将更新（含跟随变化的称谓）`:'当前叫法与已保存设置一致'}</p>
   {error&&<div className="error-box" role="alert">{error}{error.includes('已更新')&&<Button type="button" variant="secondary small" onClick={async()=>{await refresh();setMessage('最新设置已取得，请点击“载入已保存设置”核对。');}}>获取最新设置</Button>}</div>}
   {message&&<p className="success-text" role="status">{message}</p>}
   {owner?<Button type="submit" loading={busy}>保存并统一应用</Button>:<p className="muted">{demo?'示例可预览叫法，创建自己的家族后即可保存。':'本家族称谓由所有者统一设置。'}</p>}
  </form>
 </section>;
}
