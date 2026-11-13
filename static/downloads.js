export function exportURL(kind='xlsx',demo=false) {
  if(globalThis.LINAJE_STATIC) {
    const name=kind==='json'?'Linaje_datos.json':`${demo?'Linaje_DEMOSTRACION':'Linaje_pedigrees'}.xlsx`;
    return new URL('../downloads/'+name,import.meta.url).href;
  }
  return kind==='json'?'/api/export.json':`/api/export.xlsx?demo=${demo}`;
}
