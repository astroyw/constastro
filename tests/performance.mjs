import assert from 'node:assert/strict';
import {performance,performancePanel,METHOD_VERSION} from '../static/performance.js';
const horses=[{id:'s'},{id:'d'}];
const race=(id,i,position=1,extra={})=>({id:id+i,horse_id:id,race_id:id+i,position,field_size:10,distance:2000,surface:'Arena',source_url:'https://example.org/official',...extra});
const wins=n=>[...Array.from({length:n},(_,i)=>race('s',i)),...Array.from({length:n},(_,i)=>race('d',i))];
const rows=wins(3),classic=(h=horses,r=rows)=>performance('s','d',h,r).find(p=>p.name==='Classic');
assert.equal(METHOD_VERSION,'campana-regularizada-v2');
// A neutral prior is explicit; it is never presented as observed performance.
for(const p of performance('s','d',horses,[])){
 assert.equal(p.score,50);assert.equal(p.confidence,'Sin evidencia');assert.equal(p.basis,'neutral');assert.equal(p.evidenceWeight,0);
}
assert.equal(classic().score,71);assert.equal(classic().confidence,'Baja');
assert.equal(classic(horses,wins(16)).score,90);
assert.equal(classic(horses,wins(16).map(r=>({...r,position:10}))).score,10);
assert.equal(classic(horses,rows.map(r=>({...r,position:r.horse_id==='s'?1:10}))).score,50);
assert.equal(classic(horses,[race('s',1)]).score,55);
assert.equal(classic(horses,rows.slice(0,3)).score,61);
assert.equal(classic(horses,rows.slice(0,3)).basis,'one_branch');
assert.equal(performance('s','d',horses,rows).find(p=>p.name==='Turf').score,50);
for(const extra of [{field_size:1},{field_size:0},{position:11},{position:0},{position:1.5},{surface:'Desconocida'},{source_url:'javascript:alert(1)'},{distance:2201}]){
 const p=classic(horses,rows.map(r=>({...r,...extra})));assert.equal(p.score,50);assert.equal(p.uniqueStarts,0);
}
assert.equal(classic(horses,rows.map(r=>({...r,distance:2200}))).score,71);
const rankOnly=classic(horses,rows.map(r=>({...r,field_size:null})));
assert.equal(rankOnly.score,64);assert.equal(rankOnly.relativeStarts,0);assert.equal(rankOnly.rankOnlyStarts,6);
assert.ok(rankOnly.evidenceWeight<classic().evidenceWeight);
assert.equal(classic(horses,[...rows,...rows]).uniqueStarts,6);
assert.equal(classic(horses,[...rows,...rows]).score,71);
assert.equal(classic(horses,[...rows,{...rows[0],position:2}]).uniqueStarts,5);
for(const order of [rows.concat(rows.map(r=>({...r,field_size:null}))),rows.map(r=>({...r,field_size:null})).concat(rows)]){
 const p=classic(horses,order);assert.equal(p.score,71);assert.equal(p.uniqueStarts,6);assert.equal(p.relativeStarts,6);
}
const shared=[{id:'s',sire_id:'a'},{id:'d',sire_id:'a'},{id:'a'}];
const sharedResult=classic(shared,Array.from({length:3},(_,i)=>race('a',i)));
assert.equal(sharedResult.score,61);assert.equal(sharedResult.uniqueStarts,3);assert.equal(sharedResult.sharedStarts,3);assert.equal(sharedResult.confidence,'Baja');
const near=[{id:'s',sire_id:'a'},{id:'a'},{id:'d'}];
const far=[{id:'s',sire_id:'b'},{id:'b',sire_id:'c'},{id:'c',sire_id:'a'},{id:'a'},{id:'d'}];
const ancestral=Array.from({length:16},(_,i)=>race('a',i));
assert.ok(classic(near,ancestral).score>classic(far,ancestral).score);
assert.ok(classic(far,ancestral).score>50);
// Horse campaigns keep a bounded contribution; a busy ancestor cannot become 100 branches.
assert.equal(classic(near,[...rows,...Array.from({length:30},(_,i)=>race('a',i,10))]).score,61);
assert.throws(()=>performance('s','s',horses,[]));assert.throws(()=>performance('s','unknown',horses,[]));
const fullFamilies=[{id:'s',sire_id:'s1',dam_id:'s2'},{id:'d',sire_id:'d1',dam_id:'d2'},...['s1','s2','d1','d2'].map(id=>({id}))];
const fullCampaigns=fullFamilies.flatMap(h=>Array.from({length:5},(_,i)=>race(h.id,i)));
assert.equal(classic(fullFamilies,fullCampaigns).confidence,'Moderada');
assert.equal(classic(fullFamilies,fullCampaigns.map(r=>({...r,field_size:null}))).confidence,'Baja');
const html=performancePanel(performance('s','d',horses,[]));
assert.equal((html.match(/<strong>50 \/ 100<\/strong>/g)||[]).length,5);
assert.ok(!html.includes('Sin datos suficientes'));assert.ok(html.includes('Base neutral'));assert.ok(html.includes('ni una predicción genética validada'));assert.ok(html.includes('Confianza: Sin evidencia'));
console.log('PASS: 0–100 regularized scores, explicit neutral prior, small/one-sided samples, rank-only evidence, conflicts, deduplication, shared ancestors and distance attenuation.');
