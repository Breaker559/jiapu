import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSync } from 'esbuild';
const compiled=buildSync({entryPoints:['src/treeLayout.ts'],bundle:true,write:false,format:'esm',platform:'node'}).outputFiles[0].text;
const {layoutPeople,relationshipEdges,familyGroups,familyTreeEdges,generationRows,CARD_WIDTH,CARD_HEIGHT}=await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const person=id=>({id,kind:'person',version:1,data:{name:id}});
const relation=(id,from,to,type)=>({id,kind:'relation',version:1,data:{from_id:from,to_id:to,type}});
const make=(ids,rels)=>{
 const people=ids.map(person),positions=layoutPeople(people,rels);
 const nodes=people.map(p=>({id:p.id,position:positions.get(p.id),data:{person:p}}));
 return {nodes,edges:relationshipEdges(nodes,rels),positions};
};

test('co-parenting, remarriage, adoption and step-parenting keep independent edges',()=>{
 const rels=[relation('ab','a','b','coparent'),relation('ac','a','c','married'),relation('ad','a','d','parent'),relation('bd','b','d','parent'),relation('cd','c','d','step'),relation('ce','c','e','adoptive')];
 const {positions,edges,nodes}=make(['a','b','c','d','e'],rels);
 assert.equal(edges.length,rels.length);
 assert.equal(positions.get('a').y,positions.get('b').y);
 assert.equal(positions.get('a').y,positions.get('c').y);
 for(const edge of edges){
  const parent=['ad','bd','cd','ce'].includes(edge.id);
  assert.equal(edge.sourceHandle,parent?'child-out':'peer-right-out');
  assert.equal(edge.targetHandle,parent?'parent-in':'peer-left-in');
  if(parent)assert.ok(positions.get(edge.source).y<positions.get(edge.target).y);
 }
 assert.equal(edges.find(e=>e.id==='ab').label,'共同育儿');
 assert.equal(edges.find(e=>e.id==='ac').data.detour,false);
 assert.equal(edges.find(e=>e.id==='ab').data.detour,false);
 for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
  const a=nodes[i].position,b=nodes[j].position;
  assert.ok(Math.abs(a.x-b.x)>=216||Math.abs(a.y-b.y)>=82,'cards overlap');
 }
});
test('parents of the same child do not imply any lateral relationship',()=>{
 const {edges}=make(['a','b','c'],[relation('ac','a','c','parent'),relation('bc','b','c','adoptive')]);
 assert.equal(edges.length,2);assert.ok(edges.every(e=>e.type==='parent'));
});
test('parent-descendant lateral links never collapse ancestry ranks',()=>{
 const {positions}=make(['a','b','c'],[relation('ab','a','b','parent'),relation('bc','b','c','parent_unknown'),relation('ac','a','c','partner')]);
 assert.ok(positions.get('a').y<positions.get('b').y);
 assert.ok(positions.get('b').y<positions.get('c').y);
});
test('reversed lateral records and dragged cards use the correct side',()=>{
 const rel=relation('ab','b','a','former_partner');
 const {nodes}=make(['a','b'],[rel]);
 assert.equal(relationshipEdges(nodes,[rel])[0].source,'a');
 nodes[0].position.x=nodes[1].position.x+400;
 const edge=relationshipEdges(nodes,[rel])[0];
 assert.equal(edge.source,'b');assert.equal(edge.sourceHandle,'peer-right-out');assert.equal(edge.targetHandle,'peer-left-in');
});
test('parallel historical relations get separate routes and retain uncertainty',()=>{
 const rels=[relation('ab1','a','b','former_spouse'),relation('ab2','b','a','coparent')];
 rels[1].data.certainty='uncertain';
 const {edges}=make(['a','b'],rels);
 assert.equal(edges[0].data.detour,false);assert.equal(edges[1].data.detour,true);
 assert.equal(edges[1].label,'共同育儿 · 待核实');
});
test('empty and disconnected families remain renderable',()=>{
 assert.equal(make([],[]).nodes.length,0);
 const {nodes,edges}=make(['a','b','c'],[]);
 assert.equal(edges.length,0);assert.equal(nodes.length,3);
 assert.ok(nodes.every(n=>Number.isFinite(n.position.x)&&Number.isFinite(n.position.y)));
});

test('siblings with the same parent records share one trunk without losing records',()=>{
 const rels=[relation('ab','a','b','married')];
 for(const child of ['c','d','e'])for(const parent of ['a','b'])rels.push(relation(parent+child,parent,child,'parent'));
 const {nodes}=make(['a','b','c','d','e'],rels);
 const grouped=familyTreeEdges(nodes,rels);
 assert.equal(grouped.length,2);
 const family=grouped.find(e=>e.type==='family');
 assert.deepEqual(family.data.parents,['a','b']);assert.deepEqual(family.data.children,['c','d','e']);
 assert.equal(family.data.relationships.length,6);assert.equal(family.data.pairedRelation,'ab');
 assert.equal(family.label,'');assert.equal(grouped.find(e=>e.id==='ab').label,'配偶');
 assert.deepEqual(family.data.childLabels.map(x=>x.text),['孩子','孩子','孩子']);
 for(const [id,gender] of [['c','male'],['d','female'],['e','male']])nodes.find(n=>n.id===id).data.person.data.gender=gender;
 assert.deepEqual(familyTreeEdges(nodes,rels,true).find(e=>e.type==='family').data.childLabels.map(x=>x.text),['子','女','子']);
 const hidden=familyTreeEdges(nodes,rels,false);
 assert.equal(hidden.find(e=>e.type==='family').data.childLabels.length,0);
 assert.equal(hidden.find(e=>e.id==='ab').label,'');
 assert.equal(new Set(family.data.paths).size,family.data.paths.length,'no duplicate trunk segments');
});
test('children with different parent sets or relation types never share an inferred family',()=>{
 const rels=[relation('ac','a','c','parent'),relation('bc','b','c','parent'),relation('ad','a','d','parent'),relation('ed','e','d','parent'),relation('af','a','f','adoptive'),relation('bf','b','f','parent')];
 const groups=familyGroups(rels);
 assert.equal(groups.length,3);
 assert.deepEqual(groups.map(g=>g.children),[['c'],['d'],['f']]);
 assert.deepEqual(groups.map(g=>g.parents),[['a','b'],['a','e'],['a','b']]);
});
test('a neutral parent bracket cannot invent marriage, and can include more than two parents',()=>{
 const rels=[relation('ad','a','d','parent'),relation('bd','b','d','adoptive'),relation('cd','c','d','step')];
 const {nodes}=make(['a','b','c','d'],rels);
 const edges=familyTreeEdges(nodes,rels);
 assert.equal(edges.length,1);assert.equal(edges[0].type,'family');assert.equal(edges[0].data.pairedRelation,undefined);
 assert.deepEqual(edges[0].data.parents,['a','b','c']);assert.equal(edges[0].data.relationships.length,3);
 for(const parent of nodes.slice(0,3))assert.ok(edges[0].data.paths.some(path=>path.startsWith(`M ${parent.position.x+CARD_WIDTH/2} ${parent.position.y+CARD_HEIGHT} V `)));
});
test('family branches follow every child after dragging, not only the first child',()=>{
 const rels=[relation('ab','a','b','parent'),relation('ac','a','c','parent')];
 const {nodes}=make(['a','b','c'],rels);
 nodes[2].position={x:780,y:480};
 const edge=familyTreeEdges(nodes,rels)[0];
 assert.ok(edge.data.paths.some(path=>path.endsWith('V 480')&&path.startsWith(`M ${780+CARD_WIDTH/2} `)));
});
test('uncertainty stays visible in details and cannot merge with confirmed sibling records',()=>{
 const rels=[relation('ab','a','b','parent'),relation('ac','a','c','parent')];rels[1].data.certainty='uncertain';
 assert.equal(familyGroups(rels).length,2);
 const {nodes}=make(['a','b','c'],rels);
 const edges=familyTreeEdges(nodes,rels);
 assert.equal(edges.find(e=>e.data.children.includes('c')).style.strokeDasharray,'5 4');
 assert.equal(edges.find(e=>e.data.children.includes('c')).data.relationships[0].data.certainty,'uncertain');
});

const kinshipCode=buildSync({entryPoints:['src/kinship.ts'],bundle:true,write:false,format:'esm',platform:'node'}).outputFiles[0].text;
const {relationLabel,relationPairLabel,familyChildTitle}=await import('data:text/javascript;base64,'+Buffer.from(kinshipCode).toString('base64'));
const relatives=[['father','male'],['mother','female'],['son','male'],['daughter','female'],['unknown','unknown']].map(([id,gender])=>({...person(id),data:{name:id,gender}}));
test('titles describe the other person and follow the direction of the relationship',()=>{
 for(const [parent,child,parentTitle,childTitle] of [['father','son','父','子'],['father','daughter','父','女'],['mother','son','母','子'],['mother','daughter','母','女']]){
  const r=relation('r',parent,child,'parent');
  assert.equal(relationLabel(r,relatives,parent),childTitle);
  assert.equal(relationLabel(r,relatives,child),parentTitle);
  assert.equal(relationPairLabel(r,relatives),`${parentTitle} → ${childTitle}`);
  assert.equal(relationPairLabel(r,relatives,child),`${childTitle} ← ${parentTitle}`);
 }
});
test('adoption and step relationships preserve the specific title in both directions',()=>{
 for(const [type,prefix] of [['adoptive','养'],['step','继']])for(const [parent,child,p,c] of [['father','son','父','子'],['mother','daughter','母','女']]){
  const r=relation('r',parent,child,type);
  assert.equal(relationLabel(r,relatives,parent),prefix+c);
  assert.equal(relationLabel(r,relatives,child),prefix+p);
 }
 const links=[relation('a','father','son','parent'),relation('b','mother','son','step')];
 assert.equal(familyChildTitle(links,relatives.find(p=>p.id==='son')),'子');
});
test('titles never infer gender from names, or biological nature from an unspecified relation',()=>{
 const people=[...relatives.map(p=>({...p,data:{...p.data}}))];people.find(p=>p.id==='unknown').data.name='王小妹';
 const r=relation('r','unknown','son','parent_unknown');
 assert.equal(relationLabel(r,people,'son'),'家长');
 assert.equal(relationLabel(r,people,'unknown'),'子');
 assert.equal(relationLabel(relation('u','father','unknown','parent'),people,'father'),'孩子');
 assert.equal(r.data.type,'parent_unknown');
 people.find(p=>p.id==='unknown').data.gender='female';
 assert.equal(relationLabel(r,people,'son'),'母');
});
test('marriage titles do not turn co-parenting or non-married partners into spouses',()=>{
 assert.equal(relationLabel(relation('r','father','mother','married'),relatives,'father'),'妻');
 assert.equal(relationLabel(relation('r','father','mother','married'),relatives,'mother'),'夫');
 assert.equal(relationLabel(relation('r','father','mother','former_spouse'),relatives,'father'),'前妻');
 assert.equal(relationLabel(relation('r','father','mother','partner'),relatives,'father'),'伴侣');
 assert.equal(relationLabel(relation('r','father','mother','coparent'),relatives,'father'),'共同育儿');
 const married=relation('r','father','mother','married');
 assert.equal(relationPairLabel(married,relatives,'mother'),'夫妻');
 assert.equal(relationPairLabel(married,relatives,'father'),'夫妻');
 assert.equal(relationPairLabel(married,[]),'夫妻');
 assert.equal(relationPairLabel(relation('r','father','son','married'),relatives),'夫妻');
 assert.equal(relationPairLabel(relation('r','father','mother','former_spouse'),relatives),'曾为夫妻');
 assert.equal(relationPairLabel(married,relatives,'father',{husband:'丈夫',wife:'妻子'}),'夫妻');
 assert.equal(relationPairLabel(married,relatives,'father',{marriage:'配偶关系'}),'配偶关系');
 assert.equal(relationLabel(married,relatives,'father',{marriage:'配偶关系'}),'妻');
 married.data.certainty='uncertain';
 assert.equal(relationPairLabel(married,relatives),'夫妻 · 待核实');
});
test('a pending verification stays attached to the gendered title',()=>{
 const r=relation('r','father','daughter','parent');r.data.certainty='uncertain';
 assert.equal(relationLabel(r,relatives,'father'),'女 · 待核实');
 assert.equal(relationLabel(r,relatives,'daughter'),'父 · 待核实');
});

test('one custom title applies to every record, with derived names and explicit overrides',()=>{
 const terms={son:'儿子',father:'父亲'};
 const bio=relation('b','father','son','parent'),adopted=relation('a','father','son','adoptive');
 assert.equal(relationLabel(bio,relatives,'father',terms),'儿子');
 assert.equal(relationLabel(bio,relatives,'son',terms),'父亲');
 assert.equal(relationLabel(adopted,relatives,'father',terms),'养儿子');
 assert.equal(relationLabel(adopted,relatives,'father',{...terms,adoptive_son:'养子'}),'养子');
 assert.equal(relationLabel(bio,relatives,'father',{}),'子');
 assert.equal(relationPairLabel(bio,relatives,'father',terms),'父亲 → 儿子');
});
test('family and network views consume the same custom dictionary for all children',()=>{
 const rels=[relation('fs','father','son','parent'),relation('fd','father','daughter','parent')];
 const people=relatives.filter(p=>['father','son','daughter'].includes(p.id));
 const positions=layoutPeople(people,rels),nodes=people.map(p=>({id:p.id,position:positions.get(p.id),data:{person:p}}));
 const terms={son:'儿子',daughter:'女儿'};
 assert.deepEqual(familyTreeEdges(nodes,rels,true,terms)[0].data.childLabels.map(x=>x.text),['儿子','女儿']);
 assert.deepEqual(relationshipEdges(nodes,rels,true,terms).map(e=>e.label),['儿子','女儿']);
 assert.deepEqual(familyTreeEdges(nodes,rels)[0].data.childLabels.map(x=>x.text),['子','女']);
});

test('each household follows its recorded family branch, even after dragging',()=>{
 const rel=relation('former','mother','father','former_spouse');
 const parent=relation('parent','elder','father','parent');
 const people=[...relatives.filter(p=>['father','mother'].includes(p.id)),person('elder')];
 const rels=[rel,parent],positions=layoutPeople(people,rels),nodes=people.map(p=>({id:p.id,position:positions.get(p.id),data:{person:p}}));
 const assertDirection=()=>{const edge=relationshipEdges(nodes,rels).find(e=>e.id==='former');assert.equal(edge.label,'前妻');assert.equal(edge.data.familyOrigin,'father');assert.equal(edge.data.relative,'mother');assert.ok(edge.source==='father'?edge.markerEnd&&!edge.markerStart:edge.markerStart&&!edge.markerEnd);};
 assertDirection();nodes[0].position.x=nodes[1].position.x+400;assertDirection();
 assert.equal(relationshipEdges(nodes,[rel],true,{},rels)[0].label,'前妻');
 assert.equal(relationshipEdges(nodes,rels,true,{former_wife:'前任妻子'}).find(e=>e.id==='former').label,'前任妻子');
 assert.equal(relationshipEdges(nodes,rels,false).find(e=>e.id==='former').label,'');
 // With no ancestry distinguishing the household members, retain the recorded direction.
 assert.equal(relationshipEdges(nodes,[rel])[0].label,'前夫');
});

test('households label children, and a child can head the next generation',()=>{
 const rels=[relation('fs','father','son','parent'),relation('ms','mother','son','parent'),relation('fd','father','daughter','parent'),relation('md','mother','daughter','parent'),relation('sg','son','grandchild','parent')];
 const people=[...relatives.filter(p=>p.id!=='unknown'),{...person('grandchild'),data:{name:'grandchild',gender:'female'}}],positions=layoutPeople(people,rels),nodes=people.map(p=>({id:p.id,position:positions.get(p.id),data:{person:p}}));
 const families=familyTreeEdges(nodes,rels),first=families.find(e=>e.data.children.includes('son')),next=families.find(e=>e.data.children.includes('grandchild'));
 assert.deepEqual(first.data.arrows.map(x=>[x.id,x.direction]),[['son','down'],['daughter','down']]);
 assert.equal(first.data.childLabels.find(x=>x.id==='son').text,'子');
 assert.deepEqual(next.data.parents,['son']);
 assert.equal(next.data.childLabels[0].text,'女');
 assert.equal(first.data.relationships.length,4);assert.equal(next.data.relationships.length,1);
});

test('generation rail labels each layout row once and keeps its rank after dragging',()=>{
 const {nodes}=make(['a','b','c'],[relation('ab','a','b','married'),relation('ac','a','c','parent'),relation('bc','b','c','parent')]);
 nodes.forEach(n=>{n.data.person.data.generation=n.id==='c'?'第二代':'第一代';n.data.rowY=n.position.y;});
 assert.deepEqual(generationRows(nodes).map(r=>r.label),['第一代','第二代']);
 nodes[0].position.y+=100;
 assert.deepEqual(generationRows(nodes).map(r=>r.label),['第一代','第二代']);
 nodes[0].data.person.data.generation='第三代';
 assert.equal(generationRows(nodes)[0].label,'世次待核对');
});
