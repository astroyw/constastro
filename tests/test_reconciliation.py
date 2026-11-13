import unittest
from app.reconciliation import proposals

def family():
 a={'id':'a','name':'Child','birth_year':1970,'sex':'M','sire_id':'as','dam_id':'ad','source_id':'uy-studbook','source_url':'https://www.studbook.com.uy/child'}
 b={**a,'id':'b','sire_id':'bs','dam_id':'bd','source_id':'ar-studbook','source_url':'https://www.studbook.org.ar/child'}
 return [a,b,{'id':'as','name':'Father','birth_year':1940,'sex':'M','source_id':'uy-studbook','source_url':'https://www.studbook.com.uy/father'}, {'id':'ad','name':'Mother','birth_year':1942,'sex':'H','source_id':'uy-studbook'}, {'id':'bs','name':'Father','birth_year':1940,'sex':'M','sire_id':'old','source_id':'ar-studbook','source_url':'https://www.studbook.org.ar/father'}, {'id':'bd','name':'Mother','birth_year':1942,'sex':'H','source_id':'ar-studbook'}, {'id':'old','name':'Older','birth_year':1920,'source_id':'ar-studbook'}]
class ReconciliationTests(unittest.TestCase):
 def test_same_documented_child_supports_parent_identity_not_just_name(self):
  h=family();p=proposals(h,{x['id']:x for x in h},{'as'});self.assertEqual(p[0]['fields'],{'sire_id':'old'});self.assertEqual(p[0]['child_evidence'][0]['role'],'sire_id')
 def test_conflicting_parent_year_and_unverified_child_prevent_completion(self):
  h=family();h[4]['birth_year']=1941;self.assertEqual(proposals(h,{x['id']:x for x in h},{'as'}),[])
  h=family();h[1]['birth_year']=1971;self.assertEqual(proposals(h,{x['id']:x for x in h},{'as'}),[])
 def test_only_required_nodes_and_only_missing_facts(self):
  h=family();self.assertEqual(proposals(h,{x['id']:x for x in h},set()),[])
  h[2]['sire_id']='known';self.assertEqual(proposals(h,{x['id']:x for x in h},{'as'}),[])
 def test_duplicate_child_records_may_confirm_one_unambiguous_parent(self):
  h=family();h.append({**h[1],'id':'b-duplicate'})
  p=proposals(h,{x['id']:x for x in h},{'as'})
  self.assertEqual(p[0]['fields'],{'sire_id':'old'})
  self.assertFalse(p[0]['child_evidence'][0]['child_identity_supported'])
  self.assertEqual(set(p[0]['child_evidence'][0]['convergent_child_candidates']),{'b','b-duplicate'})
 def test_duplicate_candidates_with_different_parent_ids_are_not_resolved_by_name(self):
  h=family();h.extend([{**h[1],'id':'b-duplicate','sire_id':'bs2'},{**h[4],'id':'bs2'}])
  self.assertEqual(proposals(h,{x['id']:x for x in h},{'as'}),[])
 def test_any_candidate_with_different_parent_name_prevents_parent_confirmation(self):
  h=family();h.extend([{**h[1],'id':'b-duplicate','sire_id':'bs2'},{**h[4],'id':'bs2','name':'Other father'}])
  self.assertEqual(proposals(h,{x['id']:x for x in h},{'as'}),[])
