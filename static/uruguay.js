export function uruguayPanel({icon}) {
  return `<div id="uruguay-import">
    <div class="uy-section-heading"><span class="tag">🇺🇾 CONECTORES DE URUGUAY</span><h2>Del registro a tu base.</h2><p class="section-description">Consultá los servicios públicos oficiales. Los registros conservan su ID, fuente y fecha de incorporación.</p></div>
    <section class="uy-import-section"><h3>Buscar en el Stud Book Uruguayo</h3><p class="subtle-note">Elegí el ejemplar por su año y sus progenitores. Los nombres parecidos pueden corresponder a caballos distintos.</p>
      <form id="uy-search-form" class="uy-search-form"><label class="field"><span>Nombre del caballo</span><input class="input" id="uy-search" placeholder="Ej.: Invasor, Mad Sharp…" minlength="3" maxlength="120" required></label><button class="button primary" type="submit">${icon('search')} Buscar</button></form>
      <div id="uy-search-results" aria-live="polite"></div>
    </section>
    <section class="uy-import-section"><h3>Resultados de una carrera</h3><p class="subtle-note">Se consulta una carrera por vez. Solo se guardan llegadas numéricas definitivas; si faltan posiciones, se indica cobertura parcial.</p>
      <form id="uy-race-form" class="form-grid"><label class="field full-width"><span>Hipódromo</span><select id="uy-track"><option value="1">Maroñas</option><option value="13">Las Piedras</option><option value="4">Colonia</option><option value="21">Paysandú</option><option value="16">Melo</option></select></label><label class="field"><span>Fecha de la reunión</span><input id="uy-date" class="input" type="date" required></label><label class="field"><span>Número de carrera</span><input id="uy-race-number" class="input" type="number" min="1" max="30" value="1" required></label><button class="button primary full-width" type="submit">${icon('download')} Importar resultados oficiales</button></form>
      <div id="uy-race-message" role="status"></div>
    </section>
    <p class="subtle-note">Las consultas respetan robots.txt y un intervalo mínimo entre solicitudes. La información se actualiza cuando importás; no hay un feed continuo en segundo plano.</p>
  </div>`;
}

export function bindUruguay({api,esc,icon,safeURL,onImported}) {
  const form=document.querySelector('#uy-search-form');
  if(!form)return;
  const results=document.querySelector('#uy-search-results');
  form.onsubmit=async e=>{
    e.preventDefault();
    const button=form.querySelector('button');
    const query=form.querySelector('input').value.trim();
    if(query.length<3)return;
    button.disabled=true;
    results.innerHTML='<div class="subtle-note">Consultando el registro oficial…</div>';
    try{
      const data=await api('/api/uruguay/search?'+new URLSearchParams({q:query}));
      if(!results.isConnected)return;
      results.innerHTML=data.horses.length?`<p class="subtle-note">${data.horses.length} de ${esc(data.count)} coincidencias. Afiná el nombre si no aparece el ejemplar.</p><div class="uy-horse-options">${data.horses.map(h=>`<article class="uy-horse-option"><div><strong>${esc(h.name)}</strong><small>${esc(h.birth_date||'Nacimiento sin registrar')} · ${{M:'Macho',H:'Hembra',C:'Castrado',U:'Sexo sin registrar'}[h.sex]||'Sexo sin registrar'} · ID ${esc(h.id)}</small><p>${esc(h.sire||'Padre sin registrar')} × ${esc(h.dam||'Madre sin registrar')}</p><a href="${safeURL(h.source_url)}" target="_blank" rel="noopener noreferrer" class="text-link">Ver registro de origen ↗</a></div><button class="button light" data-import-uy="${esc(h.id)}">Importar pedigree ${icon('tree')}</button></article>`).join('')}</div>`:'<div class="notice">No se encontraron caballos con ese nombre. Probá un nombre más corto o su variante registrada.</div>';
    }catch(error){if(results.isConnected)results.innerHTML=`<div class="error-message">${esc(error.message)}</div>`}
    finally{button.disabled=false}
  };
  results.onclick=async e=>{
    const button=e.target.closest('[data-import-uy]');
    if(!button||button.disabled)return;
    button.disabled=true;
    button.textContent='Importando…';
    const card=button.closest('article');
    card.querySelector('.uy-import-feedback')?.remove();
    const feedback=document.createElement('div');
    feedback.className='uy-import-feedback';
    card.append(feedback);
    try{
      const data=await api('/api/uruguay/pedigree',{method:'POST',body:JSON.stringify({horse_id:Number(button.dataset.importUy)})});
      await onImported();
      if(!card.isConnected)return;
      feedback.innerHTML=`<div class="success-message">${data.horses} registros incorporados a la base real. <button class="text-link" data-real-horse="${esc(data.horse_id)}">Abrir ficha y pedigree</button></div>`;
      button.textContent='Actualizar pedigree';
    }catch(error){if(card.isConnected)feedback.innerHTML=`<div class="error-message">${esc(error.message)}</div>`;button.textContent='Reintentar importación'}
    finally{button.disabled=false}
  };
  const raceForm=document.querySelector('#uy-race-form');
  const raceMessage=document.querySelector('#uy-race-message');
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Montevideo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  document.querySelector('#uy-date').max=today;
  document.querySelector('#uy-date').value=today;
  raceForm.onsubmit=async e=>{
    e.preventDefault();
    const button=raceForm.querySelector('button');
    button.disabled=true;button.textContent='Consultando carrera y llegadas…';
    raceMessage.innerHTML='';
    try{
      const data=await api('/api/uruguay/results',{method:'POST',body:JSON.stringify({track_id:Number(document.querySelector('#uy-track').value),date:document.querySelector('#uy-date').value,race_number:Number(document.querySelector('#uy-race-number').value)})});
      await onImported();
      if(!raceMessage.isConnected)return;
      raceMessage.innerHTML=`<div class="success-message">${data.results} llegadas guardadas. Cobertura ${data.scope==='full'?'completa':'parcial'}${data.field_size?' de '+data.field_size+' participantes oficiales':''}. <a class="text-link" href="#resultados">Ver resultados de Uruguay</a></div>`;
    }catch(error){if(raceMessage.isConnected)raceMessage.innerHTML=`<div class="error-message">${esc(error.message)}</div>`}
    finally{button.disabled=false;button.innerHTML=`${icon('download')} Importar resultados oficiales`}
  };
}
