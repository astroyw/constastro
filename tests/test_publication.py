import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import db
from app.main import app


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.environment=patch.dict(os.environ,{
            'CONSTASTRO_DB':str(Path(self.tmp.name)/'public.sqlite3'),
            'PUBLIC_READ_ONLY':'true',
        })
        self.environment.start()
        self.client=TestClient(app).__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.environment.stop()
        self.tmp.cleanup()

    def test_public_visitors_cannot_write_or_trigger_source_requests(self):
        with patch('app.main.save_batch') as save,patch('app.main.uruguay.search_horses') as search,patch('app.main.uruguay.import_pedigree') as pedigree,patch('app.main.fetch_public') as fetch:
            for path in ('/api/import','/api/scrape','/api/uruguay/pedigree','/api/uruguay/results','/api/import/'):
                with self.subTest(path=path):
                    self.assertEqual(self.client.post(path,json={}).status_code,403)
            self.assertEqual(self.client.get('/api/uruguay/search?q=invasor').status_code,403)
            self.assertEqual(self.client.delete('/api/import').status_code,403)
            for action in (save,search,pedigree,fetch):action.assert_not_called()
        with db.connection() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM imports').fetchone()[0],0)

    def test_consultation_analysis_and_excel_remain_available(self):
        configuration=self.client.get('/api/config').json()
        self.assertTrue(configuration['read_only'])
        self.assertIsInstance(configuration['reference_checks'],list)
        for path in ('/','/static/app.js','/api/health','/api/horses?demo=true','/api/rankings','/api/results','/api/export.json'):
            with self.subTest(path=path):self.assertEqual(self.client.get(path).status_code,200)
        cross=self.client.post('/api/compatibility',json={'sire_id':'demo-faro','dam_id':'demo-brisa','demo':True})
        self.assertEqual(cross.status_code,200,cross.text)
        self.assertIn('coefficient',cross.json())
        excel=self.client.get('/api/export.xlsx?demo=true')
        self.assertEqual(excel.status_code,200)
        self.assertIn('Pedigree 3G',load_workbook(io.BytesIO(excel.content),read_only=True).sheetnames)

    def test_unknown_setting_is_safe_and_local_mode_can_import(self):
        with patch.dict(os.environ,{'PUBLIC_READ_ONLY':'tru'}):
            self.assertEqual(self.client.post('/api/import',json={}).status_code,403)
        with patch.dict(os.environ,{'PUBLIC_READ_ONLY':'false'}):
            self.assertFalse(self.client.get('/api/config').json()['read_only'])
            response=self.client.post('/api/import',json={'horses':[{'id':'local-only','name':'Registro local','sex':'M'}]})
            self.assertEqual(response.status_code,200,response.text)
