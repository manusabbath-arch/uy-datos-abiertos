"""Feriados nacionales de Uruguay y días hábiles, calculados sin red a partir de la ley.

Las normas (texto vigente en IMPO, leído el 2026-11-27)
------------------------------------------------------
- **Decreto-Ley 14.977** (1979), arts. 1 y 2: la lista. 1 y 6 de enero; lunes y martes de Carnaval;
  la Semana de Turismo («la sexta semana siguiente a la de Carnaval»); 19 de abril; 1 y 18 de mayo;
  19 de junio; 18 de julio; 25 de agosto; 12 de octubre; 2 de noviembre; 25 de diciembre.
- **Ley 12.590**, art. 18: cinco de ellos son **pagos** (1/1, 1/5, 18/7, 25/8 y 25/12). El resto son
  feriados **laborables**: la actividad puede seguir.
- **Ley 16.805**, art. 1, con el art. 2 en la redacción de la **Ley 17.414** (08/11/2001): un feriado
  que cae martes o miércoles se observa el lunes anterior; jueves o viernes, el lunes siguiente;
  sábado, domingo o lunes, ese día. Del régimen quedan exceptuados Carnaval, Turismo y nueve fechas
  fijas, así que **solo se trasladan tres**: 19 de abril, 18 de mayo y 12 de octubre.
- **MTSS**: el 1 de marzo en que hay transmisión del mando presidencial es feriado no laborable.

Las trampas
-----------
- **Un feriado puede no caer en su fecha.** El 18/05/2027 es martes: el feriado se observa el lunes
  17. Quien busca «18 de mayo» en el calendario cuenta mal los días hábiles de esa semana.
- **Dos feriados pueden caer el mismo día.** En 2025 el 19 de abril cayó sábado, dentro de la Semana
  de Turismo. `del_anio` devuelve los dos; `feriados_de` devuelve una lista y no un único feriado.
- **«Día hábil» no tiene una sola definición.** Un 6 de enero muchos trabajan y los bancos no.
  `dias_habiles` cuenta dos cosas por separado: lunes a viernes sin ningún feriado, y lunes a viernes
  sin feriados pagos. Elegir una de las dos sin decirlo es la cifra creíble pero falsa.

Lo que no se calcula
--------------------
- El día del Censo de Población (feriado no laborable): lo fija el Poder Ejecutivo cada vez.
- Feriados departamentales y los que fija un convenio colectivo para una rama.
- Una ley puntual que mueva un feriado en un año dado. El módulo aplica el régimen general vigente.

Antes de 2002 rige la redacción anterior del art. 2 de la Ley 16.805, que no se modela: esos años se
rechazan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

ANIO_MINIMO = 2002  # el art. 2 de la Ley 16.805 vigente es el de la Ley 17.414, de noviembre de 2001

FUENTE = (
    "Decreto-Ley 14.977 (lista), Ley 12.590 art. 18 (pagos), Ley 16.805 con la redacción de la "
    "Ley 17.414 (traslados), MTSS (1 de marzo de transmisión de mando)"
)

# (mes, día) -> nombre. `PAGOS` y `TRASLADABLES` salen de las leyes del docstring.
FIJOS: dict[tuple[int, int], str] = {
    (1, 1): "Año Nuevo",
    (1, 6): "Día de Reyes",
    (4, 19): "Desembarco de los Treinta y Tres Orientales",
    (5, 1): "Día de los Trabajadores",
    (5, 18): "Batalla de Las Piedras",
    (6, 19): "Natalicio de Artigas",
    (7, 18): "Jura de la Constitución",
    (8, 25): "Declaratoria de la Independencia",
    (10, 12): "12 de octubre",
    (11, 2): "Día de los Difuntos",
    (12, 25): "Navidad",
}
PAGOS = frozenset({(1, 1), (5, 1), (7, 18), (8, 25), (12, 25)})
TRASLADABLES = frozenset({(4, 19), (5, 18), (10, 12)})


@dataclass(frozen=True, order=True)
class Feriado:
    fecha: date  # el día en que se observa
    nombre: str
    tipo: str  # "pago" | "laborable" | "no_laborable"
    fecha_original: date  # la del calendario; distinta de `fecha` solo si se trasladó

    @property
    def trasladado(self) -> bool:
        return self.fecha != self.fecha_original


def pascua(anio: int) -> date:
    """Domingo de Pascua del calendario gregoriano (algoritmo anónimo de Meeus/Jones/Butcher)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes, dia = divmod(h + l_ - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def observado(fecha: date) -> date:
    """El día en que se observa un feriado trasladable que cae en `fecha` (Ley 16.805, art. 1)."""
    dia = fecha.weekday()  # lunes = 0
    if dia in (1, 2):  # martes o miércoles: el lunes anterior
        return fecha - timedelta(days=dia)
    if dia in (3, 4):  # jueves o viernes: el lunes siguiente
        return fecha + timedelta(days=7 - dia)
    return fecha  # sábado, domingo o lunes


def _validar_anio(anio: int) -> None:
    if not isinstance(anio, int) or isinstance(anio, bool):
        raise ValueError(f"año {anio!r}: se espera un entero")
    if anio < ANIO_MINIMO:
        raise ValueError(
            f"año {anio}: antes de {ANIO_MINIMO} regía otra redacción de la Ley 16.805 (art. 2), que no se modela"
        )


def del_anio(anio: int) -> list[Feriado]:
    """Todos los feriados nacionales de `anio`, ordenados por el día en que se observan."""
    _validar_anio(anio)
    out: list[Feriado] = []
    for (mes, dia), nombre in FIJOS.items():
        original = date(anio, mes, dia)
        fecha = observado(original) if (mes, dia) in TRASLADABLES else original
        out.append(Feriado(fecha, nombre, "pago" if (mes, dia) in PAGOS else "laborable", original))
    domingo = pascua(anio)
    for n, nombre in ((48, "Carnaval (lunes)"), (47, "Carnaval (martes)")):
        d = domingo - timedelta(days=n)
        out.append(Feriado(d, nombre, "laborable", d))
    for n in range(7):  # Semana de Turismo: de lunes a domingo, la semana que termina en Pascua
        d = domingo - timedelta(days=6 - n)
        out.append(Feriado(d, "Semana de Turismo", "laborable", d))
    if anio % 5 == 0:  # el período presidencial empieza el 1 de marzo de 2005, 2010, ...
        d = date(anio, 3, 1)
        out.append(Feriado(d, "Transmisión del mando presidencial", "no_laborable", d))
    return sorted(out)


def feriados_de(fecha: date) -> list[Feriado]:
    """Los feriados que se observan en `fecha` (puede haber dos, o ninguno)."""
    return [f for f in del_anio(fecha.year) if f.fecha == fecha]


@dataclass(frozen=True)
class DiasHabiles:
    desde: date
    hasta: date
    dias: int  # días corridos, ambos extremos incluidos
    lunes_a_viernes: int
    sin_ningun_feriado: int  # lunes a viernes que no son feriado de ningún tipo
    sin_feriados_pagos: int  # lunes a viernes que no son feriado pago ni no laborable
    feriados_en_dias_de_semana: list[Feriado]


def dias_habiles(desde: date, hasta: date) -> DiasHabiles:
    """Cuenta los días hábiles entre `desde` y `hasta`, ambos incluidos, con las dos definiciones."""
    if desde > hasta:
        raise ValueError(f"desde {desde} es posterior a hasta {hasta}")
    if (hasta - desde).days > 366 * 10:
        raise ValueError("rango demasiado largo: hasta 10 años por consulta")
    por_dia: dict[date, list[Feriado]] = {}
    for anio in range(desde.year, hasta.year + 1):
        for f in del_anio(anio):
            por_dia.setdefault(f.fecha, []).append(f)
    semana = ningun = sin_pagos = 0
    en_semana: list[Feriado] = []
    d = desde
    while d <= hasta:
        if d.weekday() < 5:
            semana += 1
            fs = por_dia.get(d, [])
            en_semana.extend(fs)
            if not fs:
                ningun += 1
            if not any(f.tipo in ("pago", "no_laborable") for f in fs):
                sin_pagos += 1
        d += timedelta(days=1)
    return DiasHabiles(desde, hasta, (hasta - desde).days + 1, semana, ningun, sin_pagos, en_semana)
