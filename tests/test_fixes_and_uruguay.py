import copy
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from app import db
from app.excel import export_workbook
from app.genetics import validate_graph
from app.scraper import ScrapeError,parse_results,source_by_id,fetch_public_json
from app.uruguay import parse_pedigree,parse_race,format_time
import test_workflow as workflow
from test_workflow import horse


def fixture(name):
    return json.loads((Path('tests/fixtures')/name).read_text())


class UruguayParserTests(unittest.TestCase):
    def test_json_with_utf8_bom_is_accepted(self):
        with patch('app.scraper.authorize_public'),patch('app.scraper.download',return_value='\ufeff{"ok":true}'):
            self.assertEqual(fetch_public_json('https://www.studbook.com.uy/',source_by_id('uy-studbook')),{'ok':True})

    def test_official_pedigree_keeps_ids_relations_and_three_generations(self):
        data=fixture('uruguay-pedigree.json')
        records=parse_pedigree(data['pedigree'],data['profile'])
        graph=validate_graph(records)
        root=graph['uy-studbook:49882']
        self.assertEqual(len(records),15)
        self.assertEqual(root['birth_year'],2002)
        self.assertEqual(graph[root['sire_id']]['name'],'CANDY STRIPES (USA)')
        self.assertEqual(graph[root['dam_id']]['name'],'QUENDOM (ARG)')
        self.assertEqual(sum(h['featured'] for h in records),1)

    def test_profile_id_mismatch_rejected(self):
        data=fixture('uruguay-pedigree.json');data['profile']['id']=999
        with self.assertRaisesRegex(ScrapeError,'mismo ID'):
            parse_pedigree(data['pedigree'],data['profile'])

    def test_official_maronas_race_has_six_individual_times(self):
        data=fixture('maronas-race.json')
        rows=parse_race(data['race'],data['participants'],1,'2026-10-18',1)
        self.assertEqual([r['position'] for r in rows],[1,2,3,4,5,6])
        self.assertTrue(all(r['scope']=='full' and r['field_size']==6 for r in rows))
        self.assertTrue(all(r['time_kind']=='individual' for r in rows))
        self.assertEqual(rows[0]['horse_name'],'Mad Sharp')
        self.assertEqual(rows[0]['time'],'1:23.312')
        self.assertNotEqual(rows[1]['time'],rows[0]['time'])

    def test_missing_finisher_is_partial_and_wrong_race_is_rejected(self):
        data=fixture('maronas-race.json')
        rows=parse_race(data['race'],data['participants'][:2],1,'2026-10-18',1)
        self.assertTrue(all(r['scope']=='partial' for r in rows))
        with self.assertRaisesRegex(ScrapeError,'no corresponde'):
            parse_race(data['race'],data['participants'],13,'2026-10-18',1)
        data['race']['StatusId']=1
        with self.assertRaisesRegex(ScrapeError,'definitivos'):
            parse_race(data['race'],data['participants'],1,'2026-10-18',1)

    def test_missing_date_becomes_useful_validation_error(self):
        html=Path('tests/fixtures/results.html').read_text()
        with self.assertRaisesRegex(ScrapeError,'fecha'):
            parse_results(html,'https://hipica.maronas.com.uy/',source_by_id('uy-maronas'),{'date':None})

    def test_time_format_preserves_exact_minutes(self):
        self.assertEqual(format_time('00:02:00'),'2:00')
        self.assertEqual(format_time('00:01:23.3120000'),'1:23.312')


class ImportRegressionTests(unittest.TestCase):
    setUp=workflow.ApplicationTests.setUp
    tearDown=workflow.ApplicationTests.tearDown

    def test_partial_import_cannot_erase_sex_source_country_or_parentage(self):
        rows=[horse('father'),horse('mother','H'),{**horse('child','H','father','mother'),'country':'ARG','source_id':'ar-studbook','notes':'Información documentada'}]
        self.assertEqual(self.client.post('/api/import',json={'horses':rows}).status_code,200)
        response=self.client.post('/api/import',json={'horses':[{'id':'child','name':'Nombre actualizado'}]})
        self.assertEqual(response.status_code,200,response.text)
        child=self.client.get('/api/horses/child').json()['horse']
        self.assertEqual((child['sex'],child['country'],child['source_id']),('H','ARG','ar-studbook'))
        self.assertEqual(child['dam_id'],'mother')
        self.assertEqual(child['notes'],'Información documentada')

    def test_stub_import_does_not_demote_a_profile_or_make_known_sex_unknown(self):
        self.client.post('/api/import',json={'horses':[{**horse('known'),'featured':True,'source_id':'uy-studbook'}]})
        r=self.client.post('/api/import',json={'horses':[{**horse('known','U'),'featured':False,'source_id':'uy-studbook'}]})
        self.assertEqual(r.status_code,200,r.text)
        saved=self.client.get('/api/horses/known').json()['horse']
        self.assertEqual(saved['sex'],'M');self.assertTrue(saved['featured'])

    def test_duplicate_ids_fail_without_partially_saving(self):
        r=self.client.post('/api/import',json={'horses':[horse('same'),{**horse('same'),'name':'Otro nombre'}]})
        self.assertEqual(r.status_code,422)
        self.assertEqual(self.client.get('/api/horses').json(),[])

    def test_results_date_is_validated_and_migration_is_repeatable(self):
        self.assertEqual(self.client.get('/api/results?on_date=incorrecta').status_code,422)
        db.init();db.init()
        with db.connection() as con:
            self.assertIn('time_kind',{r['name'] for r in con.execute('PRAGMA table_info(results)')})

    def test_native_uruguay_routes_save_the_official_payloads(self):
        data=fixture('uruguay-pedigree.json')
        rows=parse_pedigree(data['pedigree'],data['profile'])
        with patch('app.uruguay.import_pedigree',return_value=rows):
            r=self.client.post('/api/uruguay/pedigree',json={'horse_id':49882})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['horses'],15)
        race=fixture('maronas-race.json')
        results=parse_race(race['race'],race['participants'],1,'2026-10-18',1)
        with patch('app.uruguay.import_race',return_value=results):
            r=self.client.post('/api/uruguay/results',json={'track_id':1,'date':'2026-10-18','race_number':1})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['results'],6)
        self.assertEqual(r.json()['scope'],'full')

    def test_campaign_and_excel_preserve_timing_and_coverage(self):
        self.test_native_uruguay_routes_save_the_official_payloads()
        wb=load_workbook(io.BytesIO(self.client.get('/api/export.xlsx').content))
        headers=[c.value for c in wb['Resultados'][1]]
        self.assertIn('Tipo de tiempo',headers)
        self.assertIn('Participantes oficiales',headers)
        self.assertEqual(wb['Resultados'].max_row,7)


class ExcelRegressionTests(unittest.TestCase):
    def test_all_split_sheets_have_headers_and_filters_even_when_empty(self):
        rows=[{**horse(str(i)),'source_id':'manual'} for i in range(5)]
        wb=load_workbook(io.BytesIO(export_workbook(rows,[],[],sheet_row_limit=4)))
        self.assertEqual(wb['Caballos'].max_row,4)
        self.assertEqual(wb['Caballos 2'].max_row,3)
        self.assertEqual(wb['Caballos'].auto_filter.ref,'A1:N4')
        self.assertEqual(wb['Caballos 2'].auto_filter.ref,'A1:N3')
        self.assertEqual(wb['Resultados']['A1'].fill.fgColor.rgb,'00203B31')


if __name__=='__main__':unittest.main()
