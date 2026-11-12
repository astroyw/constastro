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

Las tarjetas Classic (2000 m arena), Distaff (1800 m arena), Turf (2400 m césped), Mile (1600 m césped) y Sprint (1200 m arena) muestran un índice descriptivo 0–100 de especialización de campañas con margen ±200 m. No es una puntuación genética validada ni una probabilidad de éxito. Cada rama contribuye la mitad; cada actuación se pondera por profundidad del caballo: 1, ½, ¼ y ⅛. Se exigen tres actuaciones utilizables por rama y se deduplican carreras por caballo. Se excluyen distancias/superficies desconocidas, registros sin fuente y actuaciones sin un ID enlazado. Si falta evidencia se muestra «Sin datos suficientes», incluso en demostración. La base actual tiene sólo 15 resultados, por lo que los cruces carecen generalmente de evidencia para puntuar ambas ramas. La consanguinidad de Wright se sigue mostrando por separado.

`node tests/affinity.mjs` comprueba extremos, ponderación, faltantes y duplicados. `python scripts/browser_search.py` verifica búsquedas, teclado, selección, tarjetas y móvil con la vista de `exports/preview/` servida en el puerto 8083. `python scripts/build_preview.py` reconstruye el HTML interactivo a partir de `dist/`.
