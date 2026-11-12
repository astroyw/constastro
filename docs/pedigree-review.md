# Ampliación y contraste documental de pedigrees

El conjunto de trabajo está fijado en los **2.452 registros que existían antes de la ampliación** (`samples/pedigree_targets.json`), según la aclaración del usuario. Son registros de fuentes diferentes; no equivalen a 2.452 identidades biológicas distintas. Los ancestros nuevos ayudan a completar sus ramas, pero no se convierten en nuevos objetivos de ampliación.

El límite histórico es un año de nacimiento documentado **1935 o anterior**, época de Nearco. Se aplica a **todas las ramas**; encontrar a Nearco en una rama no completa las demás. Los años desconocidos no acreditan haber llegado al límite. Cuando una rama alcanza ese año, no se exige completar el pedigree adicional de ese antepasado. La tabla histórica muestra cada ID una vez, en la generación más cercana; permite buscarlo y abrir su ficha. La vista gráfica de padres, abuelos y bisabuelos se conserva.

## Evidencias y campos pendientes

Se descargan los pedigrees públicos de los Stud Books de Uruguay y Argentina, conservando sus identificadores, URL de procedencia y fecha de consulta. Los adaptadores pueden leer las cuatro generaciones publicadas y continuar con fichas de los ancestros necesarios. No se inventan progenitores para celdas vacías o enlaces sin un ID estable. Las fechas imposibles permanecen pendientes y no se corrigen por conjetura. Cada lote pasa las validaciones de sexo, edad, referencias y ausencia de ciclos.

El contraste utiliza **editores diferentes**, no dos URL de un mismo Stud Book. Nombre normalizado, año y ambos padres deben coincidir, con un único candidato por editor y sin contradicción de sexo, antes de respaldar una correspondencia documental. Los IDs se mantienen separados. Acentos y sufijos de país pueden variar; no se eliminan palabras del nombre ni se hace emparejamiento aproximado. Una coincidencia de nombre y año sin ambos padres se señala como candidato, no como verificación. Cuando falta el año, nombre y padre coincidentes permiten mostrar un candidato, pero no confirmar su identidad.

Se comparan por separado nombre, año, sexo, padre, madre, país de nacimiento y pelaje. Un campo vacío no cuenta como coincidencia. Las diferencias se muestran con ambos valores. **La coincidencia parcial no certifica todo el árbol ni verifica campañas o ganancias.** La aplicación no afirma que todos los datos estén comprobados en dos fuentes: esas comprobaciones siguen pendientes cuando falta evidencia independiente.

Las fichas de Equibase devolvieron una comprobación de acceso; PedigreeQuery no permitió consultar su robots.txt (HTTP 403). JBIS exige en robots.txt un intervalo superior al admitido por el importador interactivo. No se eluden estos controles. Los rankings y resultados existentes conservan sus fuentes y sus limitaciones.

## Archivos reproducibles

- `scripts/expand_pedigrees.py`: continúa los pendientes del conjunto original con una cola por fuente, intervalo mínimo de dos segundos por host y caché persistente. `--limit N` limita las consultas nuevas por fuente en esa ejecución. Los perfiles sin datos adicionales quedan pendientes; no se reintentan en bucle.
- `data/deep_pedigree/`: fichas factuales incorporadas y registro de consultas/fallos, sin datos de propietarios ni credenciales.
- `scripts/archive_pedigree_review.py`: valida el grafo y archiva los registros atribuidos y la auditoría individual de los 2.452 objetivos.
- `samples/extended_pedigrees.json`: instantánea incorporable a una instalación nueva, con resumen cuantitativo.
- `samples/pedigree_review.json`: auditoría por caballo, enlaces faltantes y contraste con URL y fechas.
- `exports/Linaje_revision_pedigrees.csv`: resumen de cobertura por objetivo original.

El Excel mantiene **Caballos** como tabla normalizada con todas las generaciones enlazadas. **Cobertura 1935** informa profundidad, ancestros únicos, ramas terminales y enlaces faltantes. **Contraste fuentes** documenta candidatos, campos corroborados y diferencias. **Pedigree 3G** conserva los catorce casilleros originales. El libro real tiene once hojas cuando incluye rankings; el de demostración conserva siete. La demostración no participa en la verificación documental.

`pedigree_evidence.json` conserva una observación atribuida que realmente muestra los campos comparados, en lugar de usar un enlace posterior que sólo mencione al caballo. `scripts/complete_pedigree_review.py` reanuda la ampliación, archiva el resultado disponible, comprueba la aplicación y publica los dos artefactos preservando el resto de la rama remota. El estado queda en `data/deep_pedigree/completion.json`; cualquier fallo detiene la publicación. Que termine la cola accesible no implica que todos los datos tengan dos fuentes.

## Conciliación documentada de progenitores

`scripts/reconcile_documented_parents.py` puede completar campos vacíos de un progenitor cuando dos registros de un **mismo hijo corroborado** lo identifican como padre o madre. El hijo debe coincidir de forma única entre editores en nombre, año y ambos progenitores; los registros de sus padres deben ser compatibles en nombre, año, sexo y nacimiento conocidos, y la correspondencia debe ser recíproca y única por editor. Nunca se identifica un caballo solamente por el nombre.

Se añaden únicamente años o enlaces publicados en la observación del registro correspondiente del otro Stud Book. No se fusionan IDs ni se reemplazan campos conocidos. El grafo vuelve a validar sexo, cronología y ciclos. Cada complemento conserva ambas fichas del hijo, la ficha del progenitor que publica el dato, fechas y valores exactos en `samples/pedigree_reconciliations.json`. Un complemento documentado puede tener una sola fuente para el dato añadido: **no se lo presenta como corroborado en dos fuentes**. Las discrepancias se dejan pendientes. Sólo se completan los nodos necesarios para los 2.452 objetivos originales hasta 1935.
