"""Nivel y caudal del río Uruguay en el sistema de alerta del INA (INFORM, `alerta.ina.gob.ar`).

La red de escalas de Prefectura Nacional Argentina entra al sistema de alerta del INA y es su
mismo dato el que publica el HTML de Prefectura: no hace falta scrapear Prefectura, el dato está
acá con su fecha de carga (`timeupdate`). Abierto, sin token, en el canal `a5` del API del
INFORM (`obs/puntual`).

Medido el 2026-10-27 (hora de Uruguay), sobre bajadas reales del API:

- Serie 79 (altura de Concordia), rango cerrado 1931-01-01 a 2026-10-25: **37.876 filas**,
  4.986.175 bytes, sha256 `c78f3ad9d0871605…`. Una fila por *medición puntual* (`timestart ==
  timeend` en las 37.876), **orden ascendente**, **0 valores vacíos**, extremos de 95 años
  **-0,24 a 17,82 m**. El cero de la escala se pasa por debajo: hay valores negativos y no son
  un defecto.
- La cadencia **no es un dato por día**: 2.524 de 34.932 días traen 2 lecturas, y 2 filas
  legítimas de 2024-10-23/24 vienen con la columna `nombre` vacía (la hora de la lectura del
  operador, que no siempre es 00:00). El lector no asume cadencia y no valida la columna `nombre`.
- Serie 926 (caudal en Salto Grande Arriba, serie viva el 2026-10-25 desde 1995-05-01): 12.273
  filas bajadas del 1900 a 2026-10-25, extremos 33,0 a 33.837 m³/s; el dato del 26/10/2026 quedó
  cargado a las 18:01 UY del mismo día. Serie 927 (Abajo, desde 2006-01-01): 8.178 filas
  (ventana de 1900), 0,0 a 30.437. Serie 928 (caudal de Concordia, desde 1931): 33.118 filas,
  197 a 35.389 m³/s — **y su última fila es del 15/07/2026: 3,5 meses de atraso**. La misma
  fuente, el atraso lo dice `timeupdate`: el API no avisa nada aparte.
- El dato del día sale **por la tarde**: `timeupdate` entre las 12:43 y las 15:43 UY en las
  alturas y a las 18:01 UY en los caudales del mismo día. Una tarea que corra al mediodía puede
  leer el dato de ayer sin que nada lo avise: la frescura se decide contra `timeupdate`.
- Las columnas `descripcion` y `unit_id` están **vacías en las 37.876 filas** y el API no trae
  la unidad del `H`: la fija el lector (`H` = m, `Q` = m³/s), igual que los niveles de alerta de
  la propia estación (35,5 m en Salto Grande Arriba), que están en metros.
- El filtro del API **respeta** el rango pedido (con `timeend 2015`, la última fila es del
  31/12/2015, sin fugas —medido—), pero **no lo valida**: con `timestart > timeend` responde
  HTTP 200 con cuerpo vacío, y también responde 200 con cuerpo vacío una serie `has_obs:
  false` (la 938 "Aporte Salto Grande": ni encabezado). El lector valida `desde < hasta` antes
  de salir y **levanta** si el cuerpo no trae filas.
- **La cadena de cache sirve versiones viejas.** La primera consulta del día a la ventana de 7
  días de la serie 926 trajo filas hasta el 22/10; la segunda al mismo rango trajo el 26/10 y
  desde ahí quedó estable. `Cache-Control: no-store` no lo cambió (medido). El lector no adivina
  si le sirvieron una versión vieja: el sello guarda la hora de la bajada y **el consumidor
  decide la frescura contra `timeupdate`**.
- **El id es de serie, no de estación, y por nombre se lee la fuente equivocada.** En el
  listado de 4.695 estaciones hay 6 "Concordia"; la del río Uruguay es la estación 79
  (`id_externo 700`, escala de Prefectura, país Argentina), y la estación **283 "CONCORDIA
  (DNCPVN-61…)" es de Brasil** (`rio: RIO URUGUAI`, red `red_ana_hidro`). Fijar una serie por
  nombre trae el dato de otra red sin avisarlo: el lector fija las series **por id** y trae la
  `metadata()` con el país y la red para que se pueda auditar.
- **El huso**: los `timestart` van en Z y la hora de la lectura es la del operador: 10Z la más
  común (14.535 de 37.876), después 15Z, 09Z, 07Z, 11Z, 03Z (la 03Z = 00:00 UY es la diaria
  reciente). **52 de 37.876 filas están a las 00-02Z**: su día local uruguayo es el anterior.
  El día local es una función con el desfase como parámetro (-3), no una constante escondida.

Uso:

    python -m uydatos ina bajar datos/ina --dias 30
    python -m uydatos ina obs datos/ina/serie_77.csv --limite 10
    python -m uydatos ina resumen datos/ina
    python -m uydatos ina meta 77
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

from uydatos import procedencia, red
from uydatos.errores import DatosInvalidos

BASE = "https://alerta.ina.gob.ar/a5/obs/puntual"
CODIFICACION = "utf-8"

COLUMNAS = [
    "id",
    "tipo",
    "series_id",
    "timestart",
    "timeend",
    "nombre",
    "descripcion",
    "unit_id",
    "timeupdate",
    "valor",
]

# Lo que el API no declara, con la medida del histórico completo: la unidad de la variable
# (H = metros, Q = m³/s) y su rango físico. Un valor nuevo fuera de estos rangos es un defecto
# de la fuente y se rechaza; un valor raro dentro se declara en `resumen()`, no se corrige.
RANGO_FISICO = {
    "H": (-10.0, 60.0),  # 95 años en Concordia: -0,24 a 17,82; el cero de la escala se pasa por debajo
    "Q": (0.0, 60000.0),  # 33.118 lecturas de Concordia: 0,0 a 35.389; el máximo va con margen
}
UNIDADES = {"H": "m", "Q": "m³/s"}

# Las series del canal del río Uruguay, fijadas por id (medido el 2026-10-27). El mismo
# "Concordia" figura en 6 estaciones de otras redes y la 283 es de Brasil: no se fija por nombre.
SERIES = {
    77: {"nombre": "Salto Grande Arriba", "var": "H", "estacion": 77},
    78: {"nombre": "Salto Grande Abajo", "var": "H", "estacion": 78},
    79: {"nombre": "Concordia", "var": "H", "estacion": 79},
    926: {"nombre": "Salto Grande Arriba", "var": "Q", "estacion": 77},
    927: {"nombre": "Salto Grande Abajo", "var": "Q", "estacion": 78},
    928: {"nombre": "Concordia", "var": "Q", "estacion": 79},
}

NOMBRE_FUENTE = "upsertObservacionesPuntual"  # lo que el API pone en la columna `nombre`


class InaInvalido(DatosInvalidos):
    """El cuerpo del API no cumple el contrato medido de la fuente."""


def url_observaciones(id_serie: int, desde: date, hasta: date) -> str:
    """La URL del request, con el rango validado y en hora de Uruguay (-03:00). **No sale a la red.**"""
    if not desde < hasta:
        raise InaInvalido(
            f"serie {id_serie}: el rango pedido es desde={desde} hasta={hasta}; el API responde "
            "HTTP 200 con cuerpo vacío a un rango inválido, así que se valida antes de salir"
        )
    params = (
        f"format=csv&tipo=puntual&series_id={id_serie}"
        f"&timestart={desde.isoformat()}T00:00:00.000-03:00"
        f"&timeend={hasta.isoformat()}T23:59:59.000-03:00"
    )
    return f"{BASE}/series/{id_serie}/observaciones?{params}"


def dia_local(instante: datetime, desfase_horas: int = -3) -> date:
    """El día local de un instante Z, con el desfase como parámetro. Uruguay es UTC-3 todo el
    año (sin cambio de hora desde 2015).

    Medido: 52 de 37.876 filas de la serie H de Concordia están a las 00-02Z, y su día local
    uruguayo es el anterior. No se esconde en una constante."""
    return (instante + timedelta(hours=desfase_horas)).date()


def _instante_z(s: str, ruta: Path, fila: int, campo: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        raise InaInvalido(
            f"{ruta.name} fila {fila}: {campo} ilegible {s!r}; el API manda 2026-10-26T03:00:00.000Z"
        ) from None


def _fila(cruda: dict[str, str], id_serie: int, desde: datetime, hasta: datetime, ruta: Path, n: int) -> dict:
    """Una fila del CSV del API, tipada y validada. Levanta con el motivo; never completa ni corrige."""
    if cruda.get("tipo") != "puntual":
        raise InaInvalido(
            f"{ruta.name} fila {n}: tipo {cruda.get('tipo')!r} fuera del dominio "
            "medido: el API trae 'puntual' en todas las filas"
        )
    try:
        se = int(cruda["series_id"])
    except (TypeError, ValueError):
        raise InaInvalido(f"{ruta.name} fila {n}: series_id ilegible {cruda['series_id']!r}") from None
    if se != id_serie:
        raise InaInvalido(f"{ruta.name} fila {n}: series_id {se} distinto del pedido ({id_serie})")
    instante = _instante_z(cruda["timestart"], ruta, n, "timestart")
    fin = _instante_z(cruda["timeend"], ruta, n, "timeend")
    if fin != instante:
        raise InaInvalido(
            f"{ruta.name} fila {n}: la serie puntual trae timeend {fin} distinto de "
            f"timestart {instante}: el contrato medido los coincide en 37.876 filas"
        )
    if not (desde <= instante <= hasta):
        raise InaInvalido(
            f"{ruta.name} fila {n}: timestart {instante.isoformat()} queda fuera del rango pedido "
            f"{desde.isoformat()} a {hasta.isoformat()}: el API no está respetando el filtro"
        )
    carga = _instante_z(cruda["timeupdate"], ruta, n, "timeupdate")
    if not cruda.get("valor"):
        # El API no trae filas con el valor vacío (medido: 0 de 37.876): los huecos son filas que
        # no existen. Una fila con el valor vacío es un cambio del dominio.
        raise InaInvalido(
            f"{ruta.name} fila {n}: valor vacío; el hueco de una serie son filas que no existen, no filas sin valor"
        )
    try:
        valor = float(cruda["valor"])
    except ValueError:
        raise InaInvalido(f"{ruta.name} fila {n}: valor ilegible {cruda['valor']!r}; se esperaba un número") from None
    var = SERIES[id_serie]["var"] if id_serie in SERIES else None
    if var is not None:
        vmin, vmax = RANGO_FISICO[var]
        if not vmin <= valor <= vmax:
            raise InaInvalido(
                f"{ruta.name} fila {n}: valor {valor} {UNIDADES[var]} fuera del rango físico del {var} "
                f"({vmin} a {vmax}, medido sobre el histórico completo)"
            )
    return {
        "id": int(cruda["id"]),
        "serie_id": se,
        "var": var or "",
        "unidad": UNIDADES.get(var, ""),
        "instancia": instante,
        "dia_local": dia_local(instante),
        "valor": valor,
        "carga": carga,
        "nombre_fuente": cruda.get("nombre") or "",
    }


def observaciones(id_serie: int, desde: date, hasta: date, *, crudo: Optional[Path] = None) -> list[dict]:
    """Las observaciones de una serie declarada en `SERIES`, ya tipadas. **Sale a la red**; con
    `crudo`, lee ese archivo (lo que `bajar()` escribió o un fixture) y no toca la red.

    `desde` y `hasta` son días locales de Uruguay: van al API con el offset -03:00 y la respuesta
    vuelve con instantes en Z. El lector no filtra cadencia: trae las filas que el API tiene, y
    la misma serie trae días con 2 lecturas (medido: 2.524 de 34.932).

    Con `crudo` valida el mismo contrato y el mismo rango (es otra bajada, revisada en frío).
    Las filas vuelven ordenadas por `instancia` (el API trae así y se reafirma)."""
    if id_serie not in SERIES:
        raise InaInvalido(
            f"serie {id_serie} no está declarada; las medidas en el 2026-10-27 son "
            f"{sorted(SERIES)}. Si hace falta otra, se mide con datos de verdad y "
            "se agrega a SERIES con su unidad y su rango"
        )
    if not desde < hasta:
        raise InaInvalido(
            f"serie {id_serie}: el rango pedido es desde={desde} hasta={hasta}; "
            "el API responde HTTP 200 con cuerpo vacío a un rango inválido"
        )
    desde_dt = datetime(desde.year, desde.month, desde.day, 0, 0, tzinfo=timezone.utc)
    hasta_dt = datetime(hasta.year, hasta.month, hasta.day, 23, 59, 59, tzinfo=timezone.utc)
    if crudo is not None:
        crudo = Path(crudo)
        if not crudo.is_file():
            raise InaInvalido(f"{crudo}: el archivo no está en el disco")
        texto = crudo.read_text(encoding=CODIFICACION)
        ruta = Path(crudo)
    else:
        cuerpo = red.pedir(url_observaciones(id_serie, desde, hasta))
        if not cuerpo.strip():
            raise InaInvalido(
                f"serie {id_serie}: el API respondió cuerpo vacío al rango {desde} a {hasta} "
                "(HTTP 200): pasa con series `has_obs: false` y con rangos inválidos, ya "
                "validados acá; mirar la metadata de la serie"
            )
        texto = cuerpo.decode(CODIFICACION)
        ruta = Path(f"serie_{id_serie}.csv")

    filas = list(csv.reader(io.StringIO(texto)))
    if not filas:
        raise InaInvalido(f"serie {id_serie}: el cuerpo no trae filas para {desde} a {hasta}")
    encabezado = [c.replace("﻿", "").strip() for c in filas[0]]
    if encabezado != COLUMNAS:
        raise InaInvalido(
            f"serie {id_serie}: encabezado inesperado {encabezado}; el medida es {COLUMNAS}: cambió el formato del API"
        )
    tipadas = []
    for i, campos in enumerate(filas[1:], start=2):
        if len(campos) != len(COLUMNAS):
            raise InaInvalido(f"{ruta.name} fila {i}: {len(campos)} columnas, se esperaban {len(COLUMNAS)}")
        cruda = dict(zip(COLUMNAS, (c.strip() for c in campos)))
        if not any(cruda.values()):
            continue
        tipadas.append(_fila(cruda, id_serie, desde_dt, hasta_dt, ruta, i))
    if not tipadas:
        raise InaInvalido(f"serie {id_serie}: ninguna fila de datos en el cuerpo")
    tipadas.sort(key=lambda x: x["instancia"])
    return tipadas


def metadata(id_serie: int) -> dict:
    """La metadata del API de una serie: estación, variable y los niveles de alerta de la propia
    escala. **Sale a la red.**

    El id es de serie (77, 928…), no de estación (el API tiene los dos espacios de id y se midió
    que se confunden: la estación 283 "CONCORDIA (DNCPVN-61…)" es de Brasil)."""
    cuerpo = red.pedir(f"{BASE}/series/{id_serie}")
    if not cuerpo.strip():
        raise InaInvalido(f"serie {id_serie}: la metadata vino vacía; ¿existe el id?")
    d = json.loads(cuerpo.decode(CODIFICACION))
    e = d.get("estacion") or {}
    if not e:
        raise InaInvalido(f"serie {id_serie}: la metadata no trae la estación (¿el id existe?)")
    var = (d.get("var") or {}).get("var", "")
    return {
        "serie_id": d["id"],
        "estacion_id": e.get("id"),
        "nombre": e.get("nombre"),
        "pais": e.get("pais"),
        "rio": e.get("rio"),
        "red": (e.get("red") or {}).get("nombre"),
        "tabla": e.get("tabla"),
        "nivel_alerta": e.get("nivel_alerta"),
        "nivel_evacuacion": e.get("nivel_evacuacion"),
        "nivel_aguas_bajas": e.get("nivel_aguas_bajas"),
        "var": var,
        "unidad": UNIDADES.get(var, ""),
    }


def resumen(filas: list[dict]) -> dict:
    """Las cuentas que dejan ver las trampas sin romper la lectura.

    Declara los **extremos por serie** (es lo que deja ver un valor raro sin rechazar el archivo),
    la fecha de la **última carga** (la frescura del dato: Concordia del 15/07/2026 y nada lo
    dice en el cuerpo), y las filas con la columna `nombre` distinta de la esperada (2 legítimas
    en 37.876, con el valor bien puesto, así que no se rechazan: se cuentan)."""
    if not filas:
        raise InaInvalido("resumen() necesita al menos una fila")
    series_out = {}
    for sid in sorted({f["serie_id"] for f in filas}):
        s = [f for f in filas if f["serie_id"] == sid]
        v = [f["valor"] for f in s]
        dias = [f["dia_local"] for f in s]
        series_out[sid] = {
            "n": len(s),
            "unidad": s[0]["unidad"],
            "min": min(v),
            "max": max(v),
            "primer_dia": min(dias),
            "ultimo_dia": max(dias),
            "ultima_carga": max(f["carga"] for f in s),
            "dias_con_mas_de_una_lectura": sum(1 for c in Counter(dias).values() if c > 1),
        }
    return {
        "filas": len(filas),
        "series_distintas": len(series_out),
        "series": series_out,
        "nombre_inesperado": sum(1 for f in filas if f["nombre_fuente"] not in ("", NOMBRE_FUENTE)),
    }


def descargar(destino: Path, *, dias: int = 30, series: Sequence[int] = tuple(SERIES)) -> dict[int, Path]:
    """La ventana de los últimos `dias` días de cada serie, a `destino/serie_{id}.csv`.
    **Sale a la red.** El `timeend` de la URL va hasta HOY (hora de Uruguay) para que la fila del
    día entre si ya está cargada; la frescura de lo bajado la decide el consumidor contra
    `timeupdate`, contra el reloj del sello."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    hasta = dia_local(datetime.now(timezone.utc))
    desde = hasta - timedelta(days=dias)
    return {sid: red.bajar(url_observaciones(sid, desde, hasta), destino / f"serie_{sid}.csv") for sid in series}


def sello(
    id_serie: int,
    ruta: Path,
    *,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    filas: Optional[int] = None,
):
    """El sello de procedencia de una serie bajada: fuente, URL exacta del pedido, fecha, sha256 y filas."""
    s = SERIES[id_serie]
    url = url_observaciones(id_serie, desde, hasta) if desde and hasta else None
    return procedencia.sello(f"INA a5 — {s['nombre']} ({s['var']})", ruta=Path(ruta), url=url, filas=filas)


def _id_de_serie(ruta: Path) -> int:
    """El id de serie del nombre del archivo bajado (`serie_77.csv`). Nada de adivinar el contenido."""
    p = Path(ruta)
    try:
        return int(p.stem.split("_")[1])
    except (IndexError, ValueError):
        raise InaInvalido(f"{p}: el archivo no se llama serie_<id>.csv, no se puede inferir la serie") from None


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos ina", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "obs", "resumen", "meta"])
    ap.add_argument("ruta", type=Path, nargs="?")
    ap.add_argument("--dias", type=int, default=30, help="ventana de bajado en días")
    ap.add_argument(
        "--serie", type=int, action="append", help="repetible; sólo están declaradas 77, 78, 79, 926, 927, 928"
    )
    ap.add_argument("--desde", type=_fecha_iso, help="AAAA-MM-DD; con obs/resumen, la ventana que se declara")
    ap.add_argument("--hasta", type=_fecha_iso)
    ap.add_argument("--limite", type=int, default=10)
    args = ap.parse_args(argv)

    if args.accion == "meta":
        print(_completar_metadata(metadata(args.serie[0] if args.serie else 77)))
        return 0
    if args.accion == "bajar":
        if args.ruta is None:
            ap.error("bajar necesita la carpeta de destino")
        for sid, p in sorted(descargar(args.ruta, dias=args.dias, series=tuple(args.serie or SERIES)).items()):
            print(f"{sid:>5}  {p}")
        return 0
    if args.ruta is None:
        ap.error(f"{args.accion} necesita una ruta")
    # obs/resumen leen lo ya bajado: la ventana se declara y es la misma con la que se bajo
    desde = args.desde or date(1900, 1, 1)
    hasta = args.hasta or date(2100, 12, 31)
    if args.accion == "obs":
        ruta = args.ruta
        sid = args.serie[0] if args.serie else _id_de_serie(ruta)
        filas = observaciones(sid, desde, hasta, crudo=ruta)
        for f in filas[: args.limite]:
            carga = f["carga"].isoformat()
            print(
                f"{f['serie_id']:>4} {f['instancia'].isoformat():<25} {f['valor']:>10.2f} "
                f"{f['unidad']:<5} carga {carga}"
            )
        return 0
    archivos = sorted(args.ruta.glob("serie_*.csv")) if args.ruta.is_dir() else [args.ruta]
    filas = []
    for a in archivos:
        filas += observaciones(_id_de_serie(a), desde, hasta, crudo=a)
    r = resumen(filas)
    print(
        f"{r['filas']} filas de {r['series_distintas']} series "
        f"(nombre de la puntuales inesperado: {r['nombre_inesperado']})"
    )
    for sid, s in r["series"].items():
        print(
            f"  serie {sid:<5} {s['n']:>6} filas · {s['primer_dia']} a {s['ultimo_dia']} · "
            f"{s['min']:>9.2f} a {s['max']:>10.2f} {s['unidad']}"
        )
        print(
            f"         última carga {s['ultima_carga'].isoformat(timespec='minutes')} · "
            f"días con 2 lecturas: {s['dias_con_mas_de_una_lectura']}"
        )
    return 0


def _fecha_iso(s: str) -> date:
    return date.fromisoformat(s)


def _completar_metadata(m: dict) -> str:
    e = m
    return (
        f"serie {e['serie_id']} | {e['nombre']} ({e['pais']}, {e['rio']}) | red: {e['red']} "
        f"| var {e['var']} ({e['unidad']}) | alerta {e['nivel_alerta']} | evacuación {e['nivel_evacuacion']}"
    )


if __name__ == "__main__":
    sys.exit(main())
