"""Select a single archived observation that actually displays the compared facts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load_evidence():
    path=ROOT/'samples'/'pedigree_evidence.json'
    return json.loads(path.read_text()) if path.exists() else {}

def collect_evidence(horses):
    nodes={h['id']:h for h in horses};best={};scores={}
    files=[ROOT/'samples'/'pedigree_evidence.json'] if (ROOT/'samples'/'pedigree_evidence.json').exists() else []
    files+=sorted((ROOT/'data'/'deep_pedigree').glob('*.json'))
    files+=sorted((ROOT/'data'/'ranking_cache').glob('uy-tree-*.json'))
    files += [ROOT/'samples'/n for n in ('historical_rankings.json','uruguay_official.json','argentina_official.json')]
    for path in files:
        data=json.loads(path.read_text());records=data.get('horses',[]) if isinstance(data,dict) else []
        if path.name=='pedigree_evidence.json':records=list(data.values())
        if path.name.startswith('uy-tree-'):
            from .uruguay import parse_pedigree
            tree=data['data'];ident='uy-studbook:'+str(tree['id'])
            records=parse_pedigree(tree,{'id':tree['id'],'sex':nodes.get(ident,{}).get('sex','U')},max_generations=4)
            for r in records:r['fetched_at']=data['retrieved_at']
        for r in records:
            current=nodes.get(r.get('id'))
            if not current:continue
            fields=('name','birth_year','sex','sire_id','dam_id','coat','birth_country')
            observation={**r}
            # An old observation cannot corroborate a different current value.
            for f in fields:
                if r.get(f)!=current.get(f):observation[f]=None
            score=sum(bool(observation.get(f)) for f in fields)
            if observation.get('sire_id') and observation.get('dam_id') and observation.get('birth_year'):score+=10
            if score>scores.get(r['id'],-1):best[r['id']]=observation;scores[r['id']]=score
    return best
