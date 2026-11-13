# Fuentes por país

Estado de validación al 20/10/2026. Los accesos de Uruguay, inicialmente bloqueados, ya respondieron. Se probaron los servicios públicos que usa el JavaScript de los sitios, sin credenciales ni acceso privado:

- **Stud Book Uruguayo:** búsqueda por nombre y consulta por ID de ficha y pedigree. Se importaron Invasor (ID 49882), China Invasora (95495) y Mad Sharp (100131), con sus ancestros hasta bisabuelos. El archivo tiene 38 IDs distintos. `URU` indica el registro consultado; no implica nacimiento en Uruguay.
- **Maroñas:** `GetRaces` y `GetRaceParticipants` del servicio público. Se importó la carrera 1 de Maroñas del 18/10/2026, con seis llegadas definitivas y tiempos individuales. La cantidad coincide con los seis participantes oficiales. La carrera está identificada por el ID 47352. El servicio tiene demoras intermitentes; las solicitudes se validan antes de guardar. Las Piedras y las demás pistas del formulario están catalogadas, pero todavía no tienen una carrera de ejemplo validada.
- **Argentina:** fichas con país de nacimiento, pedigree y total de campaña. El histórico de premios nominales en ARS se reconstruye mediante doce períodos de 1992 a 2026, ampliación por techo de premios y validación de candidatos. [Controles de cobertura](rankings.md). El 13/11/2026 se archivaron 1.832 actuaciones numéricas publicadas en las fichas de los 100 objetivos del ranking argentino, enlazadas por sus IDs oficiales. Las tablas individuales pueden cubrir sólo parte de la campaña; no son clasificaciones completas de las carreras ni documentan el número de participantes.

La búsqueda uruguaya sólo muestra diez coincidencias por consulta para que el usuario elija el registro correcto. No se recorre ni se descarga automáticamente todo el stud book. Los resultados de Maroñas no se enlazan por nombre a los IDs del Stud Book: son espacios de identificación diferentes.

En los demás países se consultó robots.txt y se conservó el resultado en el historial. JBIS declara `Crawl-delay: 600`; no se realizaron consultas masivas. The Jockey Club declara 120 segundos, Equibase 5 y BHA 10. El importador interactivo rechaza intervalos superiores a 30 segundos. Las portadas accesibles no prueban que sus datos se puedan extraer.

| País / región | Pedigrees | Resultados y pistas prioritarias |
|---|---|---|
| Uruguay | Stud Book Uruguayo (`www.studbook.com.uy`) | Maroñas Hípica (`hipica.maronas.com.uy`); Resultado de Maroñas validado. El formulario permite Las Piedras y el interior mediante el mismo servicio; faltan ejemplos verificados de esas pistas. |
| Estados Unidos | The Jockey Club (`www.jockeyclub.com`) | Equibase (`www.equibase.com`); Churchill Downs, Belmont Park, Saratoga, Santa Anita, Keeneland, Gulfstream Park. |
| Francia | France Galop (`www.france-galop.com`) | France Galop; ParisLongchamp, Chantilly, Deauville. |
| Gran Bretaña | Weatherbys General Stud Book (`www.weatherbys.co.uk`) | British Horseracing Authority (`www.britishhorseracing.com`); Ascot, Epsom, Newmarket, York. |
| Japón | JBIS (`www.jbis.jp`) | JRA (`www.jra.go.jp`); Tokyo, Nakayama, Kyoto, Hanshin. |
| Hong Kong | Hong Kong Jockey Club (`racing.hkjc.com`) | HKJC; Sha Tin y Happy Valley. HKJC es el organismo de carreras, no un stud book de cría local independiente. |
| Brasil | Stud Book Brasileiro (`www.studbook.com.br`) | Jockey Club Brasileiro (`www.jcb.com.br`, estadísticas en `site.jcb.com.br`) para Gávea; Cidade Jardim y Cristal requieren fuentes específicas adicionales. |
| Argentina | Stud Book Argentino (`www.studbook.org.ar`) | Adaptador de perfiles y campañas validado con Electric Mud (La Plata). Palermo y San Isidro requieren validar ejemplos adicionales; resultados de campaña son parciales. |
| Chile | Stud Book de Chile (`www.studbook.cl`) | Futuros conectores por pista: Club Hípico, Hipódromo Chile y Valparaíso Sporting. La cobertura de resultados de la fuente aún debe comprobarse. |

Un stud book y un proveedor de resultados cumplen funciones diferentes. El directorio no garantiza que una entidad ofrezca todos los datos pedidos ni que las páginas sean públicas o permitan scraping. Las pistas aparecen como categorías de organización, no como feeds conectados.

Los destinos necesarios se guardaron en `network.allowed_domains` del borrador del entorno, conservando el preset existente. El usuario debe revisar y guardar la configuración y publicar el entorno para activarla, según el flujo de la plataforma. Los servicios uruguayos se reconsultaron con éxito. Los conectores internacionales restantes necesitan comprobar sus condiciones de uso y adaptar cada estructura. No se pidieron contraseñas ni tokens: no hay evidencia de que una credencial sea la solución al bloqueo del proxy.

## Rankings históricos

Equibase: se validaron dos páginas públicas, con 200 puestos distintos por ganancias nominales en USD; su cohorte requiere al menos una salida en EE. UU., Canadá o Puerto Rico. HRU: estadísticas acumuladas de su circuito en UYU, filtradas por nacimiento URU, con reconciliación documental del pedigree en el Stud Book. [Alcance, importación y fuentes pendientes](rankings.md). Los rankings nacionales no usan el país de registro como sustituto del nacimiento.

PedigreeQuery respondió 403 con una verificación de acceso, y las fichas individuales de Equibase mostraron una comprobación contra robots; no se evadieron. El portal nacional brasileño presenta un error TLS y el JCB accesible publica estadísticas de temporada de Gávea. El endpoint argentino limita cada consulta a tres años y 150 filas; el nuevo importador combina períodos consecutivos y comprueba límites de candidatos omitidos para reconstruir la clasificación nominal en ARS de 1992–2026. Las fichas indican sólo carreras oficiales de Argentina; no es una clasificación de premios mundiales.

La ABCPCC [documenta su herramienta de estadísticas nacionales y exportación Excel/PDF](https://www.abcpcc.com.br/noticias/post/abcpcc-disponibiliza-ferramenta-de-acompanhamento-instantaneo-das-estatisticas-nacionais), con acceso a temporadas anteriores. Se confirmó su existencia; el bloqueo pendiente es la conexión TLS de este entorno al portal, no la inexistencia de estadísticas nacionales. El sitio aclara que depende de los reportes enviados por los hipódromos.
