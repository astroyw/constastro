# Campañas y cobertura individual

La revisión de carreras incluye **cada registro real de la biblioteca**, también los ancestros incorporados. El objetivo genealógico permanece en los **2.452 registros originales**: no se convierten los nuevos ancestros en otros árboles a completar.

Cada ficha muestra las actuaciones enlazadas a su ID, filtros por año e hipódromo, y detalles de distancia, superficie, llegada, participantes, jinete, entrenador, caballeriza, pesos, premios, tiempos y video cuando la fuente los publica. Los estados de llegada no numéricos se conservan sin inventar un puesto. Un tiempo del ganador no se atribuye al caballo que llegó detrás. Los importes conservan la moneda y el valor de la fuente.

## Qué significa «completa en esta fuente»

Se compara el número de carreras distintas recuperadas con el total que publica la misma fuente. Si falta el total, hay diferencias o filas no interpretables, la campaña sigue parcial. Cero actuaciones descargadas no significa que el caballo nunca corrió.

- Stud Book Argentino: el total y las actuaciones se refieren a **carreras oficiales de Argentina**. La letra **C significa césped**, según la tabla de desglose de superficies de la misma ficha; se corrigió la lectura anterior y se conserva el código original.
- HRU/Maroñas: el servicio público `GetHorseCard` puede devolver campañas detalladas y participantes oficiales. Algunas fichas antiguas sólo devuelven un total sin las actuaciones. Hay demoras intermitentes. Los IDs de HRU se enlazan al Stud Book únicamente al coincidir nombre, año documentado, ambos progenitores y los demás campos de identidad conocidos.
- Las fichas sin una consulta o sin un ID de carreras reconciliado permanecen pendientes. No se han certificado campañas completas en todos los países del mundo.

La hoja **Cobertura campañas** del Excel incluye todos los registros y sus consultas, incluso los que no tienen resultados. **Resultados** conserva cada actuación y sus detalles. **Ampliaciones documentadas** conserva las fuentes de las revisiones individuales del pedigree, incluida la discrepancia de año de Eclair.

## Continuar sin repetir trabajo

```bash
.venv/bin/python scripts/collect_campaigns.py argentina
.venv/bin/python scripts/collect_campaigns.py uruguay
.venv/bin/python scripts/collect_campaigns.py archive
```

Sin `--limit`, se recorre toda la cola disponible de la fuente. `--limit 200` permite un lote. Las observaciones guardadas en SQLite y `samples/campaign_results.json` permiten reanudar incluso en otra instalación; los HTML comprimidos y las respuestas de trabajo permanecen en `data/full_campaign_cache/`, fuera de Git. `--retry-errors` vuelve a intentar únicamente las consultas fallidas. Las revisiones correctas no se borran.

Se consulta robots.txt, se limita la frecuencia y se detiene la fuente ante controles de acceso o tres errores consecutivos. Los pendientes no se rellenan con carreras sintéticas. En Uruguay, ampliar la cola exige reconciliar más IDs con documentación; no basta una coincidencia de nombre.

```bash
.venv/bin/python scripts/archive_pedigree_review.py
.venv/bin/python scripts/build_static.py
.venv/bin/python scripts/build_preview.py
python3 scripts/check_publication.py
```

El ZIP contiene la edición estática y las descargas. El HTML independiente incluye datos, módulos y Excel. Las cifras de la edición publicada son una instantánea; no cambian hasta reconstruirla y publicarla.
