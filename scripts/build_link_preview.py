"""Small interactive preview wrapper for HTML Preview, without enabling Pages.

The public source branch supplies immutable JSON/XLSX. The wrapper embeds its
reviewed styles and ES modules, preserving MIME types and import maps in srcdoc.
"""
import argparse,base64,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist'

def data_url(path,mime):
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()

def build(revision):
    if not re.fullmatch(r'[a-f0-9]{40}',revision):raise ValueError('Se exige un commit inmutable completo.')
    base=f'https://raw.githubusercontent.com/astroyw/constastro/{revision}/'
    imports={}
    for path in sorted((DIST/'static').glob('*.js')):
        if path.name=='deployment.js':continue
        source=path.read_text()
        if path.name=='snapshot-api.js':
            source=source.replace("new URL('../data/site.json',import.meta.url)",json.dumps(base+'data/site.json'))
        if path.name=='downloads.js':
            source='const base='+json.dumps(base)+';\n'+'''export function exportURL(kind='xlsx',demo=false) {
  return base+'downloads/'+(kind==='json'?'Linaje_datos.json':(demo?'Linaje_DEMOSTRACION':'Linaje_pedigrees')+'.xlsx');
}
document.addEventListener('click',async event=>{
  const link=event.target.closest('a[href]');
  if(!link||!link.href.startsWith(base+'downloads/'))return;
  event.preventDefault();
  const name=link.href.split('/').pop(),original=link.textContent;
  link.textContent='Preparando descarga…';
  try {
    const response=await fetch(link.href);
    if(!response.ok)throw new Error('No se pudo descargar el archivo.');
    const url=URL.createObjectURL(await response.blob());
    const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  } catch(error) { alert(error.message); }
  finally {link.textContent=original;}
},true);
'''
        for dep in (DIST/'static').glob('*.js'):source=source.replace('./'+dep.name,'linaje/'+dep.stem)
        source=source.replace('static/horse-art.svg',data_url(DIST/'static'/'horse-art.svg','image/svg+xml'))
        imports['linaje/'+path.stem]='data:text/javascript;base64,'+base64.b64encode(source.encode()).decode()
    html=(DIST/'index.html').read_text()
    html=html.replace('<head>','<head><base href="about:srcdoc">',1)
    html=html.replace('static/favicon.svg',data_url(DIST/'static'/'favicon.svg','image/svg+xml'))
    html=html.replace('<link rel="stylesheet" href="static/styles.css">','<style>'+(DIST/'static'/'styles.css').read_text()+'</style>')
    html=html.replace('<script src="static/deployment.js"></script>','')
    scripts='<script>globalThis.LINAJE_STATIC=true;</script><script type="importmap">'+json.dumps({'imports':imports})+'</script><script type="module">import "linaje/app";</script>'
    html=html.replace('<script type="module" src="static/app.js"></script>',scripts)
    # HTML Preview rewrites literal script tags. Escaped srcdoc keeps the inner
    # module/importmap/JSON types intact and renders the actual app in an iframe.
    source=json.dumps(html,ensure_ascii=True).replace('<','\\u003c')
    wrapper='''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Linaje · Preview interactiva</title><style>html,body{margin:0;height:100%;overflow:hidden;background:#f5f7f4}iframe{display:block;border:0;width:100%;height:100dvh}</style></head><body><iframe id="linaje-preview" title="Linaje · Pedigrees, carreras y compatibilidad" allow="fullscreen"></iframe><script>document.getElementById('linaje-preview').srcdoc='''+source+''';</script></body></html>'''
    dest=ROOT/'exports'/'preview-link.html';dest.write_text(wrapper)
    print('Preview con fuentes fijadas al commit',revision,';',dest.stat().st_size,'bytes')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('revision');build(p.parse_args().revision)
