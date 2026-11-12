import unittest
from app.ancestry import audit
from app.verification import compare_all
from app.argentina import parse_profile
from app.scraper import ScrapeError


def h(ident,name,year=1960,sire=None,dam=None,source='uy-studbook'):
    return dict(id=ident,name=name,birth_year=year,sire_id=sire,dam_id=dam,sex='M',source_id=source,source_url='https://'+('www.studbook.org.ar' if source=='ar-studbook' else 'www.studbook.com.uy')+'/'+ident)

class AncestryTests(unittest.TestCase):
    def test_nearco_alone_is_not_a_complete_tree(self):
        rows=[h('r','Root',2000,'n'),h('n','NEARCO',1935)]
        a=audit('r',{x['id']:x for x in rows})
        self.assertFalse(a['complete']);self.assertEqual(a['missing_links'],1)
        self.assertEqual(a['nearco'],[{'id':'n','generation':1}])

    def test_stops_at_target_era_without_completing_new_ancestors(self):
        rows=[h('r','Root',2000,'a','b'),h('a','Old',1935),h('b','Older',1930)]
        a=audit('r',{x['id']:x for x in rows})
        self.assertTrue(a['complete']);self.assertEqual(a['ancestor_count'],2)

    def test_unknown_year_is_not_a_terminal_and_repeated_ancestor_counts_once(self):
        rows=[h('r','Root',2000,'a','a'),h('a','Unknown',None)]
        a=audit('r',{x['id']:x for x in rows})
        self.assertFalse(a['complete']);self.assertEqual(a['ancestor_count'],1);self.assertEqual(a['missing_links'],2)
        self.assertEqual(audit('missing',{})['missing_links'],1)

class VerificationTests(unittest.TestCase):
    def families(self):
        return [h('a','NEARCO (ITY)',1935,'ap','am'),h('ap','PHAROS',1920),h('am','NOGARA',1928),
                h('b','NEARCO',1935,'bp','bm','ar-studbook'),h('bp','PHAROS',1920,source='ar-studbook'),h('bm','NOGARA',1928,source='ar-studbook')]

    def test_two_publishers_corroborate_only_known_fields(self):
        a=compare_all(self.families())['a']
        self.assertEqual(a['status'],'partial_agreement')
        self.assertIn('sire',a['confirmed_fields']);self.assertIn('coat',a['pending_fields'])
        self.assertFalse(a['all_data_verified'])

    def test_two_urls_same_publisher_are_not_two_sources(self):
        rows=self.families()
        for x in rows:x['source_id']='uy-studbook'
        self.assertEqual(compare_all(rows)['a']['status'],'single_source')

    def test_homonym_or_different_parent_does_not_verify_identity(self):
        rows=self.families();rows[-1]['name']='DIFFERENT'
        a=compare_all(rows)['a'];self.assertEqual(a['status'],'review_candidates');self.assertEqual(a['confirmed_fields'],[])
        self.assertEqual(a['comparisons'][0]['differences'][0]['field'],'dam')

    def test_multiple_candidates_are_ambiguous(self):
        rows=self.families();rows.append({**rows[3],'id':'b2'})
        self.assertEqual(compare_all(rows)['a']['status'],'review_candidates')

    def test_conflicting_coat_is_not_corroborated(self):
        rows=self.families();rows[0]['coat']='ZAINO';rows[3]['coat']='ALAZAN'
        a=compare_all(rows)['a'];self.assertIn('coat',a['pending_fields'])
        self.assertEqual(a['comparisons'][0]['differences'][0]['field'],'coat')

    def test_missing_year_and_manual_source_never_corroborate(self):
        rows=self.families();rows[0]['birth_year']=None
        self.assertEqual(compare_all(rows)['a']['status'],'review_candidates')
        self.assertEqual(compare_all(rows)['a']['confirmed_fields'],[])
        rows=self.families();rows[0]['source_id']='manual'
        self.assertEqual(compare_all(rows)['a']['status'],'single_source')

    def test_observation_without_parents_cannot_corroborate_carried_over_links(self):
        rows=self.families();evidence={h['id']:dict(h) for h in rows}
        evidence['b']['dam_id']=None
        self.assertEqual(compare_all(rows,evidence)['a']['status'],'review_candidates')
        self.assertEqual(compare_all(rows,{})['a']['confirmed_fields'],[])

class ArgentinaPartialTests(unittest.TestCase):
    def test_missing_ancestor_id_stays_unlinked_without_bridging_generations(self):
        from pathlib import Path
        from bs4 import BeautifulSoup
        url='https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud'
        soup=BeautifulSoup(Path('tests/fixtures/argentina-profile.html').read_text(),'html.parser')
        link=soup.select_one('#table-pedigree td.l1 a');link['href']='javascript:void(0)'
        with self.assertRaises(ScrapeError):parse_profile(str(soup),url)
        rows=parse_profile(str(soup),url,allow_missing_ids=True)
        root=next(r for r in rows if r['id']=='ar-studbook:429310')
        self.assertIsNone(root['sire_id']);self.assertIn('sin identificador',root['notes'])
