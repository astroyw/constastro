// Wright's pedigree method, shared by the static edition and its parity checks.
export function validateGraph(horses) {
  const nodes=new Map(horses.map(h=>[h.id,h])),visiting=new Set(),done=new Set();
  function visit(id) {
    if(visiting.has(id))throw new Error('El pedigree contiene un ciclo de parentesco.');
    if(done.has(id))return;
    const h=nodes.get(id);
    if(!h)throw new Error(`Falta el registro del progenitor ${id}.`);
    visiting.add(id);
    if(visiting.size>100)throw new Error('El pedigree supera 100 generaciones encadenadas.');
    if(h.sire_id&&h.sire_id===h.dam_id)throw new Error('Un caballo no puede tener el mismo padre y madre.');
    for(const [key,sex] of [['sire_id','M'],['dam_id','H']]) {
      if(!h[key])continue;
      visit(h[key]);
      const p=nodes.get(h[key]);
      if(![sex,'U'].includes(p.sex||'U'))throw new Error('El sexo de un progenitor no coincide con su relación.');
      if(h.birth_year&&p.birth_year&&p.birth_year>=h.birth_year)throw new Error('Un progenitor debe haber nacido antes que su descendiente.');
    }
    visiting.delete(id);done.add(id);
  }
  for(const id of nodes.keys())visit(id);
  return nodes;
}

export function pedigree(id,nodes,generations=3) {
  function branch(ident,depth,path) {
    if(depth>generations)return null;
    const h=nodes.get(ident);
    return {...(h||{id:null,name:'Sin registrar'}),depth,path,
      sire:branch(h?.sire_id,depth+1,path+'s'),dam:branch(h?.dam_id,depth+1,path+'d')};
  }
  return branch(id,0,'');
}

export function analyze(sireId,damId,horses) {
  const nodes=validateGraph(horses);
  if(!nodes.has(sireId)||!nodes.has(damId))throw new Error('Seleccioná dos caballos registrados.');
  if(sireId===damId)throw new Error('Seleccioná dos caballos diferentes.');
  if(nodes.get(sireId).sex!=='M'||nodes.get(damId).sex!=='H')throw new Error('El cruce requiere un padrillo y una yegua con sexo registrado.');
  const ranks=new Map(),coefficients=new Map();
  function rank(id) {
    if(!id)return -1;
    if(!ranks.has(id)) {
      const h=nodes.get(id);
      ranks.set(id,1+Math.max(rank(h.sire_id),rank(h.dam_id)));
    }
    return ranks.get(id);
  }
  function kinship(a,b) {
    if(!a||!b)return 0;
    const key=JSON.stringify([a,b]);
    if(coefficients.has(key))return coefficients.get(key);
    let result;
    if(a===b) {
      const h=nodes.get(a);result=(1+kinship(h.sire_id,h.dam_id))/2;
    } else {
      if(rank(a)<rank(b))[a,b]=[b,a];
      const h=nodes.get(a);result=(kinship(h.sire_id,b)+kinship(h.dam_id,b))/2;
    }
    coefficients.set(key,result);return result;
  }
  function ancestors(id) {
    const found=new Map();let count=0;
    function walk(ident,depth) {
      if(!ident||depth>3)return;
      if(depth){count++;if(!found.has(ident))found.set(ident,new Set());found.get(ident).add(depth)}
      const h=nodes.get(ident);walk(h.sire_id,depth+1);walk(h.dam_id,depth+1);
    }
    walk(id,0);return {found,count};
  }
  const a=ancestors(sireId),b=ancestors(damId);
  const shared=[...a.found.keys()].filter(id=>b.found.has(id)).sort().map(id=>({id,name:nodes.get(id).name,
    sire_generations:[...a.found.get(id)].sort(),dam_generations:[...b.found.get(id)].sort()}));
  // Coefficients are binary fractions. Match Python's even rounding at exact
  // decimal midpoints (e.g. 0.1953125%), rather than JavaScript's toFixed rule.
  const scaled=kinship(sireId,damId)*100*1e6,whole=Math.floor(scaled),fraction=scaled-whole;
  const rounded=fraction>.5||fraction===.5&&whole%2?whole+1:whole;
  return {coefficient:rounded/1e6,coverage:Number(((a.count+b.count)/28*100).toFixed(1)),
    known_slots:a.count+b.count,total_slots:28,shared_ancestors:shared,
    method:'Coeficiente de consanguinidad esperado de la cría (Wright). Usa todos los ancestros guardados; cobertura y lista compartida muestran las primeras tres generaciones.',
    limitations:'Los fundadores sin datos se consideran no emparentados. Un valor bajo con pedigree incompleto puede subestimar la consanguinidad. No es una prueba de ADN ni predice salud, fertilidad o rendimiento. Consultá a un veterinario genetista antes de decidir un cruce.'};
}
