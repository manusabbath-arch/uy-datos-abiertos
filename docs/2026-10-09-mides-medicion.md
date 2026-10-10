# La forma de cinco indicadores de MIDES, medida antes de escribir el lector

Fecha: 2026-10-09 (hora de Montevideo). Todo lo de acá se midió **por HTTP el 09/10/26** y sale de
un archivo o de una respuesta con su fecha, no de memoria.

MIDES tiene **1.875 datasets** en `catalogodatos.gub.uy`, el **69%** del catálogo, y casi todos
siguen el patrón `mides-indicador-NNNNN`. Antes de decidir si se escribe **un lector de familia**
(`uydatos/mides.py`) o **una declaración de columnas por indicador** hay que saber si esos
indicadores comparten forma. Este documento mide cinco, uno por tema distinto, y contesta.

## 1. Qué se buscó, con qué consulta y cuándo

La consulta exacta, el 09/10/26:

```python
from uydatos import catalogo
r = catalogo.buscar("", organizacion="mides", filas=100)
```

Respuesta: `total=1875`, `organizaciones={'mides': 1875}`,
`formatos={'CSV': 1840, 'JSON': 1836, 'XLSX': 1836, 'XML': 1836, 'PDF': 6, 'TXT': 2}`.

O sea: **no todos los 1.875 traen CSV** (1.840), pero los cuatro formatos «de dato» (CSV, JSON,
XLSX, XML) están en 1.836 cada uno. Los cinco que se midieron abajo son del tipo
`mides-indicador-N`, que es la mayoría del fondo.

Los 100 resultados de esa consulta quedaron en
`%LOCALAPPDATA%\Temp\mides\mides-100.json`, y se eligieron los cinco **por tema**, no los primeros
cinco. Los cinco elegidos y por qué:

| Indicador | Tema | Por qué ese |
|---|---|---|
| `mides-indicador-10745` | medio ambiente | DBO industrial vertida a los cursos de agua: una serie ambiental con una sola dimensión temporal |
| `mides-indicador-10885` | social | pobreza según sexo por ascendencia afro: **dos** dimensiones de desagregación además del año |
| `mides-indicador-5974` | salud | personas mayores según institución prestadora de salud: **una** dimensión institucional |
| `mides-indicador-14089` | vivienda / territorio | régimen de tenencia por departamento: la dimensión es territorial (los 19 departamentos) |
| `mides-indicador-13198` | económico / gasto público | Gasto Público Social en pesos corrientes, por función: valores grandes, misma forma |

Los cinco tienen los cuatro recursos (JSON de metadatos, CSV, XLSX, XML) y **un solo CSV** cada uno.
Se bajó el CSV de cada uno a `%LOCALAPPDATA%\Temp\mides\` (no al repo). Los archivos son de
terceros y **no se versionan**.

## 2. La tabla de medición

| Indicador | Tema | Filas de dato | Columnas | sha256 (12) | ¿En el datastore? |
|---|---|---:|---:|---|---|
| `mides-indicador-10745` | medio ambiente | 2 | 2 | `2267d9c4fe3d` | sí — `total` 2 |
| `mides-indicador-10885` | social | 56 | 4 | `577842db7dc5` | sí — `total` 56 |
| `mides-indicador-5974` | salud | 108 | 3 | `a55da9a64948` | sí — `total` 108 |
| `mides-indicador-14089` | vivienda / territorio | 1.235 | 4 | `ce685f934a40` | sí — `total` 1.235 |
| `mides-indicador-13198` | económico / gasto público | 70 | 3 | `58fd5841db0e` | sí — `total` 70 |

Comunes a los cinco, medidos uno por uno sobre el archivo bajado:

- **codificación `latin-1`** (los cinco hacen fallar `utf-8`), **sin BOM**;
- **delimitador `,`** (coma), no `;`;
- **sin celdas vacías** en ninguna columna de ninguno;
- `valor` viene como **texto con punto decimal** (`56.3`), y `año` como año de cuatro dígitos.

## 3. El encabezado de cada uno, textual

Tal cual viene en la primera línea del archivo (comillas incluidas; el separador es la coma):

**`mides-indicador-10745`** (medio ambiente)

```
año,valor
```

**`mides-indicador-10885`** (social)

```
"Sexo","Ascendencia Racial",año,valor
```

**`mides-indicador-5974`** (salud)

```
"institucion",año,valor
```

**`mides-indicador-14089`** (vivienda / territorio)

```
"Tenencia De Vivienda","departamento",año,valor
```

**`mides-indicador-13198`** (económico / gasto público)

```
"Funciones GPS_fg",año,valor
```

Dos detalles que salen de mirar los tres encabezados juntos:

1. **`año` y `valor` son siempre las dos últimas columnas, siempre sin comillas**, y con esos dos
   nombres exactos en los cinco. Lo demás es el nombre de la dimensión, que cambia.
2. Los **nombres de las columnas de dimensión van entre comillas** en cuatro de los cinco (no en
   `10745`, que no tiene dimensión): son etiquetas con espacios y mayúsculas inconsistentes
   (`"Sexo"`, `"Ascendencia Racial"`, `"Tenencia De Vivienda"`, `"Funciones GPS_fg"`).

## 4. La pregunta que decide todo: ¿el datastore tiene estos recursos?

Sí. Los cinco están cargados en el datastore de CKAN, consultados con
`catalogo.datastore_search(<id del recurso>, limite=1)`:

| Indicador | id del recurso | `datastore_search` |
|---|---|---|
| `mides-indicador-10745` | `b70fca51-d9ab-4271-b9f5-6d54740c850e` | `total` **2**, campos `_id, año, valor` |
| `mides-indicador-10885` | `2031a3c6-fd11-4189-83d0-e558005e5164` | `total` **56**, campos `_id, Sexo, Ascendencia Racial, año, valor` |
| `mides-indicador-5974` | `db5db6b5-24e4-4b50-8608-4501ad4da431` | `total` **108**, campos `_id, institucion, año, valor` |
| `mides-indicador-14089` | `2815141a-045a-4622-91ce-466fae7fdfa8` | `total` **1.235**, campos `_id, Tenencia De Vivienda, departamento, año, valor` |
| `mides-indicador-13198` | `fad9a50a-34e7-4144-9df6-eedcf2f5db52` | `total` **70**, campos `_id, Funciones GPS_fg, año, valor` |

Ninguno devolvió error. En los cinco, el `total` del datastore **coincide exacto con las filas de
dato** del CSV: el encabezado se usó como **nombres de campo**, no como una fila más. (Ojo: en el
INUMET medido el 09/10/26 el `total` **sí** venía uno arriba, con el encabezado adentro; no es una
ley del datastore, es por recurso. Quien lea del datastore tiene que mirar el `total` contra su
propio conteo, no asumir.)

El datastore además **devuelve `año` y `valor` ya tipados** (enteros y float), no como texto como
el CSV. Para un lector de familia eso es una diferencia de contrato, no de forma.

## 5. Veredicto

**Los cinco comparten la forma: cero o más columnas de dimensión, de nombre libre, seguidas
siempre de las dos columnas `año` y `valor`, en ese orden.**

Lo único que cambia entre indicadores es **cuántas** columnas de dimensión hay (0 en `10745`, 1 en
`5974` y `13198`, 2 en `10885` y `14089`) y **cómo se llaman** (`Sexo`, `departamento`,
`Funciones GPS_fg`, …). El tramo `año,valor` es invariante en los cinco.

## 6. La consecuencia

Como la forma se comparte, **se puede escribir `uydatos/mides.py` como lector de familia**, y no
hace falta una declaración de columnas por indicador. El lector que la forma admite:

- toma **todas las columnas menos las dos últimas como dimensión**, y las devuelve como un dict
  (`{"Sexo": "Mujeres", "Ascendencia Racial": "Afrodescendiente"}`) — no las declara;
- exige que las **dos últimas** sean exactamente `año` y `valor`; un indicador que rompa eso se
  rechaza con motivo (es el defecto que cambia el dominio del dato);
- `año` → entero, `valor` → `float` con punto decimal (`latin-1`, separador `,`);
- puede leer **del CSV bajado o del datastore**, porque los cinco están cargados: del lado del
  servidor no hace falta bajar el archivo, pero el datastore tipa y el CSV no, y esa diferencia
  hay que declararla.

Queda como medición, no como promesa: estos son **cinco de 1.840** CSV. La forma se comparte en la
muestra que se eligió por tema; el lector de familia tiene que probarse contra una tanda más ancha
antes de darla por cierta (y un indicador que no cierre las dos últimas columnas en `año,valor` es
el caso que hay que buscar).

## 7. Fuentes, fecha y sha256 de lo bajado

Todo se consultó el 09/10/26. Los archivos están en `%LOCALAPPDATA%\Temp\mides\` y **no se
versionan** (datos de terceros con licencia propia; el repo publica código, no datos). El script de
medición (`elegir.py`, `medir.py`) también vive ahí, no en el repo.

| Archivo | sha256 | Qué se usó |
|---|---|---|
| `mides-indicador-10745.csv` | `2267d9c4fe3d582d67f7594f042de1a274a04a0a9ee3809092438e07c6a1e81c` | 2 filas, 2 columnas |
| `mides-indicador-10885.csv` | `577842db7dc56e1771de8e764c75bf002136da8e1a114599e9eca41921d5fe54` | 56 filas, 4 columnas |
| `mides-indicador-5974.csv` | `a55da9a649489714a115ce5cbb90df91ba316b29d6fb1da4a871f751bac3d53f` | 108 filas, 3 columnas |
| `mides-indicador-14089.csv` | `ce685f934a409cae677a4ac3e45225a4e1cf42e8cc46b9e8e30415884f848d44` | 1.235 filas, 4 columnas |
| `mides-indicador-13198.csv` | `58fd5841db0e1e101c47ae2cf70952e43f761ffadd7cb5aaaa22c87c7ee093f1` | 70 filas, 3 columnas |

**Sin archivo, citando la respuesta de la API con su fecha:** el `total` y los `formatos` de
`catalogo.buscar` (§1); los recursos, sus URLs y sus ids por `package_show` (§1 y §4); y los
`total`, `campos` y primeras filas del datastore (§4).
