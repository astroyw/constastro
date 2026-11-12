from contextlib import asynccontextmanager
import os
from datetime import date as Date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import db
from .catalog import COUNTRIES, SOURCES
from .excel import export_workbook
from .verification import compare_all
from .evidence import load_evidence
from .ancestry import original_targets,audit
from .genetics import analyze, pedigree, validate_graph
from .scraper import ScrapeError, fetch_public, parse_horses, parse_results, source_by_id, validate_url
from .argentina import parse_profile, parse_campaign
from . import uruguay

STATIC=Path(__file__).resolve().parents[1]/"static"
COUNTRY_CODES={c['code'] for c in COUNTRIES}


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app=FastAPI(title="Linaje · Pedigrees y resultados hípicos",version="1.0.0",lifespan=lifespan)
app.mount("/static",StaticFiles(directory=STATIC),name="static")


def public_read_only():
    # Unknown nonempty values fail closed, rather than enabling imports by mistake.
    return os.environ.get('PUBLIC_READ_ONLY','').strip().lower() not in ('','0','false','no','off')


@app.middleware('http')
async def public_access(request,call_next):
    if public_read_only():
        consultation=request.method in ('GET','HEAD','OPTIONS')
        analysis=request.method=='POST' and request.url.path=='/api/compatibility'
        if (not consultation and not analysis) or request.url.path.rstrip('/')=='/api/uruguay/search':
            return JSONResponse({'detail':'Las importaciones se realizan durante el mantenimiento de la base.'},status_code=403)
    return await call_next(request)


@app.get('/api/config')
def config():
    return {'read_only':public_read_only()}


class Horse(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    id:str=Field(min_length=1,max_length=180,pattern=r"^[A-Za-z0-9._:-]+$")
    name:str=Field(min_length=1,max_length=200)
    country:str="URU"
    birth_country:str|None=Field(default=None,pattern=r"^[A-Z]{3}$")
    birth_year:int|None=Field(default=None,ge=1600,le=Date.today().year+1)
    sex:Literal["M","H","C","U"]="U"
    coat:str=Field(default="",max_length=80)
    sire_id:str|None=None
    dam_id:str|None=None
    source_url:str=Field(default="",max_length=2000)
    source_id:str=Field(default="manual",max_length=100)
    notes:str=Field(default="",max_length=2000)
    featured:bool=True

    @field_validator("id")
    @classmethod
    def no_demo(cls,value):
        if value.startswith("demo-"): raise ValueError("El prefijo demo- está reservado a ejemplos ficticios.")
        return value

    @field_validator("country")
    @classmethod
    def country_supported(cls,value):
        if value not in COUNTRY_CODES: raise ValueError("País no admitido.")
        return value


class RaceResult(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    id:str=Field(min_length=1,max_length=180,pattern=r"^[A-Za-z0-9._:-]+$")
    country:str
    track:str=Field(min_length=1,max_length=150)
    date:Date
    race_name:str=Field(min_length=1,max_length=200)
    distance:int|None=Field(default=None,gt=0,le=20000)
    surface:str=Field(default="",max_length=100)
    position:int=Field(ge=1,le=100)
    horse_name:str=Field(min_length=1,max_length=200)
    horse_id:str|None=None
    jockey:str=Field(default="",max_length=150)
    time:str=Field(default="",max_length=80)
    source_url:str=Field(min_length=8,max_length=2000)
    race_id:str=Field(default="",max_length=180)
    time_kind:Literal["winner","individual","unknown"]="unknown"
    scope:Literal["partial","full"]="partial"
    field_size:int|None=Field(default=None,ge=1,le=100)

    @field_validator("country")
    @classmethod
    def country_supported(cls,value):
        if value not in COUNTRY_CODES: raise ValueError("País no admitido.")
        return value

    @field_validator("source_url")
    @classmethod
    def http_url(cls,value):
        from urllib.parse import urlsplit
        p=urlsplit(value)
        if p.scheme!="https" or not p.hostname or p.username or p.password:
            raise ValueError("Indicá una URL de procedencia HTTPS sin credenciales.")
        return value


class ImportBatch(BaseModel):
    model_config=ConfigDict(extra="forbid")
    horses:list[Horse]=Field(default_factory=list,max_length=50000)
    results:list[RaceResult]=Field(default_factory=list,max_length=20000)


class Cross(BaseModel):
    sire_id:str
    dam_id:str
    demo:bool=False


class UruguayHorseImport(BaseModel):
    horse_id:int=Field(gt=0)


class UruguayRaceImport(BaseModel):
    track_id:Literal[1,13,4,21,16]=1
    date:Date
    race_number:int=Field(default=1,ge=1,le=30)


class ScrapeRequest(BaseModel):
    source_id:str
    url:str=Field(max_length=2000)
    kind:Literal["pedigree","results"]
    date:Date|None=None
    track:str=Field(default="",max_length=150)
    race_name:str=Field(default="",max_length=200)
    distance:int|None=Field(default=None,gt=0,le=20000)
    surface:str=Field(default="",max_length=100)


def save_batch(horses,results):
    for label,rows in [("caballos",horses),("resultados",results)]:
        ids=[row.get('id') for row in rows]
        if len(ids)!=len(set(ids)):
            raise ValueError(f"El lote contiene IDs de {label} repetidos. Revisá el archivo antes de importar.")
    with db.connection() as con:
        existing={r['id']:dict(r) for r in con.execute("SELECT * FROM horses WHERE is_demo=0")}
        demo_ids={r[0] for r in con.execute("SELECT id FROM horses WHERE is_demo=1")}
        normalized=[]
        for h in horses:
            model=Horse.model_validate({k:v for k,v in h.items() if k not in ('is_demo','fetched_at')})
            previous=existing.get(model.id,{})
            parsed=model.model_dump(exclude_unset=bool(previous))
            parsed['fetched_at']=h.get('fetched_at') or db.now()
            parsed['is_demo']=0
            # A partial web listing may enrich, but cannot erase known parentage.
            updates={k:v for k,v in parsed.items() if v not in (None,"") or k not in previous}
            if previous.get('sex') in ('M','H','C') and updates.get('sex')=='U':
                updates.pop('sex')
            if previous.get('featured') and parsed.get('source_id') in {s['id'] for s in SOURCES}:
                updates['featured']=True
            merged={**previous,**updates}
            existing[parsed['id']]=merged
            normalized.append(merged)
        validate_graph(list(existing.values()))
        for h in normalized:
            keys=['id','name','country','birth_country','birth_year','sex','coat','sire_id','dam_id','source_url','source_id','fetched_at','is_demo','featured','notes']
            cols=','.join(keys)
            updates=','.join(f'{k}=excluded.{k}' for k in keys if k!='id')
            con.execute(f"INSERT INTO horses ({cols}) VALUES ({','.join('?' for _ in keys)}) ON CONFLICT(id) DO UPDATE SET {updates}",[h.get(k) for k in keys])
        for r in results:
            model=RaceResult.model_validate({k:v for k,v in r.items() if k not in ('is_demo','fetched_at')})
            previous_row=con.execute('SELECT * FROM results WHERE id=? AND is_demo=0',(model.id,)).fetchone()
            previous=dict(previous_row) if previous_row else {}
            parsed={**previous,**model.model_dump(mode='json',exclude_unset=bool(previous))}
            if parsed['horse_id'] and parsed['horse_id'] not in existing:
                raise ValueError("El resultado referencia un caballo que no está en la base real.")
            if parsed['id'] in demo_ids:
                raise ValueError("ID reservado para demostración.")
            parsed['fetched_at']=r.get('fetched_at') or db.now()
            parsed['is_demo']=0
            keys=list(parsed)
            con.execute(f"INSERT INTO results ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)}) ON CONFLICT(id) DO UPDATE SET {','.join(f'{k}=excluded.{k}' for k in keys if k!='id')}",[parsed[k] for k in keys])
    return {"horses":len(horses),"results":len(results)}


@app.get("/")
def index():
    return FileResponse(STATIC/"index.html")


@app.get("/api/health")
def health():
    with db.connection() as con: con.execute("SELECT 1").fetchone()
    return {"status":"ok","database":"sqlite","version":"1.0.0"}


@app.get("/api/countries")
def countries(): return COUNTRIES


@app.get('/api/rankings')
def rankings():
    from .rankings import list_rankings
    return list_rankings()


@app.get('/api/rankings/{ranking_id}')
def ranking(ranking_id:str):
    from .rankings import get_ranking
    data=get_ranking(ranking_id)
    if data is None:raise HTTPException(404,'No se encontró ese ranking.')
    return data


@app.get("/api/horses")
def horses(demo:bool=False,country:str="",q:str=Query(default="",max_length=200),featured:bool=False):
    rows=db.horse_rows(demo)
    return [h for h in rows if (not country or h['country']==country) and (not q or q.casefold() in h['name'].casefold()) and (not featured or h['featured'])]


@app.get("/api/horses/{horse_id}")
def horse(horse_id:str,demo:bool=False):
    nodes={h['id']:h for h in db.horse_rows(demo)}
    if horse_id not in nodes: raise HTTPException(404,"No se encontró el caballo en esta base.")
    with db.connection() as con:
        campaign=[dict(r) for r in con.execute('SELECT * FROM results WHERE horse_id=? AND is_demo=? ORDER BY date DESC,position',(horse_id,int(demo)))]
    return {"horse":nodes[horse_id],"pedigree":pedigree(horse_id,nodes),"campaign":campaign,"original_target":None if demo else horse_id in original_targets(),"verification":None if demo else compare_all(list(nodes.values()),load_evidence())[horse_id]}


@app.post("/api/compatibility")
def compatibility(body:Cross):
    try: return analyze(body.sire_id,body.dam_id,db.horse_rows(body.demo))
    except ValueError as e: raise HTTPException(422,str(e)) from e


@app.get("/api/results")
def results(country:str="URU",track:str="",on_date:str=""):
    if country not in COUNTRY_CODES: raise HTTPException(422,"País no admitido.")
    if on_date:
        try: on_date=Date.fromisoformat(on_date).isoformat()
        except ValueError as e: raise HTTPException(422,"La fecha debe tener formato AAAA-MM-DD.") from e
    with db.connection() as con:
        rows=[dict(r) for r in con.execute("SELECT * FROM results WHERE is_demo=0 AND country=? ORDER BY date DESC,track,race_name,position",(country,))]
    return [r for r in rows if (not track or r['track']==track) and (not on_date or r['date']==on_date)]


@app.get("/api/sources")
def sources():
    with db.connection() as con:
        logs=[dict(r) for r in con.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 200")]
    adapters={'ar-studbook':'Pedigrees y campañas oficiales; reconstrucción histórica de premios nominales en ARS desde 1992',
              'us-equibase':'Top 200 histórico por ganancias en USD; fichas detalladas con acceso protegido',
              'uy-studbook':'Búsqueda y pedigree: servicio público oficial',
              'uy-maronas':'Resultados definitivos por pista, fecha y carrera: servicio público oficial'}
    return [{**s,"latest_attempt":next((r for r in logs if r['source_id']==s['id']),None),
             "adapter":adapters.get(s['id'],"Tablas HTML públicas; estructura del sitio sin validar")} for s in SOURCES]


@app.get('/api/uruguay/search')
def uruguay_search(q:str=Query(min_length=3,max_length=120)):
    if len(q.strip())<3:raise HTTPException(422,'Escribí al menos tres caracteres del nombre.')
    try:return uruguay.search_horses(q.strip())
    except ValueError as e:raise HTTPException(422,str(e)) from e


@app.post('/api/uruguay/pedigree')
def uruguay_pedigree(body:UruguayHorseImport):
    url=uruguay.profile_url(body.horse_id)
    try:
        saved=save_batch(uruguay.import_pedigree(body.horse_id),[])
    except ValueError as e:
        db.record_import('uy-studbook',url,'pedigree','blocked',message=str(e))
        raise HTTPException(422,str(e)) from e
    db.record_import('uy-studbook',url,'pedigree','success',saved['horses'],'Pedigree de tres generaciones importado del servicio público del Stud Book Uruguayo.')
    return {'status':'imported',**saved,'horse_id':'uy-studbook:'+str(body.horse_id)}


@app.post('/api/uruguay/results')
def uruguay_results(body:UruguayRaceImport):
    url=uruguay.MARONAS_API+'GetRaces'
    if body.date>Date.today():raise HTTPException(422,'Seleccioná una fecha que ya haya ocurrido.')
    try:
        rows=uruguay.import_race(body.track_id,body.date.isoformat(),body.race_number)
        saved=save_batch([],rows)
    except ValueError as e:
        db.record_import('uy-maronas',url,'results','blocked',message=str(e))
        raise HTTPException(422,str(e)) from e
    scope=rows[0]['scope']
    db.record_import('uy-maronas',rows[0]['source_url'],'results','success',saved['results'],
                     f"{uruguay.TRACKS[body.track_id]} · {body.date.isoformat()} · carrera {body.race_number}. Llegadas importadas: {len(rows)}; cobertura {'completa' if scope=='full' else 'parcial'}.")
    return {'status':'imported',**saved,'scope':scope,'field_size':rows[0]['field_size']}


@app.get("/api/stats")
def stats(demo:bool=False):
    rows=db.horse_rows(demo)
    with db.connection() as con:
        n=con.execute("SELECT COUNT(*) FROM results WHERE is_demo=0").fetchone()[0]
        ranked=0 if demo else con.execute('SELECT COUNT(DISTINCT horse_id) FROM ranking_entries').fetchone()[0]
    complete=0
    nodes={h['id']:h for h in rows}
    def known(h,depth):
        if depth==0:return bool(h)
        return bool(h) and known(nodes.get(h.get('sire_id')),depth-1) and known(nodes.get(h.get('dam_id')),depth-1)
    for h in rows:
        if known(h,3): complete+=1
    targets=original_targets()
    historical_review=None
    if not demo and targets and targets.issubset(nodes):
        finished=sum(audit(i,nodes)['complete'] for i in targets)
        historical_review={'targets':len(targets),'complete':finished,'pending':len(targets)-finished}
    return {"historical_review":historical_review,"horses":len(rows),"featured":sum(bool(h['featured']) for h in rows),"ranked_horses":ranked,"complete_pedigrees":complete,"results":n,"countries":len(COUNTRIES),"demo":demo}


@app.post("/api/import")
def import_json(body:ImportBatch):
    if not body.horses and not body.results: raise HTTPException(422,"El archivo no contiene registros.")
    try:
        saved=save_batch([h.model_dump(exclude_unset=True) for h in body.horses],[r.model_dump(mode='json',exclude_unset=True) for r in body.results])
    except ValueError as e: raise HTTPException(422,str(e)) from e
    db.record_import('manual','','json','success',sum(saved.values()),'Importación validada; procedencia declarada por el usuario.')
    return {"status":"imported",**saved}


@app.post("/api/scrape")
def scrape(body:ScrapeRequest):
    logged_url=""
    try:
        source=source_by_id(body.source_id)
        validate_url(body.url,source)
        logged_url=body.url
        if source['kind'] not in (body.kind,'both'):
            raise ScrapeError("La fuente seleccionada no corresponde al tipo de información.")
        html=fetch_public(body.url,source)
        arg_profile=body.source_id=='ar-studbook' and '/ejemplares/perfil/' in body.url
        hs=parse_profile(html,body.url) if arg_profile else parse_horses(html,body.url,source) if body.kind=='pedigree' else []
        rs=(parse_campaign(html,body.url) if arg_profile else parse_results(html,body.url,source,body.model_dump(mode='json'))) if body.kind=='results' else []
        saved=save_batch(hs,rs)
    except ValueError as e:
        db.record_import(body.source_id,logged_url,body.kind,'blocked',message=str(e))
        raise HTTPException(422,str(e)) from e
    db.record_import(body.source_id,body.url,body.kind,'success',sum(saved.values()),'Importado desde HTML público; revisar contra el registro oficial.')
    return {"status":"imported",**saved}


@app.get("/api/export.xlsx")
def excel(demo:bool=False):
    with db.connection() as con:
        rs=[] if demo else [dict(r) for r in con.execute("SELECT * FROM results WHERE is_demo=0")]
        logs=[dict(r) for r in con.execute("SELECT * FROM imports ORDER BY id DESC")]
    from .rankings import export_rankings
    content=export_workbook(db.horse_rows(demo),rs,logs,demo,rankings=None if demo else export_rankings())
    name="Linaje_DEMOSTRACION.xlsx" if demo else "Linaje_pedigrees.xlsx"
    return Response(content,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="{name}"'})


@app.get("/api/export.json")
def export_json():
    hs=[{k:v for k,v in h.items() if k not in ('is_demo','fetched_at')} for h in db.horse_rows(False)]
    with db.connection() as con:
        rs=[{k:v for k,v in dict(r).items() if k not in ('is_demo','fetched_at')} for r in con.execute("SELECT * FROM results WHERE is_demo=0")]
    from fastapi.responses import JSONResponse
    return JSONResponse({"horses":hs,"results":rs},headers={"Content-Disposition":'attachment; filename="Linaje_datos.json"'})
