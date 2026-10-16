export type FamilyDate = {calendar?: 'solar'|'lunar'; year?: number|null; month?: number|null; day?: number|null; leap?: boolean; approximate?: boolean; original?: string};
export type Entry = {id:string; kind:string; data:Record<string,any>; version:number; created?:string; updated?:string; deleted?:boolean; birth_info?:any; death_info?:any; anniversary?:{date:string;days:number;calendar:string}|null};
export type Family = {id:string;name:string;role:string;[key:string]:any};
export type State = {family:Family;records:Entry[];members:any[];audit:any[]};
export const relationNames: Record<string,string> = {
  parent:'血缘', adoptive:'收养', step:'继亲',
  parent_unknown:'未注明', married:'夫妻',
  partner:'伴侣（非婚姻）', former_spouse:'曾为夫妻',
  former_partner:'前伴侣', coparent:'共同育儿', other:'其他关系（见备注）',
  spouse:'配偶 / 伴侣（旧记录，待细分）',
};
export const parentTypes = new Set(['parent','adoptive','step','parent_unknown']);
export const isParentRelation = (type:string) => parentTypes.has(type);
export const roleNames:Record<string,string>={owner:'所有者',editor:'家族编辑',contributor:'资料贡献者',viewer:'家族成员'};
export const formatTime=(v:string)=>new Date(v).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Shanghai'});
export const initials=(name:string)=>(name||'?').slice(-2);
