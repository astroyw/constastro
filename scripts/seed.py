"""Import the small attributed official archive once, without overwriting user data."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db
from app.main import save_batch
from app.rankings import save_ranking

db.init()
with db.connection() as con:
    already=con.execute("SELECT 1 FROM horses WHERE is_demo=0 LIMIT 1").fetchone()
if not already:
    archived=[json.loads((ROOT/'samples'/name).read_text()) for name in ('argentina_official.json','uruguay_official.json')]
    saved=save_batch([h for batch in archived for h in batch['horses']],[r for batch in archived for r in batch['results']])
    db.record_import('archive','','archive','success',sum(saved.values()),'Muestras oficiales consultadas el 20/10/2026: registros de Uruguay y Argentina, campaña individual y una clasificación de Maroñas. No es una sincronización actual.')
    print('Muestras oficiales archivadas:',saved)
    ranking_archive=ROOT/'samples'/'historical_rankings.json'
    if ranking_archive.exists():
        archive=json.loads(ranking_archive.read_text())
        saved=save_batch(archive['horses'],[])
        for batch in archive['rankings']:
            save_ranking(batch['ranking'],batch['entries'])
        db.record_import('archive','','ranking','success',sum(len(b['entries']) for b in archive['rankings']),
                         'Instantáneas archivadas de Equibase, HRU y los rankings oficiales incorporados; países de nacimiento y monedas separados. Ver cobertura y pendientes en docs/rankings.md.')
        print('Rankings históricos archivados:',saved)
    extension=ROOT/'samples'/'extended_pedigrees.json'
    if extension.exists():
        saved=save_batch(json.loads(extension.read_text())['horses'],[])
        print('Ascendencia histórica archivada:',saved)
    campaigns=ROOT/'samples'/'campaign_results.json'
    if campaigns.exists():
        saved=save_batch([],json.loads(campaigns.read_text())['results'])
        print('Actuaciones documentadas archivadas:',saved)
        for review in json.loads(campaigns.read_text()).get('reviews',[]):
            db.save_campaign_review(review['horse_id'],review['source_id'],review)
else:
    print('Base real existente conservada.')
