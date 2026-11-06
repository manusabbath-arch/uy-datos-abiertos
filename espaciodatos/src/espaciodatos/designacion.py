"""Una sola clave para el mismo objeto, escrito de cuatro formas por las dos agencias.

Medido el 2026-11-06:

- **JPL** usa en `des` el número si el objeto está numerado (`"443104"`) y si no la designación
  provisional **con espacio** (`"2008 JL3"`). El `fullname` agrega paréntesis y, en CAD,
  **espacios a la izquierda** para alinear columnas (49.015 de 52.247 filas): `"       (2014 SC324)"`.
- **La ESA** escribe la provisional **sin espacio** (`"2008JL3"`) y un numerado como el número,
  espacios y la provisional pegada: `"443104               2013XK22"` (1 de 2.205 filas).
- Comparar las dos listas por el texto da **0 coincidencias**; con la clave de acá, 1.974.

- **La lista de retirados de Sentry trae otras dos formas** (3 de 3.596): cometas (`P/2005 JQ5`,
  `P/2003 KV2`) y una designación del relevamiento Palomar-Leiden (`6344 P-L`). Esta última es la
  peligrosa: un "número y lo que siga" la lee como el asteroide **6344**, que es otro objeto, y
  no da error. Las dos formas se reconocen explícitamente y se devuelven como vienen.

La clave es la de JPL: el número si lo hay, si no la provisional con un espacio; cometas y
relevamientos, tal cual. Lo que no tiene ninguna forma medida se rechaza: no se adivina.
"""

from __future__ import annotations

import re

from uydatos.errores import DatosInvalidos


class DesignacionInvalida(DatosInvalidos):
    """El texto no tiene ninguna de las formas de designación medidas."""


# 2008 JL3, 2008JL3, 1979 XB, 2012 BA102: año, dos letras y un número opcional
_PROVISIONAL = re.compile(r"^(\d{4})\s*([A-Z]{2})(\d*)$")
# 6344 P-L, 2040 T-1: relevamientos Palomar-Leiden y Trojan; NO son el numerado 6344
_RELEVAMIENTO = re.compile(r"^(\d{4}) (P-L|T-[123])$")
# P/2005 JQ5, C/2020 F3: cometas con designación provisional
_COMETA = re.compile(r"^[PCDXI]/\d{4} [A-Z]{1,2}\d*(?:-[A-Z])?$")
# 443104, 443104 2013XK22 (ESA), 443104 (2013 XK22) (JPL fullname), 101955 Bennu (1999 RQ36)
_NUMERADO = re.compile(r"^(\d+)(?:\s+(?:[A-Z][a-z][\w' -]*|\d{4}\s*[A-Z]{2}\d*)?\s*(?:\(\d{4} [A-Z]{2}\d*\))?)?$")


def clave(texto: str) -> str:
    """La clave de JPL para `texto`: `"443104"` o `"2008 JL3"` (y cometas o relevamientos tal
    cual: `"P/2005 JQ5"`, `"6344 P-L"`). Levanta si no reconoce la forma."""
    t = re.sub(r"\s+", " ", texto.strip())
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    m = _PROVISIONAL.match(t)
    if m:
        return f"{m.group(1)} {m.group(2)}{m.group(3)}"
    if _RELEVAMIENTO.match(t) or _COMETA.match(t):
        return t
    m = _NUMERADO.match(t)
    if m:
        return str(int(m.group(1)))
    raise DesignacionInvalida(
        f"{texto!r}: no es una designación provisional (2008 JL3) ni un numerado (443104 …); no se adivina"
    )


def provisional(texto: str) -> str | None:
    """La designación provisional que trae un texto con número y paréntesis, o `None`.

    `"443104 (2013 XK22)"` → `"2013 XK22"`; `"443104               2013XK22"` → `"2013 XK22"`.
    Sirve para encontrar un objeto que una agencia ya numeró y la otra todavía no. Un cometa o un
    relevamiento no tienen provisional de asteroide: `None`."""
    t = texto.strip()
    if _COMETA.match(t) or _RELEVAMIENTO.match(t):
        return None
    for parte in re.findall(r"\d{4}\s*[A-Z]{2}\d*", texto):
        return clave(parte)
    return None
