"""Reconstruct a bounded historical earnings list from public SBARG statistics."""
import re
from datetime import date,timedelta
from decimal import Decimal
from urllib.parse import urljoin,urlsplit

from bs4 import BeautifulSoup

from .argentina import parse_profile
from .rankings import suffix_country
from .scraper import ScrapeError
from .uruguay import quarantine_inconsistent_birth_years


def amount(text,locale):
    value=re.sub(r'^(?:U\$S|\$)\s*','',text.strip()).replace('\xa0','').replace(' ','')
    pattern=r'\d+(?:\.\d{3})*(?:,\d{1,2})?' if locale=='es' else r'\d+(?:,\d{3})*(?:\.\d{1,2})?'
    if not re.fullmatch(pattern,value):raise ScrapeError('Formato de ganancias no reconocido en el Stud Book Argentino.')
    return str(Decimal(value.replace('.','').replace(',','.')) if locale=='es' else Decimal(value.replace(',','')))


def parse_statistics(html,start,end,url,ceiling=None):
    soup=BeautifulSoup(html,'html.parser')
    table=soup.select_one('#orden > tbody')
    if table is None:raise ScrapeError('No se encontró la tabla pública de estadísticas argentina.')
    entries=[];ids=set()
    for row in table.find_all('tr',recursive=False):
        cells=row.find_all('td',recursive=False)
        if len(cells)!=11:raise ScrapeError('Cambió el formato de estadísticas por ejemplar.')
        link=cells[1].find('a',href=True)
        path=urlsplit(urljoin('https://www.studbook.org.ar',link['href'])) if link else None
        match=re.fullmatch(r'/ejemplares/perfil/(\d+)(?:/[^/]+)?',path.path) if path and path.hostname=='www.studbook.org.ar' else None
        if not match:raise ScrapeError('Un candidato no tiene ID de perfil oficial.')
        ident=match[1]
        position=re.fullmatch(r'(\d+)º',cells[0].get_text(strip=True))
        if not position or int(position[1])!=len(entries)+1 or ident in ids:
            raise ScrapeError('Puestos de estadísticas no consecutivos o IDs repetidos.')
        earnings=amount(cells[2].get_text(strip=True),'es')
        if ceiling is not None and Decimal(earnings)>Decimal(ceiling):
            raise ScrapeError('El filtro de premios no actuó sobre el total del ejemplar.')
        flag=cells[1].find('img',class_='flag')
        # These country flags are checked again against the profile's explicit country.
        country={'/img/banderas/10.png':'ARG','/img/banderas/25.png':'BRA'}.get(flag.get('src')) if flag else None
        entries.append({'source_id':ident,'name':link.get_text(' ',strip=True),'url':path.geturl(),
                        'birth_country':country,'earnings':earnings})
        ids.add(ident)
    if not entries or len(entries)>150:raise ScrapeError('Cantidad de filas de estadísticas no compatible.')
    if any(Decimal(a['earnings'])<Decimal(b['earnings']) for a,b in zip(entries,entries[1:])):
        raise ScrapeError('La tabla argentina no está ordenada por ganancias descendentes.')
    return {'start':start,'end':end,'source_url':url,'ceiling':ceiling,'entries':entries,
            'cutoff':entries[-1]['earnings'] if len(entries)==150 else '0'}


def candidate_bounds(windows,count=100,country='ARG'):
    """An omitted horse cannot exceed the sum of each interval's final cutoff."""
    grouped={}
    for window in windows:grouped.setdefault((window['start'],window['end']),[]).append(window)
    previous=None;periods=[];candidates={}
    for (start,end),parts in sorted(grouped.items()):
        if previous and date.fromisoformat(start)!=previous+timedelta(days=1):
            raise ValueError('Los períodos deben cubrir fechas consecutivas sin solaparse.')
        previous=date.fromisoformat(end)
        base=[p for p in parts if p['ceiling'] is None]
        if len(base)!=1:raise ValueError('Cada período necesita exactamente una consulta sin techo.')
        cutoff=Decimal(base[0]['cutoff']);merged={}
        for part in [base[0]]+sorted([p for p in parts if p['ceiling'] is not None],key=lambda p:Decimal(p['ceiling']),reverse=True):
            if part['ceiling'] is not None and Decimal(part['ceiling'])<cutoff:
                raise ValueError('El refinamiento deja una franja de premios sin consultar.')
            cutoff=min(cutoff,Decimal(part['cutoff']))
            for entry in part['entries']:
                old=merged.get(entry['source_id'])
                if old and old!=entry:raise ValueError('Las consultas del mismo período se contradicen; actualizar la instantánea.')
                merged[entry['source_id']]=entry
        index=len(periods)
        periods.append({'start':start,'end':end,'cutoff':str(cutoff),'count':len(merged)})
        for entry in merged.values():
            row=candidates.setdefault(entry['source_id'],{**entry,'period_earnings':{}})
            if row['name']!=entry['name'] or row['birth_country']!=entry['birth_country']:
                raise ValueError('La identidad de un candidato cambió entre períodos.')
            row['period_earnings'][index]=Decimal(entry['earnings'])
    limits=[Decimal(p['cutoff']) for p in periods]
    national=[]
    for row in candidates.values():
        if row['birth_country']!=country:continue
        row['lower']=sum(row['period_earnings'].values(),Decimal(0))
        row['upper']=row['lower']+sum((limit for i,limit in enumerate(limits) if i not in row['period_earnings']),Decimal(0))
        national.append(row)
    national.sort(key=lambda r:(-r['lower'],r['source_id']))
    if len(national)<count:raise ValueError('No hay suficientes candidatos nacionales.')
    threshold=national[count-1]['lower'];unseen=sum(limits,Decimal(0))
    if unseen>=threshold:
        raise ValueError(f'Falta refinar estadísticas: un omitido podría sumar {unseen}, frente al corte {threshold}.')
    eligible=[r for r in national if r['upper']>=threshold]
    return eligible,{'start':periods[0]['start'],'end':periods[-1]['end'],'periods':periods,
                     'candidates':len(national),'eligible':len(eligible),'unseen_upper':str(unseen),'threshold_lower':str(threshold)}


def parse_ranked_profile(html,url):
    soup=BeautifulSoup(html,'html.parser');title=soup.select_one('#titulo')
    if title is None:raise ScrapeError('La ficha no tiene título de ejemplar.')
    text=soup.get_text(' ',strip=True);begin=text.index(title.get_text(' ',strip=True));header=text[begin:begin+700]
    country=re.search(r'\b(Argentina|Brasil|Brazil|Uruguay|Estados Unidos|Chile)\s*\|',header)
    if country is None:raise ScrapeError('No se pudo comprobar el país de nacimiento en la ficha.')
    birthplace={'Argentina':'ARG','Brasil':'BRA','Brazil':'BRA','Uruguay':'URU','Estados Unidos':'USA','Chile':'CHL'}[country[1]]
    totals=[]
    for table in soup.select('table'):
        if [x.get_text(' ',strip=True) for x in table.select(':scope > thead > tr > th')]!=['Importe']:continue
        cells=table.select(':scope > tbody > tr > td.result')
        for cell in cells:
            peso=cell.select_one('.p-peso');dollar=cell.select_one('.p-dolar')
            if peso and dollar:totals.append((amount(peso.get_text(' ',strip=True),'en'),amount(dollar.get_text(' ',strip=True),'en')))
    if not totals or len(set(totals))!=1:raise ScrapeError('No se encontró un total de campaña inequívoco en la ficha.')
    years=sorted({int(a['data-anio']) for a in soup.select('a.view2.total[data-anio]') if a['data-anio'].isdigit() and int(a['data-anio'])>0})
    if not years:raise ScrapeError('No hay años de campaña verificables en la ficha.')
    records=parse_profile(html,url)
    root=next(h for h in records if h['featured'])
    for h in records:h['birth_country']=birthplace if h['id']==root['id'] else suffix_country(h['name'])
    records=quarantine_inconsistent_birth_years(records)
    return {'horses':records,'horse_id':root['id'],'birth_country':birthplace,'earnings_ars':totals[0][0],
            'earnings_usd':totals[0][1],'campaign_years':years,'source_url':url}
