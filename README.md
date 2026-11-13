# Linaje · constastro

Plataforma de pedigrees y resultados hípicos en español, con foco en Uruguay. Aplicación FastAPI + SQLite + interfaz web adaptable, sin servicios de pago ni claves requeridas para el modo local.

Para alojarla en **Netlify**, se incluye una edición estática con las fichas, los rankings, el cálculo de parentesco en el navegador y los Excel. `bash scripts/build-netlify.sh` genera `dist/` y `exports/Linaje-Netlify.zip`; `netlify.toml` configura el despliegue desde Git. Ver [publicación manual y desde Git](docs/publicacion.md).

## Ejecutar

Requiere Python 3.12 y acceso a PyPI para la instalación inicial.

```bash
cd /workspace/constastro
bash scripts/install.sh
bash scripts/start.sh
```

El servidor usa el puerto 8000, configurable mediante `PORT`. `GET /api/health` comprueba la aplicación y SQLite. La documentación de API está disponible en `/docs` en el servidor. No se necesita Node.

## Funciones disponibles

- Panorama con foco en Uruguay y separación entre datos reales y demostración.
- Biblioteca de caballos, búsqueda por nombre, país de registro y sexo, con páginas de 50 registros.
- Fichas con padres, cuatro abuelos y ocho bisabuelos; navegación a cada ancestro y campaña de resultados vinculados por ID.
- Análisis de parentesco de un padrillo y una yegua: F esperado de la cría (Wright), cobertura y ancestros compartidos. Usa el árbol disponible completo; cobertura y ancestros compartidos resumen tres generaciones.
- Resultados persistidos, filtros por país, pista y fecha, enlace a la fuente. Cada carrera distingue clasificación completa de posiciones parciales; cada tiempo indica si es individual o del ganador.
- Directorio de fuentes para Uruguay, Estados Unidos, Francia, Gran Bretaña, Japón, Hong Kong, Brasil, Argentina y Chile.
- Búsqueda e importación de pedigrees del Stud Book Uruguayo; resultados de Maroñas por pista, fecha y número de carrera. Consultas anónimas a los servicios públicos que usan ambos sitios.
- Importador específico de perfiles y campañas públicas del Stud Book Argentino; importador genérico de tablas compatibles para otras fuentes y carga atómica de registros JSON con IDs explícitos.
- Rankings por ganancias con puestos, moneda, alcance de fuente y país de nacimiento separado del registro; acceso a cada pedigree y búsqueda en la lista.
- Exportación XLSX con once hojas reales (siete en demostración), y respaldo JSON reimportable de caballos y resultados.

**Muestra original de partida (20/10/2026):** 53 registros reales: 38 del Stud Book Uruguayo (incluyen los pedigrees de Invasor, China Invasora y Mad Sharp) y 15 del Stud Book Argentino (Electric Mud y sus ancestros). Hay seis llegadas oficiales de Maroñas, carrera 1 del 18/10/2026, y nueve actuaciones individuales de Electric Mud en La Plata. La clasificación de Maroñas está completa respecto de sus seis participantes; las actuaciones argentinas son parciales. Se conservan, por separado, 29 caballos ficticios de demostración. La web abre la base real.

**Ampliación por ganancias (base anterior a la extensión histórica):** 2.452 registros reales en total, incluidos ancestros y registros de distintas fuentes; 400 ejemplares ocupan puestos: 200 de Equibase en USD, 100 nacidos en Uruguay con premios HRU en UYU y 100 nacidos en Argentina con premios oficiales del Stud Book en ARS entre 1992 y 2026. Los grupos uruguayo y argentino tienen las catorce posiciones de ancestros completas. Los pedigrees de Equibase siguen parciales. Los importes argentinos son nominales, sin ajuste por inflación: el orden favorece a corredores recientes y no mide calidad deportiva entre generaciones. No es una clasificación de ganancias mundiales. Brasil sigue en 0/100 por el fallo TLS del portal nacional. [Metodología, cobertura y pendientes](docs/rankings.md).

Las muestras originales están archivadas en `samples/uruguay_official.json` y `samples/argentina_official.json`; la ampliación por ganancias se conserva en `samples/historical_rankings.json`. La instalación las carga sólo si la base no tiene caballos reales. Nunca reemplaza una base existente. Son instantáneas históricas; las consultas desde la web actualizan lo que el usuario elige importar.

El acceso a los servicios uruguayos, inicialmente bloqueado, ya respondió. Se validaron en vivo la búsqueda, la importación de tres pedigrees y la importación de una clasificación de seis llegadas. El servicio de Maroñas presenta demoras y errores intermitentes; el cliente espera hasta 45 segundos por solicitud, conserva la última importación válida y no guarda datos parciales si falla la descarga. Las pistas disponibles en el formulario provienen del catálogo público; esta validación de resultados corresponde a Maroñas, no a todas las pistas.

El resto de los países sigue como directorio de fuentes e importador genérico. Sus estructuras requieren conectores específicos y verificación. No hay sincronización masiva ni una integración comprobada de todos los organismos.

Los stud books publican genealogías; los organismos y operadores hípicos publican resultados. Algunas páginas pueden requerir suscripción, autorización, JavaScript o tener prohibida la automatización. El importador consulta `robots.txt`, limita las solicitudes y no evade restricciones. [Fuentes y estado](docs/fuentes.md).

## Excel

La instalación crea estos archivos en `exports/`:

- `Linaje_pedigrees.xlsx`: base real, con los registros de Uruguay y Argentina y sus resultados; preparada para incorporar más datos.
- `Linaje_DEMOSTRACION.xlsx`: registros ficticios para mostrar el esquema y los árboles completos.

Hojas: **Leer primero, Caballos, Pedigree 3G, Resultados, Fuentes, Importaciones, Diccionario, Cobertura 1935, Contraste fuentes, Rankings y Ganancias**. Las dos últimas pertenecen a la base real. Pedigree 3G contiene una fila por caballo, con nombres e IDs de los 14 ancestros. Caballos conserva las relaciones normalizadas por ID. El exportador crea hojas adicionales si una tabla supera las 1.048.575 filas de datos permitidas por Excel. Los importes de rankings se conservan como texto decimal exacto junto a su moneda; no se convierten ni se suman monedas distintas. Los archivos están sujetos a los recursos del equipo; no se promete tamaño ilimitado.

La interfaz exporta siempre el estado actual de la base. Para regenerar archivos en disco:

```bash
.venv/bin/python scripts/export_excel.py
```

El XLSX sirve para archivo y edición. La entrada de datos a la aplicación usa JSON; no se implementó reimportación directa de XLSX. [Formato de importación](docs/importacion.md).

## Validación

```bash
.venv/bin/python -m pip install --cache-dir /workspace/.cache/pip -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
node --input-type=module --check < static/app.js  # opcional, si Node está disponible
```

Las pruebas cubren coeficientes de parentesco conocidos, padres ya consanguíneos, ciclos y coherencia de progenitores, aislamiento de demostración, pedigrees de bisabuelos, importación/rollback, filtros de resultados, procedencia y XLSX sin fórmulas ejecutables. Las tablas genéricas de `tests/fixtures` son sintéticas. `argentina-profile.html`, `uruguay-pedigree.json` y `maronas-race.json` contienen extractos factuales de las respuestas oficiales consultadas, con sólo los campos necesarios; no incluyen información de cuentas o propietarios.

`scripts/browser_check.py` prueba la navegación en Chromium, búsqueda, pedigree, análisis, filtros, fuentes, exportación y móvil. Es una verificación opcional que requiere Playwright y Chromium del entorno, y un servidor iniciado. No instala navegadores ni modifica la base real. `python3 scripts/browser_rankings.py` comprueba listas reales, monedas, nacimiento, fichas, rankings pendientes, paginación, búsquedas y móvil. `python3 scripts/browser_regressions.py` verifica además que una consulta lenta o un error de una pantalla anterior no interfieran con la navegación actual.

## Persistencia y límites

SQLite se guarda en `data/constastro.sqlite3`, fuera de Git. Se puede configurar `CONSTASTRO_DB` para pruebas o una base alternativa. Los procesos deben reiniciarse al restaurar un entorno; datos, dependencias y archivos permanecen en el snapshot publicado. Este checkout ya está aislado: no crear worktrees para ejecutar la aplicación.

No se fusionan homónimos automáticamente. Un mismo caballo con IDs de fuentes distintas necesita reconciliación documental antes de analizar un cruce. Datos faltantes o duplicados entre registros pueden subestimar la consanguinidad. Un pedigree no es un test de ADN, no evalúa mutaciones hereditarias y no predice salud, fertilidad ni rendimiento.

El modo local permite el mantenimiento de datos por un operador. La edición pública de consulta bloquea las importaciones y mantiene disponibles los pedigrees, el análisis y las descargas. Se incluyen una edición estática y configuración para Netlify; ver [publicación y actualización de datos](docs/publicacion.md). El despliegue requiere conectar una cuenta de alojamiento; estos archivos por sí solos no publican un sitio. Un servicio con edición multiusuario necesita autenticación y permisos adicionales.


## Correcciones de integridad

Las importaciones parciales conservan los campos que no se informan y los valores conocidos de sexo y parentesco. Un ancestro incluido en otro pedigree no degrada un perfil destacado a un registro secundario. Los IDs repetidos dentro de un lote se rechazan antes de escribir. Las fechas de filtros se validan y las carreras se agrupan por un ID estable, aunque provengan de fichas distintas. No se vincula un resultado de Maroñas a un ID del Stud Book por simple coincidencia de nombre.

Las columnas nuevas de resultados (`race_id`, `time_kind`, `scope`, `field_size`) se añaden mediante una migración idempotente al iniciar. Se conservó un respaldo local de SQLite antes de la migración en `data/backups/`. Las exportaciones mantienen filtros y encabezados incluso al dividir tablas en varias hojas.

## Ganancias y país de nacimiento

Ver [metodología, cobertura y pendientes de los rankings](docs/rankings.md). Equibase se limita a su cohorte de caballos con salidas en EE. UU., Canadá o Puerto Rico. HRU publica premios en UYU de su circuito. Ninguna de las dos tablas debe presentarse como un censo de ganancias mundiales de todos los caballos. El ranking argentino reconstruye el período 1992–2026 a partir de las estadísticas públicas, controla los límites de las tablas truncadas y corrobora nacimiento y premios en cada ficha. Brasil sigue pendiente de acceso al portal nacional o de una exportación verificable. PedigreeQuery y las fichas detalladas de Equibase presentan verificaciones de acceso; no se eluden.

`.venv/bin/python scripts/import_argentina_rankings.py` reanuda el importador argentino. El informe de cobertura se archiva en `samples/argentina_rankings_proof.json`. Los importadores conservan respuestas en `data/ranking_cache/` para reanudarse y guardan cada diez puestos el progreso uruguayo. `birth_country`, `ranking_sets` y `ranking_entries` se incorporan mediante migración idempotente. Se preservó una copia de SQLite antes de esta ampliación. Las fechas de nacimiento cronológicamente imposibles de las fuentes se dejan sin confirmar y se documenta el valor original, sin inventar un reemplazo ni desactivar la validación.

Las actualizaciones incompletas de rankings conservan la última lista completa; las listas nuevas pueden guardar progreso si no existe una completa. El reemplazo se serializa en SQLite. Las búsquedas de rankings aceptan tildes opcionales y espacios exteriores. La identificación de padrillos de Equibase no depende del orden de las páginas y la caché argentina distingue cada techo de premios.

La ampliación histórica conserva ese conjunto de 2.452 objetivos e incorpora sus ancestros documentados. [Alcance, contraste en dos fuentes y límites](docs/pedigree-review.md). Los totales actuales y los pendientes por caballo se encuentran en `samples/pedigree_review.json`; no se declara verificación completa cuando faltan fuentes independientes.

Las estimaciones por distancia usan `static/performance.js`: escala orientativa **0–100**, con regularización y base neutral de **50** cuando no hay actuaciones utilizables. Con evidencia se combinan posiciones relativas (participantes oficiales conocidos) o un indicador auxiliar de puesto recíproco con menor peso, conservando sus fuentes y limitaciones. Cada rama aporta la mitad; los ancestros lejanos y las muestras pequeñas tienen menos influencia. La interfaz explica fórmula, datos usados y confianza descriptiva. No es probabilidad de ganar ni predicción genética validada. [Método completo](docs/publicacion.md#búsqueda-e-índice-de-campañas). `node tests/performance.mjs` comprueba la base neutral, evidencia parcial, duplicados y ponderación. La función antigua de `affinity.js` no se presenta como rendimiento.

`python3 scripts/check_publication.py` inicia su propio servidor de prueba en un puerto libre, lo cierra al terminar y comprueba la edición HTML con Chromium. Evita depender de un servidor de otra sesión.
