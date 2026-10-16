export const DEFAULT_TERMS={
 marriage:'夫妻',past_marriage:'曾为夫妻',
 father:'父',mother:'母',son:'子',daughter:'女',parent:'家长',child:'孩子',
 husband:'夫',wife:'妻',spouse:'配偶',partner:'伴侣',former_partner:'前伴侣',coparent:'共同育儿',other:'其他关系',legacy_partner:'配偶 / 伴侣（待细分）',
 adoptive_father:'养父',adoptive_mother:'养母',adoptive_son:'养子',adoptive_daughter:'养女',adoptive_parent:'养家长',adoptive_child:'养孩子',
 step_father:'继父',step_mother:'继母',step_son:'继子',step_daughter:'继女',step_parent:'继家长',step_child:'继孩子',
 former_husband:'前夫',former_wife:'前妻',former_spouse:'前配偶',
};
export type KinshipKey=keyof typeof DEFAULT_TERMS;
export type KinshipTerms=Partial<Record<KinshipKey,string>>;
const derivedPrefixes={adoptive_:'养',step_:'继',former_:'前'};

export function kinshipTerm(key:KinshipKey,terms:KinshipTerms={}) :string {
 const custom=terms[key]?.trim();if(custom)return custom;
 for(const [prefix,word] of Object.entries(derivedPrefixes)){
  if(key.startsWith(prefix)){
   const base=key.slice(prefix.length) as KinshipKey;
   if(base in DEFAULT_TERMS)return word+kinshipTerm(base,terms);
  }
 }
 return DEFAULT_TERMS[key];
}
export const EVERYDAY_TERMS:KinshipTerms={father:'父亲',mother:'母亲',son:'儿子',daughter:'女儿',husband:'丈夫',wife:'妻子',adoptive_father:'养父',adoptive_mother:'养母',adoptive_son:'养子',adoptive_daughter:'养女',step_father:'继父',step_mother:'继母',step_son:'继子',step_daughter:'继女',former_husband:'前夫',former_wife:'前妻'};
