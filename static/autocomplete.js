const fold=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
export function suggest(input,getHorses,onChoose,{onType=()=>{},open=false}={}) {
  const box=document.createElement('div');box.className='horse-suggestions';box.id=input.id+'-options';box.setAttribute('role','listbox');box.hidden=true;
  input.parentElement.classList.add('suggestion-host');input.after(box);
  input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',box.id);input.setAttribute('aria-expanded','false');input.autocomplete='off';
  let matches=[],active=-1;
  function close(){box.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1}
  function choose(h){input.value=h.name;close();onChoose(h)}
  function draw(){
    const q=fold(input.value);close();box.replaceChildren();if(q.length<3)return;
    const all=getHorses().filter(h=>fold(h.name).includes(q)).sort((a,b)=>Number(fold(b.name).startsWith(q))-Number(fold(a.name).startsWith(q))||a.name.localeCompare(b.name));matches=all.slice(0,12);
    for(const [i,h] of matches.entries()){
      const item=document.createElement('div');item.id=box.id+'-'+i;item.setAttribute('role','option');item.setAttribute('aria-selected','false');item.className='horse-suggestion';
      const title=document.createElement('strong');title.textContent=h.name;const detail=document.createElement('small');detail.textContent=`${h.birth_year||'Año sin registrar'} · ${h.country} · ${h.id}`;item.append(title,detail);
      item.onpointerdown=e=>e.preventDefault();item.onclick=()=>choose(h);box.append(item);
    }
    const note=document.createElement('small');note.className='suggestion-count';note.textContent=all.length?`${all.length} coincidencias${all.length>12?' · Escribí más letras para afinar':''}`:'No hay coincidencias en esta base.';box.append(note);box.hidden=false;input.setAttribute('aria-expanded','true');
  }
  input.addEventListener('input',()=>{onType();draw()});input.addEventListener('focus',draw);input.addEventListener('blur',close);
  input.addEventListener('keydown',e=>{
    if(e.key==='Escape'){close();return}
    if(['ArrowDown','ArrowUp'].includes(e.key)){
      e.preventDefault();if(box.hidden)draw();if(!matches.length||box.hidden)return;
      active=active<0?(e.key==='ArrowDown'?0:matches.length-1):(active+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length;
      box.querySelectorAll('[role=option]').forEach((el,i)=>el.setAttribute('aria-selected',String(i===active)));
      input.setAttribute('aria-activedescendant',box.id+'-'+active);document.getElementById(box.id+'-'+active).scrollIntoView({block:'nearest'});
    }
    if(e.key==='Enter'&&!box.hidden&&active>=0){e.preventDefault();choose(matches[active])}
  });
  if(open)draw();return close;
}
