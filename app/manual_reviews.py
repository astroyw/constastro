"""Audited individual enrichments kept separate from automated comparisons."""
import json
from pathlib import Path

def manual_reviews():
    path=Path(__file__).resolve().parents[1]/'samples'/'pedigree_manual_reviews.json'
    return json.loads(path.read_text()).get('changes',[]) if path.exists() else []
