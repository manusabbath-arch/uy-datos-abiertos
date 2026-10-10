# Cambios

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
