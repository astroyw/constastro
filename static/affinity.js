export const PROFILES=[
  {name:'Classic',distance:2000,surface:'dirt',label:'Arena'},
  {name:'Distaff',distance:1800,surface:'dirt',label:'Arena'},
  {name:'Turf',distance:2400,surface:'turf',label:'Césped'},
  {name:'Mile',distance:1600,surface:'turf',label:'Césped'},
  {name:'Sprint',distance:1200,surface:'dirt',label:'Arena'},
];
const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
function surface(s){return ({arena:'dirt',dirt:'dirt',cesped:'turf',turf:'turf',grass:'turf',pasto:'turf'})[normalize(s)]||null}
// Descriptive campaign specialization; never a genetic or performance prediction.
export function affinity(sire,dam,horses,results){
  const nodes=new Map(horses.map(h=>[h.id,h]));
  function branch(root){
    const depths=new Map();function walk(id,d){if(!id||d>3||!nodes.has(id)||(depths.has(id)&&depths.get(id)<=d))return;depths.set(id,d);const h=nodes.get(id);walk(h.sire_id,d+1);walk(h.dam_id,d+1)}walk(root,0);
    const seen=new Set(),rows=[];
    for(const r of results){
      if(!depths.has(r.horse_id)||!r.source_url||!Number.isFinite(r.distance)||r.distance<=0||!surface(r.surface))continue;
      const key=JSON.stringify([r.horse_id,r.race_id||[r.country,r.track,r.date,r.race_name]]);if(seen.has(key))continue;seen.add(key);
      rows.push({...r,weight:2**-depths.get(r.horse_id),normalizedSurface:surface(r.surface)});
    }return rows;
  }
  const a=branch(sire),b=branch(dam);
  return PROFILES.map(p=>{
    const fraction=rows=>rows.reduce((n,r)=>n+r.weight*(r.normalizedSurface===p.surface&&Math.abs(r.distance-p.distance)<=200?1:0),0)/rows.reduce((n,r)=>n+r.weight,0);
    return {...p,sireStarts:a.length,damStarts:b.length,score:a.length>=3&&b.length>=3?Math.round(50*(fraction(a)+fraction(b))):null};
  });
}
export function affinityPanel(scores){return `<section class="panel form-panel affinity-panel"><h2>Afinidad por distancia y superficie</h2><p>Índice orientativo de especialización de las campañas familiares · escala 0–100.</p><div class="affinity-grid">${scores.map(p=>`<article><h3>${p.name}</h3><small>${p.distance} m · ${p.label} · margen ±200 m</small><strong>${p.score===null?'Sin datos suficientes':p.score+' / 100'}</strong>${p.score===null?'':`<meter min="0" max="100" value="${p.score}" aria-label="Afinidad ${p.name}"></meter>`}<small>${p.sireStarts} actuaciones en rama paterna · ${p.damStarts} en materna</small></article>`).join('')}</div><details><summary>Cómo se calcula</summary><p>Porcentaje ponderado de actuaciones documentadas que coinciden con la superficie y el rango de distancia. Se incluyen cada progenitor y sus ancestros hasta bisabuelos: pesos 1, ½, ¼ y ⅛. Cada rama aporta la mitad del índice. Se requieren al menos tres actuaciones con fuente, distancia y superficie conocidas por rama. Los registros sin identificar y las superficies desconocidas no se usan; las carreras duplicadas se cuentan una sola vez por caballo.</p><p>Describe la especialización de las campañas disponibles, sin evaluar triunfos ni calidad deportiva. No está validado como predictor de aptitud genética o rendimiento de una cría. Las categorías son perfiles de referencia; no determinan elegibilidad por edad o sexo para una carrera. Un dato faltante no equivale a cero.</p></details></section>`}
