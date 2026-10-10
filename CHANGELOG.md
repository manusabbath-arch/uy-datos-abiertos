# Cambios

## 0.3.0 — sin publicar

- **Nuevo: `uydatos.inumet`**, las observaciones meteorológicas horarias de INUMET en siete
  estaciones del país (temperatura, precipitación puntual, humedad, viento, presión y
  insolación). Rechaza la fila cuyo `estacion_id` trae el texto de un error del servidor
  (`' please try again later.'`, medido en los dos archivos completos) y no agrega un día local
  al que le falte una hora. Ver `docs/2026-10-09-fuentes-candidatas.md`.
- La versión sube a 0.3.0 y **`mcp-uruguay` tiene el pin `uydatos>=0.2.1,<0.3`**: hay que moverlo
  antes de publicar esta versión, o el servidor MCP no la va a poder usar.

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
