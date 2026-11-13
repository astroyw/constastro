"""Source-scoped lifetime campaign observations; no name-only identity joins."""
from datetime import date
from .db import now
from .scraper import ScrapeError
from .uruguay import format_time
from .verification import normalized_name
from .rankings import COUNTRY_CODES as BIRTH_COUNTRIES

STATUS_LABELS={
    'complete_in_source':'Completa en la fuente consultada',
    'partial_in_source':'Campaña parcial en la fuente',
    'no_records_in_source':'Cero actuaciones declaradas en esta fuente',
    'unavailable':'Fuente no disponible',
    'pending_identity':'Falta vincular el ID de carreras',
    'pending':'Pendiente de consultar',
}


def coverage(horses,results,reviews):
    """One accountable row for every real displayed horse, including ancestors."""
    from collections import Counter,defaultdict
    counts=Counter(r.get('horse_id') for r in results)
    grouped=defaultdict(list)
    for r in reviews:grouped[r['horse_id']].append(r)
    rows=[]
    for h in horses:
        observations=grouped[h['id']]
        status='complete_in_source' if any(r['status']=='complete_in_source' for r in observations) else observations[0]['status'] if observations else 'pending'
        rows.append({'horse_id':h['id'],'name':h['name'],'status':status,
                     'starts':counts[h['id']],'reviews':observations})
    return {'total_horses':len(rows),'with_starts':sum(r['starts']>0 for r in rows),
            'total_starts':sum(counts.values()),'statuses':dict(Counter(r['status'] for r in rows)),
            'global_complete':0,'horses':rows,
            'scope':'La coincidencia del total en una fuente no certifica todas las carreras del caballo en otros países o circuitos.'}


def translated(value):
    return next((r.get('Value','') for r in (value or {}).get('TextTranslations',[]) if r.get('LanguageId')==1),'')


def verify_identity(current,observed,nodes):
    """A cross-publisher link requires name, real year and both documented parents."""
    if normalized_name(current['name'])!=normalized_name(observed.get('Name','')):
        raise ScrapeError('La ficha de carreras no coincide con el nombre del registro.')
    raw=observed.get('BirthDate','')
    year=int(raw[:4]) if len(raw)>=4 and raw[:4].isdigit() and not raw.startswith('1900-') else None
    if not year or year!=current.get('birth_year'):
        raise ScrapeError('No coincide o no está documentado el nacimiento entre ambas fuentes.')
    for role,key in [('sire_id','Sire'),('dam_id','Mare')]:
        parent=nodes.get(current.get(role))
        other=observed.get(key) or {}
        if not parent or not other.get('Name') or normalized_name(parent['name'])!=normalized_name(other['Name']):
            raise ScrapeError('Falta corroborar ambos progenitores para enlazar la campaña.')
    other_sex=(observed.get('Sex') or {}).get('Code')
    if other_sex in ('M','H') and current.get('sex') in ('M','H') and other_sex!=current['sex']:
        raise ScrapeError('El sexo de la ficha de carreras contradice el registro.')
    code=(observed.get('Country') or {}).get('CustomCode')
    code=BIRTH_COUNTRIES.get(code,{'UY':'URU','AR':'ARG','UK':'GBR'}.get(code,code))
    if code and current.get('birth_country') and code!=current['birth_country']:
        raise ScrapeError('El país de nacimiento de la ficha de carreras contradice el registro.')


def parse_maronas_campaign(card,horse,source_horse_id,nodes):
    observed=card.get('Horse') or {}
    if observed.get('Id')!=source_horse_id:raise ScrapeError('El servicio devolvió otro ID de caballo.')
    verify_identity(horse,observed,nodes)
    url=f'https://hipica.maronas.com.uy/RacingInfo/HorseCard?HorseId={source_horse_id}'
    rows=[];skipped=0
    for p in card.get('Performances',[]):
        race=p.get('Race') or {};result=p.get('Result') or {};rr=race.get('Result') or {}
        if (p.get('Horse') or {}).get('Id')!=source_horse_id:
            raise ScrapeError('Una actuación pertenece a un caballo diferente.')
        if not race.get('Id') or race.get('StatusId')!=6 or not result:
            skipped+=1;continue
        raw_date=(race.get('RacingDate') or {}).get('Date','')[:10]
        date.fromisoformat(raw_date)
        position=result.get('FinalFinishPosition')
        if not isinstance(position,int) or isinstance(position,bool) or position<1:position=None
        finish=translated(result.get('FinishStatusText')) or translated(p.get('StatusText'))
        if position is None and not finish:
            finish='Estado de llegada publicado: '+str(result['FinishStatusId']) if result.get('FinishStatusId') is not None else ''
        if position is None and not finish:skipped+=1;continue
        track=race.get('RaceTrack') or {}
        country=(track.get('Country') or {}).get('CustomCode')
        country={'UY':'URU','AR':'ARG','BRZ':'BRA'}.get(country,country)
        if not country:skipped+=1;continue
        race_url='https://hipica.maronas.com.uy/RacingInfo/RaceResult?'+f'RaceTrackId={track.get("Id")}&RacingDate={raw_date}&RaceNumber={race.get("Number")}'
        details={'race_url':race_url,'race_number':race.get('Number'),'post_position':p.get('PostPosition'),
                 'program_number':str(p.get('ProgramNumber') or '').strip(),
                 'horse_weight_kg':(p.get('HorseWeight') or {}).get('Value'),
                 'carried_weight_kg':(result.get('JockeyWeightFirstScale') or {}).get('Value'),
                 'trainer':(p.get('Trainer') or {}).get('Name'),'stable':(p.get('Stud') or {}).get('Name'),
                 'odds':p.get('Odds'),'margin':result.get('LengthsFromFirstText'),
                 'conditions':translated(race.get('ConditionText')),'category':translated(race.get('GroupText')),
                 'going':(rr.get('CourseCondition') or {}).get('Name'),
                 'weather':(rr.get('WeatherCondition') or {}).get('Name'),
                 'winner_time':format_time(rr.get('FinalWinningTime')),
                 'official_time':format_time(result.get('OfficialTime'))}
        # Only public sports details; exclude personal contact data and addresses.
        def video(value):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k=='Url' and isinstance(v,str) and v.startswith(('https://www.youtube.com/','https://youtu.be/')):return v
                    found=video(v)
                    if found:return found
            if isinstance(value,list):
                for v in value:
                    found=video(v)
                    if found:return found
            return ''
        details['video_url']=video(rr.get('MultimediaResources'))
        elapsed=format_time(result.get('FinalTime'))
        rows.append({'id':f'uy-result:{race["Id"]}:{source_horse_id}', 'race_id':f'uy-maronas:{race["Id"]}',
                     'country':country,'track':track.get('Name') or 'Hipódromo sin nombre',
                     'date':raw_date,'race_name':f'{race.get("Number")} · {race.get("Name") or "Carrera"}',
                     'distance':int((race.get('Distance') or {}).get('Value') or 0) or None,
                     'surface':translated((race.get('SurfaceType') or {}).get('Description')),
                     'position':position,'finish_status':finish if position is None else '',
                     'horse_name':horse['name'],'horse_id':horse['id'],'jockey':(p.get('Jockey') or {}).get('Name',''),
                     'time':elapsed,'time_kind':'individual' if elapsed else 'unknown',
                     'scope':'partial','field_size':rr.get('NumberOfStarters') or None,
                     'details':{k:str(v) for k,v in details.items() if v is not None and v!=''},
                     'source_url':url,'fetched_at':now(),'is_demo':0})
    if len({r['id'] for r in rows})!=len(rows):raise ScrapeError('La fuente repite una actuación del mismo caballo.')
    expected=card.get('RacesRun')
    if not isinstance(expected,int) or isinstance(expected,bool) or expected<0:expected=None
    status='complete_in_source' if expected is not None and len(rows)==expected and expected>0 and not skipped else 'no_records_in_source' if expected==len(rows)==0 and not skipped else 'partial_in_source'
    report={'status':status,'expected_starts':expected,'observed_starts':len(rows),'source_url':url,'observed_at':now(),
            'scope':'Historial publicado por HRU/Maroñas hasta la fecha de consulta; la fuente no certifica cobertura mundial.',
            'message':'Total y actuaciones coinciden en esta fuente.' if status=='complete_in_source' else
                      f'La fuente publica {expected if expected is not None else "un total desconocido"} carreras y permite recuperar {len(rows)} actuaciones; {skipped} filas no definitivas o sin datos interpretables.'}
    return rows,report
