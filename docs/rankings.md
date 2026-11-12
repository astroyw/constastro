# Rankings por ganancias

Consulta de fuentes: 20 de octubre de 2026. El criterio de los rankings nacionales es **país de nacimiento**, confirmado por el usuario. `country` identifica el registro de procedencia; `birth_country` identifica el nacimiento. No se considera uruguayo a un caballo argentino por estar inscripto o correr en Uruguay.

## Equibase: 200 puestos

Se obtuvieron y validaron los puestos 1 a 200 de la tabla histórica de Equibase. La lista incluye caballos con al menos una salida en Estados Unidos, Canadá o Puerto Rico. No representa todos los caballos del mundo, aunque contiene premios internacionales publicados por Equibase para su cohorte. Por eso la web la denomina **Top 200 histórico · Equibase**.

Fuente pública: `https://www.equibase.com/stats/ViewAllTime.cfm?tf=all-time&rbt=TB`. El servicio que utiliza su interfaz es `/Data.cfm/Stats/Horse/AllTime/Page`, con parámetros `page`, `sort`, `dir`, `list` y `set`. Se descargaron dos páginas de cien filas y se ordenaron por el puesto que informa la fuente; no se infirió la posición por el número de página.

Las ganancias son USD nominales, sin ajuste por inflación. Se conserva el decimal exacto en SQLite y Excel, separado de la moneda. Cada puesto tiene un ID de Equibase; los padrillos adicionales son registros de pedigree y **no cuentan** para los 200 puestos. El país de nacimiento se guarda sólo cuando el sufijo de origen lo confirma; ausencia de sufijo no equivale automáticamente a USA.

La tabla informa el padre y su identificador, pero las fichas detalladas de Equibase respondieron con una verificación contra robots. PedigreeQuery devolvió HTTP 403 con una verificación de Cloudflare. No se evitó ninguna restricción. Por lo tanto, los pedigrees de este grupo son parciales y deben completarse con una fuente accesible o un archivo autorizado con IDs y filiaciones verificables.

## Uruguay: 100 nacidos allí, circuito HRU

El servicio público que utiliza Maroñas permite estadísticas acumuladas sin filtro de fechas. Se consultó `GetRacingStatistics` con `StatsType=1`, `HorseStatsType=1`, `Order=2`, `MaxRanking=300`, sin restringir pista ni fechas. Los primeros 300 puestos contienen más de cien nacidos en Uruguay; se seleccionaron los primeros 100 con `Horse.Country.CustomCode=URU`.

Los premios están expresados por la fuente en **pesos uruguayos, UYU**. Incluyen el circuito cubierto por HRU y no necesariamente carreras en el exterior. La fuente no declara el comienzo temporal de su archivo. Esto **no certifica un top 100 de ganancias mundiales de uruguayos**, ni permite ordenar estos importes junto con los USD de Equibase. La web muestra esta cobertura junto al título.

Por cada caballo se consulta `GetHorseCard`. Su ID de HRU se reconcilia con el Stud Book Uruguayo sólo si coinciden nombre normalizado, año, padre y madre, y la ficha del registro confirma nacimiento en Uruguay. Una coincidencia de nombre por sí sola no crea un enlace. El pedigree se importa hasta las catorce posiciones de padres, abuelos y bisabuelos. Los sufijos de nombres y los IDs originales se conservan.

Algunas fechas del registro son cronológicamente imposibles, por ejemplo padres y descendientes nacidos el mismo año. Se omiten las fechas implicadas y se anota el valor original y el motivo; se mantienen las relaciones. La validación general de ciclos, sexo y cronología sigue activa. Un error de consulta no se rellena con ascendientes inventados.

## Argentina: histórico nominal del Stud Book, 1992–2026

La API pública admite como máximo tres años por consulta y 150 ejemplares por tabla. Ese límite no obliga a usar sólo los últimos tres años: el importador reúne doce períodos consecutivos, sin solapamientos, del 01/01/1992 al 20/10/2026. Se empieza en 1992 para conservar la unidad monetaria ARS; no se mezclan monedas anteriores sin una conversión documentada.

El filtro público **Premio menor o igual** permite descargar otro tramo del período reciente. Se verificó que cada importe respete el techo y que los IDs repetidos tengan el mismo premio; no se suman dos veces las filas que aparecen en ambos tramos. Se comprueban orden, cantidad, posiciones, fechas e identidad.

No basta sumar los nombres encontrados en tablas truncadas. Para controlar los omitidos, se usa la suma del último premio incluido en cada período: cualquier caballo nunca listado queda por debajo o igual a ese límite. Tras ampliar el período reciente, ese techo es ARS 49.392.403, mientras que el puesto 100 ya observado tiene al menos ARS 61.399.500. Por eso, un caballo ausente de todas las tablas no puede desplazar a los cien primeros dentro de esta cobertura.

La unión contiene 1.782 candidatos con bandera argentina. Para cada candidato también se calcula un máximo: premios observados más los cortes de los períodos donde no aparece. Se consultan las fichas que aún podrían entrar en el top 100. Hay 182 candidatos iniciales; los que quedan estrictamente por debajo del corte final pueden descartarse por su límite, sin volver a consultar. Una ficha que falta y todavía podría alterar los cien puestos impide marcar la lista como completa.

En cada ficha se corrobora el nacimiento explícito **Argentina**, el total de premios y los años de campaña, además de importar el pedigree con sus IDs hasta bisabuelos. Se usa el total de campaña, no la ganancia media por carrera. El equivalente USD que publica la fuente se conserva en las notas, sin crear una conversión propia. Los totales se contrastan con los límites inferior y superior de las tablas. Una contradicción detiene la certificación de ese candidato.

La clasificación usa **ARS nominales**. La inflación favorece a los corredores recientes; este orden no mide calidad deportiva entre generaciones. La campaña del perfil está identificada por el propio Stud Book como **sólo carreras oficiales de Argentina**: no se presentan esos importes como ganancias mundiales ni se incluyen años anteriores a 1992. El título, período, moneda y alcance se muestran junto a la lista. Los puestos durante una importación incompleta son provisionales.

La comprobación detallada queda en `samples/argentina_rankings_proof.json` y la instantánea de caballos y puestos en `samples/historical_rankings.json`. La caché guarda extractos factuales de fichas: filiación, nacimiento y premios, sin datos de propietarios ni cuentas. Los fallos transitorios de algunas fichas se reintentan después de completar la pasada; el tiempo de espera del sitio argentino es de 45 segundos. Las fechas de relleno como 01/01/0001 se omiten y se documenta el valor publicado.

## Brasil: acceso pendiente al portal nacional

Se volvió a consultar `https://studbook.com.br/` y `https://www.studbook.com.br/`. Ambos devolvieron HTTP 503 con `CERTIFICATE_VERIFY_FAILED` en la conexión TLS de origen desde este entorno. La ABCPCC responde y sus enlaces oficiales de búsqueda, simulador y estadística nacional apuntan a ese mismo portal. Se revisaron la noticia oficial que explica las funciones de búsqueda, la página de enlaces, el buscador de noticias y el acervo digital de Turfe e Fomento. El acervo consultado contiene revistas históricas, no una tabla de ganancias acumuladas nacionales que permita certificar los cien puestos solicitados.

La existencia de la herramienta y sus exportaciones sí está confirmada por la noticia oficial [ABCPCC disponibiliza ferramenta de acompanhamento instantâneo das estatísticas nacionais](https://www.abcpcc.com.br/noticias/post/abcpcc-disponibiliza-ferramenta-de-acompanhamento-instantaneo-das-estatisticas-nacionais). Indica: **Stud Book → Estatística Nacional → Temporada → Animais → Processar → Ferramentas → Excel**. Permite temporadas anteriores y también genera PDF. La ABCPCC aclara que la cobertura depende de los informes remitidos por cada hipódromo. Si el portal funciona desde el navegador del usuario, las exportaciones de las temporadas pertinentes permitirían continuar la reconstrucción y corroborar las filiaciones disponibles. Se encontraron, además, resúmenes nacionales de 2016/2017, pero incluyen sólo cinco puestos de animales y cantidades resumidas; no certifican los cien históricos.

No se desactivó TLS ni se usaron fichas inventadas. Las estadísticas accesibles del Jockey Club Brasileiro corresponden a temporadas de Gávea; no sustituyen el histórico nacional por país de nacimiento. Brasil conserva **0/100 · Pendiente de fuente**. Para completarlo hace falta que el portal vuelva a ser accesible desde este entorno, o una exportación verificable de sus estadísticas y filiaciones. No se requiere enviar contraseñas.

## Reanudar y exportar

```bash
.venv/bin/python scripts/import_historical_rankings.py equibase
.venv/bin/python scripts/import_historical_rankings.py uruguay
.venv/bin/python scripts/import_argentina_rankings.py
.venv/bin/python scripts/import_historical_rankings.py pending
.venv/bin/python scripts/export_excel.py
```

Las respuestas consultadas se conservan en `data/ranking_cache/`, con fecha de recuperación, para reanudar sin repetir solicitudes ya completadas. Ejecutar estos comandos de manera secuencial; no lanzar dos importaciones del mismo ranking a la vez. Una ejecución reanudada usa la misma instantánea archivada, no implica actualizar todas las ganancias al día actual. Para una nueva instantánea, respaldar y mover el caché primero. El cliente respeta robots.txt e intervalos por host.

`GET /api/rankings` devuelve cobertura y recuentos; `GET /api/rankings/{id}` devuelve los puestos, importes y cobertura del pedigree. El Excel real añade las hojas **Rankings** y **Ganancias** a las siete originales. La lista de ejemplos ficticios sigue separada y no puede participar en un ranking real. El respaldo `/api/export.json` conserva caballos y resultados; las tablas de rankings se archivan en SQLite, en su muestra JSON y en el Excel.

## Conservación de rankings durante una actualización

Una descarga parcial, interrumpida o bloqueada no reemplaza una lista completa que ya está guardada. La actualización se publica al obtener otra lista completa y válida. Si todavía no existe una instantánea completa, se admite guardar el progreso parcial. La comprobación y el reemplazo se realizan dentro de una transacción de escritura para evitar que un proceso atrasado borre el resultado completo de otro. Una invalidación deliberada de datos incorrectos puede usar el parámetro interno `allow_incomplete_replacement=True`; no se utiliza para reintentos normales.

Se rechazan listas que exceden el número de puestos solicitado. El tramo argentino por techo de premios conserva una clave de caché con el intervalo y el techo reales; no reutiliza silenciosamente un tramo de otra consulta. La caché previa de esta instantánea fue contrastada con la comprobación archivada antes de adoptar la clave nueva.

En Equibase, aparecer como padre de otro caballo establece sexo macho por el ID publicado, independientemente del orden de las páginas. Esa información se conservó para los corredores que también figuran como padrillos. La búsqueda de rankings ignora tildes y espacios al principio o al final.

Se intentó consultar el índice público de Common Crawl como posible vía para localizar documentos históricos del portal brasileño. El proxy respondió 403 antes de acceder al índice. `index.commoncrawl.org` y `data.commoncrawl.org` quedaron agregados al borrador de red para revisión; no se descargaron documentos de ese archivo ni se da por comprobada su cobertura. Esta vía sigue pendiente de habilitación y de una prueba de acceso.
