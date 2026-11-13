import {exportURL} from './downloads.js';
export function rankingsPage({intro,icon}) {
  return `${intro('La trayectoria en cifras','Los grandes, por sus ganancias.','Rankings con fuente, moneda y país de nacimiento. Uruguay tiene su propio lugar.',`<a class="button light" href="${exportURL()}">${icon('download')} Exportar Excel</a>`)}<p class="notice">Estos rankings usan la base real, incluso si estás explorando ejemplos ficticios. Cada lista conserva el alcance de su fuente: los premios de distintos circuitos y monedas no se suman.</p><div id="rankings-root" aria-live="polite"><div class="loading-state">Consultando rankings guardados…</div></div>`;
}

export async function bindRankings({api,esc,safeURL,icon}) {
  const root=document.querySelector('#rankings-root');
  let request=0;
  const status={complete:'Lista completa',partial:'Importación parcial',blocked:'Pendiente de fuente'};
  const fold=value=>String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
  try {
    const sets=await api('/api/rankings');
    if(!root.isConnected)return;
    if(!sets.length){root.innerHTML='<section class="panel form-panel"><h2>Todavía no hay rankings importados.</h2><p class="subtle-note">Las listas se incorporan desde fuentes verificables, con moneda y cobertura.</p></section>';return}
    root.innerHTML=`<div class="ranking-cards" role="group" aria-label="Seleccionar ranking">${sets.map(s=>`<button class="ranking-card" data-ranking="${esc(s.id)}"><span class="eyebrow">${esc(s.birth_country||'EQUIBASE')}</span><strong>${s.count}<small> / ${s.requested_count}</small></strong><span>${esc(s.title)}</span><span class="tag ${s.status==='complete'?'':'neutral'}">${status[s.status]}</span></button>`).join('')}</div><section id="ranking-detail" class="panel"></section>`;
    async function select(id) {
      const version=++request;
      root.querySelectorAll('[data-ranking]').forEach(b=>{const selected=b.dataset.ranking===id;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected))});
      const target=root.querySelector('#ranking-detail');
      target.innerHTML='<div class="loading-state">Cargando puestos…</div>';
      try {
        const {ranking:s,entries}=await api(`/api/rankings/${encodeURIComponent(id)}`);
        if(!root.isConnected||version!==request)return;
        target.innerHTML=`<div class="panel-header ranking-header"><div><span class="eyebrow">${esc(s.currency||'MONEDA A CONFIRMAR')} · ${esc(s.observed_at.slice(0,10))}</span><h2>${esc(s.title)}</h2><p>${esc(s.scope)}</p></div><a class="button text" href="${safeURL(s.source_url)}" target="_blank" rel="noopener noreferrer">Ver fuente ${icon('external')}</a></div><div class="ranking-method"><p>${esc(s.methodology)}</p>${s.blocker?`<div class="notice">${esc(s.blocker)}</div>`:''}</div>${entries.length?'<div class="toolbar ranking-toolbar"><div class="search-field"><input class="input" id="ranking-search" aria-label="Buscar en este ranking" placeholder="Buscar entre los puestos guardados…"></div><span class="count" id="ranking-count"></span></div><div class="table-scroll"><table class="horse-table ranking-table"><thead><tr><th>Puesto</th><th>Caballo</th><th>Nacimiento</th><th>Ganancias</th><th>Ficha</th></tr></thead><tbody id="ranking-rows"></tbody></table></div>':'<div class="empty-state"><h3>Sin puestos verificados todavía.</h3><p>Esta lista necesita una fuente histórica que permita verificar el país de nacimiento y las ganancias.</p></div>'}`;
        if(!entries.length)return;
        const money=new Intl.NumberFormat('es-UY',{style:'currency',currency:s.currency,currencyDisplay:'code',maximumFractionDigits:2});
        function draw(query='') {
          const filtered=entries.filter(h=>fold(h.name).includes(fold(query)));
          target.querySelector('#ranking-count').textContent=`${filtered.length} / ${entries.length} caballos`;
          target.querySelector('#ranking-rows').innerHTML=filtered.length?filtered.map(h=>`<tr><td><span class="ranking-position">${h.position}</span></td><td><button class="horse-name-button" data-real-horse="${esc(h.horse_id)}">${esc(h.name)}</button><small class="ranking-birth">${esc(h.birth_year||'Año sin verificar')}</small></td><td>${esc(h.birth_country||'Sin verificar')}</td><td class="ranking-earnings">${esc(money.format(h.earnings))}</td><td><button class="table-arrow" data-real-horse="${esc(h.horse_id)}" aria-label="Ver pedigree de ${esc(h.name)}">${icon('tree')}</button><small class="ranking-birth">${h.pedigree_known??'—'} / 14</small></td></tr>`).join(''):'<tr><td colspan="5">Ningún caballo coincide con la búsqueda.</td></tr>';
        }
        target.querySelector('#ranking-search').oninput=e=>draw(e.target.value);
        draw();
      } catch(e) {if(root.isConnected&&version===request)target.innerHTML=`<div class="error-message">${esc(e.message)}</div>`}
    }
    root.querySelectorAll('[data-ranking]').forEach(b=>b.onclick=()=>select(b.dataset.ranking));
    await select(sets.find(s=>s.id==='uru-100'&&s.count)?.id||sets[0].id);
  } catch(e) {if(root.isConnected)root.innerHTML=`<div class="error-message">${esc(e.message)}</div>`}
}
