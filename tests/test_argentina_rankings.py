import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from app.argentina_rankings import amount,parse_statistics,candidate_bounds,parse_ranked_profile
from app.genetics import validate_graph
from app.argentina import parse_profile
from app.scraper import ScrapeError


def window(start,end,values,cutoff,ceiling=None):
    return dict(start=start,end=end,ceiling=ceiling,cutoff=str(cutoff),entries=[
        dict(source_id=ident,name=ident,url='https://www.studbook.org.ar/ejemplares/perfil/'+ident,
             birth_country='ARG',earnings=str(value)) for ident,value in values])


class ArgentineHistoricalRankingTests(unittest.TestCase):
    def test_actual_statistics_has_ids_birth_flags_and_exact_nominal_amounts(self):
        html=Path('tests/fixtures/argentina-statistics.html').read_text()
        data=parse_statistics(html,'2024-01-01','2026-10-20','https://www.studbook.org.ar/estadisticas/generales')
        self.assertEqual(len(data['entries']),150)
        self.assertEqual(data['entries'][0]['name'],"THE GLADIATOR'S HAT")
        self.assertEqual(data['entries'][0]['earnings'],'300200750')
        self.assertEqual(data['entries'][0]['birth_country'],'ARG')
        self.assertEqual(next(e for e in data['entries'] if e['name']=='OBATAYE (BRZ)')['birth_country'],'BRA')
        self.assertEqual(data['cutoff'],'50596100')
        with self.assertRaisesRegex(ScrapeError,'filtro'):parse_statistics(html,'2024-01-01','2026-10-20','https://www.studbook.org.ar/',ceiling='50000000')

    def test_official_profile_uses_total_prize_not_prize_per_start(self):
        data=parse_ranked_profile(Path('tests/fixtures/argentina-earnings.html').read_text(),
                                  'https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud')
        self.assertEqual(data['birth_country'],'ARG')
        self.assertEqual(data['earnings_ars'],'10714850')
        self.assertEqual(data['earnings_usd'],'7598')
        self.assertEqual(data['campaign_years'],[2025,2026])
        nodes=validate_graph(data['horses'])
        self.assertEqual(nodes['ar-studbook:429310']['birth_country'],'ARG')
        self.assertEqual(nodes['ar-studbook:369626']['birth_country'],'CHL')

    def test_amount_conventions_preserve_cents_and_reject_malformed_values(self):
        self.assertEqual(amount('$1.234.567,89','es'),'1234567.89')
        self.assertEqual(amount('$1,234,567.89','en'),'1234567.89')
        for text in ('$1,23,4','U$S NaN','$-3'):
            with self.assertRaises(ScrapeError):amount(text,'en')

    def test_year_one_source_placeholder_does_not_break_a_valid_pedigree(self):
        html=Path('tests/fixtures/argentina-profile.html').read_text().replace('05/08/2011','01/01/0001')
        rows=parse_profile(html,'https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud')
        root=next(h for h in rows if h['id']=='ar-studbook:369626')
        self.assertIsNone(root['birth_year'])
        self.assertIn('Año publicado 1 omitido',root['notes'])
        validate_graph(rows)

    def test_missing_period_contributions_keep_a_potential_winner_in_candidates(self):
        a=window('2000-01-01','2002-12-31',[('a',100),('b',80),('c',70)],50)
        b=window('2003-01-01','2005-12-31',[('a',20),('b',10),('d',55)],10)
        eligible,proof=candidate_bounds([a,b],count=2)
        self.assertEqual({e['source_id'] for e in eligible},{'a','b','d'})
        self.assertEqual(next(e for e in eligible if e['source_id']=='d')['upper'],105)
        self.assertEqual(proof['unseen_upper'],'60')
        self.assertEqual(proof['threshold_lower'],'90')

    def test_refinement_is_not_added_twice_and_must_not_leave_a_gap(self):
        base=window('2000-01-01','2002-12-31',[('a',100),('b',80)],80)
        refine=window('2000-01-01','2002-12-31',[('b',80),('c',70)],70,ceiling='80')
        eligible,proof=candidate_bounds([base,refine],count=2)
        self.assertEqual(proof['candidates'],3)
        self.assertEqual(proof['unseen_upper'],'70')
        self.assertEqual(next(e for e in eligible if e['source_id']=='b')['lower'],80)
        bad=copy.deepcopy(refine);bad['ceiling']='75'
        with self.assertRaisesRegex(ValueError,'franja'):candidate_bounds([base,bad],count=2)
        bad=copy.deepcopy(refine);bad['entries'][0]['earnings']='79'
        with self.assertRaisesRegex(ValueError,'contradicen'):candidate_bounds([base,bad],count=2)

    def test_unseen_horses_and_date_gaps_prevent_a_completeness_claim(self):
        a=window('2000-01-01','2002-12-31',[('a',100),('b',80)],80)
        with self.assertRaisesRegex(ValueError,'refinar'):candidate_bounds([a],count=2)
        b=window('2004-01-01','2006-12-31',[('a',100)],10)
        with self.assertRaisesRegex(ValueError,'consecutivas'):candidate_bounds([a,b],count=2)

    def test_refinement_cache_key_changes_with_the_actual_prize_ceiling(self):
        from scripts.import_argentina_rankings import collect_windows
        def keys_for(ceiling):
            calls=[]
            def cache(key,operation):calls.append(key);return 'unused: parser replaced below'
            def parse(html,start,end,url,ceiling=None):
                return {'start':start,'end':end,'cutoff':str(ceiling or prize_limit)}
            prize_limit=ceiling
            with patch('scripts.import_argentina_rankings.cached',side_effect=cache),patch('scripts.import_argentina_rankings.parse_statistics',side_effect=parse):
                collect_windows()
            return calls
        first=keys_for('50596100');second=keys_for('60000000')
        self.assertEqual(first[:-1],second[:-1])
        self.assertNotEqual(first[-1],second[-1])
        self.assertIn('50596100',first[-1]);self.assertIn('60000000',second[-1])


if __name__=='__main__':unittest.main()
