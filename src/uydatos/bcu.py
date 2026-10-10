"""Cotizaciones del Banco Central del Uruguay, desde su web service SOAP público.

Monedas declaradas (códigos y nombres tal como los devuelve `awsbcumonedas`):

- **2225, DLS. USA BILLETE**.
- **9800, UNIDAD INDEXADA**: sigue al IPC de Uruguay día a día. Sirve de deflactor para comparar
  pesos de dos fechas sin bajar el IPC del INE aparte (`a_pesos_de`).
- **501, PESO ARG.BILLETE** y **1001, REAL BILLETE**: las monedas de las dos fronteras. Con el
  IPC de cada país (`uydatos.indec`, `uydatos.ibge`) arman el tipo de cambio real bilateral.

Las trampas, y por qué el lector las corta
-----------------------------------------
1. **Una respuesta mala igual se guarda.** `status 0` o `codigoerror` distinto de 0 se rechaza:
   no es "un mes sin cotización".
2. **Un archivo, una moneda.** La UI (~6,3) leída como dólar (~40) no da error, da un cálculo
   absurdo. Se rechaza el archivo que trae otra moneda o dos.
3. **Fines de semana y feriados no vienen.** `cotizacion_del_dia` devuelve `None` salvo que se
   pida `hacia_atras=True`, y aun así no salta más de `MAX_DIAS_ATRAS` días: un hueco de un mes
   es un archivo que falta, no un fin de semana.
4. **El mes en curso viene parcial.** `promedio_mensual` declara los días de cada mes.
5. **El servicio rechaza rangos largos** (`codigoerror 104`): `descargar` baja un mes por archivo.

Qué cotización corresponde para un fin fiscal (la del día, la del día hábil anterior, compra o
venta) **no lo decide este lector**. `TCC` y `TCV` vienen iguales en todo lo observado; se usa
`TCV` y se rechaza un día donde difieran, para que nadie elija en silencio.

Uso:
    python -m uydatos.bcu bajar DIRECTORIO 9800 2024-01 2026-09
    python -m uydatos.bcu serie DIRECTORIO 9800
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Sequence

from uydatos import red

URL = "https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcucotizaciones"

MONEDAS = {
    2225: "DLS. USA BILLETE",
    9800: "UNIDAD INDEXADA",
    501: "PESO ARG.BILLETE",
    1001: "REAL BILLETE",
    1111: "EURO",
    5900: "FRANCO SUIZO",
    1620: "RAND SUDAFRICANO",
}

MAX_DIAS_ATRAS = 7

_NS = "{Cotiza}"


class BcuInvalido(ValueError):
    """El archivo no cumple el contrato de la fuente."""


def _texto(nodo: ET.Element, etiqueta: str) -> str:
    hijo = nodo.find(f"{_NS}{etiqueta}")
    return (hijo.text or "").strip() if hijo is not None else ""


def leer_crudo(ruta: Path, moneda: int) -> dict[date, float]:
    """Lee una respuesta SOAP guardada y devuelve {fecha: TCV}. Rechaza en vez de arreglar."""
    ruta = Path(ruta)
    try:
        raiz = ET.parse(ruta).getroot()
    except ET.ParseError as e:
        raise BcuInvalido(f"{ruta.name}: no es XML ({e})") from e

    status = raiz.find(f".//{_NS}respuestastatus")
    if status is None:
        raise BcuInvalido(f"{ruta.name}: sin respuestastatus (no es una respuesta de cotizaciones)")
    st, cod = _texto(status, "status"), _texto(status, "codigoerror")
    if st != "1" or cod != "0":
        raise BcuInvalido(
            f"{ruta.name}: respuesta mala del BCU (status {st}, codigoerror {cod}: "
            f"{_texto(status, 'mensaje')!r}). No se lee como mes sin cotización."
        )

    serie: dict[date, float] = {}
    for dato in raiz.iter(f"{_NS}datoscotizaciones.dato"):
        m = _texto(dato, "Moneda")
        if m != str(moneda):
            raise BcuInvalido(f"{ruta.name}: trae la moneda {m}, se pidió {moneda} ({MONEDAS.get(moneda, '?')})")
        fecha = date.fromisoformat(_texto(dato, "Fecha"))
        tcc, tcv = float(_texto(dato, "TCC")), float(_texto(dato, "TCV"))
        if tcc != tcv:
            raise BcuInvalido(f"{ruta.name}: {fecha} trae TCC {tcc} != TCV {tcv}. Elegir una no es tarea del lector.")
        if fecha in serie:
            raise BcuInvalido(f"{ruta.name}: {fecha} repetido")
        serie[fecha] = tcv
    if not serie:
        raise BcuInvalido(f"{ruta.name}: respuesta buena sin datos")
    return serie


def leer_serie(directorio: Path, moneda: int) -> dict[date, float]:
    """Une los archivos `<moneda>_AAAA-MM.xml` de un directorio. Un día en dos archivos es error."""
    serie: dict[date, float] = {}
    patron = re.compile(rf"^{moneda}_\d{{4}}-\d{{2}}\.xml$")
    archivos = sorted(p for p in Path(directorio).iterdir() if patron.match(p.name))
    if not archivos:
        raise BcuInvalido(f"{directorio}: no hay archivos de la moneda {moneda}")
    for p in archivos:
        parte = leer_crudo(p, moneda)
        repetidos = serie.keys() & parte.keys()
        if repetidos:
            raise BcuInvalido(f"{p.name}: días ya leídos en otro archivo: {sorted(repetidos)[:3]}")
        serie.update(parte)
    return dict(sorted(serie.items()))


def cotizacion_del_dia(serie: dict[date, float], dia: date, hacia_atras: bool = False) -> Optional[float]:
    """La cotización de `dia`. Sin publicación: None, o la del último día previo si se pide."""
    if dia in serie:
        return serie[dia]
    if not hacia_atras:
        return None
    for atras in range(1, MAX_DIAS_ATRAS + 1):
        previo = dia - timedelta(days=atras)
        if previo in serie:
            return serie[previo]
    return None


def promedio_mensual(serie: dict[date, float]) -> list[dict]:
    """Promedio simple por mes calendario, con la cantidad de días publicados que lo forman."""
    por_mes: dict[str, list[float]] = defaultdict(list)
    for f, v in serie.items():
        por_mes[f"{f.year:04d}-{f.month:02d}"].append(v)
    return [
        {"mes": mes, "promedio": round(sum(vs) / len(vs), 6), "dias": len(vs)} for mes, vs in sorted(por_mes.items())
    ]


def a_pesos_de(montos: dict[str, float], base: str, ui: dict[str, float]) -> dict[str, float]:
    """Lleva montos mensuales ('AAAA-MM' -> pesos corrientes) a pesos del mes `base`.

    `ui` es {'AAAA-MM': UI promedio del mes}, por ejemplo
    `{f["mes"]: f["promedio"] for f in promedio_mensual(leer_serie(dir, 9800))}`.
    Un mes sin UI **se rechaza**: dejarlo nominal mezclaría pesos de dos fechas sin avisar.
    """
    faltan = sorted(m for m in [*montos, base] if m not in ui)
    if faltan:
        raise BcuInvalido(f"sin UI para {faltan}: bajar la serie 9800 de esos meses")
    return {m: v * ui[base] / ui[m] for m, v in montos.items()}


def _sobre(moneda: int, desde: date, hasta: date) -> bytes:
    return (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cot="Cotiza">'
        "<soapenv:Header/><soapenv:Body><cot:wsbcucotizaciones.Execute><cot:Entrada>"
        f"<cot:Moneda><cot:item>{moneda}</cot:item></cot:Moneda>"
        f"<cot:FechaDesde>{desde.isoformat()}</cot:FechaDesde><cot:FechaHasta>{hasta.isoformat()}</cot:FechaHasta>"
        "<cot:Grupo>0</cot:Grupo></cot:Entrada></cot:wsbcucotizaciones.Execute></soapenv:Body></soapenv:Envelope>"
    ).encode("utf-8")


def _meses(desde: str, hasta: str) -> list[tuple[date, date]]:
    a, m = map(int, desde.split("-"))
    fa, fm = map(int, hasta.split("-"))
    out = []
    while (a, m) <= (fa, fm):
        ini = date(a, m, 1)
        sig = date(a + (m == 12), m % 12 + 1, 1)
        out.append((ini, sig - timedelta(days=1)))
        a, m = sig.year, sig.month
    return out


def descargar(moneda: int, desde: str, hasta: str, destino: Path) -> list[Path]:
    """Baja un archivo por mes (`desde` y `hasta` en 'AAAA-MM') a `destino`.

    **Única función que sale a la red.** No pisa un archivo que ya existe: un mes cerrado no
    debería cambiar, y si cambia conviene verlo comparando, no sobreescribiendo. El mes en
    curso queda parcial: para completarlo, borrar ese archivo y volver a bajarlo.
    """
    if moneda not in MONEDAS:
        raise BcuInvalido(f"moneda {moneda} no declarada en MONEDAS")
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    escritos = []
    for ini, fin in _meses(desde, hasta):
        p = destino / f"{moneda}_{ini:%Y-%m}.xml"
        if p.exists():
            continue
        cuerpo = red.pedir(
            URL,
            datos=_sobre(moneda, ini, fin),
            cabeceras={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "Cotizaaction/AWSBCUCOTIZACIONES.Execute",
            },
        )
        p.write_bytes(cuerpo)
        escritos.append(p)
    return escritos


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.bcu", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar", help="baja un archivo por mes")
    b.add_argument("directorio", type=Path)
    b.add_argument("moneda", type=int, choices=sorted(MONEDAS))
    b.add_argument("desde", help="AAAA-MM")
    b.add_argument("hasta", help="AAAA-MM")
    s = sub.add_parser("serie", help="promedio mensual de lo bajado")
    s.add_argument("directorio", type=Path)
    s.add_argument("moneda", type=int, choices=sorted(MONEDAS))
    args = ap.parse_args(argv)

    if args.orden == "bajar":
        for p in descargar(args.moneda, args.desde, args.hasta, args.directorio):
            print(f"bajado {p.name}")
        return 0
    serie = leer_serie(args.directorio, args.moneda)
    print(f"# {MONEDAS[args.moneda]} ({args.moneda}): {len(serie)} días, {min(serie)} a {max(serie)}")
    print("mes;promedio;dias")
    for fila in promedio_mensual(serie):
        print(f"{fila['mes']};{fila['promedio']};{fila['dias']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
