import copy
import io
import json
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app import db
from app.excel import export_workbook
from app.genetics import validate_graph
from app.main import save_batch
from app.rankings import parse_equibase,save_ranking,export_rankings
from app.uruguay import quarantine_inconsistent_birth_years
import test_workflow as workflow


def pages():
    return json.loads(Path('tests/fixtures/equibase-alltime.json').read_text())


def meta(ident='test',country=None,status='complete',count=1):
    return dict(id=ident,title='Fixture de prueba',birth_country=country,currency='USD',scope='Prueba aislada',
                source_url='https://www.equibase.com/',observed_at=db.now(),requested_count=count,
                status=status,methodology='Fixture',blocker='')


def entry(ident,position=1,earnings='123.45'):
    return dict(position=position,horse_id=ident,earnings=earnings,source_horse_id=ident,
                source_url='https://www.equibase.com/',observed_at=db.now())


class RankingParserTests(unittest.TestCase):
    def test_actual_equibase_two_pages_have_200_distinct_ranked_horses(self):
        horses,entries=parse_equibase(pages())
        self.assertEqual(len(entries),200)
        self.assertEqual([e['position'] for e in entries],list(range(1,201)))
        self.assertEqual(len({e['horse_id'] for e in entries}),200)
        nodes=validate_graph(horses)
        self.assertEqual(nodes[entries[0]['horse_id']]['name'],'Forever Young (JPN)')
        self.assertEqual(entries[0]['earnings'],'32313590.0')
        self.assertEqual(nodes[entries[0]['horse_id']]['birth_country'],'JPN')
        self.assertIsNone(next(h for h in horses if h['name']=='Arrogate')['birth_country'])
        self.assertEqual(sum(bool(h['featured']) for h in horses),200)
        self.assertGreater(len(horses),200)  # Ancestors never pad the ranking count.

    def test_incomplete_duplicate_or_unordered_download_is_rejected(self):
        data=pages()
        with self.assertRaisesRegex(ValueError,'exactamente'):parse_equibase(data[:1])
        broken=copy.deepcopy(data)
        broken[0]['stats'][1]['referenceNumber']=broken[0]['stats'][0]['referenceNumber']
        with self.assertRaisesRegex(ValueError,'repite'):parse_equibase(broken)
        broken=copy.deepcopy(data)
        broken[0]['stats'][1]['earnings']=999999999
        with self.assertRaisesRegex(ValueError,'descendente'):parse_equibase(broken)

    def test_ranked_sires_keep_their_known_sex_regardless_of_download_order(self):
        data=pages()
        forward={h['id']:h for h in parse_equibase(data)[0]}
        reverse={h['id']:h for h in parse_equibase(data[::-1])[0]}
        self.assertEqual({k:h['sex'] for k,h in forward.items()},{k:h['sex'] for k,h in reverse.items()})
        for name in ('Exaggerator','Tonalist','Devil His Due','Awesome Again'):
            self.assertEqual(next(h for h in forward.values() if h['name']==name)['sex'],'M')

    def test_impossible_dates_are_flagged_without_changing_relationships(self):
        records=[dict(id='s',name='S',sex='M',birth_year=1976),dict(id='d',name='D',sex='H',birth_year=1976),
                 dict(id='h',name='H',sex='M',birth_year=1976,sire_id='s',dam_id='d')]
        cleaned=quarantine_inconsistent_birth_years(records)
        nodes=validate_graph(cleaned)
        self.assertEqual(nodes['h']['sire_id'],'s')
        self.assertTrue(all(h['birth_year'] is None for h in cleaned))
        self.assertTrue(all('1976' in h['notes'] for h in cleaned))
        self.assertTrue(all(h['birth_year']==1976 for h in records))


class RankingPersistenceTests(unittest.TestCase):
    setUp=workflow.ApplicationTests.setUp
    tearDown=workflow.ApplicationTests.tearDown

    def test_country_of_birth_is_independent_of_registry_and_required(self):
        save_batch([dict(id='a',name='A',country='USA',birth_country='URU',sex='M'),
                    dict(id='b',name='B',country='URU',birth_country='ARG',sex='M')],[])
        save_ranking(meta(country='URU'),[entry('a')])
        self.assertEqual(self.client.get('/api/rankings/test').json()['entries'][0]['birth_country'],'URU')
        with self.assertRaisesRegex(ValueError,'nacimiento'):save_ranking(meta(country='URU'),[entry('b')])
        self.assertEqual(self.client.get('/api/rankings/test').json()['entries'][0]['horse_id'],'a')

    def test_rankings_cannot_use_demo_horses_or_claim_incomplete_as_complete(self):
        with self.assertRaisesRegex(ValueError,'ficticios'):save_ranking(meta(),[entry('demo-faro')])
        with self.assertRaisesRegex(ValueError,'completo'):save_ranking(meta(count=100),[])
        save_ranking(meta(status='blocked',count=100),[])
        row=self.client.get('/api/rankings').json()[0]
        self.assertEqual((row['count'],row['status']),(0,'blocked'))
        self.assertEqual(self.client.get('/api/rankings/missing').status_code,404)

    def test_bad_order_or_duplicate_ids_cannot_replace_a_valid_snapshot(self):
        save_batch([dict(id=x,name=x,country='URU',sex='M') for x in ('a','b')],[])
        save_ranking(meta(count=2),[entry('a',1,'9007199254740993.12'),entry('b',2,'12.25')])
        for invalid in ([entry('a',1,'1'),entry('b',2,'2')],[entry('a',1),entry('a',2)]):
            with self.assertRaises(ValueError):save_ranking(meta(count=2),invalid)
        data=self.client.get('/api/rankings/test').json()
        self.assertEqual(data['entries'][0]['earnings'],'9007199254740993.12')

    def test_interrupted_or_failed_refresh_preserves_the_last_complete_ranking(self):
        save_batch([dict(id=x,name=x,country='URU',sex='M') for x in ('a','b')],[])
        original=meta(count=2)
        self.assertTrue(save_ranking(original,[entry('a',1,'200'),entry('b',2,'100')]))
        before=self.client.get('/api/rankings/test').json()
        progress=meta(status='partial',count=2)
        progress['observed_at']='2026-10-21T00:00:00+00:00'
        self.assertFalse(save_ranking(progress,[entry('b',1,'300')]))
        self.assertFalse(save_ranking(meta(status='blocked',count=2),[]))
        self.assertEqual(self.client.get('/api/rankings/test').json(),before)
        self.assertTrue(save_ranking(meta(count=2),[entry('b',1,'300'),entry('a',2,'200')]))
        self.assertEqual(self.client.get('/api/rankings/test').json()['entries'][0]['horse_id'],'b')

    def test_progress_without_a_complete_snapshot_and_deliberate_invalidation_are_supported(self):
        save_batch([dict(id=x,name=x,country='URU',sex='M') for x in ('a','b')],[])
        self.assertTrue(save_ranking(meta(status='partial',count=2),[entry('a')]))
        self.assertTrue(save_ranking(meta(count=2),[entry('a',1,'200'),entry('b',2,'100')]))
        self.assertTrue(save_ranking(meta(status='blocked',count=2),[],allow_incomplete_replacement=True))
        self.assertEqual(self.client.get('/api/rankings/test').json()['entries'],[])

    def test_extra_positions_are_rejected_instead_of_inflating_the_requested_count(self):
        save_batch([dict(id=x,name=x,country='URU',sex='M') for x in ('a','b')],[])
        for status in ('complete','partial'):
            with self.assertRaisesRegex(ValueError,'supera'):
                save_ranking(meta(status=status,count=1),[entry('a',1,'200'),entry('b',2,'100')])

    def test_excel_keeps_birthplace_exact_earnings_scope_and_missing_lists(self):
        save_batch([dict(id='a',name='=unsafe()',country='USA',birth_country='URU',sex='M')],[])
        save_ranking(meta(country='URU'),[entry('a',earnings='9007199254740993.12')])
        save_ranking(meta(ident='pending',status='blocked',count=100),[])
        data=self.client.get('/api/export.xlsx').content
        wb=load_workbook(io.BytesIO(data))
        self.assertEqual(len(wb.sheetnames),13)
        self.assertEqual(wb['Ramas pendientes']['E1'].value,'Objetivos originales afectados')
        self.assertEqual(wb['Cobertura 1935']['C2'].value,'Pendiente')
        self.assertEqual(wb['Ganancias'].max_row,2)
        self.assertEqual(wb['Rankings'].max_row,3)
        self.assertEqual(wb['Ganancias']['F2'].value,'9007199254740993.12')
        self.assertEqual(wb['Ganancias']['D2'].data_type,'s')
        self.assertEqual(wb['Caballos']['N2'].value,'URU')
        self.assertIn('Cobertura',[c.value for c in wb['Rankings'][1]])
        split=load_workbook(io.BytesIO(export_workbook(db.horse_rows(False),[],[],rankings=export_rankings(),sheet_row_limit=2)))
        self.assertIn('Rankings 2',split.sheetnames)
        self.assertEqual(split['Rankings 2'].auto_filter.ref,'A1:K2')


if __name__=='__main__':unittest.main()
