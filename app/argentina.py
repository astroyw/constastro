"""Stud Book Argentino public profile adapter, validated against an actual profile."""
import re
from datetime import datetime
from urllib.parse import urlsplit, urljoin

from bs4 import BeautifulSoup

from .db import now
from .scraper import ScrapeError
from .rankings import suffix_country


def parse_profile(html,url,max_generations=3,allow_missing_ids=False):
    soup=BeautifulSoup(html,'html.parser')
    title=soup.select_one('#titulo')
    table=soup.select_one('#table-pedigree')
    match=re.search(r'/ejemplares/perfil/(\d+)(?:/|$)',urlsplit(url).path)
    if not title or not table or not match:
        raise ScrapeError('La URL no corresponde a una ficha de pedigree del Stud Book Argentino compatible.')
    text=soup.get_text(' ',strip=True)
    title_text=title.get_text(' ',strip=True)
    header=text[text.index(title_text):text.index(title_text)+700]
    dates=re.findall(r'\b\d{2}/\d{2}/(\d{4})\b',header)
    sex='M' if re.search(r'\|\s*Macho\s*\|',header) else 'H' if re.search(r'\|\s*Hembra\s*\|',header) else 'C' if re.search(r'\|\s*Castrado\s*\|',header) else 'U'
    paths={}
    unlinked=0
    def record(ident,name,sex,year,featured=False):
        note='Extraído del pedigree público del Stud Book Argentino. País indica el registro de origen, no el país de nacimiento. Revisar fechas convencionales 01/01 en ancestros históricos.'
        if year is not None and year<1600:
            note+=f' Año publicado {year} omitido: fecha de relleno o fuera del rango histórico admitido.'
            year=None
        return {'id':'ar-studbook:'+ident,'name':name,'country':'ARG','birth_country':suffix_country(name),'birth_year':year,'sex':sex,
                'sire_id':None,'dam_id':None,'source_id':'ar-studbook','source_url':url,'fetched_at':now(),
                'is_demo':0,'featured':featured,'notes':note}
    paths['']=record(match[1],title_text,sex,int(dates[0]) if dates else None,True)
    coat=re.search(r'\|\s*(?:Macho|Hembra|Castrado)\s*\|\s*([^|]+)\s*\|',header)
    if coat:paths['']['coat']=coat[1].strip()
    birthplace=re.search(r'(Argentina|Uruguay|Brasil|Estados Unidos|Gran Bretaña|Irlanda|Francia|Chile|Japón|Italia|Canadá)\s*\|\s*(?:Macho|Hembra|Castrado)\s*\|',header)
    if birthplace:
        paths['']['birth_country']={'Argentina':'ARG','Uruguay':'URU','Brasil':'BRA','Estados Unidos':'USA','Gran Bretaña':'GBR','Irlanda':'IRL','Francia':'FRA','Chile':'CHL','Japón':'JPN','Italia':'ITA','Canadá':'CAN'}[birthplace[1]]
    rows=table.find_all('tr',recursive=False)
    if len(rows)!=2: raise ScrapeError('Cambió la estructura de las ramas del pedigree argentino; no se importaron registros.')
    for row,prefix in zip(rows,['s','d']):
        for generation in range(1,max_generations+1):
            cell=row.select_one('td.l'+str(generation))
            if cell is None: raise ScrapeError('Falta una columna del pedigree argentino.')
            boxes=cell.find_all('div',recursive=False)
            if len(boxes)!=2**(generation-1): raise ScrapeError('La cantidad de ancestros no coincide con la generación esperada.')
            for i,box in enumerate(boxes):
                link=box.find('a',href=True)
                if not link: continue
                m=re.search(r'/ejemplares/perfil/(\d+)(?:/|$)',link['href'])
                if not m and link.get_text(' ',strip=True).upper()=='SIN ASIGNAR':
                    continue
                if not m:
                    if allow_missing_ids:
                        unlinked+=1
                        continue
                    raise ScrapeError('Un ancestro no tiene identificador de registro estable.')
                path=prefix+''.join('d' if bit=='1' else 's' for bit in (format(i,'0'+str(generation-1)+'b') if generation>1 else ''))
                dates=re.findall(r'\b\d{2}/\d{2}/(\d{4})\b',box.get_text(' ',strip=True))
                sex='M' if 'wMacho' in box.get('class',[]) else 'H' if 'wHembra' in box.get('class',[]) else 'U'
                paths[path]=record(m[1],link.get_text(' ',strip=True),sex,int(dates[0]) if dates else None)
    if unlinked:
        paths['']['notes']+=f' {unlinked} posiciones sin identificador estable quedaron sin vincular; no se dedujeron relaciones por nombre.'
    merged={}
    for path,h in paths.items():
        h['sire_id']=paths.get(path+'s',{}).get('id')
        h['dam_id']=paths.get(path+'d',{}).get('id')
        previous=merged.get(h['id'],{})
        for key in ('name','birth_year','sex','sire_id','dam_id'):
            a,b=previous.get(key),h.get(key)
            if a not in (None,'','U') and b not in (None,'','U') and a!=b:
                raise ScrapeError(f'El pedigree argentino publica datos contradictorios para {h["id"]} ({key}); requiere revisión.')
        if previous.get('sex') in ('M','H','C') and h.get('sex')=='U':
            h['sex']=previous['sex']
        merged[h['id']]={**previous,**{k:v for k,v in h.items() if v is not None or k not in previous}}
    return list(merged.values())


def parse_campaign(html,url,*,quarantine_conflicts=False):
    """Individual starts from a horse's official campaign, not complete race fields."""
    soup=BeautifulSoup(html,'html.parser')
    title=soup.select_one('#titulo')
    root=re.search(r'/ejemplares/perfil/(\d+)(?:/|$)',urlsplit(url).path)
    table=soup.select_one('table.carreras')
    if not title or not root or not table: raise ScrapeError('No se encontró la campaña del ejemplar.')
    records=[]
    tracks={'LPA':'La Plata','SIS':'San Isidro','SIS.':'San Isidro','ARG':'Palermo','PAL':'Palermo','S.I.':'San Isidro'}
    for row in table.select('tbody tr[data-fecha]'):
        cells=row.find_all('td',recursive=False)
        if len(cells)!=18: raise ScrapeError('Cambió el formato de la campaña argentina. Importación detenida.')
        values=[c.get_text(' ',strip=True) for c in cells]
        race_link=cells[0].find('a',href=True)
        match=re.search(r'/reuniones/carrera/(\d+)(?:/|$)',race_link['href']) if race_link else None
        if not match: raise ScrapeError('Una actuación no tiene identificador de carrera estable.')
        position=int(values[15]) if values[15].isdigit() and int(values[15])>0 else None
        if position is None and not values[15]:
            raise ScrapeError('Una actuación no tiene puesto ni estado de llegada publicado.')
        dt=datetime.strptime(row['data-fecha'],'%d/%m/%Y').date().isoformat()
        def txt(selector):
            el=row.select_one(selector)
            return el.get_text(' ',strip=True) if el else ''
        video=cells[1].find('a',href=True)
        winner_time=values[6] if re.search('[1-9]',values[6].split('/')[0]) else ''
        distance=int(values[5]) if values[5].isdigit() and int(values[5])>0 else None
        details={'race_url':urljoin(url,race_link['href']),'race_number':values[3],
                 'published_order':values[4],'winner_time':winner_time,
                 'distance_raw':values[5] if distance is None else '',
                 'time_raw':values[6] if not winner_time else '',
                 'category':values[8],'conditions':values[9],
                 'surface_code':values[10],'going_code':values[11],
                 'horse_weight_kg':values[12] if values[12] not in ('0','0.0') else '', 'stable':txt('.switch-1'),
                 'trainer':txt('.switch-2'),'earnings_ars':txt('.p-peso'),
                 'earnings_usd_source':txt('.p-dolar'),'odds':values[17],
                 'video_url':urljoin(url,video['href']) if video else ''}
        race_name=cells[7].get('title') or next((x['title'] for x in cells[7].select('[title]')),'') or values[7]
        records.append({'id':f'ar-result:{match[1]}:{root[1]}','country':'ARG','track':tracks.get(values[2],values[2]),
            'date':dt,'race_name':values[3]+' · '+race_name,'distance':distance,
            'surface':{'A':'Arena','T':'Césped','C':'Césped'}.get(values[10],values[10]),'position':position,
            'finish_status':values[15] if position is None else '', 'details':{k:v for k,v in details.items() if v},
            'horse_name':title.get_text(' ',strip=True),'horse_id':'ar-studbook:'+root[1],
            'jockey':values[13],'time':winner_time if position==1 else '', 'source_url':url,'fetched_at':now(),'is_demo':0,
            'race_id':'ar-race:'+match[1],'time_kind':'winner' if position==1 and winner_time else 'unknown','scope':'partial'})
    if len({r['id'] for r in records})!=len(records):
        if not quarantine_conflicts:raise ScrapeError('La tabla repite una carrera para el mismo caballo.')
        unique={};conflicts=set()
        for r in records:
            if r['id'] in unique and any(v!=unique[r['id']].get(k) for k,v in r.items() if k!='fetched_at'):
                conflicts.add(r['id'])
            unique[r['id']]=r
        records=[r for ident,r in unique.items() if ident not in conflicts]
    return records


def campaign_report(html,url,records):
    """Reconcile the table with its official total, explicitly scoped to Argentina."""
    soup=BeautifulSoup(html,'html.parser')
    marker=soup.select_one('a.view2.total[data-anio="0"]')
    cells=marker.find_parent('tr').find_all('td',recursive=False) if marker else []
    expected=int(cells[2].get_text(strip=True)) if len(cells)>=3 and cells[2].get_text(strip=True).isdigit() else None
    observed=len({r['race_id'] for r in records})
    published_ids=set(re.findall(r'/reuniones/carrera/(\d+)(?:/|$)',str(soup.select_one('table.carreras') or '')))
    unresolved=len(published_ids)-observed
    status='complete_in_source' if expected is not None and expected==observed and expected>0 and unresolved==0 else 'no_records_in_source' if expected==observed==0 and not published_ids else 'partial_in_source'
    report={'status':status,'expected_starts':expected,'observed_starts':observed,
            'source_url':url,'observed_at':now(),'scope':'Solo carreras oficiales de Argentina publicadas por el Stud Book Argentino.',
            'message':'Total y actuaciones coinciden en esta fuente; no acredita una campaña mundial completa.' if status=='complete_in_source' else
                      'La fuente declara cero carreras en su ámbito; no acredita que el caballo nunca haya corrido.' if status=='no_records_in_source' else
                      'El total publicado no está disponible o no coincide con las actuaciones accesibles.'}
    if unresolved>0:report['message']+=f' {unresolved} carreras de la tabla permanecen sin incorporar por datos contradictorios o no interpretables; consultar la fuente.'
    return report
