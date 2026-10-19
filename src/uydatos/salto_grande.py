"""Estaciones hidrometeorológicas de la Comisión Técnica Mixta de Salto Grande.

`https://www.saltogrande.org/ws.php` es un web service SOAP público que publica, cada 15 a 60
minutos, las estaciones de la cuenca del río Uruguay, de las dos orillas (75 activas en octubre
de 2026). El WSDL (`?wsdl`) declara tres operaciones:

- `ListaEstacionesTelemetricas(Activas: bool) -> Estacion[]`: las estaciones (`leer_estaciones`).
- `DatosHidrometeorologicos(idEstacion, fechaDesde, fechaHasta) -> DatoHidrometeorologico[]`:
  lecturas cada 15 minutos de `P`, `H` y `Q` (`leer_datos`, `descargar_datos`). En la estación
  Salto hay datos desde al menos 2017.
- `HidroSerieHistorica(idEstacion, variable, fechaDesde, fechaHasta)`: la misma serie, de a una
  variable (medido: devuelve los mismos valores que la anterior). No se implementa.

Las trampas
-----------
1. **La respuesta es SOAP encoded y los elementos se llaman `item`.** El arreglo viene como
   `<return SOAP-ENC:arrayType="ns1:Estacion[75]"><item>...</item></return>`. Un lector que
   busque `findall('Estacion')` devuelve **lista vacía sin error**: "0 estaciones" parece un
   servicio caído y es un lector roto. Un arreglo vacío se rechaza.
2. **`Latitud`/`Longitud` son `nillable`.** Una estación puede venir sin coordenada: queda en
   `None` y no entra en el ranking de cercanía.
3. **El WSDL no declara unidades.** Los valores se devuelven crudos, sin etiquetarlos como mm o
   m³/s: inventar la unidad es afirmar lo que no se midió.

Y las de las lecturas, medidas el 10/10/2026:

4. **`-999` es "sin dato".** La estación Salto publica `Q = -999` en todas sus lecturas: leído como
   número, un promedio de caudal se hunde. Se devuelve `None` (`SIN_DATO`).
5. **Una fecha en otro formato no da error: da una lista vacía.** `08/10/2026` devuelve cero
   lecturas, igual que un período sin datos. Las fechas se reciben como `date` y viajan en ISO.
6. **`fechaHasta` es un instante, las 00:00 de ese día**, no el día entero. Para incluir el día
   hay que pedir hasta el siguiente (`tramos`).
7. **Más de 31 días por consulta es un SOAP Fault** ('Diferencia de fechas mayor a 31 días').
   `tramos` parte los rangos largos; el fault se rechaza con su mensaje.
8. **Hay huecos**: un mes puede traer un día menos de lecturas. `cobertura` cuenta recibidas
   contra esperadas (96 por día) en vez de esconderlo.

Uso:
    python -m uydatos.salto_grande bajar estaciones.xml
    python -m uydatos.salto_grande cerca estaciones.xml -31.383 -57.960
    python -m uydatos.salto_grande lecturas A501258E 2026-10-01 2026-10-09
"""

from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

from uydatos import red
from uydatos.errores import DatosInvalidos

WS = "https://www.saltogrande.org/ws.php"
NS = "https://www.saltogrande.org/ws.php"
ENCABEZADO_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"

SIN_DATO = -999.0
LECTURAS_POR_DIA = 96  # una cada 15 minutos
MAX_DIAS_POR_CONSULTA = 31
VARIABLES = ("P", "H", "Q")


class SaltoGrandeInvalido(DatosInvalidos):
    """La respuesta no cumple el contrato del web service."""


def _texto(item: ET.Element, tag: str) -> Optional[str]:
    """El texto de un hijo, o `None` si falta o viene nil."""
    hijo = item.find(tag)
    if hijo is None or hijo.text is None or hijo.text.strip() == "":
        return None
    return hijo.text


def _float(valor: Optional[str]) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def leer_estaciones(ruta: Path) -> list[dict]:
    """Lee una respuesta de `ListaEstacionesTelemetricas`. Rechaza en vez de arreglar.

    Devuelve, por estación, `id`, `nombre`, `lat` (float | None), `lon` (float | None),
    `fecha` (str | None, último dato) y `variables` (list[str]).
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise SaltoGrandeInvalido(f"{ruta}: el archivo no está en el disco")
    try:
        raiz = ET.parse(ruta).getroot()
    except ET.ParseError as e:
        raise SaltoGrandeInvalido(f"{ruta}: XML ilegible ({e})") from None

    ret = raiz.find(f".//{{{NS}}}return")
    if ret is None:
        ret = raiz.find(".//return")
    if ret is None:
        raise SaltoGrandeInvalido(f"{ruta}: no hay un nodo <return>: no parece una respuesta SOAP de este servicio")

    estaciones = []
    for item in ret.findall("item"):
        variables = []
        bloque = item.find("Variables")
        if bloque is not None:
            variables = [v.text.strip() for v in bloque.findall("item") if v.text and v.text.strip()]
        estaciones.append(
            {
                "id": _texto(item, "Id") or "",
                "nombre": _texto(item, "Nombre") or "",
                "lat": _float(_texto(item, "Latitud")),
                "lon": _float(_texto(item, "Longitud")),
                "fecha": _texto(item, "Fecha"),
                "variables": variables,
            }
        )

    if not estaciones:
        raise SaltoGrandeInvalido(
            f"{ruta}: respuesta SOAP sin estaciones. No es un resultado válido: el servicio puede "
            f"estar caído, o el lector busca el tag equivocado."
        )
    return estaciones


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine: distancia en línea recta, no de manejo."""
    radio = 6371.0
    p = math.radians
    dlat, dlon = p(lat2 - lat1), p(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p(lat1)) * math.cos(p(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(h))


def estaciones_cerca_de(
    estaciones: list[dict], lat: float, lon: float, radio_km: Optional[float] = None
) -> list[tuple[dict, float]]:
    """Las estaciones ordenadas por distancia al punto. Las que no tienen coordenada quedan afuera."""
    con_coord = [e for e in estaciones if e["lat"] is not None and e["lon"] is not None]
    ranking = sorted(((e, distancia_km(lat, lon, e["lat"], e["lon"])) for e in con_coord), key=lambda par: par[1])
    if radio_km is not None:
        ranking = [par for par in ranking if par[1] <= radio_km]
    return ranking


# --- Lecturas -------------------------------------------------------------------------------------


def _rechazar_fault(raiz: ET.Element, ruta: Path) -> None:
    fault = raiz.find(f".//{{{ENCABEZADO_SOAP}}}Fault")
    if fault is not None:
        motivo = (fault.findtext("faultstring") or "").strip() or "sin mensaje"
        raise SaltoGrandeInvalido(f"{ruta.name}: el servicio respondió con un error: {motivo}")


def _valor(item: ET.Element, tag: str) -> Optional[float]:
    v = _float(_texto(item, tag))
    return None if v is None or v == SIN_DATO else v


def leer_datos(ruta: Path) -> list[dict]:
    """Lee una respuesta de `DatosHidrometeorologicos`: `[{fecha, P, H, Q}]`, con `-999` como None.

    Rechaza un SOAP Fault (con su mensaje) y una fecha repetida. Una lista vacía es válida: hay
    períodos sin lecturas, y quien llama mide la cobertura.
    """
    ruta = Path(ruta)
    try:
        raiz = ET.parse(ruta).getroot()
    except ET.ParseError as e:
        raise SaltoGrandeInvalido(f"{ruta}: XML ilegible ({e})") from None
    _rechazar_fault(raiz, ruta)
    ret = raiz.find(f".//{{{NS}}}return")
    if ret is None:
        ret = raiz.find(".//return")
    if ret is None:
        raise SaltoGrandeInvalido(f"{ruta}: no hay un nodo <return>: no parece una respuesta de este servicio")
    filas, vistas = [], set()
    for item in ret.findall("item"):
        texto = _texto(item, "Fecha")
        try:
            fecha = datetime.strptime(texto or "", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise SaltoGrandeInvalido(f"{ruta}: fecha ilegible {texto!r}") from None
        if fecha in vistas:
            raise SaltoGrandeInvalido(f"{ruta}: lectura repetida {fecha}")
        vistas.add(fecha)
        filas.append({"fecha": fecha, **{v: _valor(item, v) for v in VARIABLES}})
    return sorted(filas, key=lambda f: f["fecha"])


def tramos(desde: date, hasta: date) -> list[tuple[date, date]]:
    """Los pedidos para cubrir `desde`..`hasta` **inclusive**: pares `(ini, fin)` con `fin`
    exclusivo (las 00:00 del día siguiente) y a lo sumo 31 días cada uno."""
    if desde > hasta:
        raise ValueError(f"desde {desde} es posterior a hasta {hasta}")
    fin_total, out, ini = hasta + timedelta(days=1), [], desde
    while ini < fin_total:
        fin = min(ini + timedelta(days=MAX_DIAS_POR_CONSULTA), fin_total)
        out.append((ini, fin))
        ini = fin
    return out


def _sobre_datos(estacion: str, desde: date, hasta: date) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<SOAP-ENV:Envelope xmlns:SOAP-ENV="{ENCABEZADO_SOAP}" xmlns:ns1="{NS}">'
        "<SOAP-ENV:Body><ns1:DatosHidrometeorologicos>"
        f"<idEstacion>{estacion}</idEstacion>"
        f"<fechaDesde>{desde.isoformat()}</fechaDesde><fechaHasta>{hasta.isoformat()}</fechaHasta>"
        "</ns1:DatosHidrometeorologicos></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    ).encode("utf-8")


def descargar_datos(estacion: str, desde: date, hasta: date, destino: Path) -> Path:
    """Baja las lecturas entre las 00:00 de `desde` y las 00:00 de `hasta` (1 a 31 días) a
    `destino`. **Sale a la red.** Para un rango cualquiera, recorrer `tramos()`."""
    if not isinstance(desde, date) or not isinstance(hasta, date):
        raise TypeError("desde y hasta son `date`: un texto en otro formato devuelve cero lecturas sin error")
    if not 0 < (hasta - desde).days <= MAX_DIAS_POR_CONSULTA:
        raise ValueError(f"entre {desde} y {hasta}: se piden de 1 a {MAX_DIAS_POR_CONSULTA} días por consulta")
    if not estacion.isalnum():
        raise ValueError(f"estación {estacion!r}: se espera un id como A501258E")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cabeceras = {**CABECERAS_SOAP, "SOAPAction": f"{NS}#DatosHidrometeorologicos"}
    destino.write_bytes(red.pedir(WS, datos=_sobre_datos(estacion, desde, hasta), cabeceras=cabeceras))
    return destino


def resumen_diario(lecturas: list[dict], variable: str = "H") -> list[dict]:
    """Por día: mínimo, media y máximo de `variable`, y cuántas lecturas con dato lo forman."""
    if variable not in VARIABLES:
        raise ValueError(f"variable {variable!r}: P, H o Q")
    por_dia: dict[date, list[float]] = defaultdict(list)
    dias = set()
    for f in lecturas:
        dias.add(f["fecha"].date())
        if f[variable] is not None:
            por_dia[f["fecha"].date()].append(f[variable])
    out = []
    for d in sorted(dias):
        vs = por_dia.get(d, [])
        out.append(
            {
                "dia": d,
                "min": min(vs) if vs else None,
                "media": round(sum(vs) / len(vs), 3) if vs else None,
                "max": max(vs) if vs else None,
                "lecturas": len(vs),
            }
        )
    return out


def cobertura(lecturas: list[dict], desde: date, hasta: date) -> dict:
    """Lecturas esperadas (96 por día, `desde`..`hasta` inclusive) contra recibidas y con altura."""
    return {
        "esperadas": ((hasta - desde).days + 1) * LECTURAS_POR_DIA,
        "recibidas": len(lecturas),
        "con_H": sum(1 for f in lecturas if f["H"] is not None),
    }


CABECERAS_SOAP = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f"{NS}/ListaEstacionesTelemetricas"}


def _sobre(activas: bool) -> bytes:
    """El cuerpo SOAP de `ListaEstacionesTelemetricas`."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<SOAP-ENV:Envelope xmlns:SOAP-ENV="{ENCABEZADO_SOAP}" xmlns:ns1="{NS}">'
        "<SOAP-ENV:Body>"
        f"<ns1:ListaEstacionesTelemetricas><Activas>{'true' if activas else 'false'}</Activas>"
        "</ns1:ListaEstacionesTelemetricas>"
        "</SOAP-ENV:Body></SOAP-ENV:Envelope>"
    ).encode("utf-8")


def _pedido(activas: bool = True):
    """El pedido SOAP armado. Los tests miran su `User-Agent`; `descargar_lista()` sale por
    `red.pedir()`. El servidor responde 403 al `User-Agent` por defecto de Python y 200 al del
    paquete (medido el 09/10/2026)."""
    return red.pedido(WS, datos=_sobre(activas), cabeceras=CABECERAS_SOAP)


def descargar_lista(destino: Path, activas: bool = True) -> Path:
    """Baja la lista de estaciones a `destino`. **Única función que sale a la red.**"""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(red.pedir(WS, datos=_sobre(activas), cabeceras=CABECERAS_SOAP))
    return destino


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.salto_grande", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("archivo", type=Path)
    c = sub.add_parser("cerca", help="las estaciones más cercanas a un punto")
    c.add_argument("archivo", type=Path)
    c.add_argument("lat", type=float)
    c.add_argument("lon", type=float)
    c.add_argument("-n", type=int, default=5)
    lec = sub.add_parser("lecturas", help="resumen diario de la altura (H) de una estación")
    lec.add_argument("estacion", help="id de la estación, por ejemplo A501258E (Salto)")
    lec.add_argument("desde", type=date.fromisoformat)
    lec.add_argument("hasta", type=date.fromisoformat)
    args = ap.parse_args(argv)

    if args.orden == "bajar":
        print(f"bajado {descargar_lista(args.archivo)}")
        return 0
    if args.orden == "lecturas":
        import tempfile

        lecturas: list[dict] = []
        with tempfile.TemporaryDirectory() as carpeta:
            for i, (ini, fin) in enumerate(tramos(args.desde, args.hasta)):
                lecturas += leer_datos(descargar_datos(args.estacion, ini, fin, Path(carpeta) / f"{i}.xml"))
        fin_dia = datetime.combine(args.hasta + timedelta(days=1), datetime.min.time())
        lecturas = [f for f in lecturas if f["fecha"] < fin_dia]
        c = cobertura(lecturas, args.desde, args.hasta)
        print(f"{c['recibidas']} lecturas de {c['esperadas']} esperadas ({c['con_H']} con altura)")
        print("dia;min;media;max;lecturas")
        for r in resumen_diario(lecturas, "H"):
            print(f"{r['dia']};{r['min']};{r['media']};{r['max']};{r['lecturas']}")
        return 0
    estaciones = leer_estaciones(args.archivo)
    con_coord = sum(1 for e in estaciones if e["lat"] is not None)
    print(f"{len(estaciones)} estaciones ({con_coord} con coordenada)")
    for e, d in estaciones_cerca_de(estaciones, args.lat, args.lon)[: args.n]:
        print(f"  {d:6.1f} km  {e['nombre'][:30]:30}  {e['id']}  {e['fecha']}  {','.join(e['variables'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
