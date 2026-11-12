"""Audit unique pedigree nodes until branches reach a documented birth year <=1935."""
from collections import deque

def audit(root_id,nodes,cutoff=1935):
    queue=deque([(root_id,0)]);seen=set();rows=[];missing=[];terminals=[]
    while queue:
        ident,depth=queue.popleft()
        if ident in seen:continue
        seen.add(ident);h=nodes.get(ident)
        if not h:
            missing.append({'id':ident,'role':'record'});continue
        rows.append((h,depth))
        if h.get('birth_year') and h['birth_year']<=cutoff:
            terminals.append(ident);continue
        for field in ('sire_id','dam_id'):
            if h.get(field):queue.append((h[field],depth+1))
            else:missing.append({'id':ident,'role':field})
    nearco=[{'id':h['id'],'generation':d} for h,d in rows if h['name'].upper().split(' (')[0]=='NEARCO']
    return {'complete':not missing,'ancestor_count':max(0,len(rows)-1),'max_generation':max((d for _,d in rows),default=0),
            'oldest_year':min((h['birth_year'] for h,_ in rows if h.get('birth_year')),default=None),
            'missing_links':len(missing),'unresolved':missing,'terminals_1935':len(terminals),'nearco':nearco}


def original_targets():
    import json
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'samples'/'pedigree_targets.json'
    return set(json.loads(path.read_text())) if path.exists() else set()
