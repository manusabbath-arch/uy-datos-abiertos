"""uydatos — lectores estrictos de datos públicos de Uruguay y la región.

Cada módulo lee una fuente y **rechaza en vez de arreglar**: una respuesta mala, una columna
cambiada o un hueco en la serie levantan una excepción con el motivo, en lugar de devolver una
serie creíble pero falsa. La única función de cada módulo que sale a internet se llama
`descargar*()`; todo lo demás trabaja sobre archivos en disco.

Módulos:

- `elecciones`   — resultados de la Corte Electoral por mesa, con las mesas de observados aparte.
- `bcu`          — cotizaciones del Banco Central del Uruguay (dólar, UI, peso argentino, real).
- `ancap`        — precios máximos de combustibles fijados por el Poder Ejecutivo.
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
"""

__version__ = "0.5.0"

USER_AGENT = f"uydatos/{__version__} (lectura de datos abiertos)"
