"""Create an attributed, reproducible archive of the reviewed public ranking records."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db
from app.rankings import get_ranking


def main():
    db.init()
    batches=[get_ranking(ident) for ident in ('equibase-200','uru-100','arg-100','bra-100')]
    if any(batch is None for batch in batches):raise SystemExit('Faltan metadatos de rankings.')
    for batch,count in zip(batches[:2],(200,100)):
        if batch['ranking']['status']!='complete' or len(batch['entries'])!=count:
            raise SystemExit('Esperar a que Equibase y Uruguay terminen antes de archivar.')
    if any(e['pedigree_known']!=14 for e in batches[1]['entries']):
        raise SystemExit('Revisar los pedigrees uruguayos incompletos antes de publicar la muestra.')
    arg=batches[2]
    if arg['entries'] and (arg['ranking']['status']!='complete' or len(arg['entries'])!=100 or any(e['pedigree_known']!=14 for e in arg['entries'])):
        raise SystemExit('Completar la validación del ranking y de los 100 pedigrees argentinos antes de archivar.')
    nodes={h['id']:h for h in db.horse_rows(False)}
    selected={}
    def include(ident):
        if not ident or ident in selected:return
        h=nodes[ident]
        if h['source_id'] not in ('us-equibase','uy-studbook','uy-maronas','ar-studbook'):
            raise ValueError('La muestra sólo debe contener registros de las fuentes públicas revisadas.')
        selected[ident]=h
        include(h.get('sire_id'));include(h.get('dam_id'))
    for batch in batches:
        for e in batch['entries']:include(e['horse_id'])
        batch['entries']=[{k:e[k] for k in ('position','horse_id','earnings','source_horse_id','source_url','observed_at')} for e in batch['entries']]
    proof_path=ROOT/'data'/'ranking_cache'/'ar-ranking-report.json'
    if arg['entries']:
        report=json.loads(proof_path.read_text())
        if not report['complete']:raise SystemExit('La comprobación argentina sigue incompleta.')
        for ident in report['verified_ids']+report.get('excluded_by_bound',[]):
            # A previously reviewed candidate can remain in the library even after
            # its bound excludes it from the final hundred; preserve those records.
            if 'ar-studbook:'+ident in nodes:include('ar-studbook:'+ident)
        (ROOT/'samples'/'argentina_rankings_proof.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    data={'description':'Instantánea pública consultada el 20/10/2026; cobertura y limitaciones en docs/rankings.md.',
          'horses':[selected[k] for k in sorted(selected)],'rankings':batches}
    destination=ROOT/'samples'/'historical_rankings.json'
    destination.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'{destination.name}: {len(selected)} registros, {sum(len(b["entries"]) for b in batches)} puestos, {destination.stat().st_size:,} bytes')


if __name__=='__main__':main()
