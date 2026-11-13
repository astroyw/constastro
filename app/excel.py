from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .catalog import SOURCES
from .db import now
from .ancestry import audit,original_targets,pending_branches
from .verification import compare_all
from .evidence import load_evidence
from .source_checks import reference_checks

PATHS=[("Padre","s"),("Madre","d"),("Abuelo paterno","ss"),("Abuela paterna","sd"),("Abuelo materno","ds"),("Abuela materna","dd"),
       ("Bisabuelo PPP","sss"),("Bisabuela PPM","ssd"),("Bisabuelo PMP","sds"),("Bisabuela PMM","sdd"),
       ("Bisabuelo MPP","dss"),("Bisabuela MPM","dsd"),("Bisabuelo MMP","dds"),("Bisabuela MMM","ddd")]


def export_workbook(horses,results,imports,demo=False,*,sheet_row_limit=1_048_576,rankings=None,campaign_reviews=None):
    # Streaming workbook: split sheets at Excel's hard limit instead of truncating records.
    wb=Workbook(write_only=True)
    from openpyxl.cell import WriteOnlyCell
    if not 2<=sheet_row_limit<=1_048_576:
        raise ValueError('El límite de filas por hoja debe estar entre 2 y 1.048.576.')

    def sheet(name,headers,rows):
        part=0
        row_count=0
        ws=None
        def create():
            nonlocal part,row_count
            part+=1
            out=wb.create_sheet((name if part==1 else f'{name} {part}')[:31])
            out.freeze_panes='A2'
            for i,h in enumerate(headers,1):
                out.column_dimensions[get_column_letter(i)].width=min(42,max(20,len(h)+3))
            styled=[]
            for h in headers:
                c=WriteOnlyCell(out,value=h)
                c.font=Font(name='Calibri',bold=True,color='FFFFFF',size=11)
                c.fill=PatternFill('solid',fgColor='203B31')
                c.alignment=Alignment(vertical='center')
                styled.append(c)
            out.append(styled)
            row_count=1
            return out
        for row in rows:
            if ws is None or row_count>=sheet_row_limit:
                if ws is not None:
                    ws.auto_filter.ref=f'A1:{get_column_letter(len(headers))}{row_count}'
                ws=create()
            cells=[]
            for value in row:
                cell=WriteOnlyCell(ws,value=value)
                if isinstance(value,str):cell.data_type='s'
                cells.append(cell)
            ws.append(cells)
            row_count+=1
        if ws is None:ws=create()
        ws.auto_filter.ref=f'A1:{get_column_letter(len(headers))}{row_count}'

    nodes={h["id"]:h for h in horses}
    targets=original_targets()
    info=[
        ["Proyecto","Linaje · constastro"],["Generado UTC",now()],
        ["Contenido","DEMOSTRACIÓN: todos los caballos son ficticios" if demo else "Registros importados por el usuario o desde páginas públicas; revisar su procedencia"],
        ["Cantidad de caballos",len(horses)],["Resultados",len(results)],
        ["Cómo guardar datos","Caballos es la tabla normalizada: IDs únicos y referencias Padre ID / Madre ID. Pedigree 3G presenta los 14 ancestros en una fila por caballo."],
        ["Datos desconocidos","Las celdas vacías son datos faltantes; no indican ausencia de parentesco."],
        ["Homónimos","Nunca vincular caballos únicamente por su nombre. Usar el ID y comprobar el registro de origen."],
        ["Importación","La aplicación admite JSON según docs/importacion.md; este XLSX es una exportación para archivo y edición."],
        ["Genética","Un pedigree no sustituye una prueba genética ni predice aptitud deportiva. No incluye resultados de ADN."],
        ["Capacidad","El archivo divide automáticamente cada tabla al superar 1.048.575 registros por hoja. Limitado por almacenamiento y memoria del equipo."],
    ]
    if not demo:
        info.append(['Ascendencia histórica','Caballos conserva todas las generaciones enlazadas. Cobertura 1935 audita cada registro hasta que todas sus ramas alcanzan un nacimiento documentado en 1935 o antes (época de Nearco). Vacíos y años desconocidos quedan pendientes. No implica que todos desciendan de Nearco.'])
    sheet("Leer primero",["Campo","Información"],info)
    sheet("Caballos",["ID","Nombre","País de registro","Año nacimiento","Sexo M H C U","Pelaje","Padre ID","Madre ID","Fuente","URL de origen","Consultado UTC","Demostración","Notas","País de nacimiento"],
          ([h.get(k) for k in ["id","name","country","birth_year","sex","coat","sire_id","dam_id","source_id","source_url","fetched_at","is_demo","notes","birth_country"]] for h in horses))
    def pedigree_rows():
        for h in horses:
            row=[h['id'],h['name'],h.get('country'),h.get('birth_year')]
            for label,path in PATHS:
                a=h
                for p in path:
                    a=nodes.get(a.get("sire_id" if p=='s' else "dam_id")) if a else None
                row.extend([a['id'],a['name']] if a else [None,None])
            row.extend([h.get('source_url'),h.get('is_demo')])
            yield row
    sheet("Pedigree 3G",["ID","Caballo","País de registro","Año"]+[v for label,path in PATHS for v in [label+" ID",label+" nombre"]]+["URL de origen","Demostración"],pedigree_rows())
    if not demo:
        def coverage_rows():
            for h in horses:
                a=audit(h['id'],nodes)
                yield [h['id'],h['name'],'Completo' if a['complete'] else 'Pendiente',a['ancestor_count'],a['max_generation'],a['oldest_year'],a['missing_links'],a['terminals_1935'], '; '.join(f"{n['id']} (generación {n['generation']})" for n in a['nearco']),h['id'] in targets]
        sheet('Cobertura 1935',['ID','Nombre','Hasta 1935 en todas las ramas','Ancestros únicos','Generación más lejana documentada','Año más antiguo documentado','Enlaces pendientes','Ancestros terminales hasta 1935','Nearco documentado','Objetivo original'],coverage_rows())
        sheet('Ramas pendientes',['ID','Caballo con dato faltante','Año documentado','Relación pendiente','Objetivos originales afectados','URL de origen'],
              ([r['id'],r['name'],r['birth_year'],{'sire_id':'Padre','dam_id':'Madre','record':'Registro ausente'}[r['role']],r['affected_targets'],r['source_url']]
               for r in pending_branches(nodes,targets)))
    if not demo:
        comparisons=compare_all(horses,load_evidence())
        def verification_rows():
            for h in horses:
                v=comparisons[h['id']]
                for c in v['comparisons'] or [None]:
                    yield [h['id'],h['name'],v['status'],h.get('source_id'),v['primary_url'],c['source_id'] if c else '',c['id'] if c else '',c['url'] if c else '',c['observed_at'] if c else '',bool(c and c['identity_supported']),', '.join(v['confirmed_fields']),', '.join(v['pending_fields']),'; '.join(f"{d['field']}: {d['value']} / {d['other']}" for d in c['differences']) if c else '',v['scope']]
        sheet('Contraste fuentes',['ID','Nombre','Estado','Fuente inicial','URL inicial','Segunda fuente','Segundo ID','Segunda URL','Consulta segunda fuente','Identidad respaldada','Campos corroborados','Campos pendientes','Diferencias','Alcance'],verification_rows())
    detail_headers={'distance_raw':'Distancia original sin valor utilizable','time_raw':'Tiempo original sin valor utilizable','race_url':'URL carrera','race_number':'N.º carrera','published_order':'Orden publicado (O)','post_position':'Gatera','program_number':'Número de programa','category':'Categoría','conditions':'Condiciones','going':'Estado pista','going_code':'Estado pista (código)','weather':'Meteorología','horse_weight_kg':'Peso caballo kg','carried_weight_kg':'Peso primera pesada jinete kg','trainer':'Entrenador','stable':'Caballeriza','earnings_ars':'Premios ARS publicados','earnings_usd_source':'Premios USD según fuente','odds':'Pago / dividendo','margin':'Diferencia al ganador','winner_time':'Tiempo ganador','official_time':'Tiempo individual oficial','video_url':'URL video'}
    def result_rows():
        import json
        for r in results:
            details=r.get('details') or {}
            if isinstance(details,str):details=json.loads(details)
            yield [r.get(k) for k in ['id','country','track','date','race_name','distance','surface','position','horse_name','horse_id','jockey','time','source_url','fetched_at','race_id','time_kind','scope','field_size','finish_status']]+[details.get(k) for k in detail_headers]
    sheet("Resultados",["ID","País","Hipódromo","Fecha","Carrera","Distancia m","Pista","Puesto","Caballo","Caballo ID","Jinete","Tiempo","URL","Consultado UTC","Carrera ID","Tipo de tiempo","Cobertura clasificación","Participantes oficiales","Estado de llegada"]+list(detail_headers.values()),result_rows())
    if not demo:
        from .campaigns import coverage,STATUS_LABELS
        def campaign_rows():
            for row in coverage(horses,results,campaign_reviews or [])['horses']:
                for review in row['reviews'] or [{}]:
                    yield [row['horse_id'],row['name'],row['starts'],STATUS_LABELS.get(review.get('status',row['status'])),review.get('expected_starts'),review.get('observed_starts'),review.get('source_id'),review.get('source_url'),review.get('observed_at'),review.get('scope','Campaña todavía sin revisar.'),review.get('message',''), 'No acreditada']
        sheet('Cobertura campañas',['Caballo ID','Nombre','Actuaciones guardadas','Estado de consulta','Total declarado fuente','Actuaciones recuperadas fuente','Fuente ID','URL fuente','Consulta UTC','Ámbito de la fuente','Detalle','Campaña mundial completa'],campaign_rows())
        from .manual_reviews import manual_reviews
        reviewed=[r for r in manual_reviews() if r['id'] in nodes]
        if reviewed:
            sheet('Ampliaciones documentadas',['Caballo ID','Nombre','Campo','Valor anterior','Valor añadido','Fuente','Fecha de consulta','Dato publicado','Identidad documentada','Limitaciones'],
                  ([r['id'],r['name'],field,r['before'].get(field),value,ref['url'],ref['observed_at'],ref['facts'],r['identity_basis'],r['limitations']]
                   for r in reviewed for field,value in r['fields'].items() for ref in r['references']))
    source_rows=[[s['id'],s['country'],s['name'],s['kind'],s['url'],"Directorio; conexión y esquema requieren validación en origen"] for s in SOURCES]
    source_rows.extend([s['id'],'Internacional',s['name'],'Referencia adicional',s['url'],s['checked_at']+' · '+s['message']] for s in reference_checks())
    sheet("Fuentes",["ID","País","Organismo","Tipo","URL","Estado"],source_rows)
    sheet("Importaciones",["Fecha UTC","Fuente","Tipo","Estado","Filas","URL","Detalle"],([r.get(k) for k in ['created_at','source_id','kind','status','count','url','message']] for r in imports))
    sheet("Diccionario",["Campo","Definición"],[
        ['id','Identificador estable por registro, no derivado exclusivamente del nombre.'],
        ['sire_id / dam_id','Referencias al ID del padre y de la madre.'],
        ['country','País de registro: URU USA FRA GBR JPN HKG BRA ARG CHI.'],
        ['birth_country','País de nacimiento verificado. No se deduce del país de registro. Una celda vacía indica que falta confirmar.'],
        ['sex','M: macho; H: hembra; C: castrado; U: no registrado.'],
        ['source_url','Página de procedencia. Vacía para los ejemplos ficticios.'],
        ['is_demo','1: ejemplo ficticio. 0: registro importado. No equivale a validación oficial.'],
        ['fetched_at','Fecha de incorporación UTC. No es la fecha de la carrera.'],
        ['time_kind','winner: tiempo del ganador; individual: tiempo de ese caballo; unknown: tipo no identificado.'],
        ['Cobertura campañas','Una fila por caballo y fuente consultada, incluidos los registros sin actuaciones. Completa en esta fuente significa que el total declarado coincide con las carreras recuperadas, sólo dentro de su ámbito. No acredita una campaña mundial completa.'],
        ['Detalles de carrera','Datos publicados de pista, jinete, entrenador, peso, premios y video. Se conservan códigos sin interpretación cuando falta una equivalencia documentada. C en campañas argentinas significa Césped; se conserva también el código original. Un puesto vacío puede indicar llegada no numérica: ver Estado de llegada.'],
        ['scope / field_size','full: tantas llegadas numéricas como participantes oficiales; partial: clasificación incompleta. field_size contiene el número oficial de participantes cuando se conoce.'],
        ['P / M','En las rutas de ancestros, P significa padre y M significa madre, desde el caballo hacia atrás.'],
        ['Estimaciones por distancia','Índice orientativo 0–100, método campana-regularizada-v2. Siempre ofrece un número para un cruce válido. Sin actuaciones utilizables: 50/100, base neutral explícita y confianza Sin evidencia. No es probabilidad de ganar ni predicción genética validada.'],
        ['Valor de cada actuación','Con participantes oficiales: y=(participantes−puesto)/(participantes−1), peso q=1. Sin participantes oficiales: indicador auxiliar y=1/puesto, peso q=0,5. No son medidas equivalentes ni se inventa el número de participantes. Se exige fuente, caballo enlazado, distancia, superficie y puesto válidos.'],
        ['Regularización por caballo','v=(2+Σ(q×y))/(4+Σq). Base neutral 0,5 y fuerza de regularización 4 elegidas para moderar muestras pequeñas; no son carreras observadas ni parámetros calibrados.'],
        ['Ponderación por rama','Pesos w=1, 1/2, 1/4, 1/8 desde cada progenitor hasta sus bisabuelos. B=0,5+Σ(w×(v−0,5))/máximo(1,Σw). Índice=redondear(50×(B paterna+B materna)). Cada ID se usa una vez a su profundidad más cercana. Sin observaciones, la rama conserva 0,5.'],
        ['Confianza descriptiva','Sin evidencia cuando sólo actúa la base neutral. Baja con observaciones. Moderada con ≥30 actuaciones únicas, ≥3 caballos por rama, ≥3 actuaciones de cada progenitor y ≥80% con participantes oficiales. No es confianza estadística; no ajusta clase, edad, entrenamiento o salud.'],
        ['Perfiles de referencia','Classic 2000 m arena; Distaff 1800 m arena; Mile 1600 m césped; Turf 2400 m césped; Sprint 1200 m arena. Margen ±200 m. No evalúan elegibilidad por edad o sexo.'],
        ['Ganancias de rankings','Importes nominales de cada fuente, conservados como texto decimal exacto. No sumar monedas ni equiparar circuitos. Los rankings no cuentan ancestros como puestos adicionales.'],
    ])
    if rankings is not None and not demo:
        sheet('Rankings', ['ID ranking','Título','Nacimiento requerido','Moneda','Cobertura','Fuente','Consultado UTC','Puestos solicitados','Estado','Metodología','Pendiente'],
              ([batch['ranking'].get(k) for k in ['id','title','birth_country','currency','scope','source_url','observed_at','requested_count','status','methodology','blocker']] for batch in rankings))
        sheet('Ganancias', ['Ranking ID','Puesto','Caballo ID','Nombre','País de nacimiento','Ganancias nominales exactas','Moneda','ID en fuente','Fuente','Consultado UTC'],
              ([batch['ranking']['id'],e['position'],e['horse_id'],e.get('name'),e.get('birth_country'),e['earnings'],batch['ranking']['currency'],e['source_horse_id'],e['source_url'],e['observed_at']] for batch in rankings for e in batch['entries']))
    stream=BytesIO()
    wb.save(stream)
    return stream.getvalue()
