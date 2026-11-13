import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection():
    path = Path(os.environ.get("CONSTASTRO_DB", str(ROOT / "data" / "constastro.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    with connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS horses (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL,
            birth_year INTEGER, sex TEXT NOT NULL DEFAULT 'U', coat TEXT DEFAULT '',
            sire_id TEXT REFERENCES horses(id) DEFERRABLE INITIALLY DEFERRED,
            dam_id TEXT REFERENCES horses(id) DEFERRABLE INITIALLY DEFERRED,
            source_url TEXT NOT NULL DEFAULT '', source_id TEXT NOT NULL DEFAULT 'manual',
            fetched_at TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0,
            featured INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS results (
            id TEXT PRIMARY KEY, country TEXT NOT NULL, track TEXT NOT NULL,
            date TEXT NOT NULL, race_name TEXT NOT NULL, distance INTEGER,
            surface TEXT DEFAULT '', position INTEGER NOT NULL, horse_name TEXT NOT NULL,
            horse_id TEXT REFERENCES horses(id), jockey TEXT DEFAULT '', time TEXT DEFAULT '',
            source_url TEXT NOT NULL, fetched_at TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL,
            kind TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS horse_country_idx ON horses(country, is_demo);
        CREATE INDEX IF NOT EXISTS results_date_idx ON results(country, date);
        CREATE TABLE IF NOT EXISTS ranking_sets (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, birth_country TEXT,
            currency TEXT NOT NULL, scope TEXT NOT NULL, source_url TEXT NOT NULL,
            observed_at TEXT NOT NULL, requested_count INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'partial', methodology TEXT NOT NULL DEFAULT '',
            blocker TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS ranking_entries (
            ranking_id TEXT NOT NULL REFERENCES ranking_sets(id),
            position INTEGER NOT NULL, horse_id TEXT NOT NULL REFERENCES horses(id),
            earnings TEXT NOT NULL, source_horse_id TEXT NOT NULL,
            source_url TEXT NOT NULL, observed_at TEXT NOT NULL,
            PRIMARY KEY(ranking_id,position), UNIQUE(ranking_id,horse_id)
        );
        """)
        horse_columns={r['name'] for r in con.execute('PRAGMA table_info(horses)')}
        if 'birth_country' not in horse_columns:
            con.execute('ALTER TABLE horses ADD COLUMN birth_country TEXT')
        columns={r['name'] for r in con.execute('PRAGMA table_info(results)')}
        additions={
            'race_id':"TEXT NOT NULL DEFAULT ''",
            'time_kind':"TEXT NOT NULL DEFAULT 'unknown'",
            'scope':"TEXT NOT NULL DEFAULT 'partial'",
            'field_size':'INTEGER',
            'finish_status':"TEXT NOT NULL DEFAULT ''",
            'details':"TEXT NOT NULL DEFAULT '{}'",
        }
        for name,definition in additions.items():
            if name not in columns:
                con.execute(f'ALTER TABLE results ADD COLUMN {name} {definition}')
        if any(r['name']=='position' and r['notnull'] for r in con.execute('PRAGMA table_info(results)')):
            # Non-numeric official finishes (e.g. disqualified) are starts too.
            # Preserve the entire existing table while removing only NOT NULL.
            sql=con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='results'").fetchone()[0]
            import re
            sql=re.sub(r'CREATE TABLE\s+["\[]?results["\]]?', 'CREATE TABLE results_nullable',sql,count=1,flags=re.I)
            sql=re.sub(r'position\s+INTEGER\s+NOT NULL','position INTEGER',sql,flags=re.I)
            con.execute(sql)
            cols=','.join(r['name'] for r in con.execute('PRAGMA table_info(results)'))
            con.execute(f'INSERT INTO results_nullable ({cols}) SELECT {cols} FROM results')
            con.execute('DROP TABLE results')
            con.execute('ALTER TABLE results_nullable RENAME TO results')
            con.execute('CREATE INDEX results_date_idx ON results(country,date)')
        con.execute("""CREATE TABLE IF NOT EXISTS campaign_reviews (
            horse_id TEXT NOT NULL REFERENCES horses(id), source_id TEXT NOT NULL,
            status TEXT NOT NULL, expected_starts INTEGER, observed_starts INTEGER NOT NULL DEFAULT 0,
            source_url TEXT NOT NULL, observed_at TEXT NOT NULL, scope TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '', PRIMARY KEY(horse_id,source_id))""")
        # Earlier archived Argentine campaigns have stable race IDs in their result IDs.
        con.execute("""UPDATE results SET race_id='ar-race:' || substr(id,11,instr(substr(id,11),':')-1),
            time_kind=CASE WHEN time<>'' THEN 'winner' ELSE 'unknown' END
            WHERE id LIKE 'ar-result:%' AND race_id=''""")
        if con.execute("SELECT 1 FROM horses WHERE is_demo=1 LIMIT 1").fetchone():
            return
        # Entirely fictional examples. Never presented as scraped or verified horses.
        rows = [
            ("faro", "Faro Oriental", "M", 2020, "sur", "luna", 1),
            ("brisa", "Brisa del Plata", "H", 2020, "viento", "flor", 1),
            ("cobre", "Cobre del Sur", "M", 2021, "relampago", "rosada", 1),
            ("alma", "Alma Criolla", "H", 2021, "alazan", "estrella", 1),
            ("sur", "Sur del Este", "M", 2012, "ombu", "rosada", 0),
            ("luna", "Luna Clara", "H", 2013, "alazan", "bruma", 0),
            ("viento", "Viento Norte", "M", 2012, "ombu", "estrella", 0),
            ("flor", "Flor del Río", "H", 2014, "relampago", "niebla", 0),
            ("ombu", "Don Ombú", "M", 2004, "tala", "aurora", 0),
            ("rosada", "Rosada", "H", 2005, "cedro", "arena", 0),
            ("alazan", "Alazán Mayor", "M", 2003, "sauce", "perla", 0),
            ("bruma", "Bruma", "H", 2005, "laurel", "espuma", 0),
            ("estrella", "Estrella del Este", "H", 2004, "coronel", "glicina", 0),
            ("relampago", "Relámpago", "M", 2005, "roble", "garza", 0),
            ("niebla", "Niebla", "H", 2006, "ceibo", "calandria", 0),
        ]
        for n, name, sex in [("tala","Tala Real","M"),("aurora","Aurora","H"),("cedro","Cedro","M"),("arena","Arena","H"),("sauce","Sauce Grande","M"),("perla","Perla","H"),("laurel","Laurel","M"),("espuma","Espuma","H"),("coronel","Coronel","M"),("glicina","Glicina","H"),("roble","Roble","M"),("garza","Garza","H"),("ceibo","Ceibo","M"),("calandria","Calandria","H")]:
            rows.append((n,name,sex,1995,None,None,0))
        for ident, name, sex, year, sire, dam, featured in rows:
            con.execute("""INSERT INTO horses (id,name,country,birth_year,sex,coat,sire_id,dam_id,
                source_id,source_url,fetched_at,is_demo,featured,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f"demo-{ident}",name,"URU",year,sex,"Zaino" if sex=="M" else "Alazán",
                 f"demo-{sire}" if sire else None,f"demo-{dam}" if dam else None,
                 "demo","",now(),1,featured,"Ejemplo ficticio para explorar la aplicación. No es un caballo registrado."))


def horse_rows(demo=False):
    with connection() as con:
        return [dict(r) for r in con.execute("SELECT * FROM horses WHERE is_demo=? ORDER BY featured DESC,name", (int(demo),))]


def result_record(row):
    record=dict(row)
    if isinstance(record.get('details'),str):record['details']=json.loads(record['details'] or '{}')
    return record


def campaign_reviews():
    with connection() as con:
        return [dict(r) for r in con.execute('SELECT * FROM campaign_reviews ORDER BY horse_id,source_id')]


def save_campaign_review(horse_id,source_id,report):
    keys=('status','expected_starts','observed_starts','source_url','observed_at','scope','message')
    with connection() as con:
        con.execute('INSERT INTO campaign_reviews (horse_id,source_id,'+','.join(keys)+') VALUES ('+','.join('?' for _ in range(9))+') ON CONFLICT(horse_id,source_id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in keys),
                    [horse_id,source_id,*[report.get(k) for k in keys]])


def record_import(source, url, kind, status, count=0, message=""):
    with connection() as con:
        con.execute("INSERT INTO imports(source_id,url,kind,created_at,status,count,message) VALUES(?,?,?,?,?,?,?)",
                    (source,url,kind,now(),status,count,message))
