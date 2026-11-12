"""Freeze an attributed snapshot and a per-original-horse audit for publication."""
import csv,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import db
from app.ancestry import audit,pending_branches
from app.genetics import validate_graph
from app.verification import compare_all
from app.evidence import collect_evidence

horses=db.horse_rows(False);nodes={h['id']:h for h in horses};validate_graph(horses)
target_path=ROOT/'data'/'pedigree_original_ids.json'
if not target_path.exists():target_path=ROOT/'samples'/'pedigree_targets.json'
original=json.loads(target_path.read_text())
assert len(original)==2452 and all(i in nodes for i in original)
evidence=collect_evidence(horses)
(ROOT/'samples'/'pedigree_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
checks=compare_all(horses,evidence)
rows=[{'id':i,'name':nodes[i]['name'],'source_url':nodes[i]['source_url'],'ancestry':audit(i,nodes),'verification':checks[i]} for i in original]
summary={'generated_at':db.now(),'target_birth_year':1935,'original_targets':len(original),'records_after_expansion':len(horses),'added_records':len(horses)-len(original),
         'trees_complete':sum(r['ancestry']['complete'] for r in rows),'trees_pending':sum(not r['ancestry']['complete'] for r in rows),
         'verification_status':dict(Counter(r['verification']['status'] for r in rows)),
         'all_data_two_sources_verified':sum(r['verification']['all_data_verified'] for r in rows),
         'scope':'Targets fixed before expansion. New ancestors only support their branches until documented birth <=1935. Distinct publisher records are compared without merging identities. Earnings and campaigns still lack independent corroboration.'}
pending=pending_branches(nodes,original)
summary['unique_pending_relationships']=len(pending)
(ROOT/'samples'/'extended_pedigrees.json').write_text(json.dumps({'summary':summary,'horses':horses},ensure_ascii=False,indent=2))
(ROOT/'samples'/'pedigree_review.json').write_text(json.dumps({'summary':summary,'horses':rows,'pending_branches':pending},ensure_ascii=False,indent=2))
(ROOT/'samples'/'pedigree_targets.json').write_text(json.dumps(original))
with (ROOT/'exports'/'Linaje_revision_pedigrees.csv').open('w',newline='',encoding='utf-8-sig') as f:
 writer=csv.writer(f);writer.writerow(['ID','Nombre','Arbol hasta 1935','Ancestros unicos','Generaciones','Enlaces pendientes','Contraste','Campos corroborados','Fuente'])
 for r in rows:
  a=r['ancestry'];v=r['verification'];writer.writerow([r['id'],r['name'],'Completo' if a['complete'] else 'Pendiente',a['ancestor_count'],a['max_generation'],a['missing_links'],v['status'],', '.join(v['confirmed_fields']),r['source_url']])
print(json.dumps(summary,ensure_ascii=False,indent=2))
