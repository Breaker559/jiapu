import { useState } from 'react';
import { FileCode2, Image, Download } from 'lucide-react';
import { Button, Modal } from './components';
import type { TreeExportFormat } from './treeExport';

export default function TreeExportDialog({count,scope,onClose,onExport}:{count:number;scope:string;onClose:()=>void;onExport:(format:TreeExportFormat)=>Promise<void>}){
 const [busy,setBusy]=useState<TreeExportFormat|null>(null),[error,setError]=useState(''),[done,setDone]=useState('');
 const choices:[TreeExportFormat,string,string][]=[['png','PNG 图片','适合保存、分享和打印；默认高清导出，大图自动调整分辨率。'],['svg','SVG 图形','保留文字与线条的清晰度，建议用现代浏览器打开。'],['html','HTML 离线网页','单个文件即可打开，内含头像、姓名查找、缩放和人物生平。']];
 return <Modal title="导出世系图谱" subtitle={`${scope} · ${count} 位家人`} onClose={()=>{if(!busy)onClose();}}><div className="modal-body tree-export-options"><p>导出当前筛选范围内的整张图谱，保留排版、称谓和外观，包含画布外的人物。</p>{choices.map(([format,title,description])=><Button key={format} variant="secondary tree-export-choice" disabled={!!busy} loading={busy===format} onClick={async()=>{setError('');setDone('');setBusy(format);try{await onExport(format);setDone(title+'已生成，请在浏览器下载中查看。');}catch(error:any){setError(error.message||'导出失败，请稍后重试');}finally{setBusy(null);}}}>{format==='html'?<FileCode2 size={21}/>:format==='png'?<Image size={21}/>:<Download size={21}/>}<span><strong>{title}</strong><small>{description}</small></span></Button>)}<p className="muted">文件可直接查看，不再需要账号登录，请自行保管。离线网页不含相册和文章附件；迁移完整资料请使用“备份与迁移”。</p>{error&&<div className="error-box" role="alert">{error}</div>}{done&&<p className="tree-export-success" role="status">{done}</p>}</div><div className="modal-footer"><Button variant="secondary" disabled={!!busy} onClick={onClose}>完成</Button></div></Modal>;
}
