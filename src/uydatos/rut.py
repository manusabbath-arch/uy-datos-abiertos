"""Dígito verificador de RUT y cédula de identidad uruguaya, sin salir a la red.

La validez **aritmética** no es la validez **ante DGI**: un RUT puede tener el dígito
verificador correcto y no estar inscripto. Esto solo descarta los que no pueden existir.

Dos trampas que cualquiera vuelve a pisar al leer planillas
-----------------------------------------------------------
1. **Excel entrega el RUT como `float`.** `12345678919.0` no se limpia borrando los
   separadores: eso produce `123456789190` — los dígitos corridos un lugar y un cero inventado
   al final. El valor real es `012345678919`, doce dígitos con el cero inicial que Excel se
   comió. `normalizar()` convierte el float a entero **antes** de rellenar a la izquierda.
2. **La coma puede ser separador de miles** (`'1,234,567-2'` en una cédula). Una limpieza que no
   la contemple deja la cédula como "no numérica".

Algoritmos
----------
- **RUT** (12 dígitos): pesos 4,3,2,9,8,7,6,5,4,3,2 sobre los primeros 11, módulo 11.
  dv = 11 - resto; 11 → 0; 10 → no existe RUT válido con ese resto.
- **Cédula** (8 dígitos): pesos 2,9,8,7,6,3,4 sobre los primeros 7, cada producto módulo 10,
  se suman, módulo 10; dv = (t - 10) * -1 módulo 10.

Sobre el prefijo: documentación de facturación electrónica de terceros exige que las
posiciones 1-2 estén entre 01 y 21. Hay RUT reales que empiezan en 22 y validan (sociedades
por acciones simplificadas, posteriores a esa documentación), así que el rango **no** se usa
para invalidar. Tampoco se invalida por las posiciones 9-10 distintas de `00`: se informa
aparte como `dv_ok_estructura_rara`.
"""

from __future__ import annotations

import re
from typing import Optional

PESOS_RUT = (4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_CI = (2, 9, 8, 7, 6, 3, 4)

# Separadores de presentación. La coma está a propósito: separador de miles, no decimal.
_SEPARADORES = re.compile(r"[.,\-/\s]")


def dv_rut(primeros_once: str) -> int:
    """Dígito verificador de un RUT. Devuelve -1 si no existe RUT válido con esos 11 dígitos."""
    suma = sum(int(c) * p for c, p in zip(primeros_once, PESOS_RUT))
    resto = 11 - (suma % 11)
    if resto == 11:
        return 0
    if resto == 10:
        return -1
    return resto


def dv_ci(primeros_siete: str) -> int:
    """Dígito verificador de una cédula de identidad."""
    total = sum((int(c) * p) % 10 for c, p in zip(primeros_siete, PESOS_CI)) % 10
    return ((total - 10) * -1) % 10


def texto_crudo(valor: object) -> str:
    """Texto del valor sin inventar ni perder dígitos.

    Un `float` entero se convierte por `int()`, no por `str()`: `str(1.0)` da `'1.0'`, y el
    `.0` se vuelve un dígito de más apenas alguien borra el punto como si fuera un separador.
    """
    if valor is None:
        return ""
    if isinstance(valor, float):
        return str(int(valor)) if valor == int(valor) else repr(valor)
    return str(valor).strip()


def normalizar(valor: object, ancho: int) -> tuple[Optional[str], Optional[str]]:
    """Devuelve `(digitos_rellenados, None)` o `(None, motivo)`."""
    texto = texto_crudo(valor).upper()
    if not texto or texto == "0":
        return None, "vacio_o_cero"
    if "E" in texto:
        return None, "notacion_cientifica"
    digitos = _SEPARADORES.sub("", texto)
    if not digitos.isdigit():
        return None, "no_numerico"
    if len(digitos) > ancho:
        return None, f"mas_de_{ancho}_digitos"
    return digitos.zfill(ancho), None


def validar_rut(valor: object) -> tuple[str, Optional[str]]:
    """`(estado, digitos)`. Estados: `valido`, `dv_ok_estructura_rara`, `dv_no_valida` o el
    motivo de `normalizar()` (`vacio_o_cero`, `notacion_cientifica`, `no_numerico`, ...)."""
    digitos, motivo = normalizar(valor, 12)
    if motivo or digitos is None:
        return motivo or "vacio_o_cero", None
    if dv_rut(digitos[:11]) != int(digitos[11]):
        return "dv_no_valida", digitos
    if digitos[8:10] != "00":
        return "dv_ok_estructura_rara", digitos
    return "valido", digitos


def validar_ci(valor: object) -> tuple[str, Optional[str]]:
    """`(estado, digitos)`. Estados: `valido`, `dv_no_valida` o el motivo de `normalizar()`."""
    digitos, motivo = normalizar(valor, 8)
    if motivo or digitos is None:
        return motivo or "vacio_o_cero", None
    if dv_ci(digitos[:7]) != int(digitos[7]):
        return "dv_no_valida", digitos
    return "valido", digitos


def es_rut_valido(valor: object) -> bool:
    return validar_rut(valor)[0] in ("valido", "dv_ok_estructura_rara")


def es_ci_valida(valor: object) -> bool:
    return validar_ci(valor)[0] == "valido"
