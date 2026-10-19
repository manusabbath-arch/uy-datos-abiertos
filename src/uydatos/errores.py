"""La base de los rechazos del paquete.

Cada lector levanta su propia clase (`AncapInvalido`, `InumetInvalido`, ...) porque el mensaje es del
dominio: dice qué columna, qué fila y qué valor se midió. Pero todas heredan de `DatosInvalidos`, así
que un consumidor —`mcp-uruguay`, una planilla, un `except` en un script— atrapa el rechazo de
cualquier fuente con un solo tipo, y no tiene que importar diecinueve ni actualizar el `except` cada
vez que el paquete suma un lector.

Hereda de `ValueError` a propósito: el paquete rechazaba con `ValueError` desde la 0.1.0, y un
`except ValueError` escrito contra la 0.13.0 sigue funcionando.
"""

from __future__ import annotations


class DatosInvalidos(ValueError):
    """La fuente no dice lo que el lector exige. El mensaje dice qué, dónde y el valor medido."""
