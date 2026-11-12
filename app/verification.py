"""Conservative comparison of attributed records; never merge identities by name.
Only distinct official publishers count as a second source. Agreement is per field,
not a certificate that the complete pedigree, campaign or earnings are verified.
"""
from collections import defaultdict
import re
import unicodedata
from urllib.parse import urlsplit
from .catalog import SOURCES

PUBLISHERS={'uy-studbook','ar-studbook','us-equibase'}
HOSTS={s['id']:set(s['hosts']) for s in SOURCES}

def attributed(h):
    try:
        u=urlsplit(h.get('source_url') or '')
        return h.get('source_id') in PUBLISHERS and u.scheme=='https' and u.hostname in HOSTS[h['source_id']] and not u.username and not u.password
    except ValueError:return False

FIELDS=('name','birth_year','sex','sire','dam','birth_country','coat')

def normalized_name(value):
    value=re.sub(r'\s*\([A-Z]{2,3}\)\s*$','',str(value or '').upper())
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',value) if not unicodedata.combining(c)).split())

def values(h,nodes):
    return {**{f:h.get(f) for f in FIELDS},'name':normalized_name(h.get('name')),
            'coat':normalized_name(h.get('coat')),
            'sex':None if h.get('sex')=='U' else h.get('sex'),
            'sire':normalized_name(nodes.get(h.get('sire_id'),{}).get('name')),
            'dam':normalized_name(nodes.get(h.get('dam_id'),{}).get('name'))}

def compare_all(horses,evidence=None):
    nodes={h['id']:h for h in horses};groups=defaultdict(list)
    observations={}
    for ident,h in nodes.items():
        observation=dict(evidence.get(ident,{}) if evidence is not None else h)
        # A stored audit can outlive an edit/import. It must not corroborate an
        # old birth year or parent link as though it were the current value.
        if evidence is not None:
            if not attributed(observation) or observation.get('id')!=ident or observation.get('source_id')!=h.get('source_id'):
                observation={}
            else:
                for field in ('name','birth_year','sex','sire_id','dam_id','birth_country','coat'):
                    if observation.get(field)!=h.get(field):observation[field]=None
        observations[ident]=observation
    vals={ident:values(observations[ident],nodes) for ident in nodes}
    for h in horses:
        if attributed(h) and vals[h['id']]['name']:
            groups[vals[h['id']]['name']].append(h)
    reports={}
    for h in horses:
        a=vals[h['id']];comparisons=[]
        peers=[]
        if attributed(h):
            for p in groups.get(a['name'],[]):
                b=vals[p['id']]
                if a.get('birth_year') and b.get('birth_year'):
                    if a['birth_year']==b['birth_year']:peers.append(p)
                elif a.get('sire') and a['sire']==b.get('sire'):
                    peers.append(p)  # Missing year: candidate only, never an identified match.
        for other in peers:
            if other['source_id']==h['source_id']:continue
            b=vals[other['id']]
            agreed=[f for f in FIELDS if a.get(f) and b.get(f) and a[f]==b[f]]
            differences=[{'field':f,'value':a[f],'other':b[f]} for f in FIELDS if a.get(f) and b.get(f) and a[f]!=b[f]]
            # Full names, year and both named parents must agree before calling
            # any fields corroborated. Ambiguous duplicates remain candidates.
            identity=all(f in agreed for f in ('name','birth_year','sire','dam')) and not any(d['field']=='sex' for d in differences)
            unique=all(sum(1 for p in peers if p['source_id']==sid)==1 for sid in (h['source_id'],other['source_id']))
            comparisons.append({'id':other['id'],'source_id':other['source_id'],'url':observations[other['id']].get('source_url',other['source_url']),'observed_at':observations[other['id']].get('fetched_at'),
                'identity_supported':bool(identity and unique),'agreed_fields':agreed,'differences':differences,
                'uncompared_fields':[f for f in FIELDS if not a.get(f) or not b.get(f)]})
        supported=[c for c in comparisons if c['identity_supported']]
        confirmed=sorted(set(f for c in supported for f in c['agreed_fields'])-set(d['field'] for c in supported for d in c['differences']))
        reports[h['id']]={'primary_url':observations[h['id']].get('source_url',h.get('source_url','')),'primary_observed_at':observations[h['id']].get('fetched_at'),'status':'partial_agreement' if supported else 'review_candidates' if comparisons else 'single_source',
            'confirmed_fields':confirmed,'pending_fields':[f for f in FIELDS if f not in confirmed],
            'comparisons':comparisons,'all_data_verified':False,
            'scope':'Contraste de ficha y progenitores directos. No verifica el árbol completo, las ganancias ni las actuaciones. No fusiona IDs de distintas fuentes.'}
    return reports
