# espaciodatos

> **In English:** strict, dependency-free Python readers for near-Earth object data: JPL close
> approaches (CAD), JPL Sentry and ESA NEOCC impact-risk lists, and CNEOS fireballs, plus a
> cross-check showing **where JPL and ESA disagree**. Sister package of `uydatos`: each reader
> documents its source's traps and **raises instead of silently fixing** bad data.

Lectores **estrictos** de datos abiertos del espacio cercano, en Python puro. El paquete hermano
de [`uydatos`](../README.md): la misma regla (**rechazar en vez de arreglar**) y la misma
infraestructura (red, sello de procedencia y la base de los rechazos), de la que es su única
dependencia.

| Módulo | Fuente | Qué trae | La trampa principal |
|---|---|---|---|
| `cad` | JPL Close Approach Data API | 52.247 acercamientos a la Tierra de 1900 a 2200 (a menos de 0,05 au) | La fecha no se ordena como texto (`1900-Apr` < `1900-Jan`), está en TDB, y la incertidumbre viene en tres formatos. `dist_min = 0` no es un impacto posible. |
| `sentry` | JPL Sentry | La lista de riesgo de impacto (2.239), los retirados (3.596) y el estado de un objeto | El diámetro es **estimado** con un albedo supuesto; Torino nulo no es cero; un objeto retirado responde **HTTP 200 con error**; la documentación dice string donde el API manda entero. |
| `bolidos` | CNEOS Fireball API | 1.074 bólidos desde 1988, con energía y ubicación | **Las coordenadas vienen sin signo**: ignorando el hemisferio aparecen 4 bólidos en Uruguay; hay **uno** (2008-04-07, a la altura de Salto). |
| `esa` | ESA NEOCC, lista de riesgo | 2.205 objetos, en texto de ancho fijo | La designación va sin espacio (`2008JL3`): contra JPL coinciden 0 por texto. Dos ausencias distintas del Torino (`n/a`, `n/d`). Diámetros en metros. |
| `cruce` | JPL contra ESA | Dónde no coinciden las dos agencias | **175 objetos que la ESA lista fueron retirados por JPL**, algunos en 2020; el Palermo difiere más de ×10 en 292 de 1.974. |
| `designacion` | — | Una clave para el mismo objeto escrito de cuatro formas | `6344 P-L` no es el asteroide 6344. |
| `vigilancia` | Dos copias de Sentry y de la ESA | Qué cambió: nuevos, retirados, Palermo y Torino, con el antes y el después, en Markdown | Un sha256 distinto no dice qué cambió: en 31 minutos cambiaron las tres copias y en Sentry, 2 objetos de 2.239. **2026 VX1 subió en JPL y bajó en la ESA en la misma media hora.** |
| `clima` | NOAA SWPC | Kp de 3 h (observado, estimado, pronosticado), escalas G/R/S y alertas | **La tormenta G1 empieza en Kp 4,67, no en 5**: un umbral ingenuo pierde 3 de 6 franjas. `estimated` puede ser futuro, y la clave `"1"` de las escalas es hoy. |
| `herramientas` | Lo ya bajado | Seis preguntas como funciones que devuelven JSON con advertencias y sellos, listas para un servidor MCP | Cada respuesta dice lo que una cifra **no** es (TDB, diámetro estimado, Torino nulo). |

Lo medido, con los sha256 y los números de cada trampa: [`docs/2026-11-06-neo-medicion.md`](docs/2026-11-06-neo-medicion.md)
y [`docs/2026-11-06-clima-y-vigilancia-medicion.md`](docs/2026-11-06-clima-y-vigilancia-medicion.md).

## Uso

```sh
python -m espaciodatos todo datos/                   # baja las cinco fuentes y cruza JPL con ESA
python -m espaciodatos cad proximos datos/cad.json --dias 30
python -m espaciodatos sentry resumen datos/sentry.json
python -m espaciodatos sentry estado "2024 YR4"      # retirado el 2026-03-05 16:02:50 UTC
python -m espaciodatos bolidos cerca datos/bolidos.json --lat -34.9 --lon -56.2 --radio 500
python -m espaciodatos cruce datos/
python -m espaciodatos vigilar copia-del-lunes/ copia-de-hoy/   # qué cambió, en Markdown
python -m espaciodatos clima bajar datos/ && python -m espaciodatos clima resumen datos/
python -m espaciodatos herramienta estado_de_un_objeto datos/ --param objeto="2014 ML67"
```

## Para un servidor MCP

`espaciodatos.herramientas` trae las preguntas ya resueltas; un servidor sólo las publica:

```python
from espaciodatos import herramientas

herramientas.actualizar("cache/")                     # la única que sale a la red
for nombre, h in herramientas.HERRAMIENTAS.items():   # nombre, descripción y parámetros
    ...                                               # registrar h["funcion"] con su descripción
herramientas.llamar("estado_de_un_objeto", "cache/", objeto=99942)
```

Cada respuesta tiene la forma `{"datos", "advertencias", "procedencia"}`. Para 2014 ML67:

```json
{"datos": {"clave": "2014 ML67", "jpl": null, "jpl_retirado_utc": "2021-08-09T16:58:35",
           "esa": {"palermo_acumulado": -3.81, "probabilidad": 3.6e-07, "anios": [2027, 2124]}},
 "advertencias": ["JPL lo retiró el 2021-08-09 (descartó todos sus impactos) y la ESA lo sigue listando: las agencias no coinciden."],
 "procedencia": [{"fuente": "JPL Sentry 2.0", "sha256": "b6ea1954…", "bajado": "2026-11-06T16:35"}, …]}
```

| Herramienta | Qué contesta |
|---|---|
| `proximos_acercamientos` | Qué pasa cerca de la Tierra en los próximos días |
| `riesgo_de_impacto` | Los objetos de mayor riesgo según JPL y según la ESA |
| `estado_de_un_objeto` | Todo lo que se sabe de un objeto: listas, retiro y acercamientos |
| `desacuerdos_entre_agencias` | Dónde no coinciden JPL y la ESA |
| `bolidos_cerca` | Bólidos registrados cerca de un punto (por defecto, Uruguay) |
| `clima_espacial` | Kp, tormentas próximas, escalas y alertas de NOAA |

```python
from espaciodatos import cad, cruce, esa, sentry

filas = cad.leer("datos/cad.json")             # tipadas, ordenadas por jd, con marcas
apophis = [f for f in filas if f["des"] == "99942" and f["instante_tdb"].year == 2029][0]
apophis["dist_km"]                              # 38.011 km del centro de la Tierra

c = cruce.comparar(
    sentry.leer("datos/sentry.json"),
    esa.leer("datos/esa_riesgo.txt"),
    sentry.leer_retirados("datos/sentry_retirados.json"),
)
c["esa_lista_lo_que_jpl_retiro"][0]             # {'clave': '2014 ML67', 'ps_esa': -3.81, ...}
```

Toda salida de un informe cierra con el sello de `uydatos.procedencia`, con la **versión del API
leída del propio archivo**:

```
JPL CAD 1.5 · bajado 2026-11-06 12:59 · 52.247 filas · sha256:691ce8c49032 · 10.740.795 bytes · https://ssd-api.jpl.nasa.gov/cad.api
```

## Las reglas, además de las de `uydatos`

1. **La versión mayor del API se valida; la menor no**. El contrato real es la lista de campos,
   que se valida entera: un campo nuevo se rechaza aunque la versión sea la misma.
2. **Lo que no se interpreta, se marca**: `dist_min_en_cero`, `sin_v_inf`, `cometa`,
   `torino_definido`, `diametro_estimado`. El lector no decide qué significan.
3. **Una estimación se llama estimación**: `diametro_estimado_km` en Sentry, `diametro_km` sólo
   donde es medido.
4. **El cruce no elige ganador**: dice dónde difieren las dos agencias y con qué fecha cada una.

## Desarrollo

```sh
cd espaciodatos
uvx ruff check src tests && uvx ruff format --check src tests
uv run --with pytest --with-editable .. --with-editable . pytest -q          # sin red, segundos
uv run --with pytest --with-editable .. --with-editable . pytest -q -m red   # contra JPL y ESA
```

Vive en el repositorio de `uydatos` mientras es chico y comparte su infraestructura. Se puede
separar a su propio repositorio con la historia intacta: `git subtree split --prefix espaciodatos`.
