"""Resumable, rate-limited public-source imports. Never substitutes a recent ranking for an all-time ranking."""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db,uruguay
from app.main import save_batch
from app.rankings import parse_equibase,save_ranking
from app.scraper import fetch_public_json,source_by_id

CACHE=ROOT/'data'/'ranking_cache'
CACHE.mkdir(parents=True,exist_ok=True)


def cached(key,operation):
    path=CACHE/(key+'.json')
    if path.exists():return json.loads(path.read_text())['data']
    data=operation()
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'retrieved_at':db.now(),'data':data},ensure_ascii=False))
    temporary.replace(path)
    return data


def meta(ident,title,country,currency,scope,url,count,status='partial',blocker=''):
    return {'id':ident,'title':title,'birth_country':country,'currency':currency,'scope':scope,'source_url':url,
            'observed_at':db.now(),'requested_count':count,'status':status,'methodology':'','blocker':blocker}


def equibase():
    pages=[]
    for page in (1,2):
        url='https://www.equibase.com/Data.cfm/Stats/Horse/AllTime/Page?'+urlencode({'page':page,'sort':'EARNINGS','dir':'DESC','list':'E','set':'full'})
        pages.append(cached('equibase-'+str(page),lambda url=url:fetch_public_json(url,source_by_id('us-equibase'))))
    horses,entries=parse_equibase(pages)
    save_batch(horses,[])
    setting=meta('equibase-200','Top 200 histórico · Equibase',None,'USD',
        'Cohorte de Equibase: caballos con al menos una salida en EE. UU., Canadá o Puerto Rico. No es un censo de todos los caballos del mundo.',
        'https://www.equibase.com/stats/ViewAllTime.cfm?tf=all-time&rbt=TB',200,'complete')
    setting['methodology']='Puestos 1–200 publicados por Equibase, ganancias nominales en USD. Sin ajustar por inflación. No se convierten monedas ni se infiere el país de nacimiento de caballos sin sufijo. Pedigree parcial hasta obtener una fuente accesible.'
    save_ranking(setting,entries)
    db.record_import('us-equibase',setting['source_url'],'ranking','success',200,'Puestos 1 a 200 completos, distintos y ordenados por las ganancias publicadas en USD. Las fichas de pedigree presentan verificación de acceso.')
    print(json.dumps({'ranking':'equibase-200','count':200,'horse_records':len(horses)}),flush=True)


def normalize(name):
    text=re.sub(r'\s*\([A-Z]{2,3}\)\s*$','',name.upper())
    text=''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))
    return re.sub(r'[^A-Z0-9]','',text)


def birth_code(code):
    return {'BRZ':'BRA','BR':'BRA','UY':'URU','AR':'ARG','US':'USA','GB':'GBR','IRE':'IRL'}.get(code,code)


def maronas_card(ident):
    return cached('maronas-card-'+str(ident),lambda:fetch_public_json(uruguay.MARONAS_API+'GetHorseCard',source_by_id('uy-maronas'),payload={
        'horseId':ident,'toDateTime':'2026-10-20T23:59:59','withPerformances':False,'sessionInfo':None}))


def basic_maronas(row,card=None):
    source_url='https://hipica.maronas.com.uy/RacingInfo/HorseCard?HorseId='+str(row['Horse']['Id'])
    h=(card or {}).get('Horse') or row['Horse']
    records={}
    def walk(node,depth,role=None):
        if not node or depth>3 or not node.get('Id'):return None
        ident='uy-maronas:'+str(node['Id'])
        born=node.get('BirthDate') or ''
        year=int(born[:4]) if re.match(r'(?:19|20)\d{2}',born) and not born.startswith('1900-') else None
        record={'id':ident,'name':node['Name'].strip(),'country':'URU','birth_country':birth_code((node.get('Country') or {}).get('CustomCode')),
            'birth_year':year,'sex':role or (node.get('Sex') or {}).get('Code') or 'U','featured':depth==0,
            'sire_id':walk(node.get('Sire'),depth+1,'M'),'dam_id':walk(node.get('Mare'),depth+1,'H'),
            'source_url':source_url,'source_id':'uy-maronas','notes':'Ficha pública de HRU/Maroñas. No se generaron IDs para padres sin identificador ni se dedujo el año de nacimiento a partir de la edad. Pedigree pendiente de completar en el registro.'}
        records[ident]=record
        return ident
    root_id=walk(h,0)
    if not root_id:raise ValueError('La fuente no informó un ID de caballo.')
    save_batch(uruguay.quarantine_inconsistent_birth_years(records.values()),[])
    return root_id,False


def verified_studbook(row,card):
    h=card.get('Horse') or {}
    if h.get('Id')!=row['Horse']['Id'] or birth_code((h.get('Country') or {}).get('CustomCode'))!='URU':
        raise ValueError('La ficha de HRU no confirma el ID y el país de nacimiento.')
    hits=cached('uy-search-'+str(h['Id']),lambda:uruguay.search_horses(h['Name']))
    candidates=[]
    for hit in hits['horses']:
        if normalize(hit['name'])!=normalize(h['Name']):continue
        # Reconcile using exact name, year, both parents and birth country, never only a name.
        if not h.get('Sire') or not h.get('Mare') or not hit.get('sire') or not hit.get('dam'):continue
        if normalize(hit['sire'])!=normalize(h['Sire']['Name']) or normalize(hit['dam'])!=normalize(h['Mare']['Name']):continue
        if not hit.get('birth_date') or hit['birth_date'][:4]!=(h.get('BirthDate') or '')[:4]:continue
        candidates.append(hit)
    if len(candidates)!=1:raise ValueError('No hay una coincidencia inequívoca por nombre, año y ambos progenitores.')
    ident=candidates[0]['id']
    source=source_by_id('uy-studbook')
    def profile_operation():
        data=fetch_public_json(uruguay.STUDBOOK_API+f'horse/{ident}',source)
        return {k:data.get(k) for k in ('id','name','sex','birthDate','coat','birthCountry')}
    profile=cached('uy-profile-'+str(ident),profile_operation)
    if birth_code((profile.get('birthCountry') or {}).get('abbreviation','').upper())!='URU':
        raise ValueError('El registro no confirma nacimiento en Uruguay.')
    tree=cached('uy-tree-'+str(ident),lambda:fetch_public_json(uruguay.STUDBOOK_API+f'horse/pedigree/{ident}',source))
    records=uruguay.parse_pedigree(tree,profile)
    save_batch(records,[])
    nodes={x['id']:x for x in records}
    def complete(node,depth):
        if not node:return False
        return True if depth==0 else complete(nodes.get(node.get('sire_id')),depth-1) and complete(nodes.get(node.get('dam_id')),depth-1)
    canonical='uy-studbook:'+str(ident)
    return canonical,complete(nodes[canonical],3)


def uruguayan():
    params={'StatsType':1,'HorseStatsType':1,'RoleCode':None,'RaceTrackId':None,'DateFrom':None,'DateTo':None,
        'HorseBirthDateFrom':None,'HorseBirthDateTo':None,'HorseAgeRunFrom':None,'HorseAgeRunTo':None,
        'HorseOnlyWithRating':False,'Order':2,'MaxRanking':300,'EntityId':None}
    data=cached('maronas-historical-300',lambda:fetch_public_json(uruguay.MARONAS_API+'GetRacingStatistics',source_by_id('uy-maronas'),payload={'statsParameters':params,'sessionInfo':None}))
    details=data.get('Details',[])
    if not details or [r['Ranking'] for r in details]!=list(range(1,len(details)+1)):
        raise ValueError('La tabla de HRU no tiene posiciones consecutivas.')
    selected=[r for r in details if birth_code((r['Horse'].get('Country') or {}).get('CustomCode'))=='URU'][:100]
    if len(selected)!=100:raise ValueError('No se encontraron cien caballos nacidos en Uruguay en el tramo descargado.')
    setting=meta('uru-100','Top 100 nacidos en Uruguay · premios HRU','URU','UYU',
        'Ganancias acumuladas publicadas por HRU en su circuito; no incluye necesariamente premios obtenidos en otros países. La fuente no declara el inicio temporal del archivo.',
        'https://hipica.maronas.com.uy/RacingInfo/RacingStats',100)
    setting['methodology']='Se filtró país de nacimiento URU dentro de los 300 primeros puestos históricos del servicio HRU, y se tomaron los primeros 100. Moneda nominal UYU, sin ajuste por inflación ni conversión a USD. Enlace al Stud Book sólo si coinciden nombre, año, padre, madre y país.'
    entries=[]
    for index,row in enumerate(selected,1):
        card=None;warning='';full=False
        try:
            card=maronas_card(row['Horse']['Id'])
            ident,full=verified_studbook(row,card)
        except Exception as e:
            warning=str(e)
            ident,full=basic_maronas(row,card)
        amount=row['AmountEarned']
        if (amount.get('Currency') or {}).get('Name')!='Peso Uruguayo':raise ValueError('Cambió la moneda del ranking de HRU.')
        entries.append({'position':index,'horse_id':ident,'earnings':str(amount['Value']),
            'source_horse_id':str(row['Horse']['Id']),'source_url':setting['source_url'],'observed_at':db.now()})
        if index%10==0 or index==100:
            setting['status']='complete' if index==100 else 'partial'
            save_ranking(setting,entries)
        print(json.dumps({'ranking':'uru-100','done':index,'name':row['Horse']['Name'],'pedigree_complete':full,'warning':warning},ensure_ascii=False),flush=True)
    db.record_import('uy-maronas',setting['source_url'],'ranking','success',100,'Top 100 por nacimiento URU, ganancias acumuladas del circuito HRU en UYU. La cobertura internacional no está incluida.')


def pending():
    from app.rankings import list_rankings
    present={s['id']:s for s in list_rankings()}
    for country,ident,reason,url in [
        ('ARG','arg-100','El endpoint público de estadísticas argentino exige ventanas de hasta tres años desde 1988 y no ofrece aquí una lista histórica completa por nacimiento. No se sustituyó por un ranking de los últimos tres años.','https://www.studbook.org.ar/estadisticas/generales'),
        ('BRA','bra-100','El portal nacional de Stud Book Brasileiro presenta un error de certificado TLS. La ABCPCC enlaza ese mismo portal. Falta una tabla histórica verificable; no se desactivó la verificación.','https://studbook.com.br/consultar-estatisticas')]:
        if present.get(ident,{}).get('count',0):continue
        setting=meta(ident,'Top 100 nacidos en '+('Argentina' if country=='ARG' else 'Brasil'),country,'',
            'Ranking histórico nacional por nacimiento solicitado; datos aún no disponibles.',url,100,'blocked',reason)
        setting['methodology']='Pendiente de una fuente histórica verificable; no se rellenan puestos con caballos recientes o importes estimados.'
        save_ranking(setting,[])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('target',choices=['equibase','uruguay','pending','all'])
    args=parser.parse_args();db.init()
    if args.target in ('equibase','all'):equibase()
    if args.target in ('pending','all'):pending()
    if args.target in ('uruguay','all'):uruguayan()
