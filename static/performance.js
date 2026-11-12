import {PROFILES} from './affinity.js';
export const METHOD_VERSION='campana-relativa-v1';
const fold=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const surface=s=>({arena:'dirt',dirt:'dirt',cesped:'turf',turf:'turf',grass:'turf',pasto:'turf'})[fold(s)];
function sourceURL(s){try{const u=new URL(s);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null}catch{return null}}
function depths(root,nodes){
  const result=new Map(),queue=[[root,0]];
  for(let i=0;i<queue.length;i++){
    const [id,d]=queue[i];if(!id||d>3||!nodes.has(id)||(result.has(id)&&result.get(id)<=d))continue;
    result.set(id,d);const h=nodes.get(id);queue.push([h.sire_id,d+1],[h.dam_id,d+1]);
  }return result;
}
// Historical relative finishing positions, never a calibrated prediction of a foal.
export function performance(sire,dam,horses,results){
  const nodes=new Map(horses.map(h=>[h.id,h])),aDepth=depths(sire,nodes),bDepth=depths(dam,nodes);
  const races=new Map();
  for(const r of results){
    if(!nodes.has(r.horse_id)||!sourceURL(r.source_url)||!Number.isFinite(r.distance)||r.distance<=0||!surface(r.surface))continue;
    if(!Number.isInteger(r.position)||!Number.isInteger(r.field_size)||r.field_size<2||r.position<1||r.position>r.field_size)continue;
    if(!r.race_id&&!(r.country&&r.track&&r.date&&r.race_name))continue;
    const key=JSON.stringify([r.horse_id,r.race_id||[r.country,r.track,r.date,r.race_name]]);
    const previous=races.get(key);
    // A conflicting duplicate is omitted rather than picking the first value.
    if(previous===null)continue;
    if(previous&&['position','field_size','distance'].some(f=>previous[f]!==r[f])||previous&&surface(previous.surface)!==surface(r.surface)){races.set(key,null);continue}
    if(!previous)races.set(key,{...r,key});
  }
  function branch(rows,map){
    const grouped=new Map();
    for(const r of rows){if(!map.has(r.horse_id))continue;if(!grouped.has(r.horse_id))grouped.set(r.horse_id,[]);grouped.get(r.horse_id).push(r)}
    let total=0,weights=0;
    for(const [id,starts] of grouped){const w=2**-map.get(id);total+=w*starts.reduce((v,r)=>v+(r.field_size-r.position)/(r.field_size-1),0)/starts.length;weights+=w}
    const starts=rows.filter(r=>map.has(r.horse_id));
    return {value:weights?total/weights:null,starts:starts.length,horseCount:grouped.size,
      generations:[...new Set([...grouped.keys()].map(id=>map.get(id)))].sort(),directStarts:starts.filter(r=>map.get(r.horse_id)===0).length,keys:new Set(starts.map(r=>r.key))};
  }
  return PROFILES.map(p=>{
    const rows=[...races.values()].filter(r=>r&&surface(r.surface)===p.surface&&Math.abs(r.distance-p.distance)<=200&&(aDepth.has(r.horse_id)||bDepth.has(r.horse_id)));
    const a=branch(rows,aDepth),b=branch(rows,bDepth),unique=new Set([...a.keys,...b.keys]).size;
    const horseCount=new Set(rows.map(r=>r.horse_id)).size,shared=[...a.keys].filter(k=>b.keys.has(k)).length;
    const enough=sire!==dam&&a.starts>=3&&b.starts>=3&&unique>=6&&horseCount>=2;
    const score=enough?Math.round(1+99*(a.value+b.value)/2+1e-10):null;
    const confidence=!enough?'Sin evaluar':unique>=30&&a.horseCount>=3&&b.horseCount>=3&&a.directStarts>=3&&b.directStarts>=3?'Moderada':'Baja';
    return {...p,score,confidence,sireStarts:a.starts,damStarts:b.starts,sireHorses:a.horseCount,damHorses:b.horseCount,
      uniqueStarts:unique,sharedStarts:shared,horseCount,sireGenerations:a.generations,damGenerations:b.generations,
      sources:[...new Set(rows.map(r=>sourceURL(r.source_url)))].sort(),method:METHOD_VERSION};
  });
}
export function performancePanel(scores){
  return `<section class="panel form-panel affinity-panel"><h2>Rendimiento orientativo del cruce por distancia</h2><p>Índice de antecedentes familiares · escala 1–100. No es una probabilidad de ganar ni una predicción genética validada.</p><div class="affinity-grid">${scores.map(p=>`<article><h3>${esc(p.name)}</h3><small>${p.distance} m · ${esc(p.label)} · margen ±200 m</small><strong>${p.score===null?'Sin datos suficientes':p.score+' / 100'}</strong>${p.score===null?'':`<meter min="1" max="100" value="${p.score}" aria-label="Estimación ${esc(p.name)}"></meter>`}<small>Confianza: ${esc(p.confidence)}</small><small>${p.sireStarts} actuaciones paternas (${p.sireHorses} caballos) · ${p.damStarts} maternas (${p.damHorses} caballos)</small><small>${p.uniqueStarts} actuaciones únicas · ${p.sharedStarts} compartidas entre ramas</small><small>Generaciones con datos: paterna ${p.sireGenerations.join(', ')||'—'} · materna ${p.damGenerations.join(', ')||'—'} (0 = progenitor)</small>${p.sources.length?`<details><summary>Fuentes utilizadas (${p.sources.length})</summary><ul>${p.sources.map((s,i)=>`<li><a href="${esc(s)}" target="_blank" rel="noopener noreferrer">Registro ${i+1}</a></li>`).join('')}</ul></details>`:''}</article>`).join('')}</div><details><summary>Cómo se calcula y qué significa</summary><p>Se usan actuaciones en la superficie indicada y a ±200 m de la distancia de referencia, con puesto y participantes oficiales conocidos. Cada resultado se normaliza como (participantes − puesto) / (participantes − 1). Primero se promedian las actuaciones de cada caballo; luego se ponderan los progenitores y sus ancestros hasta bisabuelos por 1, ½, ¼ y ⅛. Cada rama aporta el 50 %. El promedio se transforma a 1–100.</p><p>Se requieren al menos tres actuaciones válidas por rama, seis actuaciones únicas entre ambas y dos caballos distintos. Una actuación compartida no aumenta la evidencia única. Las filas contradictorias o sin datos suficientes se omiten. La confianza describe la cantidad y cercanía de la evidencia: sigue siendo baja salvo que haya al menos 30 actuaciones únicas, tres caballos por rama y tres actuaciones de cada progenitor. No es una confianza estadística.</p><p>El índice resume campañas históricas; no ajusta el nivel de las carreras, edad, entrenamiento o estado físico y no permite predecir el rendimiento individual de una cría. Las categorías son perfiles de referencia. Distaff también tiene restricciones de sexo que este cálculo no evalúa. Una categoría sin evidencia no indica incapacidad para correr esa distancia.</p></details></section>`;
}
