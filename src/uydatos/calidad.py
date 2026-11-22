"""Marcas de calidad de una serie de sensores: rango, plano, salto y sin dato.

Un sensor trabado devuelve un numero plausible y falso, y eso es peor que un hueco: el hueco se ve.
Estas cuatro pruebas son las de QARTOD (el manual de control de calidad de boyas y mareografos de
NOAA), reducidas a lo que se puede decidir sin historia estadistica de la estacion:

- **rango**: fuera de los limites fisicos del parametro (una altura de 90 m en el rio Uruguay).
- **plano**: el mismo valor `repeticiones` veces seguidas (un sensor congelado, o una fuente que
  repite la ultima lectura porque no llego la nueva).
- **salto**: un cambio mayor que `max_salto` entre dos lecturas consecutivas (un pico de una
  lectura, no un evento).
- **sin dato**: el valor falta o no es un numero.

`marcar` no corrige ni interpola: devuelve una marca por valor, alineada con la entrada. Quien
responde decide que hacer con las marcas (avisar, contar, excluir); corregir un valor a ciegas
seria inventar el dato.

Los limites se piden **explicitos por fuente**: no hay un rango universal, y un default razonable
para la altura del rio es un disparate para una temperatura. `sugerir_limites` da un punto de
partida medido sobre la propia serie, para revisar a mano, no para usar sin mirar.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Optional, Sequence

OK = "ok"
RANGO = "rango"
PLANO = "plano"
SALTO = "salto"
SIN_DATO = "sin_dato"

MARCAS = (OK, RANGO, PLANO, SALTO, SIN_DATO)


def marcar(
    valores: Sequence[Optional[float]],
    *,
    minimo: float,
    maximo: float,
    max_salto: Optional[float] = None,
    repeticiones: int = 6,
) -> list[str]:
    """Una marca por valor: `ok`, `rango`, `plano`, `salto` o `sin_dato`.

    `repeticiones` es cuantas lecturas iguales seguidas ya son un sensor trabado (QARTOD usa 3 a 7;
    6 es un dia y medio de lecturas cada 15 minutos). `max_salto` se compara contra la ultima
    lectura **valida** anterior, asi un hueco no convierte la vuelta en un salto. Sin `max_salto` no
    se prueba el salto.
    """
    if minimo >= maximo:
        raise ValueError(f"los limites no encierran un rango: minimo {minimo} >= maximo {maximo}")
    if repeticiones < 2:
        raise ValueError(f"repeticiones: {repeticiones} no es un numero de lecturas iguales (2 o mas)")
    if max_salto is not None and max_salto <= 0:
        raise ValueError(f"max_salto: {max_salto} tiene que ser positivo")

    marcas: list[str] = []
    anterior: Optional[float] = None
    iguales = 0
    for valor in valores:
        if valor is None or (isinstance(valor, float) and math.isnan(valor)):
            marcas.append(SIN_DATO)
            iguales = 0  # un hueco corta la racha: no es un sensor trabado
            continue
        repetido = anterior is not None and valor == anterior
        iguales = iguales + 1 if repetido else 1  # cuantas veces seguidas aparece este valor
        if not minimo <= valor <= maximo:
            marcas.append(RANGO)
        elif repetido and iguales >= repeticiones:
            marcas.append(PLANO)
        elif max_salto is not None and anterior is not None and abs(valor - anterior) > max_salto:
            marcas.append(SALTO)
        else:
            marcas.append(OK)
        anterior = valor
    return marcas


def resumen(marcas: Sequence[str]) -> dict[str, int]:
    """Cuantas lecturas hay de cada marca, con las cinco claves siempre presentes.

    Un cero es informacion (no hubo saltos), y que falte la clave no: quien lo consume no tiene que
    preguntarse si no se midio o si no se encontro.
    """
    conteo = {marca: 0 for marca in MARCAS}
    for marca in marcas:
        if marca not in conteo:
            raise ValueError(f"marca desconocida: {marca!r}; las validas son {', '.join(MARCAS)}")
        conteo[marca] += 1
    return conteo


def sugerir_limites(
    valores: Sequence[Optional[float]], *, margen: float = 0.5, k: float = 6.0, piso: Optional[float] = None
) -> dict:
    """Un punto de partida para `minimo`, `maximo` y `max_salto`, medido sobre la propia serie.

    `minimo` y `maximo` son el rango observado estirado un `margen` (0.5 = 50% para cada lado), y
    `max_salto` es `k` veces el salto tipico (la mediana de los cambios consecutivos, que no se deja
    arrastrar por los picos que justamente se quieren marcar). `piso` es el minimo fisico del parametro
    (un caudal no baja de 0): el estirado no lo cruza.

    **Es para revisar a mano, no para usar sin mirar**: una serie que ya viene trabada sugiere
    limites que dan por bueno el sensor trabado.
    """
    validos = [v for v in valores if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(validos) < 3:
        raise ValueError(f"hacen falta 3 lecturas validas para sugerir limites, hay {len(validos)}")
    bajo, alto = min(validos), max(validos)
    amplitud = alto - bajo
    saltos = [abs(b - a) for a, b in zip(validos, validos[1:]) if b != a]
    tipico = median(saltos) if saltos else 0.0
    minimo = bajo - amplitud * margen
    if piso is not None:
        minimo = max(minimo, piso)
    return {
        "minimo": round(minimo, 4),
        "maximo": round(alto + amplitud * margen, 4),
        "max_salto": round(tipico * k, 4) if tipico else None,
        "lecturas": len(validos),
        "nota": "Sugerencia medida sobre esta serie: revisar antes de usarla como limite.",
    }
