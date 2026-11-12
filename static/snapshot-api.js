import {analyze,pedigree} from './genetics.js';

export function createSnapshotAPI(data) {
  const maps={real:new Map(data.horses.real.map(h=>[h.id,h])),demo:new Map(data.horses.demo.map(h=>[h.id,h]))};
  return async function api(path,options={}) {
    const url=new URL(path,'https://linaje.invalid'),p=url.pathname,method=(options.method||'GET').toUpperCase();
    const demo=url.searchParams.get('demo')==='true',mode=demo?'demo':'real';
    if(method==='POST'&&p==='/api/compatibility') {
      const body=JSON.parse(options.body);
      return analyze(body.sire_id,body.dam_id,data.horses[body.demo?'demo':'real']);
    }
    if(method!=='GET')throw new Error('Las incorporaciones se realizan durante el mantenimiento de la base.');
    if(p==='/api/config')return {read_only:true,reference_checks:data.reference_checks||[]};
    if(p==='/api/health')return {status:'ok',edition:'static'};
    if(p==='/api/countries')return data.countries;
    if(p==='/api/sources')return data.sources;
    if(p==='/api/stats')return data.stats[mode];
    if(p==='/api/horses') {
      const country=url.searchParams.get('country'),q=(url.searchParams.get('q')||'').toLocaleLowerCase();
      return data.horses[mode].filter(h=>(!country||h.country===country)&&(!q||h.name.toLocaleLowerCase().includes(q))&&(url.searchParams.get('featured')!=='true'||h.featured));
    }
    if(p.startsWith('/api/horses/')) {
      const id=decodeURIComponent(p.slice('/api/horses/'.length)),horse=maps[mode].get(id);
      if(!horse)throw new Error('No se encontró el caballo en esta base.');
      return {horse,original_target:demo?null:(data.original_targets||[]).includes(id),verification:demo?null:data.verification?.[id],pedigree:pedigree(id,maps[mode]),campaign:demo?[]:data.results.filter(r=>r.horse_id===id)};
    }
    if(p==='/api/rankings')return data.ranking_sets;
    if(p.startsWith('/api/rankings/')) {
      const ranking=data.rankings.find(r=>r.ranking.id===decodeURIComponent(p.slice('/api/rankings/'.length)));
      if(!ranking)throw new Error('No se encontró ese ranking.');
      return ranking;
    }
    if(p==='/api/results') {
      const country=url.searchParams.get('country')||'URU',track=url.searchParams.get('track'),date=url.searchParams.get('on_date');
      return data.results.filter(r=>r.country===country&&(!track||r.track===track)&&(!date||r.date===date));
    }
    throw new Error('Esta consulta no está disponible en la edición publicada.');
  };
}

let snapshot;
export async function api(path,options) {
  if(!snapshot)snapshot=fetch('/data/site.json').then(r=>{
    if(!r.ok)throw new Error('No se pudo cargar la base publicada.');
    return r.json();
  }).then(createSnapshotAPI).catch(e=>{snapshot=undefined;throw e});
  return (await snapshot)(path,options);
}
