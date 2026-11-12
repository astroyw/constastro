"""Conservative public HTML-table importer. No logins, paywall or CAPTCHA bypasses."""
import hashlib
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date

from bs4 import BeautifulSoup

from .catalog import SOURCES
from .db import now

AGENT = "ConstastroBot/1.0"
MAX_BYTES = 3_000_000
_lock = threading.Lock()
_last_request = {}
_host_locks = {}
_policies = {}
_intervals = {}


class ScrapeError(ValueError):
    pass


def source_by_id(source_id):
    s = next((x for x in SOURCES if x["id"] == source_id),None)
    if not s: raise ScrapeError("Fuente desconocida.")
    return s


def validate_url(url, source):
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.hostname not in source["hosts"] or p.port not in (None,443) or p.username or p.password:
            raise ValueError()
        if any(re.search(r"token|password|secret|api.?key|authorization",k,re.I) for k,v in urllib.parse.parse_qsl(p.query)):
            raise ScrapeError("Usá una URL pública sin credenciales ni tokens.")
    except ValueError as e:
        raise ScrapeError("La URL debe usar HTTPS y pertenecer a la fuente seleccionada, sin credenciales ni puertos especiales.") from e
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, source): self.source=source
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl,self.source)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def download(url, source, *, payload=None, json_response=False, ajax=False):
    validate_url(url,source)
    host=urllib.parse.urlsplit(url).hostname
    with _lock:
        host_lock=_host_locks.setdefault(host,threading.Lock())
    with host_lock:
        delay=_intervals.get(host,2) - (time.monotonic()-_last_request.get(host,0))
        if delay>0: time.sleep(delay)
        _last_request[host]=time.monotonic()
        headers={"User-Agent":AGENT,"Accept":"application/json" if json_response else "text/html,text/plain;q=0.8"}
        if ajax: headers['X-Requested-With']='XMLHttpRequest'
        if payload is not None: headers['Content-Type']='application/json'
        req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        opener=urllib.request.build_opener(SafeRedirect(source))
        with opener.open(req, timeout=45 if source['id'] in ('uy-maronas','ar-studbook') else 20) as response:
            validate_url(response.url,source)
            body=response.read(MAX_BYTES+1)
            if len(body)>MAX_BYTES: raise ScrapeError("La respuesta supera el límite de 3 MB; importá una ficha o carrera por vez.")
            content_type=response.headers.get_content_type()
            accepted=("application/json","text/json","text/javascript","application/javascript") if json_response else ("text/html","text/plain","application/xhtml+xml")
            if content_type not in accepted:
                raise ScrapeError("La fuente devolvió un formato inesperado. No se importaron datos.")
            return body.decode(response.headers.get_content_charset() or "utf-8",errors="replace")


def authorize_public(url, source):
    validate_url(url,source)
    parsed=urllib.parse.urlsplit(url)
    robots_url=f"https://{parsed.netloc}/robots.txt"
    cached=_policies.get(robots_url)
    if cached and time.monotonic()-cached[0]<3600:
        rp=cached[1]
    else:
        try:
            robots=download(robots_url,source)
        except urllib.error.HTTPError as e:
            if e.code==404: robots=""
            else: raise ScrapeError(f"No se pudo verificar robots.txt (HTTP {e.code}). No se importó la página.") from e
        except (urllib.error.URLError,TimeoutError) as e:
            raise ScrapeError("No se pudo acceder a la fuente para consultar robots.txt. Revisá el acceso de red en la configuración del entorno.") from e
        rp=urllib.robotparser.RobotFileParser()
        rp.parse(robots.splitlines())
        _policies[robots_url]=(time.monotonic(),rp)
    if not rp.can_fetch(AGENT,url):
        raise ScrapeError("La fuente no permite esta consulta en robots.txt. Usá una exportación autorizada.")
    crawl_delay=rp.crawl_delay(AGENT)
    if crawl_delay:
        if crawl_delay>30: raise ScrapeError("La fuente requiere un intervalo largo. Usá una exportación autorizada o un importador programado.")
        _intervals[parsed.hostname]=max(2,crawl_delay)


def fetch_public(url, source, *, ajax=False):
    authorize_public(url,source)
    try:
        html=download(url,source,ajax=ajax)
    except (urllib.error.URLError,TimeoutError) as e:
        raise ScrapeError("No se pudo descargar la página. Puede requerir acceso de red, una sesión o autorización de la fuente.") from e
    soup=BeautifulSoup(html,"html.parser")
    if soup.select_one('input[type="password"]') or re.search(r"captcha|access denied|verify you are human", soup.get_text(" "), re.I):
        raise ScrapeError("La fuente requiere autenticación o verificación humana. No se intentará evadirla.")
    return html


def fetch_public_json(url,source,*,payload=None):
    """Anonymous JSON operations used by the official public websites themselves."""
    authorize_public(url,source)
    try:
        raw=download(url,source,payload=payload,json_response=True)
        data=json.loads(raw.lstrip('\ufeff'))
    except urllib.error.HTTPError as e:
        raise ScrapeError(f"El servicio público respondió HTTP {e.code}. No se importaron datos.") from e
    except (urllib.error.URLError,TimeoutError) as e:
        raise ScrapeError("El servicio público no respondió. Revisá el acceso o reintentá más tarde.") from e
    except json.JSONDecodeError as e:
        raise ScrapeError("El servicio devolvió una respuesta JSON inválida.") from e
    return data


def norm(s):
    return " ".join(''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c)).replace('_',' ').split())


ALIASES={
    "name":["nombre","caballo","horse","horse name","nom","cheval","nome","cavalo","馬名"],
    "id":["id","registro","registration","horse id","id caballo"],
    "sire_id":["padre id","id padre","sire id"],"dam_id":["madre id","id madre","dam id"],
    "sire":["padre","sire","pere","pai","父"],"dam":["madre","dam","mere","mae","母"],
    "birth_year":["ano","ano nacimiento","nacimiento","foaled","year","birth year","annee"],
    "sex":["sexo","sex","sexe"],"country":["pais","country","pays"],
    "position":["puesto","pos","pos.","posicion","position","place","pl.","pl","ordre","着順"],
    "jockey":["jockey","jinete","monta","cavaleiro","騎手"],
    "time":["tiempo","time","temps","tempo","タイム"],
    "date":["fecha","date","data"],"track":["hipodromo","track","racecourse","hippodrome"],
    "race_name":["carrera","race","race name","course","premio"],
    "distance":["distancia","distance","metros"],"surface":["pista","surface","terreno"],
}
LOOKUP={norm(label): key for key,labels in ALIASES.items() for label in [key,*labels]}


def tables(html):
    soup=BeautifulSoup(html,"html.parser")
    for table in soup.find_all("table"):
        rows=table.find_all("tr")
        for ri,row in enumerate(rows):
            cells=row.find_all(["th","td"],recursive=False)
            headers=[LOOKUP.get(norm(c.get_text(' ',strip=True))) for c in cells]
            if "name" not in headers: continue
            if len([x for x in headers if x])<2: continue
            for r in rows[ri+1:]:
                cells=r.find_all(["td","th"],recursive=False)
                if len(cells)!=len(headers): continue
                yield {key:cell for key,cell in zip(headers,cells) if key}
            break


def cell_text(row,key):
    return row[key].get_text(" ",strip=True) if key in row else ""


def web_id(value,source_id):
    return source_id+":"+hashlib.sha256(value.encode()).hexdigest()[:20]


def linked_identity(row,key,url,source):
    if key not in row: return None
    link=row[key].find("a",href=True)
    if not link: return None
    target=urllib.parse.urljoin(url,link["href"])
    validate_url(target,source)
    return web_id(target,source["id"])


def parse_horses(html,url,source):
    result={}
    for row in tables(html):
        if "sire" not in row and "sire_id" not in row: continue
        name=cell_text(row,"name")
        if not name: continue
        external_id=cell_text(row,"id")
        ident=web_id("id:"+external_id,source["id"]) if external_id else linked_identity(row,"name",url,source)
        if not ident:
            raise ScrapeError("La tabla no tiene identificadores o enlaces estables. No se fusionan caballos por nombre: usá el formato JSON con IDs del registro.")
        sex=norm(cell_text(row,"sex"))
        sex={"m":"M","macho":"M","male":"M","colt":"M","stallion":"M","h":"H","hembra":"H","female":"H","mare":"H","f":"H","c":"C","gelding":"C"}.get(sex,"U")
        years=re.findall(r"\b(?:19|20)\d{2}\b",cell_text(row,"birth_year"))
        record={"id":ident,"name":name,"country":source["country"],"sex":sex,"birth_year":int(years[0]) if years else None,
                "sire_id":None,"dam_id":None,"source_url":url,"source_id":source["id"],"fetched_at":now(),"is_demo":0,"featured":1}
        for role,s in [("sire","M"),("dam","H")]:
            parent_id=cell_text(row,role+"_id")
            pid=web_id("id:"+parent_id,source["id"]) if parent_id else linked_identity(row,role,url,source)
            parent_name=cell_text(row,role)
            if parent_name and not pid:
                raise ScrapeError("Los progenitores no tienen IDs o enlaces estables. La importación se detuvo para no confundir homónimos.")
            record[role+"_id"]=pid
            if pid and pid not in result:
                result[pid]={"id":pid,"name":parent_name or parent_id,"country":source["country"],"sex":s,"birth_year":None,
                             "sire_id":None,"dam_id":None,"source_url":url,"source_id":source["id"],"fetched_at":now(),"is_demo":0,"featured":0}
        result[ident]=record
    if not result:
        raise ScrapeError("No se encontró una tabla de pedigree compatible. Esta fuente puede usar JavaScript, PDF u otro esquema; su adaptador específico aún necesita validación. Podés importar un JSON autorizado.")
    return list(result.values())


def parse_results(html,url,source,context):
    results=[]
    for row in tables(html):
        if "position" not in row: continue
        pos=cell_text(row,"position").strip().rstrip('.º°')
        if not pos.isdigit(): continue
        dt=cell_text(row,"date") or context.get("date","")
        try: dt=date.fromisoformat(dt).isoformat()
        except (ValueError,TypeError) as e: raise ScrapeError("Indicá la fecha de la reunión en formato AAAA-MM-DD.") from e
        track=cell_text(row,"track") or context.get("track","")
        race=cell_text(row,"race_name") or context.get("race_name","")
        if not track or not race: raise ScrapeError("Indicá el hipódromo y la carrera para identificar estos resultados.")
        distance=cell_text(row,"distance") or str(context.get("distance") or "")
        digits=re.sub(r"[^\d]","",distance)
        name=cell_text(row,"name")
        if not name: continue
        results.append({"id":web_id('|'.join([url,dt,track,race,name]),source["id"]),"country":source["country"],
            "track":track,"date":dt,"race_name":race,"distance":int(digits) if digits else None,
            "surface":cell_text(row,"surface") or context.get("surface", ""),"position":int(pos),"horse_name":name,
            "horse_id":None,"jockey":cell_text(row,"jockey"),"time":cell_text(row,"time"),"source_url":url,"fetched_at":now(),"is_demo":0})
    if not results: raise ScrapeError("No se encontró una tabla de posiciones compatible. No se guardaron resultados. La página puede requerir un adaptador específico.")
    return results
