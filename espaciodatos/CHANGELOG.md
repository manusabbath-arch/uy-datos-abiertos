# Cambios

## Sin publicar

- **`vigilancia`**: qué cambió entre dos copias de Sentry y de la ESA (nuevos, salidos con su
  fecha de retiro, Palermo, Torino, y los objetos que las agencias movieron en direcciones
  opuestas), con un informe en Markdown: `python -m espaciodatos vigilar antes/ despues/`.
  Medido con dos copias a 31 minutos: 2026 VX1 subió en JPL (−7,27 → −7,05) y bajó en la ESA
  (−6,72 → −9,09).
- **`clima`**: Kp, escalas G/R/S y alertas de NOAA SWPC, con seis trampas medidas; la principal,
  que la tormenta G1 empieza en Kp 4,67 y un umbral de 5 pierde 3 de 6 franjas.
- **`herramientas`**: seis preguntas como funciones que devuelven `{"datos", "advertencias",
  "procedencia"}` en JSON, con su registro para un servidor MCP, y `actualizar()` como la única
  que sale a la red.
- `designacion.clave` acepta un numerado como entero (`99942`), y el sello de los retirados de
  Sentry dice "(retirados)" y lleva su URL: los dos aparecieron al correr las herramientas
  contra las fuentes reales.

## 0.1.0 — 2026-11-06

- Primera versión: `cad`, `sentry`, `bolidos`, `esa`, `cruce` y `designacion`, medidos el
  2026-11-06 contra las fuentes reales (`docs/2026-11-06-neo-medicion.md`): 20 trampas, cada
  una con su número, y el cruce JPL contra ESA.
- Depende sólo de `uydatos>=0.17` (red, procedencia y la base de los rechazos).
