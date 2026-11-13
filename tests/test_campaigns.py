import copy,io,json,os,sqlite3,tempfile,unittest
from pathlib import Path
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from app import db
from app.argentina import parse_campaign,campaign_report
from app.campaigns import parse_maronas_campaign,coverage
from app.main import app,save_batch
from app.scraper import ScrapeError

FIXTURES=Path(__file__).parent/'fixtures'
ARG_URL='https://www.studbook.org.ar/ejemplares/perfil/428095/acento-final'


class CampaignParserTests(unittest.TestCase):
    def test_argentine_total_turf_and_nonwinner_details(self):
        html=(FIXTURES/'argentina-campaign.html').read_text();rows=parse_campaign(html,ARG_URL)
        self.assertEqual(campaign_report(html,ARG_URL,rows)['status'],'complete_in_source')
        self.assertEqual(len(rows),17)
        r=rows[0];self.assertEqual(r['position'],3);self.assertEqual(r['surface'],'Césped')
        self.assertEqual(r['time'],'');self.assertTrue(r['details']['winner_time'])
        self.assertEqual(r['details']['trainer'],'Villabona Cristian P.')
        self.assertEqual(r['details']['horse_weight_kg'],'518')
        self.assertEqual(r['details']['earnings_ars'],'$7,000,000')
        self.assertIn('/reuniones/carrera/235136/',r['details']['race_url'])
        self.assertIn('youtube.com',r['details']['video_url'])

    def test_nonnumeric_finish_is_preserved_and_duplicates_rejected(self):
        soup=BeautifulSoup((FIXTURES/'argentina-campaign.html').read_text(),'html.parser')
        tr=soup.select_one('table.carreras tbody tr[data-fecha]');tr.find_all('td',recursive=False)[15].string='DESC.'
        rows=parse_campaign(str(soup),ARG_URL)
        self.assertEqual(len(rows),17);self.assertIsNone(rows[0]['position']);self.assertEqual(rows[0]['finish_status'],'DESC.')
        tr.parent.append(copy.copy(tr))
        with self.assertRaisesRegex(ScrapeError,'repite'):parse_campaign(str(soup),ARG_URL)

    def test_missing_or_mismatched_summary_never_claims_completeness(self):
        html=(FIXTURES/'argentina-campaign.html').read_text();rows=parse_campaign(html,ARG_URL)
        self.assertEqual(campaign_report(html,ARG_URL,rows[:-1])['status'],'partial_in_source')
        old=(FIXTURES/'argentina-profile.html').read_text()
        self.assertEqual(campaign_report(old,ARG_URL,[])['status'],'partial_in_source')
        self.assertIsNone(campaign_report(old,ARG_URL,[])['expected_starts'])

    def test_historical_zero_placeholders_are_unknown_not_zero_metre_races(self):
        html=(FIXTURES/'argentina-campaign-historical.html').read_text()
        url='https://www.studbook.org.ar/ejemplares/perfil/101665/ilimitada'
        rows=parse_campaign(html,url)
        self.assertEqual(len(rows),6)
        unknown=[r for r in rows if r['distance'] is None]
        self.assertEqual(len(unknown),2)
        for r in unknown:
            self.assertEqual(r['details']['distance_raw'],'0');self.assertEqual(r['time'],'')
            self.assertNotIn('horse_weight_kg',r['details']);self.assertEqual(r['time_kind'],'unknown')
        self.assertEqual(campaign_report(html,url,rows)['status'],'complete_in_source')

    def test_conflicting_source_rows_do_not_discard_other_career_starts(self):
        html=(FIXTURES/'argentina-campaign-conflict.html').read_text()
        url='https://www.studbook.org.ar/ejemplares/perfil/152723/jungle-bunny'
        rows=parse_campaign(html,url,quarantine_conflicts=True)
        self.assertEqual(len(rows),29)
        self.assertFalse(any(r['race_id']=='ar-race:71326' for r in rows))
        report=campaign_report(html,url,rows)
        self.assertEqual(report['status'],'partial_in_source')
        self.assertIn('1 carreras de la tabla permanecen sin incorporar',report['message'])

    def uruguay(self):
        card=json.loads((FIXTURES/'maronas-campaign.json').read_text());o=card['Horse']
        h={'id':'test-patriarca','name':'ES PATRIARCA','birth_year':2023,'birth_country':'URU','sex':'M','sire_id':'test-sire','dam_id':'test-dam'}
        nodes={h['id']:h,'test-sire':{'name':o['Sire']['Name']},'test-dam':{'name':o['Mare']['Name']}}
        return card,h,nodes

    def test_uruguayan_final_time_field_size_and_empty_history(self):
        card,h,nodes=self.uruguay();rows,review=parse_maronas_campaign(card,h,71619,nodes)
        self.assertEqual(review['status'],'complete_in_source');self.assertEqual(len(rows),7)
        self.assertEqual(rows[0]['field_size'],8);self.assertEqual(rows[0]['position'],5)
        self.assertEqual(rows[0]['time_kind'],'individual');self.assertEqual(rows[0]['time'],'2:37.229')
        self.assertEqual(rows[0]['details']['winner_time'],'2:35.084')
        self.assertEqual(rows[0]['details']['margin'],'12 Cpos.')
        card['Performances']=[]
        rows,review=parse_maronas_campaign(card,h,71619,nodes)
        self.assertEqual(review['expected_starts'],7);self.assertEqual(review['status'],'partial_in_source')

    def test_cross_publisher_identity_requires_both_parents_and_real_year(self):
        for mutation in ('dam','year','name'):
            card,h,nodes=self.uruguay()
            if mutation=='dam':card['Horse']['Mare']['Name']='Different dam'
            if mutation=='year':card['Horse']['BirthDate']='1900-07-01T00:00:00'
            if mutation=='name':card['Horse']['Name']='Homónimo diferente'
            with self.subTest(mutation=mutation),self.assertRaises(ScrapeError):parse_maronas_campaign(card,h,71619,nodes)

    def test_scope_includes_every_displayed_record_without_fabricating_zero_starts(self):
        report=coverage([{'id':'a','name':'A'},{'id':'b','name':'B'}],[{'horse_id':'a'}],[])
        self.assertEqual(report['total_horses'],2);self.assertEqual(report['with_starts'],1)
        self.assertEqual(report['statuses'],{'pending':2});self.assertEqual(report['global_complete'],0)


class CampaignPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.previous=os.environ.get('CONSTASTRO_DB')
        os.environ['CONSTASTRO_DB']=str(Path(self.tmp.name)/'campaign.sqlite3')
        self.client=TestClient(app);self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        if self.previous is None:os.environ.pop('CONSTASTRO_DB',None)
        else:os.environ['CONSTASTRO_DB']=self.previous
        self.tmp.cleanup()

    def test_details_null_finish_reviews_export_and_import(self):
        r=parse_campaign((FIXTURES/'argentina-campaign.html').read_text(),ARG_URL)[0]
        h={'id':r['horse_id'],'name':r['horse_name'],'country':'ARG'}
        r['position']=None;r['finish_status']='DESC.'
        save_batch([h],[r])
        review={'horse_id':h['id'],'source_id':'ar-studbook','status':'partial_in_source','expected_starts':17,'observed_starts':1,
                'source_url':ARG_URL,'observed_at':db.now(),'scope':'Sólo Argentina','message':'Faltan actuaciones'}
        db.save_campaign_review(h['id'],'ar-studbook',review)
        data=self.client.get('/api/horses/'+h['id']).json()
        self.assertEqual(data['campaign'][0]['details']['trainer'],'Villabona Cristian P.')
        self.assertIsNone(data['campaign'][0]['position']);self.assertEqual(len(data['campaign_reviews']),1)
        backup=self.client.get('/api/export.json').json()
        restored=self.client.post('/api/import',json=backup);self.assertEqual(restored.status_code,200,restored.text)
        wb=load_workbook(io.BytesIO(self.client.get('/api/export.xlsx').content))
        self.assertEqual(wb['Cobertura campañas'].max_row,2)
        header={c.value:c.column for c in wb['Resultados'][1]}
        self.assertEqual(wb['Resultados'].cell(2,header['Estado de llegada']).value,'DESC.')
        self.assertEqual(wb['Resultados'].cell(2,header['Premios ARS publicados']).value,'$7,000,000')
        invalid={**review,'status':'complete_in_source'}
        self.assertEqual(self.client.post('/api/import',json={'campaign_reviews':[invalid]}).status_code,422)

    def test_old_not_null_results_table_migration_preserves_every_row(self):
        # Recreate the previous schema, then migrate twice to prove idempotence.
        with db.connection() as con:
            con.execute('DROP TABLE results')
            con.execute('''CREATE TABLE results (id TEXT PRIMARY KEY,country TEXT NOT NULL,track TEXT NOT NULL,date TEXT NOT NULL,race_name TEXT NOT NULL,distance INTEGER,surface TEXT,position INTEGER NOT NULL,horse_name TEXT NOT NULL,horse_id TEXT REFERENCES horses(id),jockey TEXT,time TEXT,source_url TEXT NOT NULL,fetched_at TEXT NOT NULL,is_demo INTEGER NOT NULL DEFAULT 0)''')
            con.execute("INSERT INTO results VALUES ('old','ARG','Palermo','2026-01-01','Prueba',1200,'Arena',1,'Ejemplo',NULL,'Jinete','1:10','https://www.studbook.org.ar/prueba','2026-01-01',0)")
        db.init();db.init()
        with db.connection() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM results').fetchone()[0],1)
            self.assertEqual(con.execute('SELECT time FROM results').fetchone()[0],'1:10')
            self.assertFalse(next(r['notnull'] for r in con.execute('PRAGMA table_info(results)') if r['name']=='position'))
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
