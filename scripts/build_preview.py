"""Create one interactive HTML file from the reviewed static edition."""
import base64
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'


def data_url(path,mime):
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()


def build():
    out=ROOT/'exports'/'preview'
    out.mkdir(parents=True,exist_ok=True)
    downloads={
        'json':data_url(DIST/'downloads'/'Linaje_datos.json','application/json'),
        'real':data_url(DIST/'downloads'/'Linaje_pedigrees.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        'demo':data_url(DIST/'downloads'/'Linaje_DEMOSTRACION.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    }
    imports={}
    for path in sorted((DIST/'static').glob('*.js')):
        if path.name=='deployment.js':continue
        source=path.read_text()
        if path.name=='snapshot-api.js':
            start=source.index('let snapshot;')
            source=source[:start]+'''let snapshot;
export async function api(path,options) {
  if(!snapshot)snapshot=createSnapshotAPI(JSON.parse(document.querySelector('#linaje-data').textContent));
  return snapshot(path,options);
}
'''
        if path.name=='downloads.js':
            source='const downloads='+json.dumps(downloads)+';\n'+'''
export function exportURL(kind='xlsx',demo=false) {
  return downloads[kind==='json'?'json':demo?'demo':'real'];
}
const names=new Map([[downloads.json,'Linaje_datos.json'],[downloads.real,'Linaje_pedigrees.xlsx'],[downloads.demo,'Linaje_DEMOSTRACION.xlsx']]);
document.addEventListener('click',event=>{
  const link=event.target.closest('a[href]');
  if(link&&names.has(link.href))link.download=names.get(link.href);
},true);
'''
        for dependency in (DIST/'static').glob('*.js'):
            source=source.replace('./'+dependency.name,'linaje/'+dependency.stem)
        source=source.replace('/static/horse-art.svg',data_url(DIST/'static'/'horse-art.svg','image/svg+xml'))
        imports['linaje/'+path.stem]='data:text/javascript;base64,'+base64.b64encode(source.encode()).decode()
    html=(DIST/'index.html').read_text()
    html=html.replace('/static/favicon.svg',data_url(DIST/'static'/'favicon.svg','image/svg+xml'))
    html=html.replace('<link rel="stylesheet" href="/static/styles.css">','<style>'+(DIST/'static'/'styles.css').read_text()+'</style>')
    html=html.replace('<script src="/static/deployment.js"></script>','')
    payload=(DIST/'data'/'site.json').read_text().replace('<','\\u003c')
    scripts='<script>globalThis.LINAJE_STATIC=true;</script>'
    scripts+='<script type="application/json" id="linaje-data">'+payload+'</script>'
    scripts+='<script type="importmap">'+json.dumps({'imports':imports})+'</script>'
    scripts+='<script type="module">import "linaje/app";</script>'
    html=html.replace('<script type="module" src="/static/app.js"></script>',scripts)
    (out/'index.html').write_text(html)
    (ROOT/'exports'/'Linaje-interactiva.html').write_text(html)
    print('HTML interactivo generado:',len(html.encode()),'bytes; datos, módulos, estilos y descargas incluidos.')


if __name__=='__main__':build()
