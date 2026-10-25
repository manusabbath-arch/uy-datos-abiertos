# OSE, calidad del agua potable: lo medido el 25/10/2026

Medición previa al lector `uydatos.ose`, siguiendo `docs/plantilla-lector.md`. Cada número de acá
está en el docstring del módulo y en un test; los que no se midieron van como «sin medir», no como
una suposición.

## 1. La fuente

OSE publica **su propio CKAN** en `https://datos.ose.com.uy/api/3/action/`, con **28 datasets**. No
es el catálogo nacional: ninguno de esos 28 aparece en `catalogodatos.gub.uy`, donde la organización
«OSE» tiene 28 datasets distintos que son los mismos títulos pero referenciados. Por eso
`catalogo.accion()` tuvo que aceptar una URL base.

Dataset: `calidad-de-agua`. Declara **frecuencia anual** (`extras: Frecuencia de actualización`).
Son los análisis con que OSE reporta el cumplimiento de los seis parámetros del Reglamento
Bromatológico Nacional (Decreto 375/011, norma UNIT 833:2008).

Frecuencia declarada por los 28 datasets de OSE, para saber qué sirve como serie y qué no:

| frecuencia | datasets |
|---|---|
| Mensual | Conexiones de agua, Conexiones de saneamiento, **Facturación y consumo** (84 recursos) |
| Anual | **Calidad de agua**, Cobertura de agua potable, Cobertura de saneamiento, Información geográfica de agua potable (21 recursos), Información geográfica de saneamiento (21), Longitud de red de agua, Longitud de red de saneamiento, **RANC**, **Roturas en red de agua**, **Solicitudes y reclamos operativos** (8) |
| Ante cambios / a demanda | las 14 tablas de catálogo (tipos y estados) y Regiones, departamentos y localidades |

Las 14 «ante cambios» son **dimensiones**: las tablas de reclamos y facturación las referencian por
código, así que sin ellas esos datasets no se pueden decodificar. Es trabajo aparte.

## 2. La medición

Dos recursos de datos y uno de metadatos.

| archivo | filas | bytes | sha256 |
|---|---|---|---|
| `calidad_de_agua_bacteriologia_2017t1_2025t4.csv` | 152.967 | 31.259.384 | `0855acc6…c12709` |
| `calidad_de_agua_fisicoquimico_2017t1_2025t4.csv` | 531.679 | 96.317.443 | `ae052ae0…5b8781` |

Codificación **UTF-8**, delimitador `;`, todos los campos entrecomillados. Columnas:
`ANIO;TRIMESTRE;DEPARTAMENTO;LOCALIDAD;LABORATORIO;AREA_ANALISIS;PARAMETRO;METODO;ID_MUESTRA_M;VALOR`

Los **36 trimestres de 2017-T1 a 2025-T4 están completos**, sin un solo hueco: 1.910 a 2.484
muestras por trimestre en bacteriología y 3.012 a 4.323 en fisicoquímico. Es lo que vuelve útil al
dataset: nueve años de la misma medición, sin interrupciones.

El `hash` que declara CKAN por recurso es un **md5** (`1d7c5069…` y `1108c8de…`) y viene con
`hash_algorithm: null`. No se usa como huella: la que vale es el sha256 del archivo bajado.

## 3. Las trampas, cada una con el número que la prueba

1. **El separador decimal se parte por localidad, no por año.** pH: 98.215 valores con coma y
   **35.070 con punto**, de los cuales **35.062 son de Montevideo** y los otros 8 de Florida, en los
   nueve años. Turbidez: 102.601 con coma y 12.678 con punto (12.677 de Montevideo). Color: 3.430 y
   10. Un lector con un solo separador pierde el **26%** de las lecturas de pH del país sin dar
   error. Se aceptan los dos, se cuenta cuántos de cada uno, y un tercer formato se rechaza.
2. **La censura a la izquierda es la mayoría del dato.** Color verdadero: **124.424 de 132.745**
   valores son `<5` o `<2,5` (**93,7%**). Turbidez: 17.788 de 133.130. `valor` y `condicion` van en
   campos separados: tratar `<5` como 5 o como 0 cambia todos los promedios.
3. **Cuatro filas traen el signo al revés.** 2 `>0,2` (turbidez) y 2 `>5` (color), en 531.679 filas:
   una en Rivera, una en San Carlos, una en Artigas y una en Punta del Este, en 2017, 2021, 2022 y
   2023. El número es **el mismo** que el límite de detección de su columna, así que casi con
   seguridad es un error de carga. El lector lo devuelve como `mayor_que` y `resumen()` lo cuenta
   aparte: corregir el signo de un valor ajeno es inventar un dato, aunque la corrección parezca
   obvia. **Esta trampa no se midió a mano**: la encontró el propio lector al rechazar la fila
   55.440 de fisicoquímico, y por eso está acá.
4. **Hay un valor imposible, y por eso pH queda sin rango.** El pH va de 1,6 a **251,0** en una
   escala de 0 a 14. El 251,0 es **una sola fila** (2017-T2, Melo, Lab. Reg. Treinta y Tres) y el
   siguiente valor más alto de las 133.287 lecturas es 10,5; el mínimo, 1,6, es de **Salto**
   (2021-T1, Laboratorio Central), y el siguiente 1,8 (Punta del Este). Un rango 0-14 habría
   rechazado **531.679 filas por una**. Los extremos se declaran en `resumen()`. Turbidez llega a
   98,0 NTU y color a 198,0 UC, también sin rango.
5. **La bacteriología no es numérica, y aun así trae un número.** Coliformes totales y E. coli
   tienen tres valores en nueve años: `Ausencia` 151.980, `Presencia` 985 y `<1` **2**. Las dos
   filas con `<1` son de *Atlántida - Laguna del Cisne* y las dos de 2020. Un dominio de dos valores
   habría rechazado 152.967 filas por 2; uno que convierta, miente. Se declara el dominio de tres.
   Olor: `Característico` y `No Característico`, nada más.
6. **No hay columna de unidad.** Está implícita en `PARAMETRO`: turbidez en NTU, color en UC, pH
   adimensional. Se declara en `UNIDADES`; no se infiere.
7. **Una muestra no es un laboratorio.** 1.773 `ID_MUESTRA_M` de bacteriología y 3.161 de
   fisicoquímico aparecen con más de un laboratorio. Las muestras únicas son **76.784** y
   **133.598**, no 152.967 y 531.679. `resumen()` informa las dos cuentas.
8. **Los dos archivos no cubren las mismas localidades.** 38 en bacteriología y 41 en fisicoquímico.
   Maldonado, Piriápolis y San Carlos sólo están en fisicoquímico, y Punta del Este tiene 29.042
   filas en fisicoquímico y **8** en bacteriología. Cruzarlos por localidad no cierra.
9. **El nombre del recurso cambia cada año.** Se llama «Bacteriología desde 2017-Trimestre 1 a
   2025-Trimestre 4»: lleva el rango de fechas adentro. Se identifica por el nombre del **archivo**
   en la URL, y **por prefijo**, porque el de metadatos se llama
   `metadatos_calidad_agua_bacteriologia_y_fisicoquimico.csv` y contiene los dos nombres.
10. **El metadato no coincide con el dato.** El CSV de metadatos describe el atributo `año`; la
    columna real se llama `ANIO`.
11. **El trimestre es un string y no hay mes ni día.** `"trimestre 1"`, no un número. La resolución
    temporal más fina es el trimestre, y se devuelve como intervalo (`desde`, `hasta`), no como un
    día. **Es la razón por la que esta fuente no puede alimentar un semáforo diario.**
12. **El datastore tipa todo como `text`.** `datastore_search` con `filters={"ANIO": 2025}` y un
    entero devuelve **HTTP 409**; con `"2025"` responde. `{"LOCALIDAD": "Salto"}` da 8.776 filas de
    las 152.967 del recurso de bacteriología, y sirve como segunda lectura para contrastar el CSV.

## 4. Lo que no se midió

- **Si los `<5` de color son todos el mismo límite de detección** o si el límite cambió de método a
  lo largo de los nueve años. La columna `METODO` está, pero no se cruzó con el límite. Sin medir.
- **Si el pH de 251,0 y el de 1,6 están corregidos en alguna versión posterior del archivo.** La
  copia medida es la del 29/06/2026 (lo que declara CKAN como `last_modified`). Sin medir.
- **Las otras 27 tablas de OSE.** Sólo se midieron las frecuencias declaradas, no su contenido.
- **El cruce con los informes de la CARU o con el semáforo de playas.** Fuera del alcance del
  lector: lo que se mide acá es el archivo.

## 5. Decisiones que quedan registradas

- **`ose` queda en `verificar.PENDIENTES`.** Bajar 122 MB cada semana contra un dataset que se
  actualiza una vez al año es desperdicio que paga la fuente. La señal de cambio sale gratis de
  `recursos_vigentes()` (el `size` y el `last_modified` que declara CKAN) y de `hace_falta_bajar()`.
  La forma la fija el test `red` de `tests/test_ose.py`.
- **`ose` va con `datasets: ()` en el manifiesto de `fuentes`.** `deriva()` consulta el catálogo
  nacional y el dataset no está ahí. Lo vigila el test `red` del módulo, que le pregunta al CKAN de
  OSE por los dos prefijos de archivo.
- **`hace_falta_bajar()` compara tamaños, no hashes.** El `hash` de CKAN es un md5 del archivo
  subido y no hay con qué compararlo sin leer los 122 MB. Por eso la función responde si *hace
  falta* bajar, no si el archivo es correcto; la identidad la prueba el sha256 del sello.
