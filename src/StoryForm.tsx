import { useRef, useState } from 'react';
import { Bold, Eye, FileUp, Heading2, ImagePlus, List, Pencil } from 'lucide-react';
import { Button, DateField, Field, Modal } from './components';
import { upload } from './api';
import StoryMarkdown from './StoryMarkdown';
import { isVideo } from './MediaThumbnail';
import type { Entry } from './types';

export default function StoryForm({record,people,media,fid,onClose,onSave,onMedia}:{record?:Entry;people:Entry[];media:Entry[];fid:string;onClose:()=>void;onSave:(value:any)=>Promise<void>;onMedia:()=>Promise<void>}){
 const [value,setValue]=useState<any>({title:'',category:'家族故事',date:{calendar:'solar'},source:'',privacy:'family',person_ids:[],...record?.data,body:(record?.data.body||'').replace(/\r\n?/g,'\n'),format:record?.data.format||(record?'plain':'markdown')});
 const [error,setError]=useState(''),[busy,setBusy]=useState(false),[uploading,setUploading]=useState(false),[progress,setProgress]=useState(0),[preview,setPreview]=useState(false),[selected,setSelected]=useState('');
 const [uploaded,setUploaded]=useState<Entry[]>([]);
 const editor=useRef<HTMLTextAreaElement>(null),mdInput=useRef<HTMLInputElement>(null),mediaInput=useRef<HTMLInputElement>(null),selection=useRef({start:0,end:0});
 const allMedia=[...media,...uploaded.filter(item=>!media.some(existing=>existing.id===item.id))];
 const available=allMedia.filter(item=>value.privacy==='editors'||item.data.privacy!=='editors');
 const set=(key:string,data:any)=>setValue((old:any)=>({...old,[key]:data}));
 const insert=(before:string,after='',placeholder='')=>{
  const {start,end}=selection.current;
  setValue((old:any)=>{const chosen=old.body.slice(start,end)||placeholder;return {...old,format:'markdown',body:old.body.slice(0,start)+before+chosen+after+old.body.slice(end)};});
  const cursor=start+before.length+(end-start||placeholder.length)+after.length;
  selection.current={start:cursor,end:cursor};setPreview(false);
  requestAnimationFrame(()=>{editor.current?.focus();editor.current?.setSelectionRange(cursor,cursor);});
 };
 const insertMedia=(item:Entry)=>insert(`\n![${String(item.data.title||'家族记忆').replace(/[\[\]\\\r\n]/g,' ')}](media:${item.id})\n`);
 return <Modal title={record?'编辑家族档案':'记录一段家族故事'} subtitle="支持 Markdown、图片和视频，把回忆写成一篇完整的文章。" onClose={()=>{if(!busy&&!uploading)onClose();}} wide>
  <form onSubmit={async event=>{event.preventDefault();if(busy||uploading)return;setBusy(true);setError('');try{await onSave(value);}catch(error:any){setError(error.message);}finally{setBusy(false);}}}>
   <div className="modal-body">
    <Field label="标题 *"><input required maxLength={120} value={value.title} onChange={event=>set('title',event.target.value)} placeholder="给这段记忆起个名字"/></Field>
    <div className="form-grid"><Field label="分类"><select value={value.category} onChange={event=>set('category',event.target.value)}>{['家族故事','家族大事','修谱笔记','资料来源'].map(text=><option key={text}>{text}</option>)}</select></Field><Field label="可见范围"><select disabled={uploading} value={value.privacy} onChange={event=>set('privacy',event.target.value)}><option value="family">家族成员可见</option><option value="editors">仅所有者和编辑可见</option></select></Field></div>
    <DateField label="事件日期" value={value.date} onChange={date=>set('date',date)}/>
    <div className="story-editor">
     <div className="story-editor-toolbar" role="toolbar" aria-label="文章编辑工具">
      <button type="button" title="二级标题" disabled={uploading} onClick={()=>insert('\n## ','\n','标题')}><Heading2 size={17}/></button>
      <button type="button" title="加粗" disabled={uploading} onClick={()=>insert('**','**','重点文字')}><Bold size={16}/></button>
      <button type="button" title="列表" disabled={uploading} onClick={()=>insert('\n- ','\n','一条记忆')}><List size={17}/></button>
      <button type="button" disabled={uploading} onClick={()=>mdInput.current?.click()}><FileUp size={16}/>导入 .md</button>
      <button type="button" disabled={uploading} onClick={()=>mediaInput.current?.click()}><ImagePlus size={16}/>{uploading?`上传 ${progress}%`:'上传图片 / 视频'}</button>
      <button type="button" aria-pressed={preview} onClick={()=>setPreview(!preview)}>{preview?<Pencil size={16}/>:<Eye size={16}/ >}{preview?'继续编辑':'预览文章'}</button>
     </div>
     <input ref={mdInput} type="file" aria-label="导入 Markdown 文件" accept=".md,.markdown,text/markdown,text/plain" hidden onChange={async event=>{const file=event.target.files?.[0];event.target.value='';if(!file)return;setError('');if(file.size>120000){setError('Markdown 文件最多 30,000 字符');return;}try{const text=await file.text();if(text.length>30000)throw Error('正文最多 30,000 字符');if(value.body.trim()&&!window.confirm('导入将替换当前正文，是否继续？'))return;setValue((old:any)=>({...old,body:text.replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n'),format:'markdown',title:old.title||file.name.replace(/\.(md|markdown)$/i,'')}));selection.current={start:0,end:0};setPreview(false);}catch(error:any){setError(error.message);}}}/>
     <input ref={mediaInput} type="file" aria-label="上传文章图片或视频" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" hidden disabled={uploading} onChange={async event=>{
      const file=event.target.files?.[0];event.target.value='';if(!file)return;setError('');setUploading(true);setProgress(0);
      try{const form=new FormData();form.append('file',file);form.append('metadata',JSON.stringify({album:'文章附件',privacy:value.privacy,person_ids:value.person_ids}));const result=await upload(`/families/${fid}/media`,form,setProgress);setUploaded(old=>[...old,result]);insertMedia(result);await onMedia();}catch(error:any){setError(error.message);}finally{setUploading(false);}
     }}/>
     <div className="story-existing-media"><select aria-label="选择已有媒体插入正文" value={selected} onChange={event=>setSelected(event.target.value)}><option value="">选择已有图片或视频</option>{available.map(item=><option key={item.id} value={item.id}>{isVideo(item)?'视频':'图片'} · {item.data.title}</option>)}</select><Button type="button" variant="secondary small" disabled={!selected||uploading} onClick={()=>{const item=available.find(item=>item.id===selected);if(item)insertMedia(item);}}>插入正文</Button><select aria-label="正文格式" value={value.format} onChange={event=>set('format',event.target.value)}><option value="markdown">Markdown</option><option value="plain">纯文本</option></select></div>
     {preview?<div className="story-editor-preview" aria-label="文章预览"><StoryMarkdown body={value.body} format={value.format} media={allMedia} fid={fid}/>{!value.body&&<p className="muted">写下正文后，在这里预览文章。</p>}</div>:<textarea ref={editor} aria-label="正文" rows={12} maxLength={30000} value={value.body} disabled={uploading} onChange={event=>set('body',event.target.value)} onSelect={event=>{selection.current={start:event.currentTarget.selectionStart,end:event.currentTarget.selectionEnd};}} placeholder="## 那年的团圆\n\n从记得的细节开始写，也可以上传图片或视频插入正文。"/>}
     <p className="story-editor-hint">支持标题、列表、引用、链接和表格。插入的媒体保存在家族媒体库；导出的 .md 保留媒体引用，跨站迁移请使用完整家族备份。</p>
    </div>
    <Field label="关联家人"><div className="check-grid">{people.map(person=><label key={person.id}><input type="checkbox" checked={value.person_ids.includes(person.id)} onChange={event=>set('person_ids',event.target.checked?[...value.person_ids,person.id]:value.person_ids.filter((id:string)=>id!==person.id))}/>{person.data.name}</label>)}</div></Field>
    <Field label="资料来源"><input maxLength={3000} value={value.source} onChange={event=>set('source',event.target.value)}/></Field>
    {error&&<div className="error-box" role="alert">{error}</div>}
   </div><div className="modal-footer"><Button type="button" variant="secondary" disabled={busy||uploading} onClick={onClose}>取消</Button><Button type="submit" loading={busy} disabled={uploading}>保存档案</Button></div>
  </form>
 </Modal>;
}
