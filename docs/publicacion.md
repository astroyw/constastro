# Publicar Linaje en Netlify

La edición de Netlify es una web estática: conserva los pedigrees, los rankings, los resultados archivados, el análisis de parentesco en el navegador y las descargas de Excel y JSON. No necesita un servidor Python durante la visita ni un servicio de pago configurado.

## Publicación manual

1. Descargar `exports/Linaje-Netlify.zip` y descomprimirlo. Dentro deben verse `index.html`, `static/`, `data/`, `downloads/`, `_headers` y `_redirects`.
2. Iniciar sesión en [Netlify Drop](https://app.netlify.com/drop) y arrastrar la carpeta descomprimida que contiene `index.html`.
3. Netlify asigna una dirección HTTPS. Abrirla y verificar una ficha de pedigree, el cálculo de parentesco y la descarga del Excel. La dirección definitiva se obtiene del panel de Netlify.

Para actualizar un sitio existente, subir el contenido de `dist/` en la sección de despliegues de ese mismo sitio. Crear otro sitio en cada actualización genera otra dirección.

## Publicación desde Git

Conectar en Netlify la rama `main` de `astroyw/constastro`, después de subir los archivos del proyecto. `netlify.toml` configura el comando `bash scripts/build-netlify.sh` y la carpeta pública `dist`. El proceso usa Python 3.12 únicamente para construir los archivos: instala el lock de dependencias, crea una base temporal desde las muestras revisadas y genera el sitio estático y los Excel. No se configuran funciones ni un backend en Netlify.

Un dominio propio se conecta desde la configuración del dominio del sitio en Netlify, siguiendo sus registros DNS. La configuración de este repositorio no compra dominios ni contrata planes.

## Datos y actualización

El constructor `scripts/build_static.py` siempre utiliza una SQLite temporal alimentada con `samples/argentina_official.json`, `samples/uruguay_official.json` y `samples/historical_rankings.json`. No lee ni publica la base de trabajo, los respaldos, las cachés, las credenciales o los archivos de otras carpetas. Genera un ZIP que contiene únicamente el sitio público.

Estado actual: 2.452 registros reales, incluidos ancestros; 400 puestos (Equibase 200, Uruguay 100, Argentina 100), 15 resultados. Brasil sigue pendiente y los pedigrees de Equibase son parciales. Cada ranking conserva fecha, fuente, alcance y moneda. No es un ranking mundial comparable en una sola moneda.

Las importaciones y el scraping se realizan en el entorno de mantenimiento. Luego se revisan y actualizan las muestras archivadas y se despliega de nuevo. Los visitantes consultan la versión publicada; no hay actualización automática desde los stud books ni importaciones públicas. El cálculo de Wright utiliza todos los ancestros incluidos y distingue los ejemplos ficticios de los datos reales.

El JSON descargable conserva caballos y resultados; los metadatos y puestos de rankings se conservan en su instantánea y en el Excel. No se deben sustituir las muestras de rankings por ese JSON.

## Construcción y comprobación local

Con las dependencias de `requirements.lock` instaladas:

```bash
.venv/bin/python scripts/build_static.py
python3 -m http.server 8080 --directory dist
```

El resultado queda en `dist/` y `exports/Linaje-Netlify.zip`. `scripts/browser_static.py` comprueba esa edición en Chromium servido como archivos: fichas, 400 puestos, catorce ancestros, cálculo contrastado con Python, resultados, Excel real y ficticio, y móvil. Requiere Playwright y Chromium ya disponibles. Las pruebas unitarias contrastan también el coeficiente de Wright de JavaScript con Python.

La aplicación Python original conserva el mantenimiento local. Si se expone en otro servidor, establecer `PUBLIC_READ_ONLY=true` bloquea las escrituras y las consultas de importación y muestra la interfaz de consulta. No hay panel de administración público.

La generación del paquete no equivale a su publicación. La publicación del entorno de Codex conserva sus archivos y configuración, pero no aloja esta web públicamente.

## Búsqueda e índice de campañas

Las sugerencias aparecen desde tres letras, ignoran tildes y permiten seleccionar por nombre con teclado o puntero. Cada opción conserva año, registro e ID para distinguir homónimos. En compatibilidad se mantienen las listas y se añaden búsquedas separadas por sexo; editar el texto invalida la selección anterior.

Las tarjetas Classic (2000 m arena), Distaff (1800 m arena), Turf (2400 m césped), Mile (1600 m césped) y Sprint (1200 m arena) muestran un índice **0–100** con margen ±200 m. El método `campana-regularizada-v2` siempre produce un número para un cruce válido; cuando no hay actuaciones documentadas, muestra **50/100 · base neutral · confianza Sin evidencia**. No se utiliza el anterior bloqueo por un mínimo de carreras. La consanguinidad de Wright se sigue mostrando por separado.

Con participantes oficiales conocidos, cada actuación aporta `y=(participantes−puesto)/(participantes−1)`, con peso `q=1`. Si sólo se conoce el puesto se usa el indicador auxiliar `y=1/puesto`, con `q=0,5`; no se inventa el número de participantes y se informa cuántas observaciones usan cada medida. Son indicadores distintos y el peso menor del segundo es una decisión del modelo, no un parámetro validado.

Por caballo, `v=(2+Σ(q×y))/(4+Σq)`: una base neutral de 0,5 con fuerza de regularización 4. Esos números son supuestos explícitos para moderar muestras pequeñas, no carreras observadas. Los caballos se ponderan según profundidad desde cada progenitor: `w=1, ½, ¼, ⅛`; cada ID aparece una sola vez en su generación más cercana. Por rama, `B=0,5+Σ(w×(v−0,5))/máximo(1,Σw)`. El denominador mínimo evita atribuir toda una rama a un ancestro lejano aislado. El índice final es `redondear(50×(B paterna+B materna))`. Una rama sin observaciones conserva 50/100.

La confianza es descriptiva: «Sin evidencia» con la base neutral solamente, «Baja» con observaciones, «Moderada» con ≥30 actuaciones únicas, ≥3 caballos por rama, ≥3 actuaciones de cada progenitor y ≥80% con participantes oficiales. No es confianza estadística. Se deduplican carreras por caballo; observaciones contradictorias se excluyen y los ancestros compartidos no multiplican la evidencia única. Los resultados sin fuente, ID enlazado, distancia, superficie o puesto válido se omiten. No se ajustan clase de carrera, edad, entrenamiento o salud; el índice no es una probabilidad de ganar ni una predicción genética validada.

`node tests/performance.mjs` comprueba regularización, base neutral, evidencia parcial, puestos sin participantes, duplicados y ponderación por profundidad. `python scripts/check_publication.py` comprueba la edición estática con un servidor propio en un puerto disponible. `python scripts/build_preview.py` reconstruye el HTML interactivo a partir de `dist/`.
