"""Earnings rankings keep source, currency, birth origin and coverage separate."""
import re
from decimal import Decimal,InvalidOperation

from . import db

COUNTRY_CODES={'BRZ':'BRA','BRA':'BRA','URU':'URU','ARG':'ARG','GB':'GBR','GBR':'GBR','IE':'IRL','IRE':'IRL','IRL':'IRL',
               'USA':'USA','CAN':'CAN','JPN':'JPN','FR':'FRA','FRA':'FRA','GER':'DEU','AUS':'AUS',
               'NZ':'NZL','NZL':'NZL','CHI':'CHL','CHL':'CHL','PER':'PER','SAF':'ZAF','UAE':'ARE','ITY':'ITA','ITA':'ITA'}


def suffix_country(name):
    match=re.search(r'\(([A-Z]{2,3})\)\s*$',name)
    return COUNTRY_CODES.get(match[1]) if match else None


def parse_equibase(pages):
    entries={}
    horses={}
    source_url='https://www.equibase.com/stats/ViewAllTime.cfm?tf=all-time&rbt=TB'
    for page in pages:
        if not isinstance(page,dict) or not isinstance(page.get('stats'),list):
            raise ValueError('Equibase no devolvió una lista de estadísticas compatible.')
        for item in page['stats']:
            rank=item['rank'];ref=item['referenceNumber'];registry=item.get('registry','T')
            if not isinstance(rank,int) or not isinstance(ref,int) or ref<=0:
                raise ValueError('Equibase devolvió una posición o ID inválido.')
            if rank<1 or rank>200:continue
            ident=f'equibase:{registry}:{ref}'
            profile=f'https://www.equibase.com/profiles/Results.cfm?type=Horse&refno={ref}&registry={registry}&rbt=TB'
            father=item.get('sireReferenceNumber')
            father_id=f'equibase:T:{father}' if father and item.get('sireName') else None
            if father_id and father_id not in horses:
                horses[father_id]={'id':father_id,'name':item['sireName'],'country':'USA','birth_country':suffix_country(item['sireName']),
                    'sex':'M','source_id':'us-equibase','source_url':source_url,'featured':False,
                    'notes':'Progenitor identificado por el ID de padrillo que publica Equibase. Fecha y ascendencia pendientes de verificar.'}
            if father_id:
                # A horse already listed as a runner can appear later as a sire.
                # That source relation establishes its sex regardless of page order.
                horses[father_id]['sex']='M'
            horses[ident]={**horses.get(ident,{}),'id':ident,'name':item['horseName'],'country':'USA',
                'birth_country':suffix_country(item['horseName']),'sex':horses.get(ident,{}).get('sex','U'),
                'sire_id':father_id,'source_id':'us-equibase','source_url':profile,'featured':True,
                'notes':'Caballo del Top 200 histórico de Equibase por ganancias. El país de registro indica la fuente; nacimiento sólo se informa cuando se verifica. La ficha detallada está protegida por una verificación de acceso; pedigree parcial.'}
            amount=Decimal(str(item['earnings']))
            if not amount.is_finite() or amount<0:raise ValueError('Equibase devolvió ganancias inválidas.')
            row={'position':rank,'horse_id':ident,'earnings':str(amount),'source_horse_id':str(ref),
                 'source_url':source_url,'observed_at':db.now()}
            if rank in entries and entries[rank]!=row:
                old=entries[rank]
                if any(old[k]!=row[k] for k in ('horse_id','earnings')):raise ValueError('Las páginas de Equibase se contradicen.')
            entries[rank]=row
    ordered=[entries[k] for k in sorted(entries)]
    if [r['position'] for r in ordered]!=list(range(1,201)):
        raise ValueError('La descarga de Equibase no cubre exactamente los puestos 1 al 200.')
    if len({r['horse_id'] for r in ordered})!=200:raise ValueError('El ranking de Equibase repite caballos.')
    if any(Decimal(a['earnings'])<Decimal(b['earnings']) for a,b in zip(ordered,ordered[1:])):
        raise ValueError('Las ganancias no siguen el orden descendente de Equibase.')
    return list(horses.values()),ordered


def save_ranking(meta,entries,*,allow_incomplete_replacement=False):
    required={'id','title','birth_country','currency','scope','source_url','observed_at','requested_count','status','methodology','blocker'}
    if set(meta)!=required:raise ValueError('Faltan metadatos o hay campos no admitidos en el ranking.')
    if meta['status'] not in ('complete','partial','blocked'):raise ValueError('Estado de ranking inválido.')
    ranks=[e['position'] for e in entries]
    if ranks!=list(range(1,len(entries)+1)) or len({e['horse_id'] for e in entries})!=len(entries):
        raise ValueError('El ranking debe tener puestos consecutivos y caballos distintos.')
    if not isinstance(meta['requested_count'],int) or isinstance(meta['requested_count'],bool) or meta['requested_count']<1:
        raise ValueError('La cantidad solicitada debe ser un entero positivo.')
    if len(entries)>meta['requested_count']:
        raise ValueError('El ranking supera la cantidad de puestos solicitada.')
    if meta['status']=='complete' and len(entries)!=meta['requested_count']:
        raise ValueError('No se puede marcar completo un ranking sin la cantidad solicitada.')
    amounts=[]
    for entry in entries:
        try:value=Decimal(entry['earnings'])
        except (InvalidOperation,TypeError) as e:raise ValueError('Importe de ganancias inválido.') from e
        if not value.is_finite() or value<0:raise ValueError('Importe de ganancias inválido.')
        amounts.append(value)
    if any(a<b for a,b in zip(amounts,amounts[1:])):raise ValueError('Las ganancias deben estar en orden descendente.')
    with db.connection() as con:
        # Serialize the decision and replacement so concurrent refreshes cannot
        # publish incomplete progress after another refresh completed successfully.
        con.execute('BEGIN IMMEDIATE')
        for entry in entries:
            h=con.execute('SELECT birth_country,is_demo FROM horses WHERE id=?',(entry['horse_id'],)).fetchone()
            if not h or h['is_demo']:raise ValueError('Un ranking real no puede referenciar ejemplos ficticios ni IDs inexistentes.')
            if meta['birth_country'] and h['birth_country']!=meta['birth_country']:
                raise ValueError('El país de nacimiento de un caballo no coincide con el ranking.')
        previous=con.execute('SELECT status FROM ranking_sets WHERE id=?',(meta['id'],)).fetchone()
        if previous and previous['status']=='complete' and meta['status']!='complete' and not allow_incomplete_replacement:
            return False
        keys=list(meta)
        con.execute(f"INSERT INTO ranking_sets({','.join(keys)}) VALUES({','.join('?' for _ in keys)}) ON CONFLICT(id) DO UPDATE SET {','.join(f'{k}=excluded.{k}' for k in keys if k!='id')}",[meta[k] for k in keys])
        # Each explicit snapshot replaces only the entries of this particular ranking.
        con.execute('DELETE FROM ranking_entries WHERE ranking_id=?',(meta['id'],))
        for row in entries:
            con.execute('INSERT INTO ranking_entries(ranking_id,position,horse_id,earnings,source_horse_id,source_url,observed_at) VALUES(?,?,?,?,?,?,?)',
                (meta['id'],row['position'],row['horse_id'],row['earnings'],row['source_horse_id'],row['source_url'],row['observed_at']))
    return True


def list_rankings():
    with db.connection() as con:
        rows=[dict(r) for r in con.execute('SELECT s.*,COUNT(e.horse_id) AS count FROM ranking_sets s LEFT JOIN ranking_entries e ON e.ranking_id=s.id GROUP BY s.id ORDER BY CASE s.id WHEN \'equibase-200\' THEN 0 WHEN \'uru-100\' THEN 1 WHEN \'arg-100\' THEN 2 ELSE 3 END')]
    return rows


def get_ranking(ident):
    with db.connection() as con:
        row=con.execute('SELECT * FROM ranking_sets WHERE id=?',(ident,)).fetchone()
        if row is None:return None
        entries=[dict(r) for r in con.execute('''SELECT e.*,h.name,h.birth_country,h.birth_year,h.sire_id,h.dam_id,h.sex
            FROM ranking_entries e JOIN horses h ON h.id=e.horse_id WHERE e.ranking_id=? ORDER BY e.position''',(ident,))]
        nodes={r['id']:dict(r) for r in con.execute('SELECT id,sire_id,dam_id FROM horses WHERE is_demo=0')}
    def slots(ident,depth):
        node=nodes.get(ident)
        if not node or depth>3:return 0
        return 1+slots(node['sire_id'],depth+1)+slots(node['dam_id'],depth+1)
    for entry in entries:
        node=nodes[entry['horse_id']]
        entry['pedigree_known']=slots(node['sire_id'],1)+slots(node['dam_id'],1)
    return {'ranking':dict(row),'entries':entries}


def export_rankings():
    return [get_ranking(s['id']) for s in list_rankings()]
