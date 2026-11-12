"""Anonymous public services used by Stud Book Uruguayo and Maroñas Hípica."""
from datetime import date
from urllib.parse import urlencode

from .db import now
from .scraper import ScrapeError, fetch_public_json, source_by_id
from .rankings import suffix_country

STUDBOOK_API='https://backend.studbook.com.uy/api/v1/public/'
MARONAS_API='https://mobile-rest-services-v3.azurewebsites.net/XTurfRestService.svc/'
TRACKS={1:'Maroñas',13:'Las Piedras',4:'Colonia',21:'Paysandú',16:'Melo'}


def profile_url(ident):
    return f'https://www.studbook.com.uy/online-volume/horse/{ident}'


def quarantine_inconsistent_birth_years(records):
    """Keep pedigree links but do not publish chronologically impossible source dates."""
    nodes={r['id']:dict(r) for r in records}
    conflicts=set()
    for child in nodes.values():
        for key in ('sire_id','dam_id'):
            parent=nodes.get(child.get(key))
            if parent and child.get('birth_year') and parent.get('birth_year') and parent['birth_year']>=child['birth_year']:
                conflicts.update((child['id'],parent['id']))
    for ident in conflicts:
        h=nodes[ident]
        h['notes']=(h.get('notes','')+f" Año publicado {h['birth_year']} omitido por inconsistencia cronológica con un progenitor o descendiente; requiere verificación.").strip()
        h['birth_year']=None
    return list(nodes.values())


def search_horses(query):
    params=urlencode({'page':1,'pageSize':10,'search':query,'searchType':'contains'})
    data=fetch_public_json(STUDBOOK_API+'horse?'+params,source_by_id('uy-studbook'))
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list):
        raise ScrapeError('Cambió el formato de búsqueda del Stud Book Uruguayo.')
    return {'count':data.get('count',len(data['rows'])),'horses':[
        {'id':h['id'],'name':h['name'],'sex':h.get('sex','U'),'birth_date':h.get('birthDate'),
         'sire':(h.get('father') or {}).get('name'),'dam':(h.get('mother') or {}).get('name'),
         'source_url':profile_url(h['id'])} for h in data['rows'] if h.get('id') and h.get('name')]}


def parse_pedigree(tree,profile,max_generations=3):
    if not isinstance(tree,dict) or not isinstance(profile,dict) or tree.get('id')!=profile.get('id') or not tree.get('id'):
        raise ScrapeError('La ficha y el pedigree no tienen el mismo ID de registro.')
    source_url=profile_url(tree['id'])
    records={}
    def walk(node,depth,role=None):
        if not node or depth>max_generations:return None
        if not isinstance(node,dict) or not isinstance(node.get('id'),int) or node['id']<=0 or not node.get('name'):
            raise ScrapeError('Un ancestro no tiene ID o nombre válido; no se importó el pedigree.')
        ident='uy-studbook:'+str(node['id'])
        born=node.get('birthDate')
        try:year=date.fromisoformat(born[:10]).year if born else None
        except (ValueError,TypeError):year=None
        invalid_year=year if year is not None and year<1600 else None
        if invalid_year is not None:year=None
        coat=node.get('coat') or {}
        record={'id':ident,'name':node['name'],'country':'URU','birth_year':year,'birth_country':suffix_country(node['name']),
            'sex':profile.get('sex','U') if depth==0 else role or 'U',
            'coat':coat.get('description') or coat.get('abbreviation') or '',
            'sire_id':walk(node.get('father'),depth+1,'M') if depth<max_generations else None,
            'dam_id':walk(node.get('mother'),depth+1,'H') if depth<max_generations else None,
            'source_id':'uy-studbook','source_url':source_url,'fetched_at':now(),
            'is_demo':0,'featured':depth==0,
            'notes':'Consulta al servicio público del Stud Book Uruguayo. URU indica el registro de origen, no el país de nacimiento. Las fechas históricas 01/01 pueden ser convencionales.'}
        if invalid_year is not None:
            record['notes']+=f' Año publicado {invalid_year} omitido por estar fuera del rango histórico admitido; requiere verificación.'
        if depth==0:
            record['coat']=(profile.get('coat') or {}).get('description') or record['coat']
            code=(profile.get('birthCountry') or {}).get('abbreviation')
            if code:
                record['birth_country']={'BRZ':'BRA','BR':'BRA','UY':'URU','AR':'ARG','US':'USA','GB':'GBR','UK':'GBR','IRE':'IRL'}.get(code.upper(),code.upper())
        previous=records.get(ident,{})
        for key in ('name','birth_year','sex','sire_id','dam_id'):
            if previous.get(key) and record.get(key) and previous[key]!=record[key]:
                raise ScrapeError('El servicio devolvió datos contradictorios para el mismo ID de registro.')
        records[ident]={**previous,**{k:v for k,v in record.items() if v not in (None,'') or k not in previous}}
        return ident
    walk(tree,0)
    return quarantine_inconsistent_birth_years(records.values())


def import_pedigree(ident):
    source=source_by_id('uy-studbook')
    profile=fetch_public_json(STUDBOOK_API+f'horse/{ident}',source)
    tree=fetch_public_json(STUDBOOK_API+f'horse/pedigree/{ident}',source)
    return parse_pedigree(tree,profile)


def format_time(raw):
    if not isinstance(raw,str) or not raw or raw.startswith('00:00:00'):return ''
    parts=raw.split(':')
    if len(parts)!=3:return raw
    try:
        hours,minutes=int(parts[0]),int(parts[1])
        seconds=parts[2].rstrip('0').rstrip('.') if '.' in parts[2] else parts[2]
        return f'{hours*60+minutes}:{seconds}'
    except ValueError:return raw


def parse_race(race,participants,track_id,racing_date,race_number):
    if not isinstance(race,dict) or not isinstance(participants,list):
        raise ScrapeError('Cambió el formato del servicio de resultados de Maroñas.')
    if (race.get('RaceTrack') or {}).get('Id')!=track_id or race.get('Number')!=race_number or (race.get('RacingDate') or {}).get('Date','')[:10]!=racing_date:
        raise ScrapeError('La respuesta no corresponde a la pista, fecha y carrera solicitadas.')
    result=race.get('Result')
    if not result or race.get('StatusId')!=6:
        raise ScrapeError('La carrera todavía no tiene resultados definitivos o su estado no es compatible.')
    rid=race.get('Id')
    if not isinstance(rid,int) or rid<=0:raise ScrapeError('La carrera no tiene identificador estable.')
    source_url='https://hipica.maronas.com.uy/RacingInfo/RaceResult?'+urlencode({'RaceTrackId':track_id,'RacingDate':racing_date,'RaceNumber':race_number})
    translations=((race.get('SurfaceType') or {}).get('Description') or {}).get('TextTranslations',[])
    surface=next((t.get('Value','') for t in translations if t.get('LanguageId')==1),'')
    size=result.get('NumberOfStarters') or None
    records=[]
    seen=set()
    for participant in participants:
        horse=participant.get('Horse') or {}
        finish=participant.get('Result') or {}
        position=finish.get('FinalFinishPosition')
        if not isinstance(position,int) or isinstance(position,bool) or position<1:continue
        horse_id=horse.get('Id')
        if not isinstance(horse_id,int) or horse_id<=0 or not horse.get('Name'):
            raise ScrapeError('Una llegada no tiene identificador o nombre de caballo.')
        if horse_id in seen:raise ScrapeError('El servicio repite un caballo en la misma carrera.')
        seen.add(horse_id)
        elapsed=format_time(finish.get('FinalTime'))
        records.append({'id':f'uy-result:{rid}:{horse_id}','race_id':f'uy-maronas:{rid}',
            'country':'URU','track':TRACKS[track_id],'date':racing_date,'race_name':f"{race_number} · {race.get('Name') or 'Carrera'}",
            'distance':int((race.get('Distance') or {}).get('Value') or 0) or None,'surface':surface,
            'position':position,'horse_name':horse['Name'].strip(),'horse_id':None,
            'jockey':(participant.get('Jockey') or {}).get('Name','').strip(),'time':elapsed,
            'time_kind':'individual' if elapsed else 'unknown','scope':'partial','field_size':size,
            'source_url':source_url,'fetched_at':now(),'is_demo':0})
    if not records:raise ScrapeError('No hay llegadas numéricas definitivas para esta carrera.')
    if size and len(records)>size:raise ScrapeError('La cantidad de llegadas supera el número oficial de participantes.')
    if size and len(records)==size:
        for record in records:record['scope']='full'
    return sorted(records,key=lambda r:r['position'])


def import_race(track_id,racing_date,race_number):
    source=source_by_id('uy-maronas')
    data=fetch_public_json(MARONAS_API+'GetRaces',source,payload={
        'raceTrackId':track_id,'from':racing_date+'T00:00:00','to':racing_date+'T23:59:59',
        'ordinalFrom':race_number,'ordinalTo':race_number,'sessionInfo':None})
    if not isinstance(data,list) or len(data)!=1:
        raise ScrapeError('No se encontró una carrera única para esa fecha, pista y número.')
    participants=fetch_public_json(MARONAS_API+'GetRaceParticipants',source,payload={
        'raceTrackId':track_id,'date':racing_date+'T00:00:00','ordinal':race_number,'sessionInfo':None})
    return parse_race(data[0],participants,track_id,racing_date,race_number)
