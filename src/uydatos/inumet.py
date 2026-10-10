"""Observaciones meteorológicas de INUMET: hora a hora, en siete estaciones del país.

El catálogo de datos abiertos publica seis datasets de INUMET, uno por variable, con la misma
forma: un CSV `fecha;estacion_id;<valor>[,<valor>]`. Tres cosas de esa forma muerden:

- **`fecha` viene hora a hora y en UTC.** Lo dice el propio metadato del dataset, no el
  encabezado. Uruguay es UTC−3 todo el año, así que agrupar por la fecha cruda corta el día
  local a las 21:00.
- **`estacion_id` no es un id: es el nombre de la estación** («Salto G3»), y puede traer el texto
  de un error del servidor.
- **El valor viene en la unidad que declara el metadato** (ºC, mm, %, grados, hPa, horas). El
  lector no la convierte ni la inventa: devuelve el número tal cual.

El lector **rechaza en vez de arreglar**. Las trampas de acá abajo están medidas el 09/10/26
sobre los archivos completos de temperatura (332.070 valores, 12.059.752 bytes) y precipitación
(291.085 valores, 9.887.612 bytes):

1. **La columna de la estación puede traer un error del servidor.** Los dos archivos traen una
   fila cuyo `estacion_id` es `' please try again later.'`. La fila llega **sin fecha**, así que
   no es una fila de dato —igual que las siete `;;`—: se saltea y **se cuenta**
   (`filas_sin_dato()`), porque **cualquier lector que agrupe por esa columna sin validarla crea
   una octava estación**. Una fila que sí traiga fecha y una estación fuera de las siete se
   rechaza.
2. **Un valor vacío es un nulo, no un cero.** Y una fila entera vacía (`;;`, siete en cada
   archivo, la última incluida) es un separador, no un dato: se saltea.
3. **Un día local al que le falta alguna hora no es un día.** `serie_diaria()` devuelve `valor=None`
   y `horas` declaradas: una suma sobre horas sueltas es un piso, no el total. Pero **"24" no es la
   cadencia de todas las variables**: el viento se publica **cada dos horas** (12 por día) y la
   insolación es diaria; el día se mide contra `OBS_POR_DIA`, la cadencia de su propia variable.
4. **La unidad que declara el metadato puede no cerrar con el archivo.** El metadato de insolación
   dice que `heliofania` son «horas de brillo del Sol en el transcurso del día», y el archivo trae
   **4 valores por encima de 24 de 3.437, tres de ellos el 01/08/2026** (Salto 63,2 · Artigas 38,0 ·
   Mercedes 37,6). Son imposibles como horas y **no se corrigen ni se descartan: se declaran**, y
   `resumen()` los pone en los extremos por columna. Un rango (0, 24) habría rechazado el archivo
   entero por cuatro filas — que es el otro modo de falla.

Uso:
    python -m uydatos.inumet bajar precipitacion datos/inumet_precip.csv
    python -m uydatos.inumet resumen datos/inumet_precip.csv precipitacion
    python -m uydatos.inumet diaria datos/inumet_precip.csv precip_horario "Salto G3" suma
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

# Nombre corto -> (dataset del catálogo, columnas de valor medidas en el encabezado, si es horaria)
DATASETS: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "temperatura": (
        "inumet-observaciones-meteorologicas-temperatura-del-aire-en-el-uruguay",
        ("temp_aire",),
        True,
    ),
    "precipitacion": (
        "inumet-observaciones-meteorologicas-precipitacion-puntual-en-el-uruguay",
        ("precip_horario",),
        True,
    ),
    "humedad": (
        "inumet-observaciones-meteorologicas-humedad-relativa-en-el-uruguay",
        ("hum_relativa",),
        True,
    ),
    "viento": (
        "inumet-observaciones-meteorologicas-direccion-e-intensidad-del-viento-en-el-uruguay",
        ("dir_viento", "int_viento"),
        True,
    ),
    "presion": (
        "inumet-observaciones-meteorologicas-presion-atmosferica-en-el-uruguay",
        ("pres_atm_mar",),
        True,
    ),
    "insolacion": (
        "inumet-observaciones-meteorologicas-insolacion-total-en-el-uruguay",
        ("heliofania",),
        False,
    ),
}

# Las siete estaciones que declaran los metadatos. Insolación declara cinco de las siete.
ESTACIONES = (
    "Aeropuerto Melilla G3",
    "Artigas G3",
    "Colonia G3",
    "Mercedes G3",
    "Paso de los Toros G3",
    "Rocha G3",
    "Salto G3",
)

# Uruguay es UTC−3 todo el año desde 2015. Es un parámetro, no una constante escondida.
DESFASE_LOCAL = -3

# Observaciones por día que publica cada variable. **Medido el 09/10/26 sobre los seis archivos
# completos:** temperatura, precipitación, humedad y presión son hora a hora (24); el viento es
# **cada dos horas** (12: 10.841 de 11.690 días-estación) y la insolación es diaria (1). Un día al
# que le falten observaciones no es un día, pero "faltan" se mide contra la cadencia de SU variable.
OBS_POR_DIA: dict[str, int] = {
    "temp_aire": 24,
    "precip_horario": 24,
    "hum_relativa": 24,
    "dir_viento": 12,
    "int_viento": 12,
    "pres_atm_mar": 24,
    "heliofania": 1,
}
OBS_POR_DIA_POR_DEFECTO = 24

COLUMNAS_FIJAS = ["fecha", "estacion_id"]
AGREGACIONES = ("promedio", "max", "min", "suma")

# Rangos físicos amplios: atrapan un dato imposible, no uno raro. Solo las columnas cuyo rango se
# puede sostener. **`heliofania` no está a propósito**: su metadato declara horas de brillo del Sol
# y el archivo trae 4 valores por encima de 24 —imposibles—, así que un rango (0, 24) rechazaría el
# archivo entero por cuatro filas. Esos cuatro se declaran en `resumen()`, no se descartan.
RANGOS: dict[str, tuple[float, float]] = {
    "temp_aire": (-30.0, 50.0),
    "precip_horario": (0.0, 200.0),
    "hum_relativa": (0.0, 100.0),
    "dir_viento": (0.0, 360.0),
    "int_viento": (0.0, 250.0),  # km/h, la unidad que declara el metadato
    "pres_atm_mar": (900.0, 1100.0),
}

_ARCHIVO = re.compile(r"^inumet_[a-z_]+\.csv$")
_RE_FECHA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$")


class InumetInvalido(ValueError):
    """La observación no cumple el contrato de la fuente."""


def _fecha(texto: str, archivo: str, fila: int) -> datetime:
    m = _RE_FECHA.match(texto.strip())
    if not m:
        raise InumetInvalido(f"{archivo} fila {fila}: fecha ilegible {texto!r}")
    anio, mes, dia, hora, minuto = (int(x) for x in m.groups())
    try:
        return datetime(anio, mes, dia, hora, minuto)
    except ValueError:
        raise InumetInvalido(f"{archivo} fila {fila}: fecha imposible {texto!r}") from None


def _numero(valor: str, archivo: str, fila: int, columna: str) -> Optional[float]:
    if valor.strip() == "":
        return None
    try:
        numero = float(valor)
    except ValueError:
        raise InumetInvalido(f"{archivo} fila {fila}: número ilegible en {columna}: {valor!r}") from None
    if (rango := RANGOS.get(columna)) and not rango[0] <= numero <= rango[1]:
        raise InumetInvalido(f"{archivo} fila {fila}: {columna}={numero} fuera de rango {rango[0]}..{rango[1]}")
    return numero


def leer_archivo(ruta: Path, columnas: Sequence[str]) -> list[dict]:
    """Lee el CSV de una variable. Cada fila: `fecha` (datetime, en UTC), `estacion` (str) y una
    clave por cada columna de valor (`float | None`).

    Una fila **sin fecha** no es una fila de dato y se saltea: son las siete `;;` y la que trae el
    texto de un error del servidor. Rechaza: encabezado distinto de `columnas`, fila con otro
    número de columnas, estación fuera de `ESTACIONES`, fecha ilegible, número ilegible, valor
    fuera de rango y (fecha, estación) duplicada.
    """
    ruta = Path(ruta)
    esperado = [*COLUMNAS_FIJAS, *columnas]
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        try:
            encabezado = [c.strip() for c in next(lector)]
        except StopIteration:
            raise InumetInvalido(f"{ruta.name}: archivo sin filas de datos") from None
        if encabezado != esperado:
            raise InumetInvalido(f"{ruta.name}: columnas inesperadas {encabezado}, se esperaba {esperado}")
        filas: list[dict] = []
        vistas: set[tuple[datetime, str]] = set()
        for n, campos in enumerate(lector, start=2):
            if not campos or not campos[0].strip():
                continue
            if len(campos) != len(esperado):
                raise InumetInvalido(f"{ruta.name} fila {n}: {len(campos)} columnas, se esperaban {len(esperado)}")
            estacion = campos[1].strip()
            if estacion not in ESTACIONES:
                raise InumetInvalido(
                    f"{ruta.name} fila {n}: estación desconocida {estacion!r}. Las siete declaradas son {ESTACIONES}"
                )
            fecha = _fecha(campos[0], ruta.name, n)
            if (fecha, estacion) in vistas:
                raise InumetInvalido(f"{ruta.name} fila {n}: {estacion} repetida en {fecha}")
            vistas.add((fecha, estacion))
            fila: dict = {"fecha": fecha, "estacion": estacion}
            for columna, valor in zip(columnas, campos[2:]):
                fila[columna] = _numero(valor, ruta.name, n, columna)
            filas.append(fila)
    if not filas:
        raise InumetInvalido(f"{ruta.name}: archivo sin filas de datos")
    return filas


def _columnas_de(columna: str) -> tuple[str, ...]:
    """Las columnas declaradas del dataset al que pertenece `columna`. El viento trae dos, así que
    leer un archivo de viento pidiendo una sola columna da «columnas inesperadas»."""
    for _, columnas, _ in DATASETS.values():
        if columna in columnas:
            return columnas
    return (columna,)


def filas_sin_dato(ruta: Path) -> int:
    """Cuántas líneas del archivo no son filas de dato: las que no traen fecha.

    Medido el 09/10/26: **ocho en cada archivo** —siete `;;` y una cuyo `estacion_id` es el texto
    de un error del servidor—. Se cuentan, no se esconden, y un archivo que solo traiga líneas sin
    dato es un archivo vacío disfrazado (`leer_archivo` lo rechaza por no tener filas).
    """
    with Path(ruta).open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        next(lector, None)
        return sum(1 for campos in lector if not campos or not campos[0].strip())


def valor_por_estacion(archivo: Path, nombre: str) -> list[dict]:
    """El CSV descargado de `nombre` (una clave de `DATASETS`), leído. Rechaza la variable diaria:
    para esa no hay agregación horaria que hacer."""
    if nombre not in DATASETS:
        raise InumetInvalido(f"variable desconocida {nombre!r}; las declaradas son {tuple(DATASETS)}")
    _, columnas, horaria = DATASETS[nombre]
    if not horaria:
        raise InumetInvalido(f"{nombre} no es una serie horaria: se lee con leer_archivo()")
    return leer_archivo(archivo, columnas)


def resumen(serie: list[dict], desfase_horas: int = DESFASE_LOCAL) -> dict:
    """Cobertura por estación: filas, **extremos por columna**, nulos y días locales incompletos. El
    denominador va en la salida porque un promedio por estación sobre series de distinto largo
    no es comparable.

    Los días se cuentan en hora local, igual que en `serie_diaria()`: contar días UTC y agregar
    días locales daría dos denominadores distintos para la misma serie. Y "completo" se mide
    contra la cadencia de la variable (`OBS_POR_DIA`), no contra 24: el viento publica 12 por día.

    Los **extremos** están acá y no en una validación aparte porque son lo que deja ver un valor
    imposible sin rechazar el archivo: `heliofania` trae 63,2 h de brillo del Sol en un día.
    """
    if not serie:
        raise InumetInvalido("serie vacía: no hay nada que medir")
    columnas = [c for c in serie[0] if c not in ("fecha", "estacion")]
    por_estacion: dict[str, list[dict]] = defaultdict(list)
    for f in serie:
        por_estacion[f["estacion"]].append(f)
    salida: dict = {
        "filas": len(serie),
        "columnas": columnas,
        "primera": serie[0]["fecha"],
        "ultima": serie[-1]["fecha"],
    }
    obs_esperadas = max(
        (OBS_POR_DIA.get(c, OBS_POR_DIA_POR_DEFECTO) for c in columnas), default=OBS_POR_DIA_POR_DEFECTO
    )
    salida["estaciones"] = {}
    for estacion in sorted(por_estacion):
        filas = por_estacion[estacion]
        por_dia: dict[date, list[dict]] = defaultdict(list)
        for f in filas:
            por_dia[(f["fecha"] + timedelta(hours=desfase_horas)).date()].append(f)
        completos = sum(1 for del_dia in por_dia.values() if len(del_dia) >= obs_esperadas)
        salida["estaciones"][estacion] = {
            "filas": len(filas),
            "primera": min(f["fecha"] for f in filas),
            "ultima": max(f["fecha"] for f in filas),
            "nulos": {c: sum(1 for f in filas if f[c] is None) for c in columnas},
            "extremos": {
                c: {
                    "min": min((f[c] for f in filas if f[c] is not None), default=None),
                    "max": max((f[c] for f in filas if f[c] is not None), default=None),
                }
                for c in columnas
            },
            "dias": len(por_dia),
            "dias_completos": completos,
        }
    return salida


def serie_diaria(
    serie: list[dict],
    estacion: str,
    columna: str,
    agregacion: str,
    desfase_horas: int = DESFASE_LOCAL,
    obs_por_dia: Optional[int] = None,
) -> list[dict]:
    """Agrega la serie horaria al día local de `estacion`.

    `agregacion` es obligatoria y no tiene valor por defecto: para la temperatura el día es el
    `max` (y el `min`), para la lluvia es la `suma`, y elegir por vos es exactamente lo que este
    paquete no hace. `desfase_horas` es el desfase de la hora local contra UTC (Uruguay: −3).

    `obs_por_dia` es cuántas observaciones publica la fuente por día para esa columna; si no se
    pasa, sale de `OBS_POR_DIA` —**el viento publica 12, no 24**, y medirlo contra 24 deja todos sus
    días en `None`—.

    Un día al que le falta alguna observación —o que tiene algún nulo— devuelve `valor=None`, con
    `horas` y `nulos` declarados: una suma sobre horas sueltas es un piso, no el total del día.
    """
    if agregacion not in AGREGACIONES:
        raise InumetInvalido(f"agregación desconocida {agregacion!r}; las declaradas son {AGREGACIONES}")
    if columna not in (serie[0] if serie else {}):
        raise InumetInvalido(f"columna desconocida {columna!r}")
    if obs_por_dia is None:
        if columna not in OBS_POR_DIA:
            raise InumetInvalido(f"no sé cuántas observaciones por día publica {columna!r}; pasá obs_por_dia")
        obs_por_dia = OBS_POR_DIA[columna]
    por_dia: dict[date, list[Optional[float]]] = defaultdict(list)
    for f in serie:
        if f["estacion"] == estacion:
            por_dia[(f["fecha"] + timedelta(hours=desfase_horas)).date()].append(f[columna])
    if not por_dia:
        raise InumetInvalido(f"{estacion!r} no tiene filas en la serie")
    salida = []
    for dia in sorted(por_dia):
        valores = por_dia[dia]
        numeros = [v for v in valores if v is not None]
        horas, nulos = len(valores), len(valores) - len(numeros)
        total = horas >= obs_por_dia and nulos == 0
        if not total or not numeros:
            valor = None
        elif agregacion == "suma":
            valor = sum(numeros)
        elif agregacion == "promedio":
            valor = sum(numeros) / len(numeros)
        elif agregacion == "max":
            valor = max(numeros)
        else:
            valor = min(numeros)
        salida.append({"fecha": dia, "valor": valor, "horas": horas, "nulos": nulos})
    return salida


def descargar(nombre: str, destino: Path) -> Path:
    """Baja el CSV de datos de `nombre` (una clave de `DATASETS`) a `destino`. **Sale a la red.**

    El recurso de datos se elige por el nombre del archivo (`inumet_*.csv`), medido en los seis
    datasets: el catálogo publica además el metadato, y en algunos casos también en CSV.
    """
    from uydatos.catalogo import bajar_recurso, recursos

    if nombre not in DATASETS:
        raise InumetInvalido(f"variable desconocida {nombre!r}; las declaradas son {tuple(DATASETS)}")
    dataset = DATASETS[nombre][0]
    candidatos = [r for r in recursos(dataset) if _ARCHIVO.match(Path(r["url"].split("?")[0]).name)]
    if len(candidatos) != 1:
        raise InumetInvalido(f"{dataset}: {len(candidatos)} recursos de datos, se esperaba 1")
    return bajar_recurso(candidatos[0]["url"], Path(destino))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.inumet", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    bajar = sub.add_parser("bajar", help="baja el CSV de una variable del catálogo")
    bajar.add_argument("nombre", choices=sorted(DATASETS))
    bajar.add_argument("destino", type=Path)
    leer = sub.add_parser("resumen", help="cobertura de la serie horaria")
    leer.add_argument("archivo", type=Path)
    leer.add_argument("nombre", choices=sorted(DATASETS))
    diaria = sub.add_parser("diaria", help="serie diaria de una estación")
    diaria.add_argument("archivo", type=Path)
    diaria.add_argument("columna")
    diaria.add_argument("estacion")
    diaria.add_argument("agregacion", choices=AGREGACIONES)
    args = ap.parse_args(argv)

    if args.orden == "bajar":
        print(descargar(args.nombre, args.destino))
        return 0
    if args.orden == "resumen":
        # Se lee con las columnas declaradas del dataset, no con `valor_por_estacion()`: el resumen
        # vale también para la insolación, que es diaria y es la que trae el valor imposible.
        columnas = DATASETS[args.nombre][1]
        r = resumen(leer_archivo(args.archivo, columnas))
        sin_dato = filas_sin_dato(args.archivo)
        print(f"{r['filas']} filas de dato y {sin_dato} líneas sin dato, {r['primera']} a {r['ultima']}")
        for estacion, d in r["estaciones"].items():
            print(
                f"  {estacion:24} {d['filas']:>7} filas  {d['dias']:>5} días "
                f"({d['dias_completos']} completos)  nulos {d['nulos']}"
            )
            for columna, e in d["extremos"].items():
                print(f"      {columna}: {e['min']} .. {e['max']}")
        return 0
    serie = leer_archivo(args.archivo, _columnas_de(args.columna))
    diaria = serie_diaria(serie, args.estacion, args.columna, args.agregacion)
    completos = [d for d in diaria if d["valor"] is not None]
    print(f"{args.estacion}: {len(completos)} de {len(diaria)} días con {args.agregacion} calculable")
    for d in completos[-5:]:
        print(f"  {d['fecha']}  {d['valor']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
