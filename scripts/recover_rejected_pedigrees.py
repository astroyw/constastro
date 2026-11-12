"""Recover only independently valid branches of archived rejected source batches."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import db
from app.ancestry import original_targets
from app.main import save_batch
from app.recovery import recover_batch


def main():
    destination = ROOT / 'samples' / 'pedigree_recoveries.json'
    report = json.loads(destination.read_text()) if destination.exists() else {'method': 'consistent-branches-v1', 'batches': []}
    processed = {b['file'] for b in report['batches']}
    for path in sorted((ROOT / 'data' / 'deep_pedigree' / 'rejected').glob('*.json')):
        if path.name in processed:
            continue
        raw = json.loads(path.read_text())
        plan = recover_batch(db.horse_rows(False), raw['horses'], original_targets())
        if plan['records']:
            save_batch(plan['records'], [])
            # Archive the actual observation, not the merged current record.
            ids = {h['id'] for h in plan['records']}
            observations = [h for h in raw['horses'] if h['id'] in ids]
            cache = ROOT / 'data' / 'deep_pedigree' / ('recovered-' + path.name)
            cache.write_text(json.dumps({'horses': observations}, ensure_ascii=False, indent=2))
        report['batches'].append({'file': path.name, 'recovered_at': db.now(), 'original_reason': raw['reason'],
                                 'applied': plan['applied'], 'quarantined': plan['quarantined']})
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        temporary.replace(destination)
        print(path.name, 'registros recuperados:', len(plan['records']), 'registros en cuarentena:', len(plan['quarantined']), flush=True)
    print('Complementos documentados:', sum(len(b['applied']) for b in report['batches']))


if __name__ == '__main__':
    main()
