"""Document parent identity through independently corroborated child records.
No name-only merging. IDs remain distinct; every added fact records its publisher.
"""
from collections import defaultdict
from .verification import compare_all,normalized_name


def proposals(horses,evidence,required):
    nodes={h['id']:h for h in horses};checks=compare_all(horses,evidence)
    links=defaultdict(list)
    for child in horses:
        # Duplicate child IDs do not prevent identifying a parent when *every*
        # candidate agrees on name, year, both parents and the same parent ID.
        # The child IDs remain ambiguous; only the convergent parental claim is used.
        groups=defaultdict(list)
        for c in checks[child['id']]['comparisons']:groups[c['source_id']].append(c)
        for c in checks[child['id']]['comparisons']:
            peers=groups[c['source_id']]
            if not all(set(('name','birth_year','sire','dam')).issubset(p['agreed_fields']) and not any(d['field'] in ('sex','birth_country') for d in p['differences']) for p in peers):continue
            a=evidence.get(child['id'],{});b=evidence.get(c['id'],{})
            for role in ('sire_id','dam_id'):
                parent_ids={evidence.get(p['id'],{}).get(role) for p in peers}
                if len(parent_ids)!=1 or None in parent_ids:continue
                left=nodes.get(a.get(role));right=nodes.get(b.get(role))
                if not left or not right or left['source_id']==right['source_id']:continue
                if normalized_name(left['name'])!=normalized_name(right['name']):continue
                if any(left.get(f) and right.get(f) and left[f]!=right[f] for f in ('birth_year','birth_country')):continue
                if left.get('sex')!='U' and right.get('sex')!='U' and left.get('sex')!=right.get('sex'):continue
                proof={'child_id':child['id'],'other_child_id':c['id'],'role':role,
                       'child_identity_supported':c['identity_supported'],
                       'convergent_child_candidates':[p['id'] for p in peers],
                       'first_url':a['source_url'],'second_url':b['source_url'],
                       'first_observed_at':a.get('fetched_at'),'second_observed_at':b.get('fetched_at')}
                links[(left['id'],right['id'])].append(proof)
    peers=defaultdict(set)
    for left,right in links:peers[(left,nodes[right]['source_id'])].add(right)
    out=[]
    for (left,right),proofs in links.items():
        if left not in required or len(peers[(left,nodes[right]['source_id'])])!=1 or peers[(right,nodes[left]['source_id'])]!={left}:continue
        h=nodes[left];other=nodes[right];obs=evidence.get(right,{})
        fields={}
        for f in ('birth_year','sire_id','dam_id'):
            if not h.get(f) and obs.get(f) and obs[f]==other.get(f):fields[f]=obs[f]
        if not fields:continue
        out.append({'id':left,'counterpart_id':right,'fields':fields,'source_id':other['source_id'],
                    'method':'documented-child-parent-v2',
                    'source_url':obs['source_url'],'observed_at':obs.get('fetched_at'),
                    'identity_basis':'Progenitor identificado por registros de hijos coincidentes en nombre, año y ambos padres entre dos editores; todos los candidatos del otro editor señalan el mismo ID parental. Correspondencia parental recíproca única; no fusiona los IDs de los hijos.',
                    'child_evidence':proofs})
    # Multiple publishers must agree on any proposed field; otherwise leave it unknown.
    claims=defaultdict(set)
    for p in out:
        for f,value in p['fields'].items():claims[(p['id'],f)].add(value)
    for p in out:p['fields']={f:v for f,v in p['fields'].items() if len(claims[(p['id'],f)])==1}
    return [p for p in out if p['fields']]
