import dagre from '@dagrejs/dagre';
import type { Edge, Node, MarkerType } from '@xyflow/react';
import type { Entry } from './types';
import type { KinshipTerms } from './kinshipTerms';
import { isParentRelation } from './types';
import { familyChildTitle, relationLabel } from './kinship';

export const CARD_WIDTH=256, CARD_HEIGHT=132, PEER_GAP=96;

// Groups affect placement only. They never create inferred marriage or parent records.
export function layoutPeople(people:Entry[], relations:Entry[]) {
 const groups=new Map(people.map(p=>[p.id,p.id]));
 const parents=relations.filter(r=>isParentRelation(r.data.type));
 const groupOf=(id:string)=>groups.get(id)!;
 const merge=(a:string,b:string)=>{
  a=groupOf(a);b=groupOf(b);if(a===b)return;
  const links=new Map<string,Set<string>>();
  for(const r of parents){const from=groupOf(r.data.from_id),to=groupOf(r.data.to_id);if(!links.has(from))links.set(from,new Set());links.get(from)!.add(to);}
  const reaches=(from:string,to:string)=>{const seen=new Set<string>(),stack=[from];while(stack.length){const id=stack.pop()!;if(id===to)return true;if(seen.has(id))continue;seen.add(id);stack.push(...(links.get(id)||[]));}return false;};
  // Keep ancestry acyclic even for unusual inter-generation relationships.
  if(reaches(a,b)||reaches(b,a))return;
  for(const [id,group] of groups)if(group===b)groups.set(id,a);
 };
 for(const r of relations)if(!isParentRelation(r.data.type)&&r.data.type!=='other')merge(r.data.from_id,r.data.to_id);
 const childParents=new Map<string,string[]>();
 for(const r of parents){const list=childParents.get(r.data.to_id)||[];list.push(r.data.from_id);childParents.set(r.data.to_id,list);}
 for(const list of childParents.values())for(let i=1;i<list.length;i++)merge(list[0],list[i]);
 const members=new Map<string,Entry[]>();
 for(const person of people){const group=groupOf(person.id);if(!members.has(group))members.set(group,[]);members.get(group)!.push(person);}
 const graph=new dagre.graphlib.Graph();
 graph.setGraph({rankdir:'TB',nodesep:52,ranksep:150,marginx:40,marginy:40});graph.setDefaultEdgeLabel(()=>({}));
 const headroom=new Map<string,number>();
 for(const [id,list] of members){
  orderFamilyMembers(list,relations);
  const lateral=relations.filter(r=>!isParentRelation(r.data.type)&&groupOf(r.data.from_id)===id&&groupOf(r.data.to_id)===id);
  const tracks=lateral.filter(r=>Math.abs(list.findIndex(p=>p.id===r.data.from_id)-list.findIndex(p=>p.id===r.data.to_id))>1).length;
  const room=tracks?32+tracks*24:0;headroom.set(id,room);
  graph.setNode(id,{width:list.length*CARD_WIDTH+(list.length-1)*PEER_GAP,height:CARD_HEIGHT+room});
 }
 for(const r of parents)graph.setEdge(groupOf(r.data.from_id),groupOf(r.data.to_id));
 dagre.layout(graph);
 const positions=new Map<string,{x:number;y:number}>();
 for(const [id,list] of members){const box=graph.node(id);list.forEach((p,i)=>positions.set(p.id,{x:box.x-box.width/2+i*(CARD_WIDTH+PEER_GAP),y:box.y-box.height/2+headroom.get(id)!}));}
 // Order descendant blocks under the actual parent combination, not input insertion order.
 const families=familyGroups(parents);
 const rows=new Map<number,string[]>();
 for(const id of members.keys()){const y=graph.node(id).y;rows.set(y,[...(rows.get(y)||[]),id]);}
 for(const [,row] of [...rows].sort(([a],[b])=>a-b)){
  const alignedY=Math.max(...row.flatMap(id=>members.get(id)!.map(p=>positions.get(p.id)!.y)));
  for(const id of row)for(const p of members.get(id)!)positions.get(p.id)!.y=alignedY;
  const original=[...row].sort((a,b)=>graph.node(a).x-graph.node(b).x);
  const desired=(id:string)=>{
   const incoming=families.filter(f=>f.children.some(child=>groupOf(child)===id));
   return incoming.length?incoming.reduce((sum,f)=>{const xs=f.parents.map(p=>positions.get(p)!.x+CARD_WIDTH/2);return sum+(Math.min(...xs)+Math.max(...xs))/2;},0)/incoming.length:graph.node(id).x;
  };
  const ordered=[...original].sort((a,b)=>desired(a)-desired(b)||original.indexOf(a)-original.indexOf(b));
  let left=Math.min(...original.map(id=>graph.node(id).x-graph.node(id).width/2));
  for(const id of ordered){members.get(id)!.forEach((p,i)=>positions.set(p.id,{x:left+i*(CARD_WIDTH+PEER_GAP),y:positions.get(p.id)!.y}));left+=graph.node(id).width+52;}
 }
 return positions;
}

export function relationshipEdges(nodes:Node[], relations:Entry[],showLabels=true,terms:KinshipTerms={},context:Entry[]=relations):Edge[] {
 const byId=new Map(nodes.map(n=>[n.id,n]));
 const people=nodes.map(n=>n.data.person as Entry);
 const pairs=new Map<string,number>();
 const rowTracks=new Map<number,number>();
 const parentSources=[...new Set(relations.filter(r=>isParentRelation(r.data.type)).map(r=>r.data.from_id))];
 return relations.flatMap(r=>{
  let source=byId.get(r.data.from_id),target=byId.get(r.data.to_id);
  if(!source||!target)return [];
  const parent=isParentRelation(r.data.type);
  if(!parent&&source.position.x>target.position.x)[source,target]=[target,source];
  const pair=[source.id,target.id].join(':');const parallel=pairs.get(pair)||0;pairs.set(pair,parallel+1);
  const sx=source.position.x+CARD_WIDTH,tx=target.position.x;
  const origin=parent?r.data.from_id:familyOrigin(r,context);
  const label=showLabels?relationLabel(r,people,origin,terms):'';
  const marker={type:'arrowclosed' as MarkerType,width:18,height:18,color:'#168477'};
  const row=Math.min(source.position.y,target.position.y);
  const obstacle=!parent&&nodes.some(n=>n.id!==source.id&&n.id!==target.id&&n.position.x<tx&&n.position.x+CARD_WIDTH>sx&&Math.abs(n.position.y-row)<CARD_HEIGHT);
  const detour=!parent&&(obstacle||parallel>0||tx-sx<45||label.length*10>tx-sx-8||Math.abs(source.position.y-target.position.y)>1);
  const lane=detour?(rowTracks.get(row)||0):0;if(detour)rowTracks.set(row,lane+1);
  return [{id:r.id,source:source.id,target:target.id,
   sourceHandle:parent?'child-out':'peer-right-out',targetHandle:parent?'parent-in':'peer-left-in',
   type:parent?'parent':'lateral',
   label,
   markerStart:!parent&&target.id===origin?marker:undefined,markerEnd:source.id===origin?marker:undefined,
   data:{detour,lane,relationship:r,relationships:[r],parallel,familyOrigin:origin,relative:source.id===origin?target.id:source.id,midFraction:0.3+(parentSources.indexOf(r.data.from_id)%5)*0.085},
   style:{stroke:parent?'#6f9996':r.data.type==='coparent'?'#7893b1':'#b78668',strokeWidth:1.6,strokeDasharray:r.data.type==='parent'||r.data.type==='married'?undefined:'5 4'},
   labelStyle:{fill:'var(--accent)',fontSize:12,fontWeight:500},labelBgStyle:{fill:'var(--surface)'},
   ariaLabel:`${people.find(p=>p.id===origin)?.data.name} → ${relationLabel(r,people,origin,terms)} → ${people.find(p=>p.id===(origin===r.data.from_id?r.data.to_id:r.data.from_id))?.data.name}`,
  }];
 });
}


// Each household is narrated from its recorded family member, without a global protagonist.
// When just one spouse has parents in this tree, follow that person's branch;
// otherwise keep the stored direction. Gender never chooses the family member.
function familyOrigin(relation:Entry,relations:Entry[]){
 const hasParents=(id:string)=>relations.some(r=>isParentRelation(r.data.type)&&r.data.to_id===id);
 const a=relation.data.from_id,b=relation.data.to_id;
 return !hasParents(a)&&hasParents(b)?b:a;
}

// Put a person with several family relationships between their counterparts where possible.
function orderFamilyMembers(list:Entry[],relations:Entry[]) {
 const ids=new Set(list.map(p=>p.id));
 const ties=relations.filter(r=>!isParentRelation(r.data.type)&&ids.has(r.data.from_id)&&ids.has(r.data.to_id));
 const score=()=>ties.reduce((sum,r)=>sum+Math.pow(list.findIndex(p=>p.id===r.data.from_id)-list.findIndex(p=>p.id===r.data.to_id),2),0);
 for(let pass=0;pass<list.length;pass++){
  let changed=false;
  for(let i=0;i<list.length-1;i++){
   const before=score();[list[i],list[i+1]]=[list[i+1],list[i]];
   if(score()<before)changed=true;else [list[i],list[i+1]]=[list[i+1],list[i]];
  }
  if(!changed)break;
 }
}

export type FamilyGroup={id:string;parents:string[];children:string[];relations:Entry[]};
export function familyGroups(relations:Entry[]):FamilyGroup[] {
 const childRelations=new Map<string,Entry[]>();
 for(const r of relations){if(!isParentRelation(r.data.type))continue;const list=childRelations.get(r.data.to_id)||[];list.push(r);childRelations.set(r.data.to_id,list);}
 const groups=new Map<string,FamilyGroup>();
 for(const [child,links] of childRelations){
  // Both parent identity and relationship nature must match before children share a branch.
  const key=JSON.stringify(links.map(r=>[r.data.from_id,r.data.type,r.data.certainty||'confirmed']).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))));
  let group=groups.get(key);
  if(!group){group={id:'family-'+links[0].id,parents:[...new Set(links.map(r=>r.data.from_id))],children:[],relations:[]};groups.set(key,group);}
  group.children.push(child);group.relations.push(...links);
 }
 return [...groups.values()];
}

export function familyTreeEdges(nodes:Node[],relations:Entry[],showLabels=true,terms:KinshipTerms={},context:Entry[]=relations):Edge[] {
 const byId=new Map(nodes.map(n=>[n.id,n]));
 const people=nodes.map(n=>n.data.person as Entry);
 const visible=relations.filter(r=>byId.has(r.data.from_id)&&byId.has(r.data.to_id));
 const lateral=relationshipEdges(nodes,visible,showLabels,terms,context).filter(e=>e.type==='lateral');
 const tracks=new Map<number,{min:number;max:number;lane:number}[]>();
 const familyEdges:Edge[]=familyGroups(visible).map(group=>{
  const parents=group.parents.map(id=>byId.get(id)!).sort((a,b)=>a.position.x-b.position.x);
  const children=group.children.map(id=>byId.get(id)!).sort((a,b)=>a.position.x-b.position.x);
  const bottom=Math.max(...parents.map(p=>p.position.y+CARD_HEIGHT));
  const top=Math.min(...children.map(p=>p.position.y));
  const parentXs=parents.map(p=>p.position.x+CARD_WIDTH/2),childXs=children.map(p=>p.position.x+CARD_WIDTH/2);
  const anchorX=(parentXs[0]+parentXs[parentXs.length-1])/2;
  const span={min:Math.min(...parentXs,...childXs),max:Math.max(...parentXs,...childXs)};
  const taken=tracks.get(bottom)||[];
  let lane=0;while(taken.some(t=>t.lane===lane&&t.min<=span.max&&t.max>=span.min))lane++;
  taken.push({...span,lane});tracks.set(bottom,taken);
  const sameRow=parents.every(p=>Math.abs(p.position.y-parents[0].position.y)<1);
  // A side-to-side union line exists only when the corresponding relationship is recorded.
  const pair=parents.length===2&&sameRow?lateral.find(e=>[parents[0].id,parents[1].id].includes(e.source)&&[parents[0].id,parents[1].id].includes(e.target)&&!e.data?.detour):undefined;
  const joinY=bottom+24+lane*12;
  const barY=Math.min(top-28,Math.max(joinY+24,bottom+(top-bottom)*0.62+lane*18));
  const paths:string[]=[];
  if(pair){paths.push(`M ${anchorX} ${parents[0].position.y+CARD_HEIGHT/2} V ${barY}`);}
  else if(parents.length===1){paths.push(`M ${anchorX} ${bottom} V ${barY}`);}
  else {
   for(const p of parents)paths.push(`M ${p.position.x+CARD_WIDTH/2} ${p.position.y+CARD_HEIGHT} V ${joinY}`);
   paths.push(`M ${parentXs[0]} ${joinY} H ${parentXs[parentXs.length-1]}`);
   paths.push(`M ${anchorX} ${joinY} V ${barY}`);
  }
  const minChild=Math.min(anchorX,...childXs),maxChild=Math.max(anchorX,...childXs);
  if(maxChild>minChild)paths.push(`M ${minChild} ${barY} H ${maxChild}`);
  children.forEach((p,i)=>paths.push(`M ${childXs[i]} ${barY} V ${p.position.y}`));
  const childLabels=showLabels?children.map(p=>{
   const links=group.relations.filter(r=>r.data.to_id===p.id);
   return {id:p.id,x:p.position.x+CARD_WIDTH/2+14,y:p.position.y-Math.min(34,(p.position.y-barY)/2),text:familyChildTitle(links,p.data.person as Entry,terms),description:links.map(r=>`${people.find(person=>person.id===r.data.from_id)?.data.name}：${relationLabel(r,people,undefined,terms)}`).join('；')};
  }):[];
  const arrows=children.map(p=>({id:p.id,x:p.position.x+CARD_WIDTH/2,y:p.position.y,direction:'down'}));
  const uncertain=group.relations.some(r=>r.data.certainty==='uncertain');
  return {id:group.id,source:parents[0].id,target:children[0].id,sourceHandle:'child-out',targetHandle:'parent-in',type:'family',
   data:{relationships:group.relations,parents:group.parents,children:group.children,paths,childLabels,arrows,anchorX,barY,pairedRelation:pair?.id,junction:pair?{x:anchorX,y:parents[0].position.y+CARD_HEIGHT/2}:undefined},
   label:'',
   style:{stroke:'var(--tree-line)',strokeWidth:1.6,strokeDasharray:uncertain?'5 4':undefined},
   labelStyle:{fill:'var(--muted)',fontSize:11},labelBgStyle:{fill:'var(--surface)'},
   ariaLabel:`查看 ${parents.map(p=>(p.data.person as Entry).data.name).join('、')} 与 ${children.map(p=>(p.data.person as Entry).data.name).join('、')} 的亲子关系`,
  };
 });
 return [...lateral,...familyEdges];
}

export function generationRows(nodes:Node[]) {
 const levels=new Map<number,Node[]>();
 for(const n of nodes){const y=Math.round(Number(n.data.rowY??n.position.y));levels.set(y,[...(levels.get(y)||[]),n]);}
 return [...levels].sort(([a],[b])=>a-b).map(([y,list],i)=>{
  const labels=[...new Set(list.map(n=>String((n.data.person as Entry).data.generation||'').trim()).filter(Boolean))];
  return {y:y+CARD_HEIGHT/2,label:labels.length===1?labels[0]:labels.length?'世次待核对':`第 ${i+1} 层`,description:labels.length>1?labels.join('、'):labels.length?'已记录世次':'按图谱层级排列，世次未注明'};
 });
}
