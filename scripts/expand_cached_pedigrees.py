"""Recover fourth-generation facts already returned by the original public requests."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import db,uruguay
from app.main import save_batch
for path in sorted((ROOT/'data'/'ranking_cache').glob('uy-tree-*.json')):
 number=int(path.stem.rsplit('-',1)[-1]);cached=json.loads(path.read_text());profile_path=path.with_name(f'uy-profile-{number}.json')
 profile=json.loads(profile_path.read_text())['data'] if profile_path.exists() else {'id':number}
 try:
  records=uruguay.parse_pedigree(cached['data'],profile,max_generations=4)
  existing={h['id']:h for h in db.horse_rows(False)}
  for r in records:
   r['fetched_at']=cached['retrieved_at'];r['featured']=False
   for field in ('sire_id','dam_id'):
    if r.get(field) and existing.get(r['id'],{}).get(field) and r[field]!=existing[r['id']][field]:raise ValueError('Conflicting known parent')
  save_batch(records,[])
 except Exception as e:print(path.name,str(e),flush=True)
print('Cached fourth generations recovered;',len(db.horse_rows(False)),'records')
