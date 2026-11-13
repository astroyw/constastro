import {PROFILES} from './affinity.js';
export const METHOD_VERSION='campana-regularizada-v2';
export const PRIOR_WEIGHT=4;
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
// Explicit heuristic with a neutral prior. Never a calibrated genetic prediction.
export function performance(sire,dam,horses,results){
  const nodes=new Map(horses.map(h=>[h.id,h]));
  if(!nodes.has(sire)||!nodes.has(dam)||sire===dam)throw new Error('Seleccioná dos caballos registrados y diferentes.');
  const aDepth=depths(sire,nodes),bDepth=depths(dam,nodes),races=new Map();
  for(const r of results){
    if(!nodes.has(r.horse_id)||!sourceURL(r.source_url)||!Number.isFinite(r.distance)||r.distance<=0||!surface(r.surface))continue;
    if(!Number.isInteger(r.position)||r.position<1||r.position>100)continue;
    const hasField=r.field_size!==null&&r.field_size!==undefined;
    if(hasField&&(!Number.isInteger(r.field_size)||r.field_size<2||r.position>r.field_size))continue;
    if(!r.race_id&&!(r.country&&r.track&&r.date&&r.race_name))continue;
    const key=JSON.stringify([r.horse_id,r.race_id||[r.country,r.track,r.date,r.race_name]]),previous=races.get(key);
    if(previous===null)continue;
    if(previous&&(['position','distance'].some(f=>previous[f]!==r[f])||surface(previous.surface)!==surface(r.surface)||(previous.hasField&&hasField&&previous.field_size!==r.field_size))){races.set(key,null);continue}
    const quality=hasField?1:0.5;
    const value=hasField?(r.field_size-r.position)/(r.field_size-1):1/r.position;
    // An otherwise identical row with official field size supersedes the weaker
    // observation; order does not decide the score. Preserve both citations.
    const sources=new Set([...(previous?.sources||[]),sourceURL(r.source_url)]);
    if(!previous||hasField&&!previous.hasField)races.set(key,{...r,key,quality,value,hasField,sources});
    else previous.sources=sources;
  }
  function branch(rows,map){
    const grouped=new Map();
    for(const r of rows){if(!map.has(r.horse_id))continue;if(!grouped.has(r.horse_id))grouped.set(r.horse_id,[]);grouped.get(r.horse_id).push(r)}
    let delta=0,totalWeight=0,influence=0;
    const details=[];
    for(const [id,starts] of grouped){
      const depth=map.get(id),weight=2**-depth,n=starts.reduce((sum,r)=>sum+r.quality,0);
      const observation=starts.reduce((sum,r)=>sum+r.quality*r.value,0);
      const adjusted=(PRIOR_WEIGHT*0.5+observation)/(PRIOR_WEIGHT+n);
      delta+=weight*(adjusted-0.5);influence+=weight*n/(PRIOR_WEIGHT+n);totalWeight+=weight;
      details.push({id,name:nodes.get(id).name||id,depth,starts:starts.length,effectiveStarts:n,value:adjusted,weight});
    }
    const denominator=Math.max(1,totalWeight),starts=rows.filter(r=>map.has(r.horse_id));
    return {value:0.5+delta/denominator,influence:influence/denominator,starts:starts.length,horseCount:grouped.size,
      generations:[...new Set(details.map(h=>h.depth))].sort(),directStarts:starts.filter(r=>map.get(r.horse_id)===0).length,
      keys:new Set(starts.map(r=>r.key)),details};
  }
  return PROFILES.map(p=>{
    const rows=[...races.values()].filter(r=>r&&surface(r.surface)===p.surface&&Math.abs(r.distance-p.distance)<=200&&(aDepth.has(r.horse_id)||bDepth.has(r.horse_id)));
    const a=branch(rows,aDepth),b=branch(rows,bDepth),unique=new Set([...a.keys,...b.keys]).size;
    const shared=[...a.keys].filter(k=>b.keys.has(k)).length,relative=rows.filter(r=>r.hasField).length;
    const score=Math.max(0,Math.min(100,Math.round(50*(a.value+b.value)+1e-10)));
    const confidence=unique===0?'Sin evidencia':unique>=30&&a.horseCount>=3&&b.horseCount>=3&&a.directStarts>=3&&b.directStarts>=3&&relative/unique>=0.8?'Moderada':'Baja';
    return {...p,score,confidence,basis:unique===0?'neutral':a.starts===0||b.starts===0?'one_branch':'regularized',
      sireStarts:a.starts,damStarts:b.starts,sireHorses:a.horseCount,damHorses:b.horseCount,
      uniqueStarts:unique,sharedStarts:shared,horseCount:new Set(rows.map(r=>r.horse_id)).size,
      relativeStarts:relative,rankOnlyStarts:unique-relative,sireGenerations:a.generations,damGenerations:b.generations,
      sireValue:100*a.value,damValue:100*b.value,evidenceWeight:50*(a.influence+b.influence),
      sireDetails:a.details,damDetails:b.details,
      sources:[...new Set(rows.flatMap(r=>[...r.sources]))].sort(),method:METHOD_VERSION};
  });
}
export function performancePanel(scores){
  const basis={neutral:'Base neutral de 50: sin actuaciones utilizables en este perfil.',one_branch:'Una rama aporta antecedentes; la otra conserva la base neutral de 50.',regularized:'Calculado con antecedentes de ambas ramas y una base neutral que modera las muestras pequeñas.'};
  const details=(label,rows)=>`<h4>${label}</h4>${rows.length?`<ul>${rows.map(h=>`<li>${esc(h.name)} · generación ${h.depth} · ${h.starts} actuaciones · valor ajustado ${(h.value*100).toFixed(1)}/100</li>`).join('')}</ul>`:'<p>50/100 por la base neutral; no se observó una actuación utilizable.</p>'}`;
  return `<section class="panel form-panel affinity-panel"><h2>Índice orientativo del cruce por distancia</h2><p>Antecedentes familiares con regularización · escala 0–100. No es una probabilidad de ganar ni una predicción genética validada.</p><div class="affinity-grid">${scores.map(p=>`<article><h3>${esc(p.name)}</h3><small>${p.distance} m · ${esc(p.label)} · margen ±200 m</small><strong>${p.score} / 100</strong><meter min="0" max="100" value="${p.score}" aria-label="Índice ${esc(p.name)}"></meter><small class="score-basis">${basis[p.basis]}</small><small>Confianza: ${esc(p.confidence)}</small><small>Peso de antecedentes en el cálculo: ${p.evidenceWeight.toFixed(1)} %</small><small>${p.sireStarts} actuaciones paternas (${p.sireHorses} caballos) · ${p.damStarts} maternas (${p.damHorses} caballos)</small><small>${p.uniqueStarts} actuaciones únicas · ${p.sharedStarts} compartidas entre ramas</small><small>${p.relativeStarts} con participantes oficiales · ${p.rankOnlyStarts} con puesto solamente</small><details><summary>Datos y cálculo de ${esc(p.name)}</summary><p>Rama paterna: ${p.sireValue.toFixed(1)}/100 · rama materna: ${p.damValue.toFixed(1)}/100. Índice = promedio de ambas, redondeado.</p>${details('Rama paterna',p.sireDetails)}${details('Rama materna',p.damDetails)}${p.sources.length?`<p>Fuentes utilizadas:</p><ul>${p.sources.map((s,i)=>`<li><a href="${esc(s)}" target="_blank" rel="noopener noreferrer">Registro ${i+1}</a></li>`).join('')}</ul>`:''}</details></article>`).join('')}</div><details><summary>Fórmula y alcance del índice</summary><p>Se usan actuaciones documentadas en la superficie indicada y a ±200 m. Con participantes oficiales conocidos, cada resultado vale (participantes − puesto) / (participantes − 1), con peso q = 1. Cuando sólo consta el puesto, se usa el indicador auxiliar 1 / puesto con peso q = ½; no se inventa la cantidad de participantes. Las filas inválidas, sin fuente o con contradicciones se excluyen y las carreras repetidas se cuentan una sola vez por caballo.</p><p>Para cada caballo: valor ajustado = (2 + Σ(q × resultado)) / (4 + Σq). Los números 2 y 4 expresan una base neutral de 50 y cuatro unidades de regularización elegidas para moderar muestras pequeñas; no son carreras observadas ni parámetros calibrados. Después se pondera la cercanía: progenitor 1, padres ½, abuelos ¼, bisabuelos ⅛. Cada ID aparece una vez, a su generación más cercana.</p><p>Para cada rama: B = 0,5 + Σ(peso × (valor ajustado − 0,5)) / máximo(1, Σpeso). Así, un ancestro lejano aislado no ocupa toda la rama. Índice final = redondear(50 × (B paterna + B materna)). Si ninguna rama aporta actuaciones, el resultado matemático es 50/100 en todas las categorías: es el punto de partida, no una aptitud comprobada. Con una sola rama documentada, la otra mantiene 50.</p><p>La confianza describe la evidencia disponible, no una confianza estadística. Es «Sin evidencia» cuando todo procede de la base neutral; «Baja» con observaciones; y «Moderada» a partir de 30 actuaciones únicas, tres caballos por rama, tres actuaciones de cada progenitor y al menos 80 % con participantes oficiales conocidos. Un ancestro compartido no multiplica la cantidad de evidencia única.</p><p>El índice no ajusta clase de carrera, edad, entrenamiento o estado físico. Los indicadores de posición relativa y puesto recíproco no son equivalentes; el segundo recibe la mitad de peso. Las categorías son referencias y no determinan elegibilidad por edad o sexo, incluidas las restricciones de Distaff. Tampoco prueba la capacidad de una cría ni sustituye pruebas de ADN.</p></details></section>`;
}
