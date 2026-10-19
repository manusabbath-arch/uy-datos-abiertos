# Cambios

## Sin publicar

## 0.15.1 — 2026-10-19

- **`revisiones.desde_json` no cuenta como sanas a las fuentes que no se midieron.** El primer
  resumen del CI decía «sanas 19» con 8 fuentes que piden un parámetro: un verde inflado es peor que
  un amarillo. Ahora sanas son las que se midieron y no cambiaron (11 de 21).
- **El informe del CI corre aunque los tests de red fallen** (`if: always()`): la primera corrida los
  vio salteados justo cuando más servían —el Parlamento contestaba `403` desde el runner y el informe
  es lo que dice qué pasó—.
- `docs/2026-10-19-informe-de-fuentes.md` §7: lo que encontró la primera corrida (Parlamento con
  `403` desde el runner, INDEC de 117 a 65 filas, URSEA que cambia de bytes a diario), y por qué la
  línea de base no se tocó.

## 0.15.0 — 2026-10-19

- **El informe de las fuentes se compara contra una línea de base versionada.** `docs/fuentes.json`
  es el informe aceptado de las 21 fuentes (13 medidas, 8 con su motivo); `--baseline` compara la
  corrida de hoy contra ese archivo, `revisiones.markdown()` lo escribe como tabla y
  `--falla-si-cambio` sale 1 cuando una fuente se rompió o cambió de columnas. El CI semanal sube el
  informe como artifact de 90 días y escribe el diff en el resumen: antes la tabla del lunes se
  miraba y se olvidaba, porque no tenía contra qué compararse.
- **`--esquema`**: el diccionario observado (columnas por fuente, con la fecha del informe) se lee
  sin red desde el mismo JSON. No declara tipos: `hojas` es el único lector que los conoce.
- **`--json` pasa a llamarse `--salida`** (sigue andando como alias). El sha256 se informa pero no se
  usa como fallo: medido hoy que `ursea` da 49.106.270 bytes y otro sha en dos corridas de cuatro
  minutos aparte, y `limites` hace lo mismo con el WFS.
- **Los motivos de las 8 pendientes se leen como frases**: decían «requiere no lee una fuente…»,
  porque el prefijo «requiere» se pegaba a un texto que ya era una oración.
- Lo que el informe **no** mide, escrito para no prometerlo (`docs/2026-10-19-informe-de-fuentes.md`):
  distribución (nulos, rangos por columna) y linaje. Sí mide volumen, esquema y la fecha que declara
  el catálogo.

## 0.14.0 — 2026-10-19

- **Nuevo: `uydatos.verificar`**, el contrato de forma de las fuentes. Baja cada fuente, la lee
  entera con su propio lector y reporta filas, columnas, bytes y sha256; `--json` deja un informe
  comparable semana a semana. Trece fuentes se verifican sin parámetros (ANCAP, ventas, BCU, compras,
  elecciones, IBGE, INDEC, INIA, INUMET, límites, Parlamento, sanciones, URSEA) y ocho declaran qué
  parámetro les falta, con el motivo escrito: `ideuy` una dirección, `mides` un indicador,
  `observatorio` un slug, `salto_grande` una estación, `hojas` un archivo, `catalogo`/`rut`/`semanas`
  no leen una fuente. Un lector nuevo sin adaptador ni motivo se cae en el test, igual que en el
  manifiesto. Medido el 19/10: la corrida completa de las trece tarda más de siete minutos (INIA
  son 57 CSV y compras un ZIP), así que es un trabajo del lunes, no de cada commit.
- **Nuevo: `uydatos.revisiones.revisadas`**, la pregunta que faltaba: **qué filas que ya estaban
  cambiaron de valor**. Un archivo que crece se nota; uno que se reprocesa reescribe el pasado y el
  total no cambia. `desde_json` compara dos informes de `verificar` y dice qué fuente se rompió, cuál
  cambió de columnas y cuál cambió de tamaño (con umbral: `max(10 filas, 20%)`), y
  `python -m uydatos.revisiones desde-json datos/` compara los dos últimos informes de un directorio.
- **Nuevo: `uydatos.errores.DatosInvalidos`**, la base de los diecinueve rechazos del paquete: un
  consumidor atrapa el de cualquier fuente con un solo `except`, en vez de importar diecinueve
  clases. Sigue siendo `ValueError`, así que el código escrito contra la 0.13.0 no cambia.
- **Corregido: un RUT real estaba versionado.** El barrido de `git ls-files` con el validador del
  propio paquete encontró seis RUT con dígito verificador válido en archivos versionados; uno era el
  de una empresa sancionada, copiado del archivo del DSS a un doc y a una fixture. Se reemplazó por
  uno sintético y `tests/test_privacidad.py` ahora falla si vuelve a entrar uno, con una lista corta
  y explícita de los inventados —y sin publicar el número en el mensaje, que la guarda tampoco puede
  publicar lo que protege.
- `docs/2026-10-18-opp-medicion.md`: la OPP son 19 datasets y 18 tienen su último recurso de 2021 o
  antes (2012, 2016, 2017 y quince de 2021); queda escrita la decisión de no escribir el lector.
  Medido también que tres fichas declaran `metadata_modified` de 2022 con recursos de 2021.
- Link rot: medido, no es un problema de este catálogo (44 de 45 recursos responden `200` en dos
  muestras); no se agregó el censo.

## 0.13.0 — 2026-10-17

- **Nuevo: `uydatos.sanciones`**, las sanciones aplicadas a empresas por Defensa del Consumidor:
  1.528 resoluciones de 2017 a 2024, con RUT, razón social, motivo, fecha y monto. Trampas medidas: el
  recurso se llama «Sanciones aplicadas a empresas» y **no** como el archivo, así que el lector toma el
  único CSV del dataset; el `rut` viene **con relleno a la derecha** (1.443 de 1.528) y una fila tiene
  un RUT de 3 caracteres, que se cuenta en vez de arreglarse; la fecha es `d/m/AAAA` de ancho variable;
  `monto_ur` es entero y **0 es un cero medido**, no un nulo; y la única resolución de Salto no existe
  (todas son de Montevideo). El archivo tiene el **mismo sha256 que el 09/10** aunque el catálogo
  declare `metadata_modified` 2026-03-22: una fecha del catálogo no es una revisión.
- **Datos personales**: el lector devuelve `razon_social` y `rut` de personas jurídicas y, en algunos
  casos, de personas físicas. El archivo es público, pero el repositorio no publica esos datos y el
  README declara el límite.
- **Nuevo: `uydatos.fuentes`**, el manifiesto de las fuentes —una fila por lector, 21— y `deriva()`,
  que pregunta al catálogo **si el recurso se modificó después de la última medición**. No guarda
  URLs: pregunta cuál es el recurso vigente, que es la lección de la 0.12.1. Los ids de dataset se
  importan de la constante que cada módulo ya declara, así que no se escriben dos veces; `movido`
  significa «volver a medir», no «el dato cambió». `python -m uydatos.fuentes estado` es el comando
  del lunes, y el CI lo pega en el resumen del trabajo. `CADENCIA` marca las fuentes que se
  republican solas (INUMET, diaria): el aviso las distingue, porque uno que grita todas las semanas
  se ignora —y con él, las que sí importan.
- **Nuevo: `uydatos.revisiones`**, `comparar()` entre dos copias de la misma fuente: claves nuevas,
  borradas y cambiadas, filas sin clave, y un rechazo cuando el encabezado cambió («un cambio de
  columnas es otra fuente») o cuando la clave se repite. Sin dependencias y sin red.
- **`uydatos.catalogo` suma el mapa del catálogo**: `nombres()`, `todos()`, `faltantes()` y
  `formatos()`, con `--faltantes` y `--formatos` en la línea de comandos. Medido el 17/10: el endpoint
  de la lista trae **2.777** datasets y el buscador **2.716**, y los 61 que faltan son fichas
  `state=active` con **cero recursos** (visualizadores, apps, webservices), no datasets borrados. El
  facet de formatos cuenta datasets, no recursos: **2.553 de 2.716 (94%) declaran al menos un CSV**, y
  `res_format` tiene nueve formas de decir CSV.
- **Nuevo: `tests/test_trampas.py`**, las trampas declaradas reproducidas sobre archivos armados con
  `tmp_path` (dos BOM en ANCAP, la fila de error de INUMET, la estación fantasma, la respuesta mala del
  BCU, el XLSX con extensión `.xls`), más la mitad que faltaba: **el archivo válido tiene que pasar**.
  Un lector que rechaza todo pasa cualquier guarda de rechazo.
- CI: 3.14 en la matriz (esta máquina corre 3.14.7) y el estado de las fuentes en el resumen del
  trabajo del lunes.
- Docs nuevos: `docs/2026-10-17-oportunidades.md` (qué se toma de DBnomics, la API de series de
  Argentina, Frictionless, el análisis de mutación del *Fuzzing Book* y el estudio de link rot, y qué
  datos de Uruguay quedan por leer) y `docs/2026-10-17-mapa-del-catalogo.md`.
- **Docstring de `compras`**: los estados de 2025 son 3 `cancelled`, 5 `unsuccessful` y 8 `pending` (medido sobre el
  archivo de 2025), no 360 y 110. Sin cambio de comportamiento. El test de red de INUMET afirma un piso (el dataset crece
  todos los días) en vez de un conteo exacto.

## 0.12.1 — 2026-10-14

- **Arreglo: `ancap.descargar()` y `ancap_ventas.descargar()` ya no fallan con 404 cuando ANCAP
  republica.** El 12/10/26 ANCAP republicó sus dos datasets y el id de cada recurso cambió
  (`1a37fc4a` a `c486544e` en precios, `019414ce` a `e3699b01` en ventas): la URL fija dio 404 y la
  corrida semanal de `mcp-uruguay` falló. Ahora las dos preguntan al catálogo cuál es el CSV vigente
  (`url_vigente()`, por el nombre del archivo; cero o dos CSV se rechaza) y caen a `URL_CSV`, ya
  actualizada, solo si el catálogo no responde. Con una `url` explícita no consultan nada.
  **Quien tenga instalada la 0.12.0 sigue con la URL vieja hasta que actualice.**

## 0.12.0 — 2026-10-11

- **`uydatos.parlamento` suma los pedidos de informes de Diputados y la nómina**: `leer_pedidos`,
  `leer_nomina`, `identificar` y `resumen_pedidos`. Los pedidos (artículo 118 de la Constitución)
  vienen uno por uno, con organismo, autores, tema, estado y los enlaces al oficio y la respuesta:
  2.532 en la legislatura 50. Trampas medidas: la metadata dice dos estados y hay cuatro; «SIN
  CONTESTAR» incluye 115 pedidos con más de 45 días que no figuran como vencidos; no hay fecha de
  respuesta; los coautores van separados por `+` y la metadata lo deja trunco; 242 contestados sin
  enlace a la respuesta; y **la tasa de respuesta cae con la antigüedad** (92,5% de los pedidos del
  primer semestre de 2025, 31,9% de los del segundo de 2026), así que la comparación entre
  organismos se hace por cohorte (`presentados_hasta`) y sobre los pedidos con el plazo cumplido.
  La nómina identifica a 131 de 133 autores sin ambigüedad; **la edad no se lee**.
- `python -m uydatos.parlamento bajar` acepta los datasets de un solo archivo sin legislatura.

## 0.11.0 — 2026-10-11

- **Nuevo: `uydatos.ursea`**, el precio de paridad de importación (PPI) de los combustibles que
  calcula URSEA, su desglose desde el FOB en USD/m³, y el precio ex planta de ANCAP, con
  `comparar()`: **¿ANCAP vende por encima o por debajo de lo que costaría importar?** Se compara sin
  impuestos contra sin impuestos (el ex planta de ANCAP ya los descuenta) y con la mezcla de
  agrocombustibles; el PPI de la ventana que cierra el 25 rige el mes siguiente. Trampas medidas: el
  recurso «PPI al consumidor final 2002-2020» es idéntico byte a byte al de componentes (la serie
  histórica se perdió del catálogo); tres modelos de PPI que no se empalman; una ventana que termina
  antes de empezar (se descarta, no se corrige); la vigencia publicada repite el mes en 2 de 355
  filas; `FuelP_ExP` es con impuestos aunque su nombre diga lo contrario; el GLP viene en $/l en un
  archivo y en $/kg en el otro; el ex planta de ANCAP es un registro acumulado de 19.105 filas para
  1.204 pares, con tres formatos de fecha (`202,608` incluido) y 93 pares contradictorios, todos de
  gases. Medido: de 2022 a 2026 la Súper 95 y el Gasoil 50-S quedan en promedio a −1,4% y −0,8% de
  la paridad, con abril de 2026 en −10% y −31%.

## 0.10.0 — 2026-10-11

- **Nuevo: `uydatos.observatorio`**, los indicadores sociales del MIDES leídos de su página viva en
  gub.uy, con la ficha (unidad, fuente, forma de cálculo, período). **Por qué no alcanzaba
  `uydatos.mides`: la copia del catálogo quedó congelada en 2019** —medido sobre 60 indicadores: los
  57 legibles tienen `metadata_modified` de 2019, su último dato es de 2011 a 2017, y el único que
  llega a 2025 es una proyección; 3 no tienen recursos—, mientras la página viva llega a 2024. La
  lista sale del sitemap (1.264 indicadores). Trampas medidas sobre 159 páginas: la tabla está
  siempre y el gráfico no; las páginas de formato viejo usan punto decimal y una tenía la tabla
  desordenada, así que **se rechazan**; `-` y `.` son «sin dato»; una dimensión puede no tener
  filtro y aparecer entre las opciones de años; hay celdas con basura (`@`, `HOJA127b`) que hacen
  rechazar la página; 2 tablas traen columnas sin encabezado llenas de ceros; las filas «Total» van
  mezcladas (103 de 150); los mapas por departamento muestran un solo año (se marca `parcial`); la
  ficha dice otro año de fin que la tabla en 20 de 150. Lee 150 de 159.

## 0.9.0 — 2026-10-10

- **Nuevo: `uydatos.ancap_ventas`**, la cantidad de ventas de combustibles por mercado, producto y
  mes: el **denominador de mercado** que le faltaba a `uydatos.ancap`, que trae los precios. Trampas
  medidas sobre el archivo de 1.200 filas: la columna `Unidad` **mezcla miles de m³ con toneladas**
  (1.178 y 22 filas, las de toneladas son los combustibles sólidos del mercado interno), así que
  `serie_mensual()` pide la unidad y `resumen()` las suma aparte; el archivo es una **ventana móvil de
  cinco años** y los huecos no son sólo el año en curso (2024 sin octubre, 2025 sin agosto a
  octubre); `QUEROSENO` y `QUEROSENOS` parecen el error de tipeo del otro y son de familias distintas;
  hay 6 correcciones negativas que se leen y se suman.
- `mcp-uruguay` 0.8.0 mueve su pin a `>=0.9,<0.10` y usa `ancap_ventas` en la herramienta
  `ventas_combustible`: con el pin viejo el servidor resolvía la 0.8.0, que no trae el módulo.
- **La ECH del INE no es alcanzable desde el catálogo.** Sus siete datasets declaran 25 recursos
  contra `www.ine.gub.uy`, y **los 25 devuelven HTML** —la portada del sitio nuevo, con el `uuid`
  conservado como consulta—, no un archivo (medido el 10/10/26). No es un certificado roto ni un host
  caído: es link rot, y el `formato` declarado miente. Queda la guarda
  `test_los_recursos_de_la_ech_no_bajan_un_archivo` (marcada `red`), que falla el día que alguno
  vuelva a entregar un archivo.
- El docstring de `uydatos.compras` numeraba su lista `1, 2, 3, 8, 4, 5, 6, 7`. Ahora va en orden.

## 0.8.0 — 2026-10-10

- **Nuevo: `uydatos.parlamento`**: asistencias del Senado y de Diputados por legislatura (46 a 50),
  proyectos entrados (42 a 50, desde 1985) y leyes promulgadas. Trampas medidas: todos los recursos
  terminan en la URL `csv` (la legislatura sale del título); hay 3 a 4 veces más personas que bancas,
  por los suplentes, así que `resumen_asistencias` exige un mínimo de citaciones; no hay identificador
  de persona y los homónimos no se unen; hay filas sin nombre; 311 proyectos están en dos
  legislaturas; las leyes traen 2 filas duplicadas y una «ley 0», y la fecha del catálogo no dice de
  cuándo es el dato. Se exige que citaciones = asistencias + faltas, que se cumple en las 10
  legislaturas.

## 0.7.0 — 2026-10-10

- **Nuevo: `uydatos.compras`**, las adjudicaciones del Estado (ARCE, OCDS 1.1) desde 2002: organismo,
  ítems, cantidad, precio y moneda, con totales por moneda y `convertir()` a pesos con la cotización
  del día. Trampas medidas sobre 2024 y 2025: el catálogo lo declara JSON y es un ZIP cuya estructura
  cambia entre años; el total es cantidad × precio; hay llamados y anulaciones mezclados con las
  adjudicaciones (las anulaciones no apuntan a ninguna adjudicación publicada); solo las `active`
  son gasto; hay adjudicaciones sin comprador o sin proveedor. Y la más importante: **el total del año
  está dominado por registros imposibles** —un ítem es el 77% de lo adjudicado en pesos en 2024, otro
  el 53% en 2025—, así que `resumen()` devuelve siempre los mayores ítems con su peso y su `ocid`.
- `uydatos.bcu` suma euro (1111), franco suizo (5900) y rand (1620).
- **Nuevo: `uydatos.hojas`**, para leer planillas XLSX y XLS. El motor se elige por **la firma del
  archivo** y no por el `formato` que declara el catálogo, que miente: de 24 recursos declarados
  `XLS`, **23 son en realidad XLSX** y el único `.xls` de verdad de la muestra es el de AGESIC.
  openpyxl tiene sus propias dos trampas —se fía de la extensión, y en modo `read_only` informa 1×1
  cuando la hoja no declara su dimensión— y las dos quedan sorteadas. Las dependencias son
  **opcionales** (`pip install uydatos[hojas]`), así que el paquete base sigue sin ninguna: sin el
  extra, la suite saltea el módulo en vez de fallar.
- **`docs/2026-10-10-hojas-medicion.md`**: la medición de las planillas del catálogo, con lo que sí
  se puede bajar y lo que no (los `.xls` de la ECH del INE viven en el sitio viejo del INE, con el
  certificado roto, así que leer `.xls` no la destraba por sí solo).
- **Corregido en el README**: `uydatos.mides` no estaba en la tabla de módulos.

## 0.6.0 — 2026-10-10

- **Corregido: las mesas de observados se reconocían por la serie `?ZZ`**, medida solo en 2024. En
  Montevideo 2025 la serie es `A1` o `A2`, así que esas mesas se contaban como comunes (los totales no
  cambiaban; la clasificación y el filtro sí). Ahora se reconocen por **0 habilitados y 0 emitidos**,
  verificado en las tres elecciones: 118, 114 y 199 mesas, con lo declarado y lo escrutado a menos de
  0,72%.
- **Cambia la API de `votos_por_lema`**: `incluir_observados` se reemplaza por
  `excluir=mesas_de_observados(totales)`, porque el desglose no trae habilitados ni emitidos.

## 0.5.0 — 2026-10-10

- **Nuevo: `uydatos.elecciones`**, los resultados de la Corte Electoral por mesa: totales, votos
  por partido (hoja + lema) y plan circuital, de las nacionales 2024, el balotaje 2024 y las
  departamentales 2025. Trampas medidas: los observados se escrutan en **mesas especiales** (serie
  `?ZZ`, 0 habilitados y 0 emitidos) y no tienen localidad; los nombres de columnas, partidos y
  tipos de circuito cambian entre elecciones; el departamento viene en un código propio; la columna
  del local termina en espacio. **No lee la integración de las hojas**, que trae la credencial
  cívica de cada candidato.
- **`docs/2026-10-10-datos-civicos.md`**: el análisis de los datos cívicos —elecciones, Parlamento,
  compras del Estado— con las trampas y los datos personales de cada uno.

## 0.4.0 — 2026-10-10

- **Nuevo: `uydatos.limites`**: los límites del INE —departamentos (vía la IDE) y las 652
  localidades (vía el MIDES), con población y viviendas en los campos `pob_tot_23`/`viv_tot_23`— y
  en cuál cae un punto (`ubicar`, `mas_cercana`), sin dependencias de geometría. Trampas medidas el
  10/10/2026: la capa trae **20 polígonos de departamentos**, uno es el **«LIMITE CONTESTADO»** con
  Brasil y lleva el código y el ISO de Artigas; sin `srsName=EPSG:4326` llega en metros (UTM 21S) y
  ningún punto en grados cae adentro; un error del WFS llega en XML con HTTP 200.
- **`ideuy.inversa()`**: las direcciones más cercanas a un punto, ordenadas y con su distancia.
  `reverse` devuelve la más cercana **esté donde esté** (un punto en el mar dio una calle de
  Maldonado a 190 km), no respeta `limit` y `rutakm` devuelve lat/lng 0,0 con `state: 1`: esas
  respuestas se descartan.
- **Corregido: `catalogo.buscar(formato=...)` daba 0 para `geojson`.** El filtro de CKAN distingue
  mayúsculas y el catálogo publica «GeoJSON» (21 recursos), no «GEOJSON». Ahora busca todas las
  variantes que existen (`variantes_de_formato`).

## 0.3.0 — 2026-10-10

- **Nuevo en `uydatos.salto_grande`: las lecturas** (`DatosHidrometeorologicos`) de altura, lluvia
  y caudal cada 15 minutos, con `tramos()`, `resumen_diario()` y `cobertura()`. Trampas medidas el
  10/10/2026: `-999` es sin dato, una fecha en otro formato devuelve cero lecturas sin error,
  `fechaHasta` es las 00:00 y no el día entero, más de 31 días es un SOAP Fault y hay huecos.

- **Nuevo: `uydatos.inumet`**, las observaciones meteorológicas horarias de INUMET en siete
  estaciones del país (temperatura, precipitación puntual, humedad, viento, presión y
  insolación). Rechaza la fila cuyo `estacion_id` trae el texto de un error del servidor
  (`' please try again later.'`, medido en los dos archivos completos) y no agrega un día local
  al que le falte una observación. Ver `docs/2026-10-09-fuentes-candidatas.md`.
- **La cadencia por variable está declarada y medida** (`OBS_POR_DIA`): temperatura, precipitación,
  humedad y presión son horarias, **el viento publica 12 por día** y la insolación es diaria.
  Medir el viento contra 24 horas dejaba todos sus días en `None`.
- **`resumen()` declara los extremos por columna.** El metadato de insolación dice «horas de brillo
  del Sol» y el archivo trae **4 valores por encima de 24 de 3.437** (Salto 63,2; Artigas 38,0;
  Mercedes 37,6; Colonia 33,2), tres el 01/08/2026. No se corrigen ni se descartan: `heliofania`
  no lleva rango a propósito, porque un (0, 24) rechazaría el archivo entero.
- **Nuevo: `uydatos.mides`**, el lector de familia de los **1.869 indicadores de MIDES** —el 69% del
  catálogo—. La forma es una sola: cero o más columnas de dimensión de **nombre libre**, y siempre
  `año` y `valor` al final, en ese orden (49 de 49 en una muestra de 50; 25 archivos enteros sin una
  sola fila torcida ni una celda vacía). No hace falta declarar columnas por indicador. La trampa
  es la codificación: los CSV vienen en **cp1252**, y leerlos como UTF-8 no falla, convierte `año` en
  `aÃ±o` — el lector rechaza el encabezado que no cierra en `año, valor`, que es el detector.
  Ver `docs/2026-10-09-mides-medicion.md`.
- **Nuevo: `uydatos.red`**, la única salida a la red del paquete: User-Agent propio, timeout y
  tres reintentos (un 4xx no se reintenta). Los siete lectores pasan por ahí; el BCU era el único
  que no mandaba User-Agent.
- **Nuevo: `uydatos.procedencia`**, el sello de un número: fuente, fecha de la copia, sha256, bytes y
  filas. Una ruta que no existe se rechaza.
- **`uydatos.catalogo`**: `buscar()` por texto, organización y formato, con el conteo total y los
  facets; `datastore_search()` para consultar filas sin bajar el archivo; `accion()` para el resto
  de la API de CKAN.
- **`python -m uydatos <lector>`**: los subcomandos de todos los lectores en un solo lugar.
- Guía de contribución (`CONTRIBUTING.md`), plantilla para escribir un lector nuevo y documentos de
  medición de fuentes candidatas en `docs/`.

## 0.2.1 — 2026-10-09

- Publicado en PyPI: `pip install uydatos`. Se publica solo al crear una Release en GitHub, con
  trusted publishing (sin tokens).
- Marcado como paquete tipado (`py.typed`), con clasificadores y palabras clave.
- Insignias y un resumen en inglés en el README.

## 0.2.0 — 2026-10-09

- **Nuevo: `uydatos.ideuy`**, geocodificación de direcciones uruguayas con la API pública de IDE.uy.
  Cada resultado lleva su calidad (`puerta_exacta`, `puerta_aproximada`, `esquina`,
  `calle_sin_numero`) y descarta lo que la API devuelve sin haberlo encontrado:
  - el centro de la localidad;
  - **otra calle**: una calle inexistente devolvió "CALLE N 2570" con el mismo aviso que una
    puerta ajustada;
  - las respuestas de texto libre que no son una esquina.
- Las esquinas se piden a v1 como `ESQ` (con `Y` no las reconoce) y en los dos órdenes de
  calles, porque v1 depende del orden. Si v1 no responde, se conserva el resultado de v0.
- CI: tests en Python 3.10 a 3.13 y Windows, y una corrida semanal contra las fuentes reales.

## 0.1.0 — 2026-10-09

Primera versión: BCU, ANCAP, INIA, Salto Grande, INDEC, IBGE, RUT y cédula, semanas ISO y el
catálogo de datos abiertos de Uruguay.
