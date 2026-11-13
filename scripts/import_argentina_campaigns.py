"""Archive publicly displayed starts for original Argentine ranking targets.

Stable SBARG IDs link starts to horses. These are individual campaign tables,
not complete race fields or a claim of complete lifetime campaigns.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db
from app.ancestry import original_targets
from app.argentina import parse_campaign,parse_profile
from app.main import save_batch
from app.scraper import fetch_public,source_by_id
from app.verification import normalized_name

CACHE=ROOT/'data'/'campaign_cache'


def main(limit=100):
    CACHE.mkdir(exist_ok=True,parents=True)
    nodes={h['id']:h for h in db.horse_rows(False)}
    targets=original_targets()
    with db.connection() as con:
        candidates=[dict(r) for r in con.execute("SELECT horse_id,source_url FROM ranking_entries WHERE ranking_id='arg-100' ORDER BY position")]
    report={'scope':'Actuaciones numéricas publicadas en tablas individuales de los objetivos originales del ranking argentino. No son campos completos ni campañas necesariamente completas.',
            'updated_at':db.now(),'profiles':[]}
    source=source_by_id('ar-studbook')
    for candidate in candidates[:limit]:
        ident=candidate['horse_id'];url=candidate['source_url']
        if ident not in targets or ident not in nodes:continue
        path=CACHE/(ident.replace(':','-')+'.json')
        try:
            if path.exists():data=json.loads(path.read_text())
            else:
                html=fetch_public(url,source)
                identity=next(h for h in parse_profile(html,url,max_generations=1,allow_missing_ids=True) if h['id']==ident)
                data={'profile_url':url,'observed_at':db.now(),
                      'horse_identity':{k:identity.get(k) for k in ('id','name','birth_year')},
                      'results':parse_campaign(html,url)}
                path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
            identity=data['horse_identity'];current=nodes[ident]
            if identity['id']!=ident or normalized_name(identity['name'])!=normalized_name(current['name']):
                raise ValueError('La identidad de la ficha no coincide con el registro existente.')
            if identity.get('birth_year') and current.get('birth_year') and identity['birth_year']!=current['birth_year']:
                raise ValueError('El nacimiento de la ficha contradice el registro existente.')
            with db.connection() as con:
                existing={r['id']:dict(r) for r in con.execute('SELECT * FROM results WHERE horse_id=?',(ident,))}
            for r in data['results']:
                if r['horse_id']!=ident:raise ValueError('La campaña contiene otro ID de ejemplar.')
                old=existing.get(r['id'],{})
                for f in ('horse_id','position','distance','surface','date','track','race_id'):
                    if old.get(f) not in (None,'') and r.get(f) not in (None,'') and old[f]!=r[f]:
                        raise ValueError(f'La actuación {r["id"]} contradice el campo conocido {f}.')
            saved=save_batch([],data['results'])
            report['profiles'].append({'id':ident,'url':url,'status':'imported','results':saved['results'],'observed_at':data['observed_at']})
        except Exception as e:
            report['profiles'].append({'id':ident,'url':url,'status':'pending','reason':str(e)})
            print(json.dumps(report['profiles'][-1],ensure_ascii=False),flush=True)
            if any(s in str(e) for s in ('robots.txt','verificación humana','HTTP 429','HTTP 403')):break
        if len(report['profiles'])%10==0:
            print('Perfiles revisados:',len(report['profiles']),'Actuaciones documentadas:',sum(p.get('results',0) for p in report['profiles']),flush=True)
    with db.connection() as con:
        results=[dict(r) for r in con.execute("SELECT * FROM results WHERE is_demo=0 AND horse_id IN (SELECT horse_id FROM ranking_entries WHERE ranking_id='arg-100') ORDER BY id")]
    report['results']=results
    (ROOT/'samples'/'campaign_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('Campañas archivadas:',len(results),'actuaciones;',sum(p['status']=='imported' for p in report['profiles']),'perfiles importados.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=100)
    main(parser.parse_args().limit)
