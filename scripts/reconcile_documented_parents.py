"""Add only missing facts, supported by unique parent identity of corroborated children."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import db
from app.evidence import collect_evidence
from app.main import save_batch
from app.reconciliation import proposals
from scripts.expand_pedigrees import required_nodes
path=ROOT/'samples'/'pedigree_reconciliations.json'
report=json.loads(path.read_text()) if path.exists() else {'method':'documented-child-parent-v1','applied':[],'rejected':[]}
nodes={h['id']:h for h in db.horse_rows(False)}
candidates=proposals(list(nodes.values()),collect_evidence(list(nodes.values())),required_nodes(nodes))
for p in candidates:
 with db.connection() as con:h=dict(con.execute('SELECT * FROM horses WHERE id=?',(p['id'],)).fetchone())
 fields={k:v for k,v in p['fields'].items() if not h.get(k)}
 if not fields:continue
 note=' Complemento documentado de '+p['counterpart_id']+' ('+p['source_url']+'); identidad como progenitor de un hijo corroborado en dos Stud Books. Ver auditoría de conciliación; el dato complementado puede tener una sola fuente.'
 try:
  save_batch([{'id':h['id'],'name':h['name'],**fields,'notes':h['notes'][:max(0,2000-len(note))]+note}],[])
  h.update(fields);p['fields']=fields;p['applied_at']=db.now();report['applied'].append(p)
 except ValueError as e:report['rejected'].append({**p,'reason':str(e)})
path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('Propuestas',len(candidates),'complementos documentados acumulados',len(report['applied']),'rechazados acumulados',len(report['rejected']))
