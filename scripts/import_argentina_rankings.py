"""Import a historical SBARG list with explicit bounds for the truncated statistics."""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db
from app.argentina_rankings import parse_statistics,candidate_bounds,parse_ranked_profile
from app.main import save_batch
from app.rankings import save_ranking
from app.scraper import fetch_public,source_by_id
from scripts.import_historical_rankings import cached,meta


def collect_windows():
    source=source_by_id('ar-studbook');windows=[]
    periods=[(1992,1993)]+[(year,min(year+2,2026)) for year in range(1994,2027,3)]
    for lo,hi in periods:
        start=f'{lo}-01-01';end='2026-10-20' if hi==2026 else f'{hi}-12-31'
        params={'q':start,'x':end,'t':1,'cp':'total','orden':'desc'}
        url='https://www.studbook.org.ar/estadisticas/get-resultados-generales?'+urlencode(params)
        html=cached(f'ar-stat-{start}-{end}',lambda url=url:fetch_public(url,source,ajax=True))
        windows.append(parse_statistics(html,start,end,url))
    # A second tranche lowers the bound for horses omitted from the recent interval.
    recent=windows[-1];ceiling=recent['cutoff']
    params={'q':recent['start'],'x':recent['end'],'t':1,'cp':'total','orden':'desc','premio':ceiling}
    url='https://www.studbook.org.ar/estadisticas/get-resultados-generales?'+urlencode(params)
    key=f"ar-stat-{recent['start']}-{recent['end']}-ceiling-{ceiling}"
    html=cached(key,lambda:fetch_public(url,source,ajax=True))
    windows.append(parse_statistics(html,recent['start'],recent['end'],url,ceiling=ceiling))
    return windows


def import_ranking(limit=None):
    windows=collect_windows();candidates,proof=candidate_bounds(windows)
    print(json.dumps({'stage':'candidates','count':len(candidates),'proof':proof},ensure_ascii=False),flush=True)
    setting=meta('arg-100','Top 100 nacidos en Argentina · SBARG 1992–2026','ARG','ARS',
        'Premios nominales de carreras oficiales de Argentina registrados por el Stud Book Argentino, del 01/01/1992 al 20/10/2026. No incluye toda la campaña mundial; sin ajuste por inflación.',
        'https://www.studbook.org.ar/estadisticas/generales',100)
    setting['methodology']='Clasificación por nacimiento argentino y premios nominales en ARS registrados desde 1992, corroborados en las fichas oficiales. No se convierte moneda ni se ajusta por inflación: las épocas con precios más altos tienen ventaja, por lo que el puesto no mide calidad deportiva entre generaciones. No incluye ganancias mundiales. La reconstrucción y sus controles de cobertura están documentados en docs/rankings.md.'
    verified=[];failures=[];excluded=[]
    source=source_by_id('ar-studbook')
    for index,candidate in enumerate(candidates,1):
        if limit and index>limit:break
        if len(verified)>=100:
            cutoff=sorted((Decimal(r['earnings']) for r in verified),reverse=True)[99]
            if Decimal(candidate['upper'])<cutoff:
                excluded.append(candidate['source_id'])
                print(json.dumps({'done':index,'name':candidate['name'],'status':'excluded_by_bound'},ensure_ascii=False),flush=True)
                continue
        try:
            def operation():
                html=fetch_public(candidate['url'],source)
                return parse_ranked_profile(html,candidate['url'])
            data=cached('ar-ranked-profile-'+candidate['source_id'],operation)
            value=Decimal(data['earnings_ars'])
            if data['birth_country']!='ARG':raise ValueError('La ficha contradice el nacimiento argentino de las estadísticas.')
            if min(data['campaign_years'])<1992 or max(data['campaign_years'])>2026:
                raise ValueError('La campaña completa no pertenece al intervalo de la clasificación.')
            if not Decimal(candidate['lower'])<=value<=Decimal(candidate['upper']):
                raise ValueError(f"La ficha y los intervalos no concuerdan: {value} fuera de {candidate['lower']}–{candidate['upper']}. Revisar cobertura o actualización de origen.")
            records=data['horses']
            for h in records:
                if h.get('birth_country')=='CHI':h['birth_country']='CHL'
                if h['id']==data['horse_id']:
                    note=f" Premios oficiales argentinos publicados en la ficha: ARS {data['earnings_ars']}; equivalente en USD publicado por la fuente: {data['earnings_usd']}. No son ganancias mundiales."
                    h['notes']+=note
            save_batch(records,[])
            verified.append({'horse_id':data['horse_id'],'earnings':str(value),'source_horse_id':candidate['source_id'],
                             'source_url':candidate['url'],'observed_at':db.now()})
            print(json.dumps({'done':index,'eligible':len(candidates),'name':candidate['name'],'earnings_ars':str(value),'status':'imported'},ensure_ascii=False),flush=True)
        except Exception as error:
            failures.append({'source_id':candidate['source_id'],'name':candidate['name'],'error':str(error)})
            print(json.dumps({'done':index,'name':candidate['name'],'status':'unresolved','error':str(error)},ensure_ascii=False),flush=True)
        if index%10==0 or index==len(candidates):
            ranked=sorted(verified,key=lambda r:(-Decimal(r['earnings']),r['horse_id']))[:100]
            entries=[{**row,'position':i} for i,row in enumerate(ranked,1)]
            setting['status']='partial'
            setting['blocker']='' if setting['status']=='complete' else f"Validación en curso o incompleta: {len(verified)} de {len(candidates)} candidatos corroborados; {len(failures)} fichas requieren revisión. Los puestos guardados son provisionales."
            save_ranking(setting,entries)
    ranked=sorted(verified,key=lambda r:(-Decimal(r['earnings']),r['horse_id']))[:100]
    entries=[{**row,'position':i} for i,row in enumerate(ranked,1)]
    cutoff=Decimal(entries[-1]['earnings']) if len(entries)==100 else Decimal(0)
    confirmed={r['source_horse_id'] for r in verified}
    unresolved=[c['source_id'] for c in candidates if c['source_id'] not in confirmed and Decimal(c['upper'])>=cutoff]
    complete=len(entries)==100 and not unresolved
    setting['status']='complete' if complete else 'partial'
    setting['blocker']='' if complete else f"Faltan {len(unresolved)} fichas que todavía podrían alterar los primeros 100 puestos; clasificación provisional."
    save_ranking(setting,entries)
    report={'proof':proof,'windows':windows,'verified':len(verified),'verified_ids':[r['source_horse_id'] for r in verified],
            'excluded_by_bound':excluded,'failures':failures,
            'unresolved':unresolved,'final_cutoff':str(cutoff),'complete':complete}
    destination=ROOT/'data'/'ranking_cache'/'ar-ranking-report.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    db.record_import('ar-studbook',setting['source_url'],'ranking','success' if report['complete'] else 'partial',min(100,len(verified)),setting['scope']+' '+setting['blocker'])
    print(json.dumps({k:v for k,v in report.items() if k not in ('windows','verified_ids')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int)
    args=parser.parse_args();db.init();import_ranking(args.limit)
