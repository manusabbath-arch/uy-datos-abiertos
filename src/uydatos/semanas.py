"""Semanas ISO 8601 con etiqueta corta: `W41` en vez de "la semana del 05/10 al 11/10".

La convención
-------------
- **Semana ISO 8601**: de **lunes a domingo**; la W1 de un año es la que contiene su primer jueves.
  Es la de `date.isocalendar()` y la de `ISOWEEKNUM` en Excel y Google Sheets.
- Etiqueta corta **`W41`** (sin cero adelante) dentro de un mismo año; **`2026-W41`** cuando se
  cruzan años o se guarda en un archivo. Para personas, `W41 (05/10–11/10)`.
- **El año de la semana no es siempre el del día**: el 01/01/2027 es la `2026-W53` y el 29/12/2025
  es la `2026-W01`. Por eso una etiqueta sin año no se convierte en fechas
  (`Semana.desde_texto("W41")` falla).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, order=True)
class Semana:
    anio: int  # año ISO, no el del calendario
    numero: int

    @property
    def desde(self) -> date:
        return date.fromisocalendar(self.anio, self.numero, 1)

    @property
    def hasta(self) -> date:
        return self.desde + timedelta(days=6)

    def anterior(self, n: int = 1) -> "Semana":
        return semana_de(self.desde - timedelta(days=7 * n))

    def siguiente(self, n: int = 1) -> "Semana":
        return semana_de(self.desde + timedelta(days=7 * n))

    @property
    def corta(self) -> str:
        return f"W{self.numero}"

    @property
    def de_total(self) -> str:
        """`W41/53`: la semana sobre las semanas ISO del año (52 o 53)."""
        return f"{self.corta}/{semanas_del_anio(self.anio)}"

    def con_dias(self) -> str:
        return f"{self.corta} ({self.desde:%d/%m}–{self.hasta:%d/%m})"

    def __str__(self) -> str:
        return f"{self.anio}-W{self.numero:02d}"

    @classmethod
    def desde_texto(cls, texto: str) -> "Semana":
        m = re.fullmatch(r"(\d{4})-W(\d{1,2})", texto.strip())
        if not m:
            raise ValueError(f"{texto!r}: se espera AAAA-Wnn (una semana sin año es ambigua)")
        s = cls(int(m[1]), int(m[2]))
        _ = s.desde  # valida que la semana exista (W53 solo en algunos años)
        return s


def semanas_del_anio(anio: int) -> int:
    """52 o 53: el 28 de diciembre cae siempre en la última semana ISO del año."""
    return date(anio, 12, 28).isocalendar()[1]


def semana_de(dia: date) -> Semana:
    iso = dia.isocalendar()
    return Semana(iso[0], iso[1])


def etiqueta(dia: date, con_anio: bool = False) -> str:
    s = semana_de(dia)
    return str(s) if con_anio else s.corta


def etiqueta_con_dias(dia: date) -> str:
    return semana_de(dia).con_dias()


def semanas_entre(desde: date, hasta: date) -> list[Semana]:
    """Las semanas que tocan el intervalo, en orden (incluye las incompletas de los bordes)."""
    out, s = [], semana_de(desde)
    while s.desde <= hasta:
        out.append(s)
        s = s.siguiente()
    return out
