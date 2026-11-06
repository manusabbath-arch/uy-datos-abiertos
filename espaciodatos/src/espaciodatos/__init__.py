"""espaciodatos — lectores estrictos de datos abiertos del espacio cercano.

El paquete hermano de `uydatos`, con la misma regla: **rechazar en vez de arreglar**. Usa su
infraestructura (`uydatos.red` para salir a internet, `uydatos.procedencia` para el sello y
`uydatos.errores.DatosInvalidos` como base de los rechazos) y no agrega dependencias.

Módulos:

- `cad`         — acercamientos a la Tierra (JPL SBDB Close Approach Data API).
- `sentry`      — la lista de riesgo de impacto de JPL (Sentry), los objetos retirados y el estado
                  de un objeto.
- `bolidos`     — bólidos registrados por sensores del gobierno de EE.UU. (CNEOS Fireball API).
- `esa`         — la lista de riesgo de la ESA (NEOCC), en texto de ancho fijo.
- `cruce`       — dónde no coinciden la lista de JPL y la de la ESA.
- `designacion` — una sola clave para el mismo objeto escrito de cuatro formas.

Lo medido está en `docs/2026-11-06-neo-medicion.md`.
"""

from __future__ import annotations

__version__ = "0.1.0"

USER_AGENT = f"espaciodatos/{__version__} (lectura de datos abiertos)"
