# Tres fuentes que se movieron — lo medido el 06/11/2026

La primera corrida de `pytest -m red` desde el entorno en la nube con los hosts de las fuentes
habilitados dio **35 de 39 en verde**. Las cuatro rojas no eran del código: tres son fuentes que
cambiaron y una es un bloqueo del servidor. Esto es lo que se midió de cada una y qué se hizo.

## 1. Sanciones del DSS: el RUT pasó por una planilla

El catálogo reemplazó el recurso el **2026-11-03**: ahora es `datos_sanciones_2017_2025.csv`.

| | Antes (medido el 17/10) | Ahora (06/11) |
|---|---|---|
| Archivo | `datos_sanciones_2017_2024.csv` | `datos_sanciones_2017_2025.csv` |
| Bytes | 168.759 | 191.915 |
| sha256 (16) | `241a78a15e951bf9` | `2389481356510dbf` |
| Resoluciones | 1.528 | 1.835 (+307 de 2025) |
| Sexta columna | `motivo_sancion` | `tipo_infraccion` |
| RUT de 12 dígitos | casi todos (1 de 3 caracteres) | **94** |
| RUT en notación científica | 0 | **1.738 (94,7 %)** |
| Montos vacíos | 0 | 230 (todos de 2025) |
| Sin departamento | 0 | 307 (todas las de 2025) |

**Lo grave es el RUT.** `2,17795E+11` es lo que deja una planilla cuando convierte un RUT en
número: de 12 dígitos quedan 6, y no se recupera. Y no es sólo un dato perdido: **120 RUT
truncados los comparten empresas distintas, en 404 filas**. Un cruce o un ranking por RUT atribuye
a una empresa las sanciones de otra.

Qué hace el lector ahora: acepta los dos encabezados medidos (los dos llegan a `motivo`), devuelve
`rut = None` con `rut_crudo` y `rut_en_notacion_cientifica = True` —**nunca el número**—, y
`resumen()` cuenta los truncados, los compartidos, los montos nulos y las filas sin departamento.
Un monto vacío es nulo, aunque los apercibimientos de 2017-2024 vengan con 0. La línea de base
(`fuentes.json`) cambió sólo en la entrada de sanciones, en el mismo commit.

Los tests usan empresas y RUT inventados con las formas medidas: `test_privacidad.py` rechazó la
primera versión, que copiaba filas reales con un RUT válido.

## 2. INUMET: dos copias del viento, y la más nueva sin dirección en 2026

El dataset del viento publica **dos juegos completos** (CSV, XML, XLSX y metadato) con los
mismos nombres de archivo: uno modificado el 2026-10-31 04:06 y otro el 2026-11-06 04:06. No
reemplazó: agregó.

| Copia | Recurso | Bytes | sha256 (16) | Filas | Hasta | Dirección nula en 2026 |
|---|---|---|---|---|---|---|
| 31/10 | `943ff07c…` | 7.332.122 | `c2d59b1c7ec3dd10` | 195.740 | 2026-10-31 03:00 | 0 de 25.068 |
| 06/11 | `5dcb9447…` | 7.282.723 | `d5fbb5c9975e8e1d` | 196.244 | 2026-11-06 03:00 | **25.572 de 25.572** |

La copia nueva tiene 504 filas más y **la dirección de todo 2026 vacía**, en las siete estaciones;
2020-2025 son idénticas. Por eso pesa menos teniendo más filas. Elegir "la más nueva" pierde un año
de dirección sin un error; elegir la vieja pierde una semana.

Qué hace el lector ahora: `descargar()` sigue rechazando cuando hay dos CSV, pero el mensaje trae
los dos ids con su fecha; `recurso=<id>` elige uno a mano y `candidatos()` los lista. `resumen()`
agrega `ultimo_con_dato` por columna: el total de nulos (3.620 en 29.194 filas en Melilla) parecía
ruido, y son todo 2026.

`test_inumet_los_seis_datasets_declaran_un_solo_csv` **queda en rojo a propósito**: dice la verdad
sobre la fuente hasta que INUMET retire una de las copias. `verificar` usa la temperatura, que tiene
un solo CSV, así que el informe del lunes no se cae.

## 3. Parlamento: el CDN bloquea los centros de datos

`parlamento.gub.uy` responde **403 desde CloudFront** (`x-cache: Error from cloudfront`, «Request
blocked», nodo de Washington) a la descarga de asistencias del Senado. Es el mismo bloqueo que el
informe del 19/10 midió desde el runner de GitHub. `documentos.diputados.gub.uy` (pedidos de
informes de Diputados) responde bien desde el mismo entorno.

No se intentó esquivarlo (por ejemplo, cambiando el `User-Agent`): el bloqueo es una decisión del
sitio. Las salidas legítimas son medir desde una conexión residencial o pedirle acceso al
Parlamento. El lector no cambia.
