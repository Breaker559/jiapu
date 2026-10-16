import type { Entry } from './types';

export function storyExcerpt(story:Entry){
 let body=String(story.data.body||'');
 if(story.data.format==='markdown'){
  body=body.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi,'')
   .replace(/<[^>]*>/g,'').replace(/!\[([^\]]*)\]\([^)]*\)/g,'$1')
   .replace(/\[([^\]]*)\]\([^)]*\)/g,'$1').replace(/^\s*\|?\s*:?-{3,}.*$/gm,'')
   .replace(/^[\t ]{0,3}(?:#{1,6}|>|[-+*]|\d+\.)\s+/gm,'')
   .replace(/[`*_~|]/g,'');
 }
 return body.replace(/\s+/g,' ').trim().slice(0,200)||'这段故事，等待家人补充。';
}
