"""Estaciones hidrometeorológicas de la Comisión Técnica Mixta de Salto Grande.

`https://www.saltogrande.org/ws.php` es un web service SOAP público que publica, cada 15 a 60
minutos, las estaciones de la cuenca del río Uruguay, de las dos orillas (75 activas en octubre
de 2026). El WSDL (`?wsdl`) declara tres operaciones:

- `ListaEstacionesTelemetricas(Activas: bool) -> Estacion[]` — **la que implementa este módulo**.
- `DatosHidrometeorologicos(idEstacion, fechaDesde, fechaHasta) -> DatoHidrometeorologico[]`
  (campos `Fecha`, `P`, `H`, `Q`).
- `HidroSerieHistorica(idEstacion, variable, fechaDesde, fechaHasta) -> DatoSerieHistorica[]`.

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

Uso:
    python -m uydatos.salto_grande bajar estaciones.xml
    python -m uydatos.salto_grande cerca estaciones.xml -31.383 -57.960
"""

from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Sequence

WS = "https://www.saltogrande.org/ws.php"
NS = "https://www.saltogrande.org/ws.php"
ENCABEZADO_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"


class SaltoGrandeInvalido(ValueError):
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


def _pedido(activas: bool = True):
    """El pedido SOAP. Declara un User-Agent propio: el servidor responde 403 al de Python
    (`Python-urllib/*`) y 200 a cualquier otro (medido el 09/10/2026)."""
    import urllib.request

    from uydatos import USER_AGENT

    cuerpo = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<SOAP-ENV:Envelope xmlns:SOAP-ENV="{ENCABEZADO_SOAP}" xmlns:ns1="{NS}">'
        "<SOAP-ENV:Body>"
        f"<ns1:ListaEstacionesTelemetricas><Activas>{'true' if activas else 'false'}</Activas>"
        "</ns1:ListaEstacionesTelemetricas>"
        "</SOAP-ENV:Body></SOAP-ENV:Envelope>"
    ).encode("utf-8")
    return urllib.request.Request(
        WS,
        data=cuerpo,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{NS}/ListaEstacionesTelemetricas",
            "User-Agent": USER_AGENT,
        },
    )


def descargar_lista(destino: Path, activas: bool = True) -> Path:
    """Baja la lista de estaciones a `destino`. **Única función que sale a la red.**"""
    import urllib.request

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_pedido(activas), timeout=90) as r:  # noqa: S310 — host fijo
        destino.write_bytes(r.read())
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
    args = ap.parse_args(argv)

    if args.orden == "bajar":
        print(f"bajado {descargar_lista(args.archivo)}")
        return 0
    estaciones = leer_estaciones(args.archivo)
    con_coord = sum(1 for e in estaciones if e["lat"] is not None)
    print(f"{len(estaciones)} estaciones ({con_coord} con coordenada)")
    for e, d in estaciones_cerca_de(estaciones, args.lat, args.lon)[: args.n]:
        print(f"  {d:6.1f} km  {e['nombre'][:30]:30}  {e['id']}  {e['fecha']}  {','.join(e['variables'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
