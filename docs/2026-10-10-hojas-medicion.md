# Las hojas de cálculo del catálogo: qué hay, y por qué el motor sale de la firma

Fecha: 2026-10-10 (hora de Montevideo). Todo lo de acá se probó **por HTTP el 10/10/26** contra el
catálogo de datos abiertos, y cada número sale de una respuesta o de un archivo bajado. Los dos
programas de la medición viven en `scratch` y no se versionan; lo que queda es esto.

## 1. Cuántas hay

| Formato declarado | Datasets que lo declaran |
|---|---|
| XLSX | 2.162 |
| `XLS` | 60 |

Casi todo lo que no es CSV, JSON o GeoJSON es XLSX. Los 60 «XLS» son los que prometían el formato
viejo, y son el motivo de esta medición.

## 2. El metadato miente: 23 de 24

Se bajaron **24 de los 60** recursos declarados `XLS` y se miraron los primeros bytes de cada uno:

| Firma en el archivo | Cuántos | Qué es |
|---|---|---|
| `PK\x03\x04` | **23** | un ZIP de OOXML, o sea un XLSX |
| `\xd0\xcf\x11\xe0…` | **1** | un OLE/BIFF, o sea un `.xls` de verdad |

**El único `.xls` de verdad de la muestra es el de AGESIC** (`diccionario_eutic_2010.xls`, 334.848
bytes, del dataset `agesic-encuestas-de-uso-de-tic`). Los otros 23 se llaman `.xlsx`, su contenido es
OOXML, y el catálogo igual declara `XLS`.

De acá sale la regla del módulo: **el motor se elige por la firma del archivo**, no por el `formato`
que declara el catálogo ni por la extensión del recurso. Un consumidor que eligiera por el metadato
se caería en 23 de cada 24.

## 3. El XLSX de MIDES: dos hojas, y el tipo declarado

El XLSX de un indicador de MIDES trae la misma tabla que su CSV **y una hoja más**:

| Dataset | Hoja `Datos` | Hoja `Metadatos` |
|---|---|---|
| `mides-indicador-10745` | 3 filas × 2 columnas (`año`, `valor`) | 3 filas × 3 columnas |
| `mides-indicador-13198` | 71 filas × 3 columnas (`Funciones GPS_fg`, `año`, `valor`) | 4 filas × 3 columnas |

La hoja `Metadatos` se llama así por dentro y tiene las columnas `nombreDeAtributo`, `descripcion` y
`tipoDeDato`: **el XLSX declara el tipo de cada columna**, cosa que el CSV no hace. Para el 13198 dice
`String` para la dimensión y `Number` para `año` y `valor`.

Y los valores vienen **tipados**: la primera fila del 13198 trae `2005.0` y `13330423.0` como números,
no como el texto que devuelve el CSV. Quien lea el XLSX no tiene que volver a parsear nada.

La hoja `Datos` del 13198 confirma además la forma que se midió para la familia el 09/10/26: una
columna de dimensión de nombre libre adelante, y `año, valor` al final.

## 4. Dos trampas de las bibliotecas, no de la fuente

1. **openpyxl se fía de la extensión.** Con una ruta, `load_workbook()` rechaza un XLSX que se llame
   `.xls` con `InvalidFileException` — antes de mirar un solo byte. Su propio código lo dice: si el
   argumento tiene `read` no mira el nombre. El lector le pasa **el archivo abierto**, y así lee lo
   que hay adentro.
2. **openpyxl en modo `read_only` miente con las dimensiones.** Si la hoja no trae la dimensión
   declarada, `max_row` y `max_column` devuelven **1**. Una primera sonda contestó «1 fila × 1
   columna» sobre un archivo de 71 filas. El lector no usa `read_only`.

## 5. Lo que **no** se puede leer, y por qué no es culpa del lector

Los `.xls` de la **Encuesta Continua de Hogares** del INE no se pueden bajar: sus URLs viven en el
sitio viejo (`ine.gub.uy/c/document_library/get_file?uuid=…`) y redirigen a un certificado que no
valida. `red.bajar()` falla con `CERTIFICATE_VERIFY_FAILED`. Medido, no supuesto.

Consecuencia para el plan: leer `.xls` **no** destraba la ECH por sí solo. Hace falta antes resolver
la URL del INE (otro host, un espejo, o el certificado). Queda como estaba: medir antes de escribir.

## 6. Las dependencias

`openpyxl` y `xlrd` son **opcionales** (`pip install uydatos[hojas]`): el paquete base no engorda por
leer una planilla. Sin ellas, la suite saltea el módulo —284 verdes y **1 salteado**, que se ve— y el
error del lector dice cuál falta y con qué comando se instala. Los dos tests de red que fijan esto
—el `.xls` de AGESIC y un `XLS` que es XLSX— corren con las dos instaladas.
