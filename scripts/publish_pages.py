"""Publish the reviewed static build to a dedicated GitHub Pages branch."""
import argparse,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO='astroyw/constastro';BRANCH='linaje-preview'

def git(*args,**kwargs):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True,**kwargs).strip()

def main(configure=False):
    files={p.relative_to(ROOT/'dist').as_posix():p for p in (ROOT/'dist').rglob('*') if p.is_file()}
    assert {'index.html','data/site.json','static/app.js','downloads/Linaje_pedigrees.xlsx'}<=files.keys()
    # No operators' databases, caches or credentials are in dist.
    assert not any(p.suffix in ('.sqlite3','.env','.pem') for p in files.values())
    existing=git('ls-remote','--heads','origin',BRANCH)
    parent=None
    if existing:
        subprocess.run(['git','fetch','origin',BRANCH],cwd=ROOT,check=True)
        parent=git('rev-parse','FETCH_HEAD')
    with tempfile.TemporaryDirectory(prefix='linaje-pages-') as temp:
        env={**os.environ,'GIT_INDEX_FILE':str(Path(temp)/'index')}
        # Preserve unrelated remote files if this dedicated branch already exists.
        subprocess.run(['git','read-tree',parent] if parent else ['git','read-tree','--empty'],cwd=ROOT,env=env,check=True)
        nojekyll=Path(temp)/'.nojekyll';nojekyll.write_text('');files['.nojekyll']=nojekyll
        entries=['100644 '+git('hash-object','-w',str(path))+'\t'+name for name,path in sorted(files.items())]
        subprocess.run(['git','update-index','--index-info'],cwd=ROOT,env=env,input='\n'.join(entries)+'\n',text=True,check=True)
        tree=subprocess.check_output(['git','write-tree'],cwd=ROOT,env=env,text=True).strip()
        commit=git('commit-tree',tree,*(['-p',parent] if parent else []),input='Publish reviewed Linaje interactive preview\n')
    subprocess.run(['git','push','origin',commit+':refs/heads/'+BRANCH],cwd=ROOT,check=True)
    if configure:
        current=subprocess.run(['gh','api',f'repos/{REPO}/pages'],capture_output=True,text=True)
        if current.returncode==0:
            config=json.loads(current.stdout)
            if config.get('source')!={'branch':BRANCH,'path':'/'}:
                raise RuntimeError('La configuración existente de Pages es diferente; se conservó sin reemplazarla.')
        else:
            request={'build_type':'legacy','source':{'branch':BRANCH,'path':'/'}}
            subprocess.run(['gh','api','--method','POST',f'repos/{REPO}/pages','--input','-'],input=json.dumps(request),text=True,check=True)
    print(json.dumps({'commit':commit,'preview':'https://astroyw.github.io/constastro/'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--configure',action='store_true');main(p.parse_args().configure)
