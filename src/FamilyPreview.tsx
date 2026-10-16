import { GitFork } from 'lucide-react';
import { Avatar } from './components';
import type { Entry } from './types';
import type { KinshipTerms } from './kinshipTerms';
import { isParentRelation } from './types';
import { familyChildTitle } from './kinship';

export default function FamilyPreview({people,relations,fid,open,terms}:{people:Entry[];relations:Entry[];fid:string;open:(p:Entry)=>void;terms?:KinshipTerms}) {
 const first=relations.find(r=>isParentRelation(r.data.type));
 const root=people.find(p=>p.id===first?.data.from_id)||people[0];
 const childLinks=root?relations.filter(r=>isParentRelation(r.data.type)&&r.data.from_id===root.id):[];
 const children=people.filter(p=>childLinks.some(r=>r.data.to_id===p.id)).slice(0,3);
 const shown=children.length?children:people.filter(p=>p.id!==root?.id).slice(0,3);
 const centers=shown.length===1?[260]:shown.length===2?[165,355]:[90,260,430];
 const card=(p:Entry,x:number,y:number)=><foreignObject key={p.id} x={x-75} y={y} width={150} height={68}><button className="preview-node" onClick={()=>open(p)}><Avatar person={p} fid={fid} size="sm"/><div><strong>{p.data.name}</strong><small>{p.data.generation||'家族成员'}</small></div></button></foreignObject>;
 return <div className="hero-tree family-preview" aria-label="家族关系预览"><div className="graph-dot-pattern"/>{root?<>
  <svg viewBox="0 0 520 290" role="group" aria-label="家族亲缘预览">
   {children.map((p,i)=>{
    const links=childLinks.filter(r=>r.data.to_id===p.id);
    return <g key={p.id} data-parent={root.id} data-child={p.id}><path className="preview-connector" strokeDasharray={links.every(r=>r.data.type==='parent'&&r.data.certainty!=='uncertain')?undefined:'5 4'} d={`M260 94 V135 Q260 145 ${centers[i]>260?270:centers[i]<260?250:260} 145 H${centers[i]} V186`}/><text x={centers[i]+12} y={169} textAnchor="start">{familyChildTitle(links,p,terms)}</text></g>;
   })}
   {card(root,260,26)}{shown.map((p,i)=>card(p,centers[i],186))}
  </svg><span className="hero-tree-label"><GitFork size={13}/>{children.length?`${root.data.name} · 下一代`:'家族成员一览'}</span>
 </>:<div className="hero-empty"><GitFork size={65}/><p>第一条连线，从你开始</p></div>}</div>;
}
