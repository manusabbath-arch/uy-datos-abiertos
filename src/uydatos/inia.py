"""Clima diario de INIA Salto Grande: lluvia y temperaturas máxima y mínima, desde 1970.

Dataset `inia-precipitacion-temps-extremas-sg` del catálogo de datos abiertos (Unidad GRAS de
INIA, actualización quincenal): un CSV por año, `ppt_tmax_tmin_sg_AAAA.csv`, con las columnas
`fecha, temperaturaMaxima, temperaturaMinima, pluviometro` (°C, °C, mm). Una sola estación, en
−31,2728 / −57,8908, y **el día de INIA va de 9:00 a 9:00**: la lluvia del día D cayó en buena
parte la noche anterior.

El lector **rechaza en vez de arreglar**: columnas distintas, fecha ilegible o fuera del año del
archivo, fecha duplicada, hueco en la serie, archivo sin filas, número ilegible o valor fuera de
rango físico. Un hueco no se rellena. Un campo vacío es un nulo (`None`), no un cero.

Además calcula **normales y anomalías** de temperatura. Sin la anomalía, cualquier correlación
con otra serie solo redescubre que el verano es verano. Método (declarado, es una elección):

- **Normal** = media de los años `PERIODO_NORMAL` sobre una ventana circular de ±`VENTANA_DIAS`
  días alrededor de cada día del año. 1970 queda afuera porque empieza en julio.
- **Los días se indexan por (mes, día) sobre un año bisiesto**: el 29/02 tiene su normal y el
  01/03 es el mismo día en todos los años.
- **Solo temperatura.** La lluvia es asimétrica (la mayoría de los días es cero): una anomalía
  como resta no significa lo mismo. Se deja el valor observado.

Uso:
    python -m uydatos.inia bajar DIRECTORIO
    python -m uydatos.inia resumen DIRECTORIO
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Sequence

DATASET = "inia-precipitacion-temps-extremas-sg"

COLUMNAS = ["fecha", "temperaturaMaxima", "temperaturaMinima", "pluviometro"]
NUMERICAS = COLUMNAS[1:]

PERIODO_NORMAL = (1971, 2025)
VENTANA_DIAS = 7

# Rangos físicos amplios: atrapan un dato imposible, no un dato raro.
RANGO_TEMPERATURA = (-30.0, 50.0)
LLUVIA_MAXIMA = 500.0

_NOMBRE = re.compile(r"^ppt_tmax_tmin_sg_(\d{4})\.csv$")


class ClimaInvalido(ValueError):
    """La serie no cumple el contrato de la fuente."""


def _numero(valor: str, archivo: str, fila: int, columna: str) -> Optional[float]:
    if valor.strip() == "":
        return None
    try:
        return float(valor)
    except ValueError:
        raise ClimaInvalido(f"{archivo} fila {fila}: número ilegible en {columna}: {valor!r}") from None


def _validar_fisica(fila: dict, archivo: str, n: int) -> None:
    tmax, tmin, lluvia = fila["temperaturaMaxima"], fila["temperaturaMinima"], fila["pluviometro"]
    lo, hi = RANGO_TEMPERATURA
    for nombre, t in (("tmax", tmax), ("tmin", tmin)):
        if t is not None and not lo <= t <= hi:
            raise ClimaInvalido(f"{archivo} fila {n}: {nombre}={t} fuera de rango {lo}..{hi}")
    if tmax is not None and tmin is not None and tmax < tmin:
        raise ClimaInvalido(f"{archivo} fila {n}: tmax {tmax} menor que tmin {tmin}")
    if lluvia is not None and not 0.0 <= lluvia <= LLUVIA_MAXIMA:
        raise ClimaInvalido(f"{archivo} fila {n}: lluvia {lluvia} fuera de 0..{LLUVIA_MAXIMA}")


def leer_archivo(ruta: Path, anio: int) -> list[dict]:
    """Lee el CSV de un año. Cada fila: `fecha` (date) y las tres numéricas (float | None)."""
    ruta = Path(ruta)
    with ruta.open(encoding="utf-8", newline="") as f:
        lector = csv.reader(f)
        try:
            encabezado = next(lector)
        except StopIteration:
            raise ClimaInvalido(f"{ruta.name}: archivo sin filas de datos") from None
        if [c.strip() for c in encabezado] != COLUMNAS:
            raise ClimaInvalido(f"{ruta.name}: columnas inesperadas {encabezado}")
        filas = []
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue
            if len(campos) != len(COLUMNAS):
                raise ClimaInvalido(f"{ruta.name} fila {n}: {len(campos)} columnas")
            try:
                fecha = date.fromisoformat(campos[0].strip())
            except ValueError:
                raise ClimaInvalido(f"{ruta.name} fila {n}: fecha ilegible {campos[0]!r}") from None
            if fecha.year != anio:
                raise ClimaInvalido(f"{ruta.name} fila {n}: fecha {fecha} fuera del año {anio} del archivo")
            fila: dict = {"fecha": fecha}
            for col, valor in zip(NUMERICAS, campos[1:]):
                fila[col] = _numero(valor, ruta.name, n, col)
            _validar_fisica(fila, ruta.name, n)
            filas.append(fila)
    if not filas:
        raise ClimaInvalido(f"{ruta.name}: archivo sin filas de datos")
    return filas


def leer_serie(directorio: Path) -> list[dict]:
    """Serie diaria completa de los `ppt_tmax_tmin_sg_AAAA.csv` del directorio. Rechaza
    duplicados y huecos."""
    archivos = sorted(
        (int(m.group(1)), p) for p in Path(directorio).glob("ppt_tmax_tmin_sg_*.csv") if (m := _NOMBRE.match(p.name))
    )
    if not archivos:
        raise ClimaInvalido(f"ningún archivo ppt_tmax_tmin_sg_AAAA.csv en {directorio}")
    serie: list[dict] = []
    for anio, ruta in archivos:
        serie.extend(leer_archivo(ruta, anio))
    serie.sort(key=lambda f: f["fecha"])
    for previa, actual in zip(serie, serie[1:]):
        if actual["fecha"] == previa["fecha"]:
            raise ClimaInvalido(f"fecha duplicada: {actual['fecha']}")
        if actual["fecha"] - previa["fecha"] != timedelta(days=1):
            raise ClimaInvalido(f"hueco en la serie entre {previa['fecha']} y {actual['fecha']}")
    return serie


def cobertura(serie: list[dict]) -> dict:
    """Filas leídas contra días esperados, extremos y nulos por columna."""
    if not serie:
        raise ClimaInvalido("serie vacía: no hay nada que medir")
    primera, ultima = serie[0]["fecha"], serie[-1]["fecha"]
    return {
        "filas": len(serie),
        "esperado": (ultima - primera).days + 1,
        "primera": primera,
        "ultima": ultima,
        "nulos": {c: sum(1 for f in serie if f[c] is None) for c in NUMERICAS},
    }


def _indice(d: date) -> int:
    """Día del año sobre un año bisiesto (0..365)."""
    return date(2000, d.month, d.day).timetuple().tm_yday - 1


def normales(
    serie: list[dict], desde: int = PERIODO_NORMAL[0], hasta: int = PERIODO_NORMAL[1]
) -> dict[tuple[int, int], dict]:
    """Normal por (mes, día): media de tmax, tmin y lluvia en los años `desde`..`hasta`, sobre
    una ventana circular de ±VENTANA_DIAS. `n` es cuántas muestras de tmax usó."""
    campos = {"tmax": "temperaturaMaxima", "tmin": "temperaturaMinima", "lluvia": "pluviometro"}
    suma = {k: [0.0] * 366 for k in campos}
    cuenta = {k: [0] * 366 for k in campos}
    usados = 0
    for f in serie:
        if not desde <= f["fecha"].year <= hasta:
            continue
        usados += 1
        i = _indice(f["fecha"])
        for k, col in campos.items():
            if f[col] is not None:
                suma[k][i] += f[col]
                cuenta[k][i] += 1
    if usados == 0:
        raise ClimaInvalido(f"período {desde}-{hasta} sin datos en la serie")
    salida: dict[tuple[int, int], dict] = {}
    for i in range(366):
        vecinos = [(i + k) % 366 for k in range(-VENTANA_DIAS, VENTANA_DIAS + 1)]
        fila: dict = {}
        for k in campos:
            n = sum(cuenta[k][j] for j in vecinos)
            fila[k] = sum(suma[k][j] for j in vecinos) / n if n else None
            if k == "tmax":
                fila["n"] = n
        d = date(2000, 1, 1) + timedelta(days=i)
        salida[(d.month, d.day)] = fila
    return salida


def clima_diario(serie: list[dict], desde: int = PERIODO_NORMAL[0], hasta: int = PERIODO_NORMAL[1]) -> list[dict]:
    """Una fila por día: lo observado, la normal y la anomalía de temperatura (observado menos
    normal). Un nulo no inventa anomalía."""
    norm = normales(serie, desde, hasta)
    filas = []
    for f in serie:
        n = norm[(f["fecha"].month, f["fecha"].day)]
        tmax, tmin = f["temperaturaMaxima"], f["temperaturaMinima"]
        filas.append(
            {
                **f,
                "normal_tmax": n["tmax"],
                "normal_tmin": n["tmin"],
                "anom_tmax": None if tmax is None or n["tmax"] is None else tmax - n["tmax"],
                "anom_tmin": None if tmin is None or n["tmin"] is None else tmin - n["tmin"],
            }
        )
    return filas


def tendencia_anual(serie: list[dict], desde: int = PERIODO_NORMAL[0], hasta: int = PERIODO_NORMAL[1]) -> dict:
    """Tendencia lineal de la media anual de tmax y tmin, en °C por década, con su error
    estándar. Solo años **completos** (todos los días, sin nulo en la columna): un año parcial
    sesgaría la media por estacionalidad."""
    campos = {"tmax": "temperaturaMaxima", "tmin": "temperaturaMinima"}
    salida = {}
    for k, col in campos.items():
        anios, medias = [], []
        for anio in range(desde, hasta + 1):
            dias = [f for f in serie if f["fecha"].year == anio]
            esperado = (date(anio, 12, 31) - date(anio, 1, 1)).days + 1
            if len(dias) == esperado and all(f[col] is not None for f in dias):
                anios.append(anio)
                medias.append(sum(f[col] for f in dias) / len(dias))
        if len(anios) < 3:
            raise ClimaInvalido(f"tendencia: hacen falta al menos 3 años completos (hay {len(anios)})")
        n = len(anios)
        mx, my = sum(anios) / n, sum(medias) / n
        sxx = sum((a - mx) ** 2 for a in anios)
        b = sum((a - mx) * (m - my) for a, m in zip(anios, medias)) / sxx
        residuos = [m - (my + b * (a - mx)) for a, m in zip(anios, medias)]
        ee = math.sqrt(sum(e * e for e in residuos) / (n - 2) / sxx)
        salida[k] = {"por_decada": b * 10, "error_estandar": ee * 10, "anios": n}
    return salida


def dias_de_atraso(serie: list[dict], hoy: Optional[date] = None) -> int:
    """Días entre el último dato y `hoy`. La fuente se actualiza cada dos semanas."""
    if not serie:
        raise ClimaInvalido("serie vacía: no hay último dato")
    return ((hoy or date.today()) - serie[-1]["fecha"]).days


def descargar(directorio: Path) -> list[Path]:
    """Baja los CSV anuales vigentes del catálogo a `directorio`. **Sale a la red.**

    Pisa los archivos existentes: el año en curso crece cada quincena.
    """
    from uydatos.catalogo import bajar_recurso, recursos

    escritos = []
    for r in recursos(DATASET):
        nombre = Path(r["url"].split("?")[0]).name
        if _NOMBRE.match(nombre):
            escritos.append(bajar_recurso(r["url"], Path(directorio) / nombre))
    if not escritos:
        raise ClimaInvalido(f"el dataset {DATASET} no trajo ningún ppt_tmax_tmin_sg_AAAA.csv")
    return escritos


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.inia", description=__doc__.splitlines()[0])
    ap.add_argument("orden", choices=["bajar", "resumen"])
    ap.add_argument("directorio", type=Path)
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"{len(descargar(args.directorio))} archivos bajados")
        return 0
    serie = leer_serie(args.directorio)
    c = cobertura(serie)
    print(f"Filas: {c['filas']} de {c['esperado']} días, {c['primera']} a {c['ultima']}")
    print(f"Nulos por columna: {c['nulos']}")
    for var, t in tendencia_anual(serie).items():
        print(
            f"Tendencia de {var} ({t['anios']} años completos): "
            f"{t['por_decada']:+.2f} °C por década (error estándar {t['error_estandar']:.2f})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
