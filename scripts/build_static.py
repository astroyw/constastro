"""Build a public snapshot from reviewed archives, never from the operator's database."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db
from app import main
from app.rankings import export_rankings,list_rankings
from app.genetics import validate_graph
from app.verification import compare_all
from app.evidence import load_evidence
from app.ancestry import original_targets


def build():
    out=ROOT/'dist'
    if out.exists():shutil.rmtree(out)
    for folder in ('static','data','downloads'):(out/folder).mkdir(parents=True,exist_ok=True)
    for source in (ROOT/'static').iterdir():
        if source.is_file() and source.suffix in ('.js','.css','.svg'):
            shutil.copy2(source,out/'static'/source.name)
    index=(ROOT/'static'/'index.html').read_text()
    index=index.replace('<script type="module"', '<script src="/static/deployment.js"></script>\n  <script type="module"',1)
    (out/'index.html').write_text(index)
    (out/'static'/'deployment.js').write_text('globalThis.LINAJE_STATIC = true;\n')
    previous=os.environ.get('CONSTASTRO_DB')
    try:
        with tempfile.TemporaryDirectory(prefix='linaje-publication-') as tmp:
            os.environ['CONSTASTRO_DB']=str(Path(tmp)/'snapshot.sqlite3')
            subprocess.run([sys.executable,str(ROOT/'scripts'/'seed.py')],check=True,cwd=ROOT)
            with db.connection() as con:
                results=[dict(r) for r in con.execute('SELECT * FROM results WHERE is_demo=0 ORDER BY date DESC,track,race_name,position')]
            horses={'real':db.horse_rows(False),'demo':db.horse_rows(True)}
            for rows in horses.values():validate_graph(rows)
            payload={'reference_checks':main.reference_checks(),'original_targets':sorted(original_targets()),'verification':compare_all(horses['real'],load_evidence()),'horses':horses,'countries':main.COUNTRIES,'sources':main.sources(),
                     'stats':{'real':main.stats(False),'demo':main.stats(True)},
                     'results':results,'ranking_sets':list_rankings(),'rankings':export_rankings()}
            (out/'data'/'site.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
            for demo,name in ((False,'Linaje_pedigrees.xlsx'),(True,'Linaje_DEMOSTRACION.xlsx')):
                (out/'downloads'/name).write_bytes(main.excel(demo).body)
            (out/'downloads'/'Linaje_datos.json').write_bytes(main.export_json().body)
    finally:
        if previous is None:os.environ.pop('CONSTASTRO_DB',None)
        else:os.environ['CONSTASTRO_DB']=previous
    review=ROOT/'samples'/'pedigree_review.json'
    if review.exists():shutil.copy2(review,out/'downloads'/'Linaje_revision_pedigrees.json')
    reconciliations=ROOT/'samples'/'pedigree_reconciliations.json'
    if reconciliations.exists():shutil.copy2(reconciliations,out/'downloads'/'Linaje_conciliaciones.json')
    recoveries=ROOT/'samples'/'pedigree_recoveries.json'
    if recoveries.exists():shutil.copy2(recoveries,out/'downloads'/'Linaje_recuperaciones.json')
    (out/'data'/'health.json').write_text(json.dumps({'status':'ok','edition':'static'}))
    (out/'_headers').write_text('/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: DENY\n')
    (out/'_redirects').write_text('/api/health /data/health.json 200\n')
    destination=ROOT/'exports'/'Linaje-Netlify.zip'
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for file in sorted(out.rglob('*')):
            if file.is_file():archive.write(file,file.relative_to(out).as_posix())
    for name in ('Linaje_pedigrees.xlsx','Linaje_DEMOSTRACION.xlsx','Linaje_datos.json'):
        shutil.copy2(out/'downloads'/name,ROOT/'exports'/name)
    print(f'Netlify: {len(horses["real"])} registros reales; {sum(len(r["entries"]) for r in payload["rankings"])} puestos.')
    print('Sitio generado: dist/; paquete: exports/Linaje-Netlify.zip')


if __name__=='__main__':build()
