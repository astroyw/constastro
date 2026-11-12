"""Recover independent, consistent facts from rejected public pedigree batches.

Known facts are immutable. Any record participating in a contradiction is
quarantined, along with new links to it. No dates or identities are inferred.
"""
from collections import defaultdict
from copy import deepcopy

from .genetics import validate_graph

FACTS = ('name', 'birth_year', 'sex', 'sire_id', 'dam_id', 'birth_country', 'coat')


def known(field, value):
    return value not in (None, '') and not (field == 'sex' and value == 'U')


def needed_nodes(nodes, targets, cutoff=1935):
    seen = set()
    queue = list(targets)
    while queue:
        ident = queue.pop()
        if ident in seen or ident not in nodes:
            continue
        seen.add(ident)
        h = nodes[ident]
        if h.get('birth_year') and h['birth_year'] <= cutoff:
            continue
        queue.extend(h[f] for f in ('sire_id', 'dam_id') if h.get(f))
    return seen


def graph_conflicts(nodes):
    problems = []
    for ident, h in nodes.items():
        if h.get('sire_id') and h['sire_id'] == h.get('dam_id'):
            problems.append(({ident}, 'Mismo padre y madre.'))
        for role, sex in (('sire_id', 'M'), ('dam_id', 'H')):
            pid = h.get(role)
            if not pid:
                continue
            p = nodes.get(pid)
            if not p:
                problems.append(({ident}, f'Falta el registro {pid}.'))
                continue
            if p.get('sex', 'U') not in (sex, 'U'):
                problems.append(({ident, pid}, f'Sexo incompatible: {ident} / {role} / {pid}.'))
            if h.get('birth_year') and p.get('birth_year') and p['birth_year'] >= h['birth_year']:
                problems.append(({ident, pid}, f'Cronología incompatible: {ident} ({h["birth_year"]}) / {pid} ({p["birth_year"]}).'))
    active, done = [], set()

    def visit(ident):
        if ident in active:
            problems.append((set(active[active.index(ident):]), 'Ciclo de parentesco.'))
            return
        if ident in done or ident not in nodes:
            return
        if len(active) >= 100:
            problems.append((set(active) | {ident}, 'Más de 100 generaciones encadenadas.'))
            return
        active.append(ident)
        for field in ('sire_id', 'dam_id'):
            if nodes[ident].get(field):
                visit(nodes[ident][field])
        active.pop()
        done.add(ident)

    for ident in nodes:
        visit(ident)
    return problems


def recover_batch(horses, observations, targets, cutoff=1935):
    """Return a reviewable plan; caller saves it atomically and archives evidence."""
    existing = {h['id']: deepcopy(h) for h in horses}
    validate_graph(list(existing.values()))
    incoming = {}
    blocked = defaultdict(list)
    for h in observations:
        ident = h['id']
        if ident in incoming and any(known(f, incoming[ident].get(f)) and known(f, h.get(f)) and incoming[ident][f] != h[f] for f in FACTS):
            blocked[ident].append('Observaciones contradictorias del mismo ID en el lote.')
        incoming[ident] = deepcopy(h)
        old = existing.get(ident, {})
        for field in FACTS:
            if known(field, old.get(field)) and known(field, h.get(field)) and old[field] != h[field]:
                blocked[ident].append(f'Difiere el campo conocido {field}: {old[field]} / {h[field]}.')

    def proposal(trim=False):
        nodes = deepcopy(existing)
        for ident, h in incoming.items():
            if ident in blocked:
                continue
            old = existing.get(ident)
            row = deepcopy(old if old is not None else h)
            if old is not None:
                for field in FACTS:
                    if not known(field, old.get(field)) and known(field, h.get(field)):
                        row[field] = h[field]
            else:
                row['featured'] = False
            for field in ('sire_id', 'dam_id'):
                # Keep old facts, but never add a new edge into a quarantined
                # record or beyond the requested historical terminal.
                if not (old or {}).get(field) and (row.get(field) in blocked or (trim and row.get('birth_year') and row['birth_year'] <= cutoff)):
                    row[field] = None
            nodes[ident] = row
        if not trim:
            return nodes
        required = needed_nodes(nodes, targets, cutoff)
        return {**existing, **{i: h for i, h in nodes.items() if i in required}}

    while True:
        nodes = proposal()
        problems = graph_conflicts(nodes)
        if not problems:
            break
        before = len(blocked)
        for ids, reason in problems:
            for ident in ids:
                if ident in incoming and nodes.get(ident) != existing.get(ident):
                    if reason not in blocked[ident]:
                        blocked[ident].append(reason)
        if len(blocked) == before:
            raise ValueError('No se pudo aislar la contradicción; el lote no se recuperó.')

    # Check every supplied chronological relationship before stopping at 1935;
    # pruning first could conceal contradictory dates at historical terminals.
    nodes = proposal(trim=True)
    validate_graph(list(nodes.values()))
    changes, facts = [], []
    for ident in sorted(incoming):
        if ident not in nodes or ident in blocked:
            continue
        old, h = existing.get(ident), nodes[ident]
        fields = {f: h[f] for f in FACTS if known(f, h.get(f)) and (old is None or not known(f, old.get(f)))}
        if old is not None and not fields:
            continue
        observation = incoming[ident]
        row = deepcopy(h)
        if old is not None:
            note = ' Complemento de una rama válida de un lote parcialmente rechazado: ' + observation.get('source_url', '') + '. Ver auditoría de recuperación; no implica doble verificación.'
            row['notes'] = (old.get('notes') or '')[:max(0, 2000-len(note))] + note
        changes.append(row)
        facts.append({'id': ident, 'new_record': old is None, 'fields': fields,
                      'source_id': observation.get('source_id'), 'source_url': observation.get('source_url'),
                      'observed_at': observation.get('fetched_at')})
    return {'records': changes, 'applied': facts,
            'quarantined': [{'id': i, 'reasons': reasons, 'source_url': incoming[i].get('source_url'),
                             'observed_at': incoming[i].get('fetched_at')} for i, reasons in sorted(blocked.items())]}
