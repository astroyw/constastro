"""Produce separate real-data/template and clearly labeled fictional-example workbooks."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db
from app.excel import export_workbook
from app.rankings import export_rankings

db.init()
out=ROOT/'exports'
out.mkdir(exist_ok=True)
with db.connection() as con:
    results=[dict(r) for r in con.execute('SELECT * FROM results WHERE is_demo=0')]
    logs=[dict(r) for r in con.execute('SELECT * FROM imports ORDER BY id DESC')]
for demo,name in [(False,'Linaje_pedigrees.xlsx'),(True,'Linaje_DEMOSTRACION.xlsx')]:
    content=export_workbook(db.horse_rows(demo),[] if demo else results,logs,demo,rankings=None if demo else export_rankings())
    (out/name).write_bytes(content)
    print(f'{name}: {len(content):,} bytes')
