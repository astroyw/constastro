"""Publish only reviewed artifacts while preserving every other remote-main file."""
import hashlib,subprocess,time,urllib.request,os,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def git(*args,input=None):
 return subprocess.check_output(['git',*args],cwd=ROOT,input=input,text=True).strip()
def main():
 subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True)
 parent=git('rev-parse','FETCH_HEAD')
 artifacts={'linaje.html':ROOT/'exports'/'Linaje-interactiva.html','Linaje-Netlify.zip':ROOT/'exports'/'Linaje-Netlify.zip','previsualizacion-actual.png':ROOT/'exports'/'previsualizacion-actual.png'}
 assert all(p.is_file() for p in artifacts.values())
 # Back up the recovered source, installer and attributed samples alongside
 # the existing public artifacts. Never include SQLite, raw caches or secrets.
 source_paths=[]
 allowed={'.py','.sh','.js','.mjs','.json','.html','.css','.svg','.md'}
 for folder in ('app','static','scripts','samples','docs','tests'):
  source_paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix in allowed)
 source_paths.extend(ROOT/n for n in ('.gitignore','README.md','requirements.txt','requirements.lock','requirements-dev.txt','netlify.toml'))
 files={p.relative_to(ROOT).as_posix():p for p in source_paths}
 assert {p.relative_to(ROOT).as_posix() for p in (ROOT/'static').glob('*.js')}.issubset(files), 'Missing browser modules in source backup'
 files.update(artifacts)
 with tempfile.TemporaryDirectory(prefix='linaje-publish-index-') as temp:
  env={**os.environ,'GIT_INDEX_FILE':str(Path(temp)/'index')}
  subprocess.run(['git','read-tree',parent],cwd=ROOT,env=env,check=True)
  entries=[]
  for name,path in sorted(files.items()):
   mode='100755' if path.stat().st_mode&0o111 else '100644'
   entries.append(mode+' '+git('hash-object','-w',str(path))+'\t'+name)
  subprocess.run(['git','update-index','--index-info'],cwd=ROOT,env=env,input='\n'.join(entries)+'\n',text=True,check=True)
  tree=subprocess.check_output(['git','write-tree'],cwd=ROOT,env=env,text=True).strip()
 commit=git('commit-tree',tree,'-p',parent,input='Restore complete Linaje source and publish documented pedigrees and distance estimates\n')
 subprocess.run(['git','push','origin',commit+':refs/heads/main'],cwd=ROOT,check=True)
 for name,path in artifacts.items():
  expected=hashlib.sha256(path.read_bytes()).hexdigest()
  for attempt in range(3):
   try:
    with urllib.request.urlopen(f'https://raw.githubusercontent.com/astroyw/constastro/{commit}/{name}',timeout=45) as response:
     downloaded=response.read(path.stat().st_size+1)
    if hashlib.sha256(downloaded).hexdigest()!=expected:raise ValueError('Published artifact digest mismatch: '+name)
    break
   except Exception:
    if attempt==2:raise
    time.sleep(3)
 (ROOT/'exports'/'preview-commit.txt').write_text(commit+'\n')
 print('Published commit:',commit)
 for name,path in artifacts.items():print(name,hashlib.sha256(path.read_bytes()).hexdigest())
if __name__=='__main__':main()
