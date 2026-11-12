const fold=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function unresolvedRoles(h,nodes){
  if(h.birth_year&&h.birth_year<=1935)return [];
  return ['sire_id','dam_id'].filter(field=>!h[field]||!nodes.has(h[field]));
}
export function historicPedigree(id,nodes){
  const queue=[[id,0]],seen=new Set(),rows=[];let missing=0,terminals=0;
  for(let i=0;i<queue.length;i++){
    const [key,depth]=queue[i];if(seen.has(key))continue;seen.add(key);
    const h=nodes.get(key);if(!h){missing++;continue}
    rows.push({horse:h,depth});
    if(h.birth_year&&h.birth_year<=1935){terminals++;continue}
    for(const field of ['sire_id','dam_id']){if(h[field])queue.push([h[field],depth+1]);else missing++}
  }
  return {rows,missing,terminals,complete:missing===0,maxDepth:Math.max(0,...rows.map(r=>r.depth))};
}
export async function bindHistory(target,root,nodes,api,demo,onHorse,esc){
  try{
    if(!nodes)nodes=new Map((await api('/api/horses?demo='+demo)).map(h=>[h.id,h]));
    if(!target.isConnected)return;
    const summary=historicPedigree(root,nodes),all=summary.rows.filter(r=>r.depth>0);
    target.innerHTML=`<details class="historic-details"><summary>Ascendencia histórica · hasta la época de Nearco (1935)</summary><p>${summary.complete?'Todas las ramas disponibles llegan a 1935 o antes.':`Ampliación pendiente: ${summary.missing} enlaces de progenitores sin documentar antes de alcanzar 1935.`}</p><p>${all.length} ancestros únicos · hasta ${summary.maxDepth} generaciones · ${summary.terminals} ramas alcanzan 1935 o antes.</p><p class="subtle-note">Nearco nació en 1935. El objetivo es esa época en todas las ramas; no todos los caballos descienden de él. Los ancestros repetidos se muestran una vez, con su generación más cercana.</p><input class="input history-search" placeholder="Buscar un ancestro, por ejemplo Nearco…" aria-label="Buscar en la ascendencia histórica"><label class="history-pending-label"><input type="checkbox" class="history-pending"> Mostrar solo ramas pendientes (incluye el caballo consultado)</label><div class="table-scroll"><table class="horse-table"><thead><tr><th>Generación</th><th>Caballo</th><th>Año</th><th>Padre</th><th>Madre</th><th>Pendiente hasta 1935</th></tr></thead><tbody></tbody></table></div><p class="history-count"></p><button class="button light history-more" type="button">Ver 50 más</button></details>`;
    let limit=50,query='',onlyPending=false;
    const button=h=>h?`<button class="horse-name-button" type="button" data-history-id="${esc(h.id)}">${esc(h.name)}</button>`:'Sin registrar';
    function draw(){
      const matches=(onlyPending?summary.rows.filter(r=>unresolvedRoles(r.horse,nodes).length):all).filter(r=>fold(r.horse.name).includes(fold(query)));
      target.querySelector('tbody').innerHTML=matches.slice(0,limit).map(({horse:h,depth})=>`<tr><td>${depth===0?'Caballo consultado':depth}</td><td>${button(h)}<small>${esc(h.id)}</small></td><td>${h.birth_year||'Sin verificar'}</td><td>${button(nodes.get(h.sire_id))}</td><td>${button(nodes.get(h.dam_id))}</td><td>${unresolvedRoles(h,nodes).map(f=>f==='sire_id'?'Padre':'Madre').join(' y ')||'Sin enlaces directos pendientes'}</td></tr>`).join('')||'<tr><td colspan="6">Sin coincidencias con este filtro.</td></tr>';
      target.querySelector('.history-count').textContent=`${Math.min(limit,matches.length)} / ${matches.length} ${onlyPending?'caballos con ramas pendientes':'ancestros'}`;
      target.querySelector('.history-more').hidden=limit>=matches.length;
      target.querySelectorAll('[data-history-id]').forEach(b=>b.onclick=()=>onHorse(b.dataset.historyId));
    }
    target.querySelector('.history-search').oninput=e=>{query=e.target.value;limit=50;draw()};
    target.querySelector('.history-pending').onchange=e=>{onlyPending=e.target.checked;limit=50;draw()};
    target.querySelector('.history-more').onclick=()=>{limit+=50;draw()};draw();
  }catch{if(target.isConnected)target.textContent='No se pudo cargar la ascendencia histórica.'}
}
