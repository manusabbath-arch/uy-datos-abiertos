"""uydatos — lectores estrictos de datos públicos de Uruguay y la región.

Cada módulo lee una fuente y **rechaza en vez de arreglar**: una respuesta mala, una columna
cambiada o un hueco en la serie levantan una excepción con el motivo, en lugar de devolver una
serie creíble pero falsa. La única función de cada módulo que sale a internet se llama
`descargar*()`; todo lo demás trabaja sobre archivos en disco.

Módulos:

- `compras`      — compras del Estado (ARCE, OCDS): adjudicaciones, importes por moneda y concentración.
- `elecciones`   — resultados de la Corte Electoral por mesa, con las mesas de observados aparte.
- `bcu`          — cotizaciones del Banco Central del Uruguay (dólar, UI, peso argentino, real).
- `ancap`        — precios máximos de combustibles fijados por el Poder Ejecutivo.
- `ancap_ventas` — cantidad de ventas de combustibles por mercado, producto y mes.
- `inia`         — clima diario de INIA Salto Grande, con normales y anomalías.
- `salto_grande` — estaciones hidrometeorológicas de la CTM de Salto Grande.
- `inumet`       — observaciones meteorológicas horarias de INUMET, en siete estaciones.
- `indec`        — IPC nacional de Argentina (API de series de datos.gob.ar).
- `ibge`         — IPCA de Brasil (API SIDRA del IBGE).
- `ideuy`        — geocodificación de direcciones uruguayas con IDE.uy, directa e inversa.
- `limites`      — departamentos y localidades del INE (con población 2023), y en cuál cae un punto.
- `rut`          — dígito verificador de RUT y cédula uruguaya.
- `semanas`      — semanas ISO 8601 (W1, W2...) con los bordes de año resueltos.
- `catalogo`     — recursos del catálogo de datos abiertos de Uruguay (CKAN).
- `ursea`        — precio de paridad de importación de los combustibles, y su comparación con ANCAP.
- `parlamento`   — asistencias de las dos cámaras, proyectos desde 1985 y leyes promulgadas.
- `mides`        — la familia de indicadores de MIDES, todos con la misma forma (copia de 2019).
- `observatorio` — los indicadores del Observatorio Social del MIDES, de su página viva en gub.uy.
- `hojas`        — hojas de cálculo XLSX y XLS, con el motor elegido por la firma del archivo.
- `sanciones`    — sanciones a empresas de Defensa del Consumidor, con su límite de datos personales.
- `fuentes`      — el manifiesto de las fuentes y si alguna se movió desde la última medición.
- `revisiones`   — qué cambió entre dos copias de una fuente, y si el cambio es de dominio.
- `verificar`    — el contrato de forma de las fuentes: filas, columnas y sha256, semana a semana.
- `errores`      — la base común de los rechazos: `DatosInvalidos`, que atrapa a los diecinueve.
"""

__version__ = "0.15.1"

USER_AGENT = f"uydatos/{__version__} (lectura de datos abiertos)"
