import type { Node } from '@xyflow/react';
import type { Entry } from './types';
import { CARD_HEIGHT, CARD_WIDTH, generationRows } from './treeLayout';
import { birthPresentation, personFacts, todayInShanghai } from './personFacts';
import { offlineTreePage } from './treeExportPage';

export type TreeExportFormat='png'|'svg'|'html';
export type TreeExportOptions={root:HTMLElement;nodes:Node[];familyName:string;scope:string;relationCount:number;format:TreeExportFormat;today:string};
const xml=(value:string)=>value.replace(/[<>&"']/g,char=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[char]!));
const download=(blob:Blob,filename:string)=>{const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);};

export async function exportTree(options:TreeExportOptions){
 const {root,nodes,familyName,scope,relationCount,format,today}=options;
 const viewport=root.querySelector<HTMLElement>('.react-flow__viewport');
 if(!viewport||!nodes.length)throw Error('图谱尚未就绪，请稍后重试');
 await document.fonts.ready;
 try{await Promise.all([...viewport.querySelectorAll('img')].map(image=>image.decode()));}
 catch{throw Error('有头像尚未加载完成，请稍后重试');}
 const matrix=new DOMMatrix(getComputedStyle(viewport).transform),origin=viewport.getBoundingClientRect();
 let left=Math.min(...nodes.map(node=>node.position.x)),top=Math.min(...nodes.map(node=>node.position.y));
 let right=Math.max(...nodes.map(node=>node.position.x+CARD_WIDTH)),bottom=Math.max(...nodes.map(node=>node.position.y+CARD_HEIGHT));
 // Include detours and long relationship labels, including edges outside the visible canvas.
 for(const element of viewport.querySelectorAll('.react-flow__edge-path,.react-flow__edge-textwrapper,.family-kinship-label,.family-direction-arrow')){
  const rect=element.getBoundingClientRect();
  if(!rect.width&&!rect.height)continue;
  left=Math.min(left,(rect.left-origin.left)/matrix.a);top=Math.min(top,(rect.top-origin.top)/matrix.a);
  right=Math.max(right,(rect.right-origin.left)/matrix.a);bottom=Math.max(bottom,(rect.bottom-origin.top)/matrix.a);
 }
 const padding=44,rail=132,header=108,footer=42;
 const graphWidth=Math.max(760,Math.ceil(right-left+padding*2)),graphHeight=Math.ceil(bottom-top+padding*2);
 const width=graphWidth+rail,height=graphHeight+header+footer;
 const computed=getComputedStyle(root),background=computed.getPropertyValue('--bg').trim()||'#f5f8fa',foreground=computed.getPropertyValue('--text').trim()||'#173d48',muted=computed.getPropertyValue('--muted').trim()||'#718995';
 const {toSvg}=await import('html-to-image');
 const dataUrl=await toSvg(viewport,{
  width:graphWidth,height:graphHeight,skipFonts:true,includeQueryParams:true,fetchRequestInit:{credentials:'same-origin'},
  style:{width:graphWidth+'px',height:graphHeight+'px',transform:`translate(${padding-left}px,${padding-top}px) scale(1)`,transformOrigin:'0 0',background:'transparent'},
  filter:node=>!(node instanceof Element)||!node.matches('.react-flow__handle,.tree-person-peek,.react-flow__nodesselection,.react-flow__selection'),
 });
 const parsed=new DOMParser().parseFromString(decodeURIComponent(dataUrl.slice(dataUrl.indexOf(',')+1)),'image/svg+xml');
 if(parsed.querySelector('parsererror'))throw Error('图谱生成失败，请刷新页面后重试');
 const svg=parsed.documentElement;
 svg.setAttribute('width',String(width));svg.setAttribute('height',String(height));svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
 const foreign=svg.querySelector('foreignObject')!;
 foreign.setAttribute('x',String(rail));foreign.setAttribute('y',String(header));foreign.setAttribute('width',String(graphWidth));foreign.setAttribute('height',String(graphHeight));
 // html-to-image clones SVG subtrees without copying descendant stylesheet rules.
 // Embed their computed paint/text properties so arrows and underlays keep the active theme.
 const edgeOriginals=viewport.querySelectorAll('.react-flow__edges svg *');
 const edgeCopies=foreign.querySelectorAll<SVGElement>('.react-flow__edges svg *');
 const properties=['fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-dasharray','fill-opacity','stroke-opacity','opacity','font-family','font-size','font-weight','text-anchor','dominant-baseline','paint-order'];
 edgeCopies.forEach((element,index)=>{const original=edgeOriginals[index];if(!original)return;const style=getComputedStyle(original);for(const property of properties)element.style.setProperty(property,style.getPropertyValue(property));});
 for(const element of svg.querySelectorAll('[style]')){
  element.setAttribute('style',element.getAttribute('style')!.replace(/url\(["']?https?:\/\/[^#)]*#([^"')]+)["']?\)/g,'url(#$1)'));
 }
 const heading=`<rect width="100%" height="100%" fill="${xml(background)}"/><g font-family="Microsoft YaHei, PingFang SC, sans-serif"><text x="32" y="42" font-size="25" font-weight="600" fill="${xml(foreground)}">${xml(familyName)} · 世系图谱</text><text x="32" y="72" font-size="13" fill="${xml(muted)}">${xml(scope)} · ${nodes.length} 位家人 · ${relationCount} 条关系 · ${todayInShanghai()}</text></g>`;
 const railMarkup=generationRows(nodes).map(row=>{const lines=row.label.match(/.{1,9}/gu)||[''];return `<text x="20" y="${header+padding-top+row.y-(lines.length-1)*7}" fill="${xml(muted)}" font-size="12" font-family="Microsoft YaHei, sans-serif"><title>${xml(row.description)}</title>${lines.map((line,index)=>`<tspan x="20" dy="${index?14:0}">${xml(line)}</tspan>`).join('')}</text>`;}).join('');
 const tail=`<g>${railMarkup}<text x="32" y="${height-16}" font-size="11" fill="${xml(muted)}" font-family="Microsoft YaHei, sans-serif">由家谱 Jiapu 整理 · 图谱由 React Flow 绘制 · 导出文件不随在线资料更新</text></g>`;
 const serializer=new XMLSerializer();
 const content=serializer.serializeToString(foreign);
 const svgText=`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${heading}${content}${tail}</svg>`;
 const filename=(familyName+'-世系图谱-'+todayInShanghai()).replace(/[\\/:*?"<>|]/g,'_');
 if(format==='svg')download(new Blob([svgText],{type:'image/svg+xml;charset=utf-8'}),filename+'.svg');
 else if(format==='html'){
  const people=nodes.map(node=>{
   const person=node.data.person as Entry,birthday=birthPresentation(person),facts=personFacts(person,today);
   return {name:String(person.data.name),gender:facts.gender,birth:birthday.primary,alternate:birthday.secondary,age:facts.ageLabel+'：'+facts.age,
    generation:String(person.data.generation||''),branch:String(person.data.branch||''),bio:String(person.data.bio||''),source:String(person.data.source||''),
    x:rail+padding-left+node.position.x+CARD_WIDTH/2,y:header+padding-top+node.position.y+CARD_HEIGHT/2};
  });
  download(new Blob([offlineTreePage({title:familyName+' · 世系图谱',scope,svg:svgText,width,height,people,date:todayInShanghai()})],{type:'text/html;charset=utf-8'}),filename+'.html');
 }else{
  // Bound the decoded image and the canvas: very large trees stay exportable without an unbounded bitmap.
  const ratio=Math.min(2,8192/width,8192/height,Math.sqrt(24000000/(width*height)));
  const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.floor(width*ratio));canvas.height=Math.max(1,Math.floor(height*ratio));
  const rasterSource=svgText.replace(`width="${width}" height="${height}"`,`width="${canvas.width}" height="${canvas.height}"`);
  const image=new Image();image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(rasterSource);await image.decode();
  const context=canvas.getContext('2d');if(!context)throw Error('浏览器无法创建图片，请尝试 SVG 或 HTML 导出');
  context.drawImage(image,0,0,canvas.width,canvas.height);
  const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/png'));
  if(!blob)throw Error('图片尺寸过大，请筛选房支后重试，或导出 SVG');
  download(blob,filename+'.png');
 }
}
