import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSync } from 'esbuild';
const code=buildSync({entryPoints:['src/personFacts.ts'],bundle:true,write:false,format:'esm',platform:'node'}).outputFiles[0].text;
const {personFacts,todayInShanghai}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const person=(data,extra={})=>({id:'p',kind:'person',version:1,data,...extra});
const birth={calendar:'solar',year:2000,month:10,day:16};

test('living ages change on the birthday, and cards omit a death date',()=>{
 const p=person({birth,living:true,gender:'female',death:{year:2020,month:1,day:1}});
 assert.equal(personFacts(p,'2026-10-15').age,'25周岁');
 assert.equal(personFacts(p,'2026-10-16').age,'26周岁');
 assert.equal(personFacts(p,'2026-10-16').birth,'2000.10.16');
 assert.equal(personFacts(p,'2026-10-16').death,undefined);
 assert.equal(personFacts(p).gender,'女');
});
test('deceased age ends at death and does not keep increasing',()=>{
 const p=person({birth,living:false,death:{calendar:'solar',year:2020,month:1,day:1}});
 assert.equal(personFacts(p,'2026-10-16').age,'19岁');
 assert.equal(personFacts(p,'2040-10-16').age,'19岁');
 assert.equal(personFacts(p).death,'2020.01.01');
 assert.equal(personFacts(p).ageLabel,'享年');
});
test('lunar records use the converted solar date for completed years',()=>{
 const p=person({living:true,birth:{calendar:'lunar',year:2024,month:1,day:1}},{birth_info:{solar:'2024-02-10',label:'农历 2024年正月初一'}});
 assert.equal(personFacts(p,'2025-02-09').age,'不足1岁');
 assert.equal(personFacts(p,'2025-02-10').age,'1周岁');
 assert.equal(personFacts(p).birth,'农历 2024年正月初一');
});
test('approximate and incomplete dates never produce an exact age',()=>{
 assert.equal(personFacts(person({birth:{year:2000}}),'2026-10-16').age,'约 26 岁');
 assert.equal(personFacts(person({birth:{...birth,approximate:true}}),'2026-10-16').age,'约 26岁');
 assert.equal(personFacts(person({birth:{month:10,day:16}}),'2026-10-16').age,'待考');
 assert.equal(personFacts(person({birth:{calendar:'lunar',year:1800}}),'2026-10-16').age,'待考');
 assert.equal(personFacts(person({birth:{original:'旧谱有记载'}})).birth,'日期待考（有原记载）');
 assert.equal(personFacts(person({})).gender,'性别未注明');
});
test('future births and deaths before birth are flagged instead of negative ages',()=>{
 assert.equal(personFacts(person({birth}),'1999-10-16').age,'日期待核对');
 assert.equal(personFacts(person({birth,living:false,death:{year:1990,month:1,day:1}})).age,'日期待核对');
});
test('February 29 reaches a new completed year on March 1 in a non-leap year',()=>{
 const p=person({birth:{year:2024,month:2,day:29}});
 assert.equal(personFacts(p,'2025-02-28').age,'不足1岁');
 assert.equal(personFacts(p,'2025-03-01').age,'1周岁');
});
test('today follows the Shanghai date on either side of midnight',()=>{
 assert.equal(todayInShanghai(new Date('2026-10-15T15:59:59Z')),'2026-10-15');
 assert.equal(todayInShanghai(new Date('2026-10-15T16:00:00Z')),'2026-10-16');
});
