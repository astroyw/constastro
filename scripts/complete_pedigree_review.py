"""Continue the fixed-cohort job, then validate and publish its available-source result.
Completion means the accessible-source queue ended, not that missing facts were invented.
"""
import json,subprocess,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data'/'deep_pedigree'/'completion.json'
def status(stage,**extra):
 value={'stage':stage,'updated_at':datetime.now(timezone.utc).isoformat(),**extra}
 tmp=STATUS.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(STATUS)
def run(*args,env=None):subprocess.run(args,cwd=ROOT,env=env,check=True)
def main():
 try:
  status('expanding')
  run(sys.executable,'scripts/expand_pedigrees.py')
  status('archiving')
  run(sys.executable,'scripts/archive_pedigree_review.py')
  run(sys.executable,'scripts/build_static.py')
  run(sys.executable,'scripts/build_preview.py')
  status('testing')
  run(sys.executable,'-m','unittest','discover','-s','tests')
  run('node','tests/ancestry.mjs');run('node','tests/affinity.mjs');run('node','tests/performance.mjs')
  run('python3','scripts/check_publication.py')
  status('publishing')
  run(sys.executable,'scripts/publish_reviewed_preview.py')
  summary=json.loads((ROOT/'samples'/'pedigree_review.json').read_text())['summary']
  status('available_sources_reviewed',summary=summary,commit=(ROOT/'exports'/'preview-commit.txt').read_text().strip())
 except Exception as e:
  status('stopped_for_review',error=str(e));traceback.print_exc();raise
if __name__=='__main__':main()
