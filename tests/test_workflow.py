import io
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.genetics import analyze, validate_graph
from app.main import app
from app.scraper import ScrapeError, parse_horses, parse_results, source_by_id, validate_url
from app.argentina import parse_profile, parse_campaign


def horse(ident,sex="M",sire=None,dam=None):
    return {"id":ident,"name":ident,"country":"URU","sex":sex,"sire_id":sire,"dam_id":dam}


class KinshipTests(unittest.TestCase):
    def test_unrelated_founders(self):
        r=analyze('a','b',[horse('a'),horse('b','H')])
        self.assertEqual(r['coefficient'],0)
        self.assertEqual(r['coverage'],0)

    def test_full_siblings_and_parent_child(self):
        nodes=[horse('f'),horse('m','H'),horse('son','M','f','m'),horse('daughter','H','f','m')]
        self.assertEqual(analyze('son','daughter',nodes)['coefficient'],25)
        self.assertEqual(analyze('f','daughter',nodes)['coefficient'],25)

    def test_half_siblings(self):
        nodes=[horse('f'),horse('m1','H'),horse('m2','H'),horse('s','M','f','m1'),horse('d','H','f','m2')]
        self.assertEqual(analyze('s','d',nodes)['coefficient'],12.5)

    def test_inbred_parent_is_accounted_for(self):
        nodes=[horse('f'),horse('m','H'),horse('s','M','f','m'),horse('d','H','f','m'),horse('inbred','M','s','d'),horse('fresh','H'),horse('child','H','inbred','fresh')]
        self.assertEqual(analyze('inbred','child',nodes)['coefficient'],31.25)

    def test_cycles_rejected(self):
        with self.assertRaisesRegex(ValueError,'ciclo'):
            validate_graph([horse('a',sire='b'),horse('b',sire='a')])


class ParserTests(unittest.TestCase):
    def test_historical_years_are_imported_and_ambiguous_dates_are_rejected(self):
        def table(year):
            return f'<table><tr><th>ID</th><th>Nombre</th><th>Año</th><th>Padre ID</th></tr><tr><td>1</td><td>Antepasado de prueba</td><td>{year}</td><td></td></tr></table>'
        source=source_by_id('uy-studbook')
        for year in (1680,1799,1880,1935):
            with self.subTest(year=year):
                self.assertEqual(parse_horses(table(year),source['url'],source)[0]['birth_year'],year)
        with self.assertRaisesRegex(ScrapeError,'varios años'):
            parse_horses(table('1880 / 1881'),source['url'],source)

    def test_actual_argentine_profile_to_three_generations(self):
        url='https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud'
        records=parse_profile(Path('tests/fixtures/argentina-profile.html').read_text(),url)
        graph=validate_graph(records)
        root=graph['ar-studbook:429310']
        self.assertEqual(len(records),15)
        self.assertEqual(root['birth_year'],2021)
        self.assertEqual(graph[root['sire_id']]['name'],'IL CAMPIONE (CHI)')
        self.assertEqual(graph[root['dam_id']]['name'],'FIRST FACE (USA)')
        self.assertEqual(graph[graph[root['sire_id']]['sire_id']]['name'],'SCAT DADDY (USA)')

    def test_actual_campaign_preserves_positions_and_winners_time_only(self):
        url='https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud'
        rows=parse_campaign(Path('tests/fixtures/argentina-profile.html').read_text(),url)
        self.assertEqual(len(rows),9)
        self.assertEqual(rows[1]['date'],'2026-07-26')
        self.assertEqual(rows[1]['track'],'La Plata')
        self.assertEqual(rows[1]['position'],1)
        self.assertTrue(rows[1]['time'])
        self.assertEqual(rows[2]['position'],7)
        self.assertEqual(rows[2]['time'],'')

    def test_public_pedigree_table_preserves_stable_ids(self):
        src=source_by_id('uy-studbook')
        records=parse_horses(Path('tests/fixtures/pedigree.html').read_text(),'https://www.studbook.com.uy/lista',src)
        self.assertEqual(len(records),3)
        graph=validate_graph(records)
        root=next(h for h in records if h['name']=='Caballo de prueba')
        self.assertEqual(graph[root['sire_id']]['name'],'Padre de prueba')
        self.assertEqual(root['is_demo'],0)

    def test_no_merging_by_name(self):
        html='<table><tr><th>Nombre</th><th>Padre</th></tr><tr><td>Homónimo</td><td>Otro</td></tr></table>'
        with self.assertRaisesRegex(ScrapeError,'identificadores'):
            parse_horses(html,'https://www.studbook.com.uy/lista',source_by_id('uy-studbook'))

    def test_results_require_date_and_race(self):
        html=Path('tests/fixtures/results.html').read_text()
        src=source_by_id('uy-maronas')
        with self.assertRaises(ScrapeError): parse_results(html,src['url'],src,{})
        rows=parse_results(html,src['url'],src,{'date':'2026-01-01','track':'Maroñas','race_name':'Fixture sintético'})
        self.assertEqual([r['position'] for r in rows],[1,2])
        self.assertEqual(rows[0]['horse_name'],'Ejemplo ganador')

    def test_scraper_rejects_external_and_credential_urls(self):
        src=source_by_id('uy-studbook')
        for url in ['http://www.studbook.com.uy','https://127.0.0.1','https://www.studbook.com.uy.evil.org/','https://user:pass@www.studbook.com.uy','https://www.studbook.com.uy:8000/']:
            with self.subTest(url=url),self.assertRaises(ScrapeError): validate_url(url,src)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=os.environ.get('CONSTASTRO_DB')
        os.environ['CONSTASTRO_DB']=str(Path(self.tmp.name)/'test.sqlite3')
        self.client=TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        if self.previous is None: os.environ.pop('CONSTASTRO_DB',None)
        else: os.environ['CONSTASTRO_DB']=self.previous
        self.tmp.cleanup()

    def test_demo_is_separate_and_pedigree_has_eight_great_grandparents(self):
        self.assertEqual(self.client.get('/api/horses').json(),[])
        r=self.client.get('/api/horses/demo-faro?demo=true').json()
        def leaves(n): return leaves(n['sire'])+leaves(n['dam']) if n['sire'] else [n]
        great=leaves(r['pedigree'])
        self.assertEqual(len(great),8)
        self.assertTrue(all(h['id'] and h['depth']==3 for h in great))
        cross=self.client.post('/api/compatibility',json={'sire_id':'demo-faro','dam_id':'demo-brisa','demo':True}).json()
        self.assertEqual(cross['coefficient'],3.125)
        self.assertEqual(cross['coverage'],100)

    def test_json_import_roundtrip_and_transaction_rollback(self):
        rows=[horse('real-f'),horse('real-m','H'),horse('real-child','M','real-f','real-m')]
        response=self.client.post('/api/import',json={'horses':rows})
        self.assertEqual(response.status_code,200,response.text)
        exported=self.client.get('/api/export.json').json()
        self.assertEqual(len(exported['horses']),3)
        self.assertEqual(self.client.post('/api/import',json=exported).status_code,200)
        bad=[horse('bad1'),horse('bad2',sire='missing')]
        self.assertEqual(self.client.post('/api/import',json={'horses':bad}).status_code,422)
        self.assertEqual(len(self.client.get('/api/horses').json()),3)

    def test_results_are_persistent_filterable_and_exported(self):
        result={'id':'race-1','country':'URU','track':'Maroñas','date':'2026-01-01','race_name':'Fixture','position':1,'horse_name':'Prueba sintética','source_url':'https://hipica.maronas.com.uy/fixture'}
        r=self.client.post('/api/import',json={'results':[result]})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(self.client.get('/api/results?country=URU').json()),1)
        self.assertEqual(self.client.get('/api/results?country=ARG').json(),[])
        self.assertEqual(self.client.get('/api/results?on_date=2026-01-02').json(),[])
        x=self.client.get('/api/export.xlsx')
        wb=load_workbook(io.BytesIO(x.content))
        self.assertEqual(wb['Resultados'].max_row,2)

    def test_argentine_scrape_route_saves_profile_and_campaign_together(self):
        html=Path('tests/fixtures/argentina-profile.html').read_text()
        with patch('app.main.fetch_public',return_value=html):
            response=self.client.post('/api/scrape',json={'source_id':'ar-studbook','kind':'results','url':'https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['horses'],15)
        self.assertEqual(response.json()['results'],9)
        self.assertEqual(len(self.client.get('/api/results?country=ARG&track=La+Plata').json()),9)

    def test_backup_larger_than_legacy_ten_thousand_limit_can_be_restored(self):
        rows=[horse('backup-'+str(i)) for i in range(10001)]
        response=self.client.post('/api/import',json={'horses':rows})
        self.assertEqual(response.status_code,200,response.text[:300])
        self.assertEqual(response.json()['horses'],10001)
        backup=self.client.get('/api/export.json').json()
        self.assertEqual(len(backup['horses']),10001)
        response=self.client.post('/api/import',json=backup)
        self.assertEqual(response.status_code,200,response.text[:300])

    def test_excel_contains_all_fourteen_ancestor_positions_and_no_formulas(self):
        self.client.post('/api/import',json={'horses':[{**horse('formula'), 'name':'=HYPERLINK("https://example.org")'}]})
        real=self.client.get('/api/export.xlsx')
        wb=load_workbook(io.BytesIO(real.content))
        self.assertEqual(wb['Caballos']['B2'].data_type,'s')
        demo=self.client.get('/api/export.xlsx?demo=true')
        wb=load_workbook(io.BytesIO(demo.content))
        self.assertEqual(len(wb.sheetnames),7)
        self.assertEqual(wb['Pedigree 3G'].max_column,34)
        self.assertEqual(wb['Caballos'].max_row,30)
        self.assertEqual(wb['Resultados'].max_row,1)
        self.assertIn('DEMOSTRACIÓN',wb['Leer primero']['B4'].value)


if __name__=='__main__': unittest.main()
