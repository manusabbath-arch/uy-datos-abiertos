# Qué de las investigaciones de fuentes externas se puede aplicar a `uydatos` y `mcp-uruguay`

Fecha: 2026-10-09 (hora de Montevideo). Todo lo de acá se probó **por HTTP el 09/10/26**, y las
cifras salen de un archivo o de una respuesta con su fecha. No hay nada re-tipeado de memoria.

Describe qué le falta a **estos** dos repos. Las candidatas salen de una investigación previa de
fuentes externas, privada, en la que cada fuente se probó por HTTP; acá se volvieron a medir.

## 1. Método

Dos repos, dos capas, y la pregunta es siempre la misma: **¿esta fuente tiene una trampa que no
da error, y ya está escrita en algún lado?**

| Capa | Repo | Qué tiene |
|---|---|---|
| Lectores | **`uy-datos-abiertos`** (`uydatos`) | 10 módulos: la trampa de cada fuente, con excepción |
| Agente | **`mcp-uruguay`** | 13 herramientas MCP que envuelven esos módulos, con caché |

Lo que se hizo acá: **recorrer las candidatas ya probadas y medir, una por una, cuáles
le faltan a la librería**, con la trampa incluida. No es una lista de deseos: cada candidata entra
o no entra por lo que se midió al abrir el archivo.

## 2. La candidata que valía, y ya está adentro: INUMET

Antes de esta sesión, `uydatos` tenía **una** fuente de clima: `inia`, una sola estación, en Salto.
INUMET tiene **seis datasets en el catálogo**, con licencia de datos abiertos de Uruguay; los dos
que se midieron a fondo (temperatura y precipitación) traían `metadata_modified` del **09/10/26**,
el mismo día de esta corrida.

`uydatos.inumet` es nuevo (0.3.0). La forma de los archivos es `fecha;estacion_id;<valor>[,<valor>]`
y las tres trampas que se midieron leyendo los archivos **completos** de temperatura
(12.059.752 bytes, sha `ddcd33dd…`) y precipitación (9.887.612 bytes, sha `f89d5765…`) son:

1. **La columna de la estación puede traer el texto de un error del servidor.** Los dos archivos
   traen una fila cuyo `estacion_id` es `' please try again later.'`. Llega **sin fecha**, así que
   no es una fila de dato; lo peligroso es agrupar por esa columna sin validarla: crea una
   **octava estación** (« please try again later.») con sus 0 filas, y nada se pone rojo. El lector
   la saltea, la **cuenta** (`filas_sin_dato()`) y rechaza la variante que sí traiga fecha.
2. **La hora es UTC**, y lo dice el metadato del dataset, no el encabezado. Uruguay es UTC−3 todo
   el año: agregar por día sobre la fecha cruda **corta el día local a las 21:00**. `serie_diaria()`
   toma el desfase como parámetro y un día local al que le falte una hora queda en `None` con sus
   `horas` declaradas.
3. **`estacion_id` no es un id: es el nombre** («Salto G3»), y el valor viene en la unidad que
   declara el metadato. El lector no la convierte.

Medido sobre el archivo real de temperatura: **332.070 filas de dato y 8 líneas sin dato**, siete
estaciones, del 2020-01-01 00:00 UTC al 2026-10-09 03:00 UTC. Sobre precipitación, en Salto:
**1.457 de 1.532 días locales** con suma calculable (95,1%); el 2026-10-07 sumó 23,9 mm.

**Los seis quedaron medidos** (el encabezado primero, con petición de rango, y después el archivo
entero), y los cuatro últimos tenían cada uno lo suyo:

| Variable | Filas de dato | Cadencia | Lo que apareció |
|---|---|---|---|
| temperatura | 332.070 | horaria | — |
| precipitación | 291.085 | horaria | — |
| humedad | 329.794 | horaria | — |
| presión | 326.207 | horaria | — |
| **viento** | 137.030 | **cada dos horas (12 al día)** | y trae **dos** columnas de valor |
| **insolación** | 3.437 | **diaria, cinco estaciones** | **4 valores por encima de 24 h**, tres el 01/08/2026 |

Las dos correcciones que salieron de medirlos, y que ya están en el módulo:

- **La cadencia no es 24 para todas.** `serie_diaria()` medía contra 24 horas fijas, así que **el
  viento habría quedado entero en `None`** —publica 12 por día, medido en 10.841 de 11.690
  días-estación—. Ahora la cadencia vive en `OBS_POR_DIA`, por columna.
- **El metadato de insolación declara «horas de brillo del Sol en el transcurso del día» y el
  archivo trae 63,2 h.** Son 4 filas de 3.437 —tres el mismo día, en Salto (63,2), Artigas (38,0) y
  Mercedes (37,6)— y ninguna otra pasa de 20: no es ruido, es un evento de la fuente. Un rango
  (0, 24) las habría tratado como el error del servidor y habría rechazado **el archivo entero**.
  Se declaran en los extremos por columna de `resumen()`; `heliofania` queda sin rango **a
  propósito**.

## 3. Candidatas verificadas que **no** entraron todavía

Ninguna de estas es una suposición: se abrieron.

### 3.1 Sanciones de Defensa del Consumidor — la fuente no cambió, el lector de la librería falta

`defensa-del-consumidor-sanciones-a-empresas`: el recurso sigue siendo el mismo archivo
(`datos_sanciones_2017_2024.csv`, 168.759 bytes, **sha `241a78a1…`**, idéntico al medido el
04/10/26) y el corte sigue siendo **2024**: 1.528 resoluciones, 397 sólo en 2024, **483 por «Precio
no informado»** y **0 en Salto**.

Lo que falta acá es un lector **público** que devuelva las filas tal cual, sin cruzarlas con nada. **El límite que hay que declarar en el README de la
librería**, y no es chico: el archivo trae `razon_social` y `rut` de terceros. Es un dato público
—está en el catálogo abierto— pero el módulo tiene que devolver las filas y **no** decidir qué se
versiona.

Trampas medidas para ese lector: `cp1252` con `;`; el `rut` viene con **relleno de espacios a la
derecha** (`'219000000004    '`, 1.527 de 1.528 con 12 dígitos tras el `.strip()`); **una fila con
un RUT de 3 dígitos** (un vacío mal exportado) que no se descarta en silencio.

**Medido de nuevo el 2026-10-17**: mismo sha256 (`241a78a1…`), 1.528 filas, 1.443 RUT con relleno,
1 con 3 caracteres, 0 en Salto. El recurso se llama «Sanciones aplicadas a empresas»: no se elige
por el nombre del archivo. Lector: `uydatos.sanciones` (0.13.0).

### 3.2 ANCAP: la cantidad de ventas — el denominador de mercado

Además del precio (`ancap-precio-combustible-pe`, que `uydatos.ancap` ya lee), ANCAP publica
`ancap-cantidad-ventas-combustibles`, `ancap-produccion-combustibles` y
`ancap-inventario-promedio-combustibles`. El de ventas son **71.799 bytes** (sha `2c648ef7…`),
actualizado el 11/09/26, con columnas `Mercado;Mes;Anio;FamiliaDeProducto;LineaDeProducto;Bandera;CantidadCorregida;Unidad`
y la unidad declarada **«Miles de m3»**. Trampas ya vistas: coma decimal, mes y año como texto
(`'08'`, `'2026'`) y el mercado como primera columna.

**Para qué sirve:** la venta nacional de combustibles da el **denominador del mercado** contra el que se puede leer la
serie de precios: es la diferencia entre «el gasoil subió 20%» y «el gasoil subió 20% y el volumen
del mercado cayó 5%». Es una serie **sin consumidor hoy** —igual que el precio cuando entró— y por
eso va última.

### 3.3 El SIPC: la serie de precios, y su costo real

Confirmado por `package_show`: los datasets del SIPC traen **establecimiento + productos +
precios** por año, y el recurso de precios pesa **1.004,2 MB (2026)** y **2.024,7 MB (2025)**. El método
es bajar y filtrar por código de establecimiento, no una integración nueva. **No se hace hasta que exista una pregunta que necesite más de un año**: con un
año alcanza para lo que el repo mide hoy. El disparador queda escrito y no es una fecha: *cuando
exista una pregunta de precio que necesite la serie*.

### 3.4 La OPP: medida y descartada

19 datasets (`organization:opp`), y 18 tienen su último recurso de **2021-03-09 o antes** (2012,
2016, 2017 y quince de 2021); el único con datos de 2024 es el de ingresos y egresos de los
gobiernos departamentales. No es una fuente viva: es una foto del quinquenio 2015-2020. **No se
escribe el lector**, y la tabla completa con la decisión está en `2026-10-18-opp-medicion.md`.

## 4. Una trampa documentada que hoy **no se reproduce**, y por qué importa acá

Una medición del 04/10/26 encontró la **búsqueda** del catálogo rota: `package_search` devolvía
`count: 0` para todos los términos probados (`precios`, `salario`, `empleo`, `alimentarias`,
`empresas`), mientras `package_list` traía 2.779 datasets sanos. De ahí salió el método *«bajá `package_list` y filtrá en Python, el buscador no sirve»*.

**Medido hoy, con la misma llamada:**

| `q=` | `count` |
|---|---|
| `precios` | **27** |
| `sipc` | **5** |
| `combustible` | **9** |
| `salario` | **8** |
| `alimentarias` | **15** |
| `empleo` | **227** |
| `meteorologic` | 0 |

`package_list` sigue en **2.779**. O sea: **hoy el buscador del catálogo responde y encuentra**. No
se puede saber desde acá si el 04/10/26 estaba caído o si la medición de entonces fue la que
estaba mal; lo que sí se sabe es que **una trampa documentada se re-verifica antes de escribir un
workaround sobre ella**.

Por qué importa en este repo: la librería **no** tiene `buscar()` y está bien que no lo tenga
todavía —pero el día que lo agregue, el motivo por el que se elegiría `package_list` es una
medición de hace cinco días que hoy no se sostiene. `uydatos.catalogo` solo usa `package_show`,
que es lo que se midió sano en las dos fechas.

**La trampa hermana, esa sí viva:** el catálogo publica datasets cuyos recursos apuntan a URLs
**ajenas que se caen**. Los siete datasets de la ECH del INE (`ine-ech2011` y
`ine-encuesta-continua-de-hogares-*`, 2012–2017) declaran **25 recursos** —7 XLS, 7 RAR, 10 PDF y 1
DOCX—, todos contra `www.ine.gub.uy/c/document_library/get_file?...`, **sin tamaño declarado**, con
`CC0 1.0`.

**Probados los 25 el 10/10/26: los 25 devuelven HTML.** No un archivo: la portada del sitio nuevo del
INE (`https://www.gub.uy/instituto-nacional-estadistica/`), **con el `uuid` conservado como consulta**
—la firma de una migración que se dejó atrás los documentos viejos—. Ninguno bajó un XLS, un RAR ni un
PDF. El host está vivo (`179.27.170.201`, puertos 80 y 443 contestan): **no es un enlace lento ni un
certificado roto, es link rot**, y tanto el `formato` declarado como la ausencia de `tamaño` mienten
sobre estos 25 recursos.

Consecuencia: **la ECH no cambia de estado** por esta vía; el nivel socioeconómico por zona sigue
inaccesible desde el catálogo. Lo que sí queda es la guarda
(`test_los_recursos_de_la_ech_no_bajan_un_archivo`, marcada `red`), que falla el día que alguno de los
25 vuelva a entregar un archivo: esa es la señal para escribir el lector. La vía que quedaría viva no
es el catálogo sino el sitio nuevo del INE, que no se sirve por una URL de `c/document_library`.

Detalle medido de paso: el host viejo tiene además la **cadena TLS incompleta** (`*.ine.gub.uy`
verifica con error 21, «unable to verify the first certificate»), así que el mismo pedido a veces
falla por certificado y a veces redirige. Por eso la guarda cuenta las dos cosas como «no baja un
archivo», en vez de exigir que el fallo sea de una sola forma.

## 5. Orden propuesto

| # | Fuente | Estado | Necesidad que cierra | Límite |
|---|---|---|---|---|
| 1 | **INUMET** (6 variables) | **hecho** en 0.3.0 | clima en siete estaciones del país, no una | cuatro variables medidas sólo en su encabezado |
| 2 | **Sanciones DSS** | pendiente | el enforcement del SIPC, y un lector público | PII de terceros; se corta en 2024 |
| 3 | **Las URLs del INE (ECH)** | **medido 10/10/26**: enlaces muertos | el nivel socioeconómico por zona —**sigue inaccesible**— | los 25 recursos redirigen a la portada del sitio nuevo |
| 4 | **ANCAP cantidad de ventas** | pendiente | el denominador de mercado del combustible | sin consumidor todavía |
| 5 | **SIPC precios (serie)** | diferido con gate | la serie de precios minoristas | 1 a 2 GB por año |

## 6. Fuentes, fecha y sha256 de lo bajado

Todo se consultó el 09/10/26. Los archivos están en
`%LOCALAPPDATA%\hermes\cache\scratch\fuentes-nuevas\` y **no se versionan**: son datos de terceros
con licencia propia, y este repositorio publica código, no datos (ver `.gitignore`).

| Archivo | sha256 | Qué se usó |
|---|---|---|
| `inumet_temp.csv` | `ddcd33ddb7c5eca6602e2302728e0ab0baf36c58696a48269ea2441aa18819c4` | 332.070 valores; 8 líneas sin dato; 7 estaciones |
| `inumet_precip.csv` | `f89d57659d371ef8156ec896b0d4d70ad9f2259bb334a8f863a5a4e4a73c39ce` | 291.085 valores; 11.780 de 12.223 días-UTC con 24 h |
| `inumet/humedad.csv` | `1ae48bab3428d8c33c24e8804847f6e8acd647909d83e6385f7a86e5334e976c` | 329.794 valores; horaria; 10–100 % |
| `inumet/viento.csv` | `2d82284ca544b5fd1b6f902e305f35e4b3fd7cf14b927da6b1640259faec748d` | 137.030 valores; **12 por día**; dos columnas |
| `inumet/presion.csv` | `d3f935e4e116185135886908d4702ab3cbff31c7a43e4ae724df3614df37fcb7` | 326.207 valores; horaria; 990,3–1.037,4 hPa |
| `inumet/insolacion.csv` | `38095a881a42e3c2d95d60345ea611023d5369ab931b51450355ab4663b21554` | 3.437 valores; diaria; **4 por encima de 24 h** |
| `dss_sanciones.csv` | `241a78a15e951bf960f93efc12aebe0d04dc343b24198a2fa4899d1872dd4cd0` | 1.528 resoluciones; corte 2024; 483 por precio |
| `ancap_ventas.csv` | `2c648ef7eb8446c88ab46e6bbe78dd0e270fcc6566645e73dbb4fbd650dc3f7a` | 1.199 filas; unidades en miles de m³ |

**Sin archivo, citando la respuesta de la API con su fecha:** los conteos de `package_search` y
`package_list` (§4); los recursos y tamaños por `package_show` (§3); las listas de estaciones y la
unidad de cada dataset, del metadato JSON de INUMET. La investigación previa es de otro repositorio, privado, y no se copia acá.
