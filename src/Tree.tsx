import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { ReactFlow, Background, Controls, MiniMap, Handle, Position, BackgroundVariant, BaseEdge, EdgeText, SelectionMode, getSmoothStepPath } from '@xyflow/react';
import type { EdgeProps, ReactFlowInstance, Viewport } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import TreePersonPreview from './TreePersonPreview';
import TreeArrangementToolbar from './TreeArrangementToolbar';
import useTreeArrangement from './useTreeArrangement';
import { personFacts, todayInShanghai } from './personFacts';
import { Focus, GitFork, Info, Pencil, SlidersHorizontal, Users } from 'lucide-react';
import type { Entry } from './types';
import type { KinshipTerms } from './kinshipTerms';
import { Avatar, Empty } from './components';
import { CARD_HEIGHT, familyTreeEdges, generationRows, layoutPeople, relationshipEdges } from './treeLayout';

function PersonNode({data}:any){
 const p=data.person as Entry;
 const facts=personFacts(p,data.today);
 return <div className={'tree-person '+(data.selected?'focused':'')} onPointerEnter={e=>{if(e.pointerType!=='touch'&&!data.arranging)data.preview(p,e.currentTarget.getBoundingClientRect());}} onPointerLeave={data.leavePreview}>
  <Handle id="parent-in" type="target" position={Position.Top}/><Handle id="peer-left-in" type="target" position={Position.Left}/>
  <button className="tree-person-main" onClick={e=>{if(!data.arranging&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey)data.open(p);}} onDoubleClick={()=>{if(data.arranging)data.open(p);}}><Avatar person={p} fid={data.fid}/><span className="tree-person-info"><span className="tree-person-title"><strong>{p.data.name}</strong><span className="tree-gender">{facts.gender}</span></span><span className="tree-person-dates"><span>{facts.living?'生日':'生'}：{facts.birth}</span>{facts.death&&<span>卒：{facts.death}</span>}</span><span className="tree-person-age" title={facts.ageTitle}>{facts.ageLabel}：{facts.age}</span></span></button>
  <button className="tree-person-peek nodrag" aria-label={`预览${p.data.name}`} onClick={e=>{e.stopPropagation();data.preview(p,e.currentTarget.closest('.tree-person')!.getBoundingClientRect(),true);}}><Info size={15}/></button>
  <Handle id="child-out" type="source" position={Position.Bottom}/><Handle id="peer-right-out" type="source" position={Position.Right}/>
 </div>;
}
function LateralEdge(props:EdgeProps){
 const {sourceX:sx,sourceY:sy,targetX:tx,targetY:ty,data}=props;
 const laneY=Math.min(sy,ty)-CARD_HEIGHT/2-34-Number(data?.lane||0)*24;
 const path=data?.detour?`M ${sx} ${sy} H ${sx+18} V ${laneY} H ${tx-18} V ${ty} H ${tx}`:`M ${sx} ${sy} L ${tx} ${ty}`;
 return <BaseEdge id={props.id} path={path} style={props.style} markerStart={props.markerStart} markerEnd={props.markerEnd} label={props.label} labelStyle={props.labelStyle} labelBgStyle={props.labelBgStyle} labelX={(sx+tx)/2} labelY={(data?.detour?laneY:(sy+ty)/2)-17} interactionWidth={24}/>;
}
function ParentEdge(props:EdgeProps){
 const {sourceX,sourceY,targetX,targetY,data}=props;
 const fraction=Math.min(0.8,Number(data?.midFraction||0.4)+Number(data?.parallel||0)*0.13);
 const centerY=sourceY+(targetY-sourceY)*fraction;
 const [path,x,y]=getSmoothStepPath({sourceX,sourceY,targetX,targetY,sourcePosition:Position.Bottom,targetPosition:Position.Top,centerY,borderRadius:8});
 const vertical=Math.abs(sourceX-targetX)<1;
 // Keep each title with its own bend; parents sharing a child must not share a label position.
 return <><BaseEdge id={props.id} path={path} style={props.style} markerStart={props.markerStart} markerEnd={props.markerEnd} label={vertical?undefined:props.label} labelX={x} labelY={y-17} labelStyle={props.labelStyle} labelBgStyle={props.labelBgStyle} interactionWidth={24}/>{vertical&&props.label&&<SideLabel x={x+14} y={y} text={props.label}/>}</>;
}
function SideLabel({x,y,text}:{x:number;y:number;text:EdgeProps['label']}){
 // Anchor the left edge, so even a long custom title never straddles its branch.
 return <EdgeText x={x} y={y} transform={`translate(${x} ${y-7})`} label={text} labelStyle={{fill:'var(--accent)',fontSize:12,fontWeight:600}} labelBgStyle={{fill:'var(--bg)'}} labelBgPadding={[4,3]}/>;
}
function FamilyEdge(props:EdgeProps){
 const data=props.data!;
 const path=(data.paths as string[]).join(' ');
 const labels=data.childLabels as any[];
 return <><path className="tree-edge-underlay" d={path}/><BaseEdge id={props.id} path={path} style={props.style} interactionWidth={20}/>{data.junction&&<circle className="family-junction" cx={Number((data.junction as any).x)} cy={Number((data.junction as any).y)} r={2.6}/>} {labels.map(label=><g key={label.id} className="family-kinship-label" data-person={label.id}><title>{label.description}</title><SideLabel x={label.x} y={label.y} text={label.text}/></g>)}{((data.arrows as any[])||[]).map(arrow=><path key={arrow.id} className="family-direction-arrow" data-person={arrow.id} data-direction={arrow.direction} d={arrow.direction==='down'?`M ${arrow.x-4.5} ${arrow.y-9} L ${arrow.x} ${arrow.y-1} L ${arrow.x+4.5} ${arrow.y-9} Z`:`M ${arrow.x-4.5} ${arrow.y+9} L ${arrow.x} ${arrow.y+1} L ${arrow.x+4.5} ${arrow.y+9} Z`}/>)}</>;
}
const nodeTypes={person:PersonNode};
const edgeTypes={lateral:LateralEdge,parent:ParentEdge,family:FamilyEdge};

export default function Tree({people,relations,media=[],fid,open,openPhoto,openRelations,openKinship,terms,focus=''}:{people:Entry[];relations:Entry[];media?:Entry[];fid:string;open:(p:Entry)=>void;openPhoto?:(p:Entry)=>void;openRelations:(r:Entry[])=>void;openKinship?:()=>void;terms?:KinshipTerms;focus?:string}){
 const [branch,setBranch]=useState(''),[depth,setDepth]=useState('all');
 const [displayOpen,setDisplayOpen]=useState(false);
 const displayRoot=useRef<HTMLDivElement>(null),displayTrigger=useRef<HTMLButtonElement>(null);
 const displayId=useId();
 const [selecting,setSelecting]=useState(false),[snap,setSnap]=useState(true);
 const interacting=useRef(false);
 const [view,setView]=useState('family'),[showLabels,setShowLabels]=useState(true);
 const [today,setToday]=useState(()=>todayInShanghai());
 const [viewport,setViewport]=useState<Viewport>({x:0,y:0,zoom:1});
 const flow=useRef<ReactFlowInstance|null>(null);
 const [preview,setPreview]=useState<{person:Entry;anchor:DOMRect}|null>(null);
 const showTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),hideTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
 const closePreview=useCallback(()=>{clearTimeout(showTimer.current);clearTimeout(hideTimer.current);setPreview(null);},[]);
 const keepPreview=useCallback(()=>{clearTimeout(hideTimer.current);clearTimeout(showTimer.current);},[]);
 const leavePreview=useCallback(()=>{clearTimeout(showTimer.current);clearTimeout(hideTimer.current);hideTimer.current=setTimeout(()=>setPreview(null),220);},[]);
 const showPreview=useCallback((person:Entry,anchor:DOMRect,immediate=false)=>{if(interacting.current)return;clearTimeout(showTimer.current);clearTimeout(hideTimer.current);if(immediate)setPreview({person,anchor});else showTimer.current=setTimeout(()=>setPreview({person,anchor}),300);},[]);
 useEffect(()=>()=>{clearTimeout(showTimer.current);clearTimeout(hideTimer.current);},[]);
 useEffect(()=>{const update=()=>setToday(todayInShanghai());const timer=setInterval(update,60000);document.addEventListener('visibilitychange',update);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',update);};},[]);
 useEffect(()=>{if(focus)setBranch('');},[focus]);
 useEffect(()=>{window.addEventListener('resize',closePreview);window.addEventListener('scroll',closePreview);return()=>{window.removeEventListener('resize',closePreview);window.removeEventListener('scroll',closePreview);};},[closePreview]);
 useEffect(()=>{
  if(!displayOpen)return;
  const outside=(event:PointerEvent)=>{if(!displayRoot.current?.contains(event.target as Node))setDisplayOpen(false);};
  document.addEventListener('pointerdown',outside);
  return()=>document.removeEventListener('pointerdown',outside);
 },[displayOpen]);
 const openPerson=(p:Entry)=>{closePreview();open(p);};
 const model=useMemo(()=>{
  let shown=people.filter(p=>!branch||p.data.branch===branch||p.id===focus);
  if(focus&&depth!=='all'){
   const ids=new Set([focus]);let frontier=[focus];
   for(let i=0;i<Number(depth);i++){const next:string[]=[];for(const r of relations){const a=r.data.from_id,b=r.data.to_id;if(frontier.includes(a)&&!ids.has(b)){ids.add(b);next.push(b);}if(frontier.includes(b)&&!ids.has(a)){ids.add(a);next.push(a);}}frontier=next;}
   shown=shown.filter(p=>ids.has(p.id));
  }
  const ids=new Set(shown.map(p=>p.id));
  const rel=relations.filter(r=>ids.has(r.data.from_id)&&ids.has(r.data.to_id));
  return {shown,rel,positions:layoutPeople(shown,rel)};
 },[people,relations,branch,depth,focus]);
 const initialNodes=useMemo(()=>model.shown.map(p=>({id:p.id,type:'person',position:model.positions.get(p.id)!,data:{person:p,fid,today,open:openPerson,preview:showPreview,leavePreview,arranging:selecting,selected:p.id===focus,rowY:model.positions.get(p.id)!.y}})),[model,fid,focus,today,selecting,open]);
 const scope=JSON.stringify([fid,branch,depth,depth==='all'?'':focus]);
 const arrangement=useTreeArrangement(initialNodes,scope,snap,viewport.zoom);
 const {nodes,guides}=arrangement;
 const selectionCount=nodes.filter(n=>n.selected).length;
 const rows=useMemo(()=>generationRows(nodes),[nodes]);
 const edges=useMemo(()=>(view==='family'?familyTreeEdges:relationshipEdges)(nodes,model.rel,showLabels,terms,relations),[nodes,model.rel,view,showLabels,terms,relations]);
 const showAll=()=>void flow.current?.fitView({padding:.16,duration:250});
 const beginDrag=()=>{interacting.current=true;closePreview();arrangement.beginDrag();};
 const endDrag=()=>{arrangement.endDrag();interacting.current=false;};
 const autoLayout=()=>{closePreview();arrangement.autoLayout();requestAnimationFrame(()=>requestAnimationFrame(showAll));};
 if(!people.length)return <Empty icon={GitFork} title="从一位家人开始" description="添加人物后，记录父、母、子、女等亲属关系。"/>;
 return <div className={'tree-wrap'+(selecting?' is-selecting':'')} tabIndex={-1} onKeyDownCapture={e=>{
  if((e.target as HTMLElement).closest('input,textarea,select,[contenteditable="true"],[role="dialog"],.tree-display-settings'))return;
  const command=e.ctrlKey||e.metaKey;
  if(command&&['a','z','y'].includes(e.key.toLowerCase())){e.preventDefault();e.stopPropagation();closePreview();if(e.key.toLowerCase()==='a')arrangement.selectAll();else if(e.key.toLowerCase()==='y'||e.shiftKey)arrangement.redo();else arrangement.undo();}
  else if(e.key==='Escape'){arrangement.clearSelection();closePreview();}
 }} onPointerDownCapture={e=>{if((e.target as HTMLElement).closest('.tree-canvas'))e.currentTarget.focus({preventScroll:true});}}>
  <div className="tree-toolbar">
   <div className="tree-view-switch" role="group" aria-label="图谱视图"><button aria-pressed={view==='family'} onClick={()=>setView('family')}>家庭树</button><button aria-pressed={view==='network'} onClick={()=>setView('network')}>关系明细</button></div>
   <span className="tree-toolbar-count"><Users size={14}/>{nodes.length} 位家人 · {model.rel.length} 条关系</span>
   <div className="tree-display-settings" ref={displayRoot} onBlur={event=>{if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget as Node))setDisplayOpen(false);}} onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();setDisplayOpen(false);displayTrigger.current?.focus();}}}>
    <button ref={displayTrigger} className="tree-display-trigger" aria-expanded={displayOpen} aria-controls={displayId} onClick={()=>{closePreview();setDisplayOpen(value=>!value);}}><SlidersHorizontal size={14}/>显示设置{(branch||!showLabels||depth!=='all')&&<i aria-label="已调整显示设置"/>}</button>
    {displayOpen&&<div className="tree-display-panel" id={displayId} role="region" aria-label="图谱显示设置">
     <label className="tree-label-toggle"><input type="checkbox" checked={showLabels} onChange={e=>setShowLabels(e.target.checked)}/>显示称谓</label>
     {openKinship&&<button className="tree-edit-titles" onClick={()=>{closePreview();setDisplayOpen(false);openKinship();}}><Pencil size={13}/>修改称谓</button>}
     <label className="tree-display-field"><span>房支</span><select aria-label="图谱房支" value={branch} onChange={e=>setBranch(e.target.value)}><option value="">全部房支</option>{[...new Set(people.map(p=>p.data.branch).filter(Boolean))].map(x=><option key={x}>{x}</option>)}</select></label>
     {focus&&<label className="tree-display-field"><span>关系层数</span><select aria-label="显示关系层数" value={depth} onChange={e=>setDepth(e.target.value)}><option value="all">全部层级</option><option value="1">一层亲属</option><option value="2">两层亲属</option><option value="3">三层亲属</option></select></label>}
    </div>}
   </div>
   <button className="tree-fit-view" onClick={showAll}><Focus size={14}/>查看全图</button>
  </div>
  <TreeArrangementToolbar selecting={selecting} setSelecting={value=>{closePreview();setSelecting(value);}} snap={snap} setSnap={setSnap} count={selectionCount} history={arrangement.history} saved={arrangement.saved} align={arrangement.align} autoLayout={autoLayout} undo={arrangement.undo} redo={arrangement.redo} selectAll={()=>{closePreview();arrangement.selectAll();}} clearSelection={arrangement.clearSelection}/>
  <div className="tree-stage"><aside className="tree-generation-rail" aria-label="世代层级"><span className="generation-heading">世代</span>{rows.map(row=><div className="generation-row" key={row.y} title={row.description} style={{top:row.y*viewport.zoom+viewport.y}}><span>{row.label}</span><i/></div>)}</aside>
  <div className="tree-canvas"><ReactFlow key={scope} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
   onInit={instance=>{flow.current=instance;}} onViewportChange={setViewport} onMoveStart={()=>{interacting.current=true;closePreview();}} onMoveEnd={()=>{interacting.current=false;}} onNodeDragStart={beginDrag} onNodeDragStop={endDrag} onSelectionDragStart={beginDrag} onSelectionDragStop={endDrag} onPaneClick={closePreview}
   onSelectionStart={()=>{interacting.current=true;closePreview();}} onSelectionEnd={()=>{interacting.current=false;}}
   onNodesChange={arrangement.onNodesChange}
   onEdgeClick={(_,edge)=>{closePreview();openRelations(edge.data!.relationships as Entry[]);}}
   selectionOnDrag={selecting} selectionMode={SelectionMode.Partial} selectionKeyCode="Shift" multiSelectionKeyCode={['Control','Meta']} panOnDrag={selecting?false:[0,1,2]} panActivationKeyCode="Space" defaultEdgeOptions={{selectable:false}} nodeDragThreshold={4}
   fitView fitViewOptions={{padding:0.12,minZoom:0.6,maxZoom:1}} minZoom={0.12} maxZoom={1.5} nodesDraggable nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} attributionPosition="bottom-right">
   <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#d3dfe0"/><Controls showInteractive={false}/><MiniMap nodeColor={n=>n.id===focus?'#168477':'#c4ded8'} maskColor="rgba(242,247,246,.7)"/>
  </ReactFlow><svg className="tree-snap-guides" aria-hidden="true">{guides.map(guide=><line key={guide.axis} data-axis={guide.axis} x1={guide.axis==='x'?guide.value*viewport.zoom+viewport.x:guide.from*viewport.zoom+viewport.x} x2={guide.axis==='x'?guide.value*viewport.zoom+viewport.x:guide.to*viewport.zoom+viewport.x} y1={guide.axis==='y'?guide.value*viewport.zoom+viewport.y:guide.from*viewport.zoom+viewport.y} y2={guide.axis==='y'?guide.value*viewport.zoom+viewport.y:guide.to*viewport.zoom+viewport.y}/>)}</svg></div></div>
  <div className="tree-legend"><span className="tree-legend-count">{nodes.length} 人 · {model.rel.length} 条关系</span><span><i/>父母 → 子女</span><span><i className="spouse"/>夫 / 妻及其他家庭关系</span><span className="legend-tip">悬停人物查看资料 · 点击称谓编辑关系</span></div>

  {preview&&<TreePersonPreview key={preview.person.id} today={today} person={preview.person} media={media} fid={fid} anchor={preview.anchor} onClose={closePreview} onEnter={keepPreview} onLeave={leavePreview} onRelations={()=>{closePreview();openRelations(relations.filter(r=>[r.data.from_id,r.data.to_id].includes(preview.person.id)));}} hasRelations={relations.some(r=>[r.data.from_id,r.data.to_id].includes(preview.person.id))} onOpen={()=>openPerson(preview.person)} onPhoto={p=>{closePreview();openPhoto?.(p);}}/>}
 </div>;
}
