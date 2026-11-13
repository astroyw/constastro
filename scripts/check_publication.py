"""Check the standalone edition using an owned server on a free port."""
import functools,http.server,os,subprocess,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
handler=functools.partial(Quiet,directory=str(ROOT/'exports'/'preview'))
with http.server.ThreadingHTTPServer(('127.0.0.1',0),handler) as server:
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  env={**os.environ,'STATIC_SITE_URL':f'http://127.0.0.1:{server.server_port}'}
  for script in ['browser_ancestry.py','browser_static.py','browser_search.py','browser_campaigns.py']:
   subprocess.run(['python3',str(ROOT/'scripts'/script)],cwd=ROOT,env=env,check=True)
 finally:server.shutdown();thread.join()
