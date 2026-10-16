import { AlignHorizontalDistributeCenter, AlignHorizontalJustifyCenter, AlignHorizontalJustifyEnd, AlignHorizontalJustifyStart, AlignVerticalDistributeCenter, AlignVerticalJustifyCenter, AlignVerticalJustifyEnd, AlignVerticalJustifyStart, Check, Hand, Magnet, Redo2, Scan, Undo2, WandSparkles } from 'lucide-react';
import type { Alignment } from './treeArrangement';

const alignments = [
 { value: 'left', label: '左对齐', icon: AlignHorizontalJustifyStart },
 { value: 'centerX', label: '水平居中', icon: AlignHorizontalJustifyCenter },
 { value: 'right', label: '右对齐', icon: AlignHorizontalJustifyEnd },
 { value: 'top', label: '顶部对齐', icon: AlignVerticalJustifyStart },
 { value: 'centerY', label: '垂直居中', icon: AlignVerticalJustifyCenter },
 { value: 'bottom', label: '底部对齐', icon: AlignVerticalJustifyEnd },
 { value: 'distributeX', label: '水平等距', icon: AlignHorizontalDistributeCenter },
 { value: 'distributeY', label: '垂直等距', icon: AlignVerticalDistributeCenter },
] as const;

type Props = {
 selecting: boolean; setSelecting: (value: boolean) => void;
 snap: boolean; setSnap: (value: boolean) => void; count: number;
 history: { undo: boolean; redo: boolean }; saved: boolean;
 align: (alignment: Alignment) => void; autoLayout: () => void;
 undo: () => void; redo: () => void; selectAll: () => void; clearSelection: () => void;
};

export default function TreeArrangementToolbar(props: Props) {
 return <div className="tree-arrangement">
  <div className="tree-arrangement-tools" role="toolbar" aria-label="图谱排版工具">
   <div className="tree-tool-group" role="group" aria-label="画布操作">
    <button aria-pressed={!props.selecting} onClick={() => props.setSelecting(false)} title="拖动画布；按住 Shift 临时框选"><Hand size={15}/>移动</button>
    <button aria-pressed={props.selecting} onClick={() => props.setSelecting(true)} title="拖出选框，选中人物后可整组移动"><Scan size={15}/>框选</button>
   </div>
   <button className="tree-snap-toggle" aria-pressed={props.snap} onClick={() => props.setSnap(!props.snap)} title="拖动时吸附到其他人物的边缘和中心，并显示参考线"><Magnet size={15}/>吸附<span>{props.snap ? '开' : '关'}</span></button>
   <div className="tree-tool-group" role="group" aria-label="排版历史">
    <button aria-label="撤销排版" title="撤销排版（Ctrl / ⌘ Z）" disabled={!props.history.undo} onClick={props.undo}><Undo2 size={15}/></button>
    <button aria-label="重做排版" title="重做排版（Ctrl / ⌘ Shift Z）" disabled={!props.history.redo} onClick={props.redo}><Redo2 size={15}/></button>
   </div>
   <span className={'tree-layout-storage' + (props.saved ? '' : ' unsaved')} title={props.saved ? '布局自动保存在此浏览器' : '布局未能保存，请勿刷新'} aria-label={props.saved ? '布局自动保存在此浏览器' : '布局未能保存，请勿刷新'}>{props.saved ? <Check size={14}/> : '未保存'}</span>
   <button className="tree-auto-layout" onClick={props.autoLayout} title="按亲属关系整理当前可见人物；可撤销"><WandSparkles size={15}/>一键排版</button>
  </div>
  {(props.selecting || props.count > 0) && <div className="tree-selection-panel">
  <div className="tree-arrangement-status">
   <span className="tree-selection-count" role="status">{props.count ? `已选 ${props.count} 人` : '未选择人物'}</span>
   <button onClick={props.selectAll}>全选</button><button disabled={!props.count} onClick={props.clearSelection}>取消选择</button>
   {!props.count && <span className="tree-arrangement-hint">拖出选框选择人物</span>}
  </div>
  {props.count > 0 && <div className="tree-tool-group tree-align-tools" role="group" aria-label="对齐与分布">
   {alignments.map(({ value, label, icon: Icon }) => {
    const minimum = value.startsWith('distribute') ? 3 : 2;
    return <button key={value} aria-label={label} title={`${label}（至少选中 ${minimum} 人）`} disabled={props.count < minimum} onClick={() => props.align(value)}><Icon size={16}/></button>;
   })}
  </div>}
  </div>}
 </div>;
}
