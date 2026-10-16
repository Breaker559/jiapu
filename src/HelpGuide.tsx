import { DatabaseBackup, GitFork, KeyRound, Users } from 'lucide-react';
import { Button, Modal, TextLink } from './components';

export default function HelpGuide({onClose,onNavigate}:{onClose:()=>void;onNavigate:(page:string)=>void}) {
 return <Modal title="使用帮助" subtitle="从记录一位家人开始，慢慢完善家族记忆。" onClose={onClose}>
  <div className="modal-body help-guide">
   <details open><summary><GitFork size={18}/>整理世系图谱</summary><div>
    <p>先添加家人，再用“连接亲属”建立关系。拖动人物卡片可调整位置，点击“框选”后拖出选区，或按住 Shift 拖动，选中多位家人。</p>
    <p>选中多人后，浮动工具可对齐、均匀分布；开启吸附后拖动更容易排齐。“一键排版”会自动整理位置，不满意可撤销。</p>
    <p>“查看全图”可总览整个家族；在“显示设置”里筛选房支、调整称谓显示，点击“查关系”查找两位家人的关系。</p>
    <p>点击图谱工具栏的“导出”，可保存 PNG、SVG 或 HTML 离线网页；保留当前筛选范围内的整张图谱和排版，网页可离线查找姓名、查看生日与生平。</p>
    <p className="help-note">图谱位置保存在当前浏览器，同一家族在其他设备可单独排版。</p>
    <TextLink onClick={()=>onNavigate('tree')}>打开世系图谱</TextLink>
   </div></details>
   <details><summary><Users size={18}/>邀请家人一起修谱</summary><div>
    <p>家族所有者进入“家族设置 → 成员与邀请”，选择角色后生成邀请码。邀请码一次有效，72 小时内可使用。</p>
    <p>家人在登录页选择“我有家族邀请码”加入；已有账号使用原邮箱和密码即可。</p>
    <TextLink onClick={()=>onNavigate('settings')}>打开家族设置</TextLink>
   </div></details>
   <details><summary><DatabaseBackup size={18}/>备份与恢复</summary><div>
    <p>家族所有者进入“家族设置 → 备份与迁移”，设置至少 12 个字符的备份密码，导出包含人物、关系、图片、视频和档案的完整备份。</p>
    <p>请单独保存备份密码。恢复时先校验、预览，再创建新家族，现有家族不会被覆盖。</p>
    <TextLink onClick={()=>onNavigate('settings')}>打开家族设置</TextLink>
   </div></details>
   <details><summary><KeyRound size={18}/>管理自己的账号</summary><div>
    <p>点击右上角头像，可查看登录账号、修改密码或退出登录。修改密码后请保存新的恢复码，其他设备需要重新登录。</p>
    <p>忘记密码时，可在登录页使用邮箱和恢复码重设密码。</p>
   </div></details>
  </div><div className="modal-footer"><Button variant="secondary" onClick={onClose}>知道了</Button></div>
 </Modal>;
}
