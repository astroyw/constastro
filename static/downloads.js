export function exportURL(kind='xlsx',demo=false) {
  if(globalThis.LINAJE_STATIC) {
    if(kind==='json')return '/downloads/Linaje_datos.json';
    return `/downloads/${demo?'Linaje_DEMOSTRACION':'Linaje_pedigrees'}.xlsx`;
  }
  return kind==='json'?'/api/export.json':`/api/export.xlsx?demo=${demo}`;
}
