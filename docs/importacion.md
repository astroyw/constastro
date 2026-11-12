# Importación y trazabilidad

## Archivo JSON

En **Base de datos → Cargar archivo JSON**, elegir un archivo con esta estructura:

```json
{
  "horses": [
    {"id":"REG-P","name":"Padre documentado","country":"URU","sex":"M","birth_year":2000},
    {"id":"REG-M","name":"Madre documentada","country":"URU","sex":"H","birth_year":2001},
    {"id":"REG-H","name":"Descendiente documentado","country":"URU","sex":"M","birth_year":2010,"sire_id":"REG-P","dam_id":"REG-M","source_id":"manual","source_url":"https://www.studbook.com.uy/","notes":"Ejemplo de estructura. Reemplazar por registros y URL de ficha reales."}
  ],
  "results": []
}
```

Este ejemplo explica el formato; **sus nombres y registros son ficticios** y no se precargan como reales.

Campos de caballo: `id`, `name`, `country`, `birth_country`, `birth_year`, `sex`, `coat`, `sire_id`, `dam_id`, `source_url`, `source_id`, `notes`, `featured`. Sólo `id` y `name` son obligatorios. Año desconocido: `null`. Sexo: `M`, `H`, `C` o `U`. País de registro: `URU`, `USA`, `FRA`, `GBR`, `JPN`, `HKG`, `BRA`, `ARG`, `CHI`. `featured` marca perfiles destacados. Los ancestros también son registros de Caballos.

El ID debe provenir del registro de origen, con un prefijo que lo distinga de otras fuentes; se permiten letras ASCII, números, punto, guion, guion bajo y dos puntos. Nunca usar sólo el nombre. `demo-` está reservado. Los progenitores deben existir o incluirse en el mismo lote. No se permiten ciclos, progenitores con sexo incompatible o nacidos después de sus hijos. No se mezclan relaciones con ejemplos ficticios. La carga se valida completamente y se guarda en una sola transacción. Límite por lote: 50.000 caballos, 20.000 resultados y 15 MB en la interfaz; se pueden cargar tantos lotes como permita el almacenamiento.

Un resultado requiere: `id`, `country`, `track`, `date` (AAAA-MM-DD), `race_name`, `position` (entero desde 1), `horse_name`, `source_url` HTTPS. Opcionales: `distance` (metros), `surface`, `horse_id`, `jockey`, `time`. El caballo puede no estar identificado en la base; en ese caso `horse_id` es `null`. No se vincula por coincidencia de nombre. Si se incluye `horse_id`, debe pertenecer a la base real.

Reimportar un ID actualiza ese registro. Los campos omitidos no se reemplazan por valores predeterminados; `sex=U` no borra un sexo conocido. Los IDs duplicados en un mismo lote se rechazan. Los campos vacíos de un caballo no borran parentescos previamente documentados; para correcciones deliberadas se necesita revisar el registro en una tarea de edición de datos. El JSON de **Respaldar caballos y resultados** usa el mismo formato y se puede reimportar.

## Página pública

1. Seleccionar organismo y tipo de información.
2. Pegar la URL HTTPS de una tabla pública del organismo. No pegar credenciales o URLs de sesión.
3. Para resultados, completar fecha, pista y nombre/número de carrera si la tabla no los incluye.
4. El servidor consulta robots.txt, respeta intervalos y verifica TLS. No sigue redirecciones a dominios ajenos al organismo.
5. Se reconocen encabezados comunes en español, inglés, francés, portugués y algunos japoneses.

Para pedigree, la tabla debe incluir nombre, padre y madre, con IDs explícitos o enlaces estables a cada ejemplar. Las fichas enlazadas no se recorren automáticamente. Para completar las tres generaciones hay que importar las fichas/listados correspondientes a los padres y abuelos. Para resultados, se requieren nombre de caballo y posición numérica. No se inventan puestos para descalificados o retirados; la versión actual importa sólo posiciones numéricas y no es un archivo completo de incidencias de la carrera.

El importador no interpreta automáticamente PDFs, árboles visuales sin tabla, páginas de aplicación JavaScript ni APIs privadas. La estructura real de cada sitio necesita validación y, en su caso, un adaptador específico. Un error no guarda registros parciales. Se conserva un historial de intentos.


## Adaptador validado: Stud Book Argentino

Seleccionar la fuente argentina y pegar una URL de perfil como `https://www.studbook.org.ar/ejemplares/perfil/429310/electric-mud`.

- **Caballos y pedigree:** obtiene el ejemplar y sus 14 ancestros hasta bisabuelos desde `#table-pedigree`. Conserva los IDs numéricos del registro y las relaciones de cada columna; no vincula por nombre.
- **Resultados:** importa la campaña individual del perfil e incluye su pedigree para que las actuaciones queden vinculadas al ejemplar. No es la clasificación completa de cada carrera. Sólo se guarda el tiempo del ganador cuando la posición del caballo es 1; no se atribuye el tiempo ganador a los otros puestos.
- `country=ARG` significa que el dato proviene del registro argentino. No implica nacimiento en Argentina: los nombres de los ancestros conservan sus sufijos y las notas aclaran el significado.
- Se validó una ficha real consultada el 20/10/2026; la estructura de otros perfiles puede variar y un cambio de columnas detiene la importación.
- `samples/argentina_official.json` permite reproducir la muestra obtenida sin volver a consultar la web. Es un archivo histórico con procedencia, no una actualización automática.


## Conectores de Uruguay

**Base de datos → Uruguay → Buscar en el Stud Book Uruguayo:** escribir tres caracteres o más, identificar el caballo por año, padres e ID, y pulsar **Importar pedigree**. Se consultan los endpoints públicos de ficha y árbol del registro, hasta bisabuelos. No se deduce el año por la edad ni se inventan IDs de padres. Una relación desconocida queda vacía. La importación agrega ancestros por ID y conserva relaciones ya documentadas.

**Resultados:** elegir pista, fecha y número de carrera. El servicio público se consulta con parámetros anónimos para una sola carrera. Se comprueba que la respuesta corresponda a esa pista, fecha y número y que esté en el estado definitivo observado en la fuente. No se guardan programas ni resultados provisorios. Si las llegadas numéricas no cubren todos los participantes declarados, `scope=partial`; sólo se usa `full` cuando ambas cantidades coinciden. Retirados y abandonos sin posición numérica no se convierten en puestos inventados.

Cada resultado puede incluir `race_id`, `time_kind` (`individual`, `winner`, `unknown`), `scope` (`full`, `partial`) y `field_size`. Las exportaciones conservan estos campos. Una coincidencia entre nombre de Maroñas y nombre del Stud Book permite buscar en la biblioteca, pero no enlaza automáticamente ambos IDs.

La consulta de ejemplo verificada corresponde a Maroñas, 18/10/2026, carrera 1. El servicio puede tener demoras: si falla, no se escribe una clasificación incompleta ni se borra la última importación válida. Las consultas respetan robots.txt, almacenan la política durante una hora y mantienen el intervalo por host entre solicitudes.

`birth_country` es el país de nacimiento verificado, con código internacional de tres letras (`URU`, `ARG`, `BRA`, `USA`, `JPN`, etc.). Es independiente de `country`, que indica el registro. Se admite `null` cuando no se conoce; no se completa por presunción. Los rankings nacionales filtran exclusivamente este campo.
