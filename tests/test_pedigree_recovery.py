import unittest
from copy import deepcopy

from app.genetics import validate_graph
from app.recovery import recover_batch


def horse(ident, year=None, sex='M', sire=None, dam=None):
    return {'id': ident, 'name': ident, 'birth_year': year, 'sex': sex,
            'sire_id': sire, 'dam_id': dam, 'source_id': 'uy-studbook',
            'source_url': 'https://www.studbook.com.uy/online-volume/horse/1',
            'fetched_at': '2026-01-01T00:00:00Z', 'featured': False}


class RecoveryTests(unittest.TestCase):
    def test_valid_branch_survives_but_conflicting_dates_are_not_guessed(self):
        original = [horse('root', 2000, sire='sire', dam='dam'), horse('sire', 1980), horse('dam', 1981, 'H')]
        observations = [horse('sire', 1980, sire='old'), horse('old', 1930),
                        horse('dam', 1981, 'H', dam='too-young'), horse('too-young', 1990, 'H')]
        plan = recover_batch(original, observations, {'root'})
        rows = {h['id']: h for h in plan['records']}
        self.assertEqual(set(rows), {'sire', 'old'})
        self.assertEqual(rows['sire']['sire_id'], 'old')
        self.assertEqual({h['id'] for h in plan['quarantined']}, {'dam', 'too-young'})
        validate_graph(list({**{h['id']: h for h in original}, **rows}.values()))

    def test_known_values_stay_immutable_and_links_to_disputed_identity_are_omitted(self):
        original = [horse('root', 2000), horse('disputed', 1970)]
        saved = deepcopy(original)
        plan = recover_batch(original, [horse('root', 2000, sire='disputed'), horse('disputed', 1980, sire='old'), horse('old', 1930)], {'root'})
        self.assertEqual(plan['records'], [])
        self.assertEqual(original, saved)
        self.assertEqual(plan['quarantined'][0]['id'], 'disputed')

    def test_incoming_date_conflicting_with_known_descendant_quarantines_record(self):
        original = [horse('root', 1947, sire='parent'), horse('parent')]
        plan = recover_batch(original, [horse('parent', 1962, sire='old'), horse('old', 1930)], {'root'})
        self.assertEqual(plan['records'], [])
        self.assertIn('Cronología', plan['quarantined'][0]['reasons'][0])

    def test_only_original_targets_and_branches_until_cutoff_are_recovered(self):
        original = [horse('root', 2000), horse('unrelated', 1980)]
        observations = [horse('root', 2000, sire='terminal'), horse('terminal', 1935, sire='beyond'),
                        horse('beyond', 1900), horse('unrelated', 1980, sire='outside'), horse('outside', 1920)]
        plan = recover_batch(original, observations, {'root'})
        rows = {h['id']: h for h in plan['records']}
        self.assertEqual(set(rows), {'root', 'terminal'})
        self.assertIsNone(rows['terminal']['sire_id'])

    def test_cycles_are_quarantined_without_discarding_separate_branch(self):
        original = [horse('root', sire='a', dam='b'), horse('a'), horse('b', sex='H')]
        plan = recover_batch(original, [horse('a', sire='root'), horse('b', sex='H', dam='old'), horse('old', 1930, 'H')], {'root'})
        self.assertEqual({h['id'] for h in plan['records']}, {'b', 'old'})
        self.assertEqual(plan['quarantined'][0]['id'], 'a')

    def test_conflicting_repeated_id_is_not_resolved_by_input_order(self):
        original = [horse('root', 2000)]
        plan = recover_batch(original, [horse('root', 2000, sire='p'), horse('p', 1970), horse('p', 1980)], {'root'})
        self.assertEqual(plan['records'], [])
        self.assertEqual(plan['quarantined'][0]['id'], 'p')

    def test_repeated_recovery_is_idempotent(self):
        original = [horse('root', 2000)]
        observations = [horse('root', 2000, sire='p'), horse('p', 1935)]
        plan = recover_batch(original, observations, {'root'})
        updated = list({**{h['id']: h for h in original}, **{h['id']: h for h in plan['records']}}.values())
        self.assertEqual(recover_batch(updated, observations, {'root'})['records'], [])

    def test_historical_cutoff_does_not_hide_a_contradictory_birth_year(self):
        original = [horse('root', 1950)]
        observations = [horse('root', 1950, dam='terminal'), horse('terminal', 1932, 'H', dam='parent'), horse('parent', 1932, 'H')]
        plan = recover_batch(original, observations, {'root'})
        self.assertEqual(plan['records'], [])
        self.assertEqual({h['id'] for h in plan['quarantined']}, {'terminal', 'parent'})
