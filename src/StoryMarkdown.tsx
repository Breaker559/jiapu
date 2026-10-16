import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Entry } from './types';
import { isVideo } from './MediaThumbnail';

export function exportMarkdown(story:Entry){
 const blob=new Blob([story.data.body||''],{type:'text/markdown;charset=utf-8'});
 const url=URL.createObjectURL(blob),link=document.createElement('a');
 link.href=url;link.download=(story.data.title||'家族档案').replace(/[\\/:*?"<>|]/g,'_')+'.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export default function StoryMarkdown({body,format='markdown',media,fid}:{body:string;format?:string;media:Entry[];fid:string}){
 if(format==='plain')return <p className="prose">{body}</p>;
 return <div className="story-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml
  urlTransform={(url,key)=>/^media:[a-f0-9]{32}$/.test(url)?url:key==='src'?'':defaultUrlTransform(url)}
  components={{
   img:({src,alt})=>{
    const item=typeof src==='string'&&/^media:[a-f0-9]{32}$/.test(src)?media.find(item=>item.id===src.slice(6)):undefined;
    if(!item)return <span className="story-media-missing">{alt||'媒体'}：请上传或选择可访问的家族媒体</span>;
    const path=`/api/families/${fid}/media/${item.id}`;
    return <span className="story-media">{isVideo(item)?<video aria-label={alt||item.data.title} controls playsInline preload="metadata" poster={path+'/thumb'} src={path+'/display'}/>:<img alt={alt||item.data.title} loading="lazy" src={path+'/display'}/ >}{alt&&<small>{alt}</small>}</span>;
   },
   a:({href,children})=>href?.startsWith('media:')?<span>{children}（请通过插入媒体显示）</span>:<a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
   table:({children})=><div className="markdown-table-scroll"><table>{children}</table></div>,
  }}>{body}</ReactMarkdown></div>;
}
