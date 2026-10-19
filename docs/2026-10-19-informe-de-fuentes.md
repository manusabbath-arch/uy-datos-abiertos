# El informe de las fuentes: qué compara, qué no, y cómo se actualiza

Fecha: 2026-10-19 (hora de Montevideo). Todas las cifras de acá salen de dos corridas reales de
`python -m uydatos.verificar` hechas hoy, con su `docs/fuentes.json` al lado.

## 1. Qué es

`docs/fuentes.json` es el **informe aceptado** de las 21 fuentes del paquete: 13 que se bajan y se
leen enteras, y 8 que declaran qué parámetro les falta o por qué no son una fuente. Se genera con:

```sh
uv run --quiet python -m uydatos.verificar --salida docs/fuentes.json
```

y su versión legible, el **diccionario observado**, con:

```sh
uv run --quiet python -m uydatos.verificar --esquema docs/fuentes.json > docs/fuentes.md
```

El mismo archivo tiene dos usos: es la **línea de base** contra la que se compara la corrida de cada
lunes, y es el **diccionario** que se consulta sin red para saber qué columnas devuelve una fuente.
Un artefacto, no dos.

## 2. Qué mide

| Fuente | Filas | Columnas | Bytes |
|---|---:|---:|---:|
| `ancap` | 26.618 | 5 | 893.940 |
| `ancap_ventas` | 1.223 | 8 | 73.171 |
| `bcu` | 30 | 2 | 978.633 |
| `compras` | 140.144 | 8 | 27.132.122 |
| `elecciones` | 7.352 | 13 | 285.506 |
| `ibge` | 562 | 2 | 170.403 |
| `indec` | 117 | 2 | 4.265 |
| `inia` | 20.526 | 4 | 29.083.273 |
| `inumet` | 393.534 | 3 | 14.287.903 |
| `limites` | 20 | 7 | 4.709.102 |
| `parlamento` | 508 | 5 | 81.544 |
| `sanciones` | 1.528 | 8 | 168.759 |
| `ursea` | 580 | 8 | 49.106.270 |

La corrida completa tarda **4 minutos** en esta máquina (INIA son 57 CSV, compras un ZIP de 27 MB y
URSEA 49 MB).

## 3. Qué compara el CI, y dónde queda

El lunes, el trabajo `fuentes-reales` de `.github/workflows/tests.yml` escribe el informe de la
corrida en `informes/fuentes-<run_id>.json`, lo sube como **artifact de 90 días** y compara contra
`docs/fuentes.json`:

- **rompió**: la fuente estaba ok en la línea de base y hoy no se lee. Es el único rojo que importa.
- **columnas**: cambió el conjunto de columnas. El paso queda en amarillo (`--falla-si-cambio` sale 1,
  `continue-on-error` deja seguir el job) porque un cambio de columnas puede ser una mejora de la
  fuente o el fin del lector.
- **filas**: cambió el volumen por encima de `max(10 filas, 20%)`. Avisa; no frena.
- **aparece / desaparece**: una fuente entró o salió del informe. Con una corrida de un subconjunto,
  las que no se pidieron aparecen como «desaparecen»: es visible, no silencioso.

La tabla del diff se escribe en el resumen del run, junto al estado del manifiesto.

## 4. Por qué el sha256 no es un gate

Dos corridas de hoy, con cuatro minutos de diferencia, dieron **el mismo tamaño y otro sha256** en
`ursea`; y `limites` ya tenía la misma rareza anotada en el docstring del módulo, medida también hoy:

| Fuente | Bytes | sha256 | Qué se midió |
|---|---:|---|---|
| `ursea` | 49.106.270 | `a4e1876d4d8f…` → `45843cc6dcf7…` | dos corridas completas de hoy, 4 minutos aparte |
| `limites` | 4.709.102 | `f89967472c53…` | dos bajadas seguidas, mismo tamaño y otro sha (docstring de `verificar.py`) |

El WFS de límites no serializa igual dos veces, y el archivo de URSEA cambia algún byte interno sin
cambiar de tamaño. Por eso el sha se **informa** (sirve para citar exactamente lo que se leyó) pero
no se usa para decidir si hay un problema: la forma sí se compara.

## 5. Qué NO mide

Conviene escribirlo, porque el informe parece más de lo que es. Con los cinco pilares de
observabilidad de datos como referencia (frescura, distribución, volumen, esquema y linaje):

- **Sí mide volumen** (filas, bytes) y **esquema** (columnas), y tiene un sucedáneo de **frescura**:
  la fecha que declara el catálogo. El caso del DSS del 17/10 mostró que esa fecha miente en las dos
  direcciones: se movió sin que el archivo cambiara, y ANCAP cambió el archivo sin moverla.
- **No mide distribución**: nulos por columna, rangos, valores imposibles. Eso hoy vive en los tests
  de cada lector, con los números medidos en su docstring.
- **No mide linaje**: no hay tablas derivadas que seguir; el paquete lee fuentes primarias.

## 6. Cómo se actualiza la línea de base

**A mano, y en el mismo commit que el cambio que la explica.** Cuando la fuente cambia de verdad
(agrega una columna, republica el archivo) y el lector se adapta:

```sh
uv run --quiet python -m uydatos.verificar --salida docs/fuentes.json
uv run --quiet python -m uydatos.verificar --esquema docs/fuentes.json > docs/fuentes.md
git diff docs/fuentes.json      # esto ES la revisión: qué cambió, con fecha
```

Nunca por un bot que la actualice sola: eso convertiría el aviso en algo que siempre está verde, que
es exactamente el error que `CADENCIA` corrigió en 0.13 con INUMET. Si el cambio no se entiende
todavía, la línea de base **no se toca** y el amarillo del lunes queda ahí hasta que se entienda.

El historial de cada corrida no vive en el repo: son los artifacts de Actions, 90 días.
