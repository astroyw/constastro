"""Resume official pedigrees until every available branch reaches 1935 or earlier.
Unresolved source leaves remain explicitly unresolved; names never merge IDs.
"""
import argparse,json,sys,threading,re,unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import db,uruguay
from app.argentina import parse_profile
from app.main import save_batch
from app.scraper import fetch_public,fetch_public_json,source_by_id

CACHE=ROOT/'data'/'deep_pedigree';CACHE.mkdir(parents=True,exist_ok=True)
LOCK=threading.Lock()
TARGET_PATH=ROOT/'data'/'pedigree_original_ids.json'
if not TARGET_PATH.exists():TARGET_PATH=ROOT/'samples'/'pedigree_targets.json'
TARGETS=set(json.loads(TARGET_PATH.read_text()))

def required_nodes(nodes):
 # Fixed original cohort; newly discovered ancestors are only traversed along
 # the branches needed to reach 1935, never promoted to new target horses.
 seen=set();queue=list(TARGETS)
 while queue:
  ident=queue.pop()
  if ident in seen:continue
  seen.add(ident);h=nodes.get(ident)
  if not h or (h.get('birth_year') and h['birth_year']<=1935):continue
  queue.extend(h[k] for k in ('sire_id','dam_id') if h.get(k))
 return seen

def atomic(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(path)

def run(source_id,limit):
 path=CACHE/(source_id+'-progress.json')
 progress=json.loads(path.read_text()) if path.exists() else {'attempted':{},'queries':0}
 tried=set(progress['attempted']);done=0
 while True:
  with LOCK:nodes={h['id']:h for h in db.horse_rows(False)}
  required=required_nodes(nodes)
  candidates=[h for h in nodes.values() if h['id'] in required and h['source_id']==source_id and (not h['birth_year'] or h['birth_year']>1935) and (not h['sire_id'] or not h['dam_id']) and h['id'] not in tried]
  if not candidates or (limit and done>=limit):break
  # Older shared ancestors connect many modern pedigrees and reach the target era sooner.
  h=min(candidates,key=lambda h:(h['birth_year'] or 9999,h['id']));ident=h['id'];tried.add(ident);done+=1
  records=None
  try:
   cache=CACHE/(ident.replace(':','-')+'.json')
   if cache.exists():records=json.loads(cache.read_text())['horses']
   elif source_id=='uy-studbook':
    number=int(ident.split(':')[1]);old=ROOT/'data'/'ranking_cache'/f'uy-tree-{number}.json'
    tree=json.loads(old.read_text())['data'] if old.exists() else fetch_public_json(uruguay.STUDBOOK_API+f'horse/pedigree/{number}',source_by_id(source_id))
    records=uruguay.parse_pedigree(tree,{'id':number,'sex':h['sex']},max_generations=4)
   else:
    slug=re.sub('[^a-z0-9]+','-',unicodedata.normalize('NFKD',h['name']).encode('ascii','ignore').decode().lower()).strip('-')
    url='https://www.studbook.org.ar/ejemplares/perfil/'+ident.split(':')[1]+'/'+slug
    records=parse_profile(fetch_public(url,source_by_id(source_id)),url,max_generations=4,allow_missing_ids=True)
   for r in records:r['featured']=False
   with LOCK:
    # Fail on conflicting known links instead of silently replacing genealogy.
    existing={n['id']:n for n in db.horse_rows(False)}
    for r in records:
     old=existing.get(r['id'],{})
     for field in ('sire_id','dam_id'):
      if r.get(field) and old.get(field) and r[field]!=old[field]:raise ValueError(f'Conflicting {field} for {r["id"]}')
    save_batch(records,[])
   atomic(cache,{'horses':records})
   progress['attempted'][ident]={'status':'expanded','name':h['name'],'records':len(records)}
  except Exception as error:
   if records:
    rejected=CACHE/'rejected';rejected.mkdir(exist_ok=True)
    atomic(rejected/(ident.replace(':','-')+'.json'),{'reason':str(error),'horses':records})
   progress['attempted'][ident]={'status':'unresolved','name':h['name'],'reason':str(error)}
   print(json.dumps({'source':source_id,'id':ident,'error':str(error)},ensure_ascii=False),flush=True)
   if 'robots.txt' in str(error) or 'verificación humana' in str(error):
    progress['blocked']=str(error);atomic(path,progress);break
  progress['queries']+=1;atomic(path,progress)
  if done%10==0:print(json.dumps({'source':source_id,'processed':done,'remaining_frontier':len(candidates)-1,'records':len(nodes)},ensure_ascii=False),flush=True)
 print(json.dumps({'source':source_id,'finished_batch':done,'attempted_total':len(progress['attempted'])}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
 db.init()
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(run,source,args.limit) for source in ('uy-studbook','ar-studbook')]
  for future in futures:future.result()
