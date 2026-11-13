"""Resume campaigns for ALL existing records; preserve source-scoped coverage.

Run without --limit to traverse the entire source queue. Caches are immutable
observations and access challenges stop that host. No guessed or synthetic starts.
"""
import argparse,gzip,json,sys,re,unicodedata
from collections import Counter
from datetime import date,datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import db,uruguay
from app.argentina import parse_profile,parse_campaign,campaign_report
from app.campaigns import parse_maronas_campaign,coverage,verify_identity
from app.main import save_batch
from app.scraper import fetch_public,fetch_public_json,source_by_id,ScrapeError
from app.verification import normalized_name
from app.ancestry import original_targets

CACHE=ROOT/'data'/'full_campaign_cache'


def archive():
    horses=db.horse_rows(False);reviews=db.campaign_reviews()
    with db.connection() as con:
        rows=[db.result_record(r) for r in con.execute('SELECT * FROM results WHERE is_demo=0 ORDER BY id')]
    report=coverage(horses,rows,reviews)
    payload={'updated_at':db.now(),'scope':report['scope'],'results':rows,'reviews':reviews,
             'summary':{k:v for k,v in report.items() if k!='horses'}}
    path=ROOT/'samples'/'campaign_results.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2));tmp.replace(path)
    print(json.dumps(payload['summary'],ensure_ascii=False),flush=True)


def safe_save(rows):
    # Existing facts must agree. C -> Césped is an explicit code normalization.
    with db.connection() as con:
        old={r['id']:dict(r) for r in con.execute('SELECT * FROM results WHERE is_demo=0')}
    for r in rows:
        for f in ('horse_id','position','distance','surface','date','race_id'):
            a=old.get(r['id'],{}).get(f);b=r.get(f)
            if f=='surface' and r['id'].startswith('ar-result:') and a=='C' and b=='Césped':continue
            if a not in (None,'') and b not in (None,'') and a!=b:
                raise ScrapeError(f'La actuación {r["id"]} contradice el campo conocido {f}.')
    if rows:save_batch([],rows)


def unavailable(ident,source,url,error):
    return {'horse_id':ident,'source_id':source,'status':'unavailable','expected_starts':None,'observed_starts':0,
            'source_url':url,'observed_at':db.now(),'scope':'Consulta individual de campaña en la fuente indicada.',
            'message':str(error)[:1500]}


def argentina(limit):
    nodes={h['id']:h for h in db.horse_rows(False)};targets=original_targets()
    with db.connection() as con:ranked={r[0] for r in con.execute('SELECT horse_id FROM ranking_entries')}
    candidates=sorted((h for h in nodes.values() if h['id'].startswith('ar-studbook:')),
                      key=lambda h:(h['id'] not in ranked,h['id'] not in targets,-(h.get('birth_year') or 0),h['id']))
    source=source_by_id('ar-studbook');done=0;consecutive_errors=0
    reviewed={r['horse_id'] for r in db.campaign_reviews() if r['source_id']=='ar-studbook'}
    for h in candidates:
        path=CACHE/(h['id'].replace(':','-')+'.json')
        if path.exists() or h['id'] in reviewed:continue
        slug=re.sub(r'[^a-z0-9]+','-',''.join(c for c in unicodedata.normalize('NFKD',h['name'].lower()) if not unicodedata.combining(c))).strip('-')
        url='https://www.studbook.org.ar/ejemplares/perfil/'+h['id'].split(':')[1]+'/'+slug
        try:
            raw_path=path.with_suffix('.html.gz')
            if raw_path.exists():
                with gzip.open(raw_path,'rt',encoding='utf-8') as f:html=f.read()
                observed_at=datetime.fromtimestamp(raw_path.stat().st_mtime,timezone.utc).isoformat(timespec='seconds')
            else:
                html=fetch_public(url,source);observed_at=db.now()
                with gzip.open(raw_path,'wt',encoding='utf-8') as f:f.write(html)
            identity=next(x for x in parse_profile(html,url,max_generations=1,allow_missing_ids=True) if x['id']==h['id'])
            identity['fetched_at']=observed_at
            if normalized_name(identity['name'])!=normalized_name(h['name']) or (identity.get('birth_year') and h.get('birth_year') and identity['birth_year']!=h['birth_year']):
                raise ScrapeError('La identidad de la ficha contradice el nombre o nacimiento del registro.')
            from bs4 import BeautifulSoup
            present=bool(BeautifulSoup(html,'html.parser').select_one('table.carreras'))
            rows=parse_campaign(html,url,quarantine_conflicts=True) if present else []
            review=campaign_report(html,url,rows)
            review['observed_at']=observed_at
            for row in rows:row['fetched_at']=observed_at
            if not present:review['message']='La ficha no publica una tabla de actuaciones ni un total verificable. No se deduce que el caballo nunca corrió.'
            safe_save(rows)
            observation={'identity':identity,'results':rows,'review':review}
        except Exception as exc:
            review=unavailable(h['id'],'ar-studbook',url,exc)
            observation={'review':review,'results':[]}
        db.save_campaign_review(h['id'],'ar-studbook',review)
        path.write_text(json.dumps(observation,ensure_ascii=False,indent=2))
        done+=1
        consecutive_errors=consecutive_errors+1 if review['status']=='unavailable' else 0
        if done%10==0:print('Argentina:',done,'fichas nuevas; última:',h['name'],review['status'],flush=True)
        if done%50==0:archive()
        if review['status']=='unavailable' and any(x in review['message'] for x in ('robots.txt','verificación humana','HTTP 429','HTTP 403')):
            print('Consulta de la fuente detenida:',review['message'],flush=True);break
        if consecutive_errors>=3:
            print('Fuente detenida tras tres errores consecutivos. Las fichas restantes siguen pendientes.',flush=True);break
        if limit and done>=limit:break
    archive()


def uruguayan(limit):
    nodes={h['id']:h for h in db.horse_rows(False)}
    with db.connection() as con:
        mappings={r['horse_id']:int(r['source_horse_id']) for r in con.execute("SELECT * FROM ranking_entries WHERE ranking_id='uru-100'")}
    # Extra cached official cards can match any original or added record, but only
    # with name, year, both parents and any known country/sex corroborated.
    for path in (ROOT/'data'/'ranking_cache').glob('maronas-card-*.json'):
        observed=json.loads(path.read_text())['data']['Horse'];matches=[]
        for h in nodes.values():
            if normalized_name(h['name'])!=normalized_name(observed.get('Name','')):continue
            try:verify_identity(h,observed,nodes);matches.append(h['id'])
            except ScrapeError:pass
        if len(matches)==1:mappings[matches[0]]=observed['Id']
    done=0;consecutive_errors=0
    reviewed={r['horse_id'] for r in db.campaign_reviews() if r['source_id']=='uy-maronas'}
    for ident,remote in mappings.items():
        path=CACHE/f'uy-maronas-{remote}.json'
        if path.exists() or ident in reviewed:continue
        url=f'https://hipica.maronas.com.uy/RacingInfo/HorseCard?HorseId={remote}'
        try:
            card=fetch_public_json(uruguay.MARONAS_API+'GetHorseCard',source_by_id('uy-maronas'),payload={
                'horseId':remote,'toDateTime':date.today().isoformat()+'T23:59:59','withPerformances':True,'sessionInfo':None})
            rows,review=parse_maronas_campaign(card,nodes[ident],remote,nodes)
            safe_save(rows)
            observation={'horse_id':ident,'source_horse_id':remote,'results':rows,'review':review,
                         'identity':{k:card['Horse'].get(k) for k in ('Id','Name','BirthDate','Sex','Country','Sire','Mare')}}
        except Exception as exc:
            review=unavailable(ident,'uy-maronas',url,exc);observation={'horse_id':ident,'review':review,'results':[]}
        db.save_campaign_review(ident,'uy-maronas',review)
        path.write_text(json.dumps(observation,ensure_ascii=False,indent=2))
        done+=1
        consecutive_errors=consecutive_errors+1 if review['status']=='unavailable' else 0
        if done%10==0:print('Uruguay:',done,'fichas nuevas; última:',nodes[ident]['name'],review['status'],flush=True)
        if done%50==0:archive()
        if review['status']=='unavailable' and any(x in review['message'] for x in ('robots.txt','verificación humana','HTTP 429','HTTP 403')):
            print('Consulta de la fuente detenida:',review['message'],flush=True);break
        if consecutive_errors>=3:
            print('Fuente detenida tras tres errores consecutivos. Las fichas restantes siguen pendientes.',flush=True);break
        if limit and done>=limit:break
    archive()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',choices=['argentina','uruguay','archive']);p.add_argument('--limit',type=int,default=0)
    p.add_argument('--retry-errors',action='store_true',help='Retry previous unavailable observations; keep valid earlier data.')
    args=p.parse_args();CACHE.mkdir(parents=True,exist_ok=True);db.init()
    if args.retry_errors and args.source!='archive':
        source='ar-studbook' if args.source=='argentina' else 'uy-maronas'
        with db.connection() as con:
            con.execute("DELETE FROM campaign_reviews WHERE source_id=? AND status='unavailable'",(source,))
        for path in CACHE.glob(source+'-*.json'):
            if json.loads(path.read_text()).get('review',{}).get('status')=='unavailable':path.unlink()
    {'argentina':lambda:argentina(args.limit),'uruguay':lambda:uruguayan(args.limit),'archive':archive}[args.source]()
