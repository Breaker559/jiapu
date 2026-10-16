import type { Entry } from './types';
import { isParentRelation } from './types';
import { kinshipTerm } from './kinshipTerms';
import type { KinshipKey, KinshipTerms } from './kinshipTerms';

const otherKeys:Record<string,KinshipKey>={partner:'partner',former_partner:'former_partner',coparent:'coparent',other:'other',spouse:'legacy_partner'};
const status=(r:Entry)=>r.data.certainty==='uncertain'?' · 待核实':'';

// Use recorded gender only. Relationship nature is stored separately from the title.
export function parentChildTitle(type:string,person:Entry|undefined,side:'parent'|'child',terms:KinshipTerms={}) {
 const gender=person?.data.gender;
 const base=side==='parent'?(gender==='male'?'father':gender==='female'?'mother':'parent'):(gender==='male'?'son':gender==='female'?'daughter':'child');
 const key=((type==='adoptive'?'adoptive_':type==='step'?'step_':'')+base) as KinshipKey;
 return kinshipTerm(key,terms);
}
function spouseTitle(type:string,person:Entry|undefined,terms:KinshipTerms) {
 const base=person?.data.gender==='male'?'husband':person?.data.gender==='female'?'wife':'spouse';
 return kinshipTerm(((type==='former_spouse'?'former_':'')+base) as KinshipKey,terms);
}

/** The title of the other person, as seen from perspective (never a biological category). */
export function relationLabel(r:Entry,people:readonly Entry[],perspective?:string,terms:KinshipTerms={}):string {
 if(!perspective || ![r.data.from_id,r.data.to_id].includes(perspective))return relationPairLabel(r,people,r.data.from_id,terms);
 const forward=perspective===r.data.from_id;
 const other=people.find(p=>p.id===(forward?r.data.to_id:r.data.from_id));
 const type=r.data.type;
 const title=isParentRelation(type)?parentChildTitle(type,other,forward?'child':'parent',terms)
  :type==='married'||type==='former_spouse'?spouseTitle(type,other,terms):kinshipTerm(otherKeys[type]||'other',terms);
 return title+status(r);
}

/** Parent/child roles in displayed order, or a name for the pair's recorded relationship. */
export function relationPairLabel(r:Entry,people:readonly Entry[],firstId=r.data.from_id,terms:KinshipTerms={}):string {
 const first=people.find(p=>p.id===firstId);
 const second=people.find(p=>p.id===(firstId===r.data.from_id?r.data.to_id:r.data.from_id));
 const type=r.data.type;
 if(isParentRelation(type)){
  const forward=firstId===r.data.from_id;
  return parentChildTitle(type,first,forward?'parent':'child',terms)+(forward?' → ':' ← ')+parentChildTitle(type,second,forward?'child':'parent',terms)+status(r);
 }
 if(type==='married'||type==='former_spouse'){
  return kinshipTerm(type==='married'?'marriage':'past_marriage',terms)+status(r);
 }
 return kinshipTerm(otherKeys[type]||'other',terms)+status(r);
}

export function familyChildTitle(links:Entry[],child:Entry,terms:KinshipTerms={}) {
 // When different adults have different roles, the shared branch gets a neutral title.
 // The individual adoptive/step roles remain available in each original relation.
 const types=new Set(links.map(r=>r.data.type));
 const type=types.size===1?links[0]?.data.type:'parent_unknown';
 return parentChildTitle(type,child,'child',terms)+(links.some(r=>r.data.certainty==='uncertain')?' · 待核实':'');
}
