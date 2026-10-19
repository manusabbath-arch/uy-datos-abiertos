"""Compras del Estado (ARCE), en el estándar internacional OCDS 1.1: qué compró cada organismo.

La ARCE publica un archivo por año (2002 en adelante) en el catálogo de datos abiertos, con un JSON
por mes de llamados (`l-MM-AAAA.json`) y de adjudicaciones (`a-MM-AAAA.json`). Este módulo lee las
adjudicaciones. La medición completa está en `docs/2026-10-10-datos-civicos.md`.

Las trampas, medidas el 10/10/2026 sobre 2024 y 2025
---------------------------------------------------
1. **El catálogo lo declara JSON y es un ZIP.** Un archivo que no es ZIP se rechaza.
2. **La estructura del ZIP cambia entre años**: en 2025 los JSON están en una carpeta `2025/`, en
   2024 sueltos. Buscar `/a-` en la ruta lee 2025 y en 2024 da cero compras sin error. Los archivos
   se eligen por su nombre base.
3. **El importe es el precio unitario, no el total**: el total es cantidad × precio, y 222.616 ítems
   de 2025 tienen cantidad distinta de 1. Ninguna adjudicación trae un total; los únicos totales
   del archivo son los montos **estimados** de los llamados.
4. **El total del año está dominado por registros imposibles.** Un solo ítem de UTE («colocación de
   alambrado de ley 7 hilos», 850.000 × 461.611) es el **77%** de lo adjudicado en pesos en 2024;
   otro («suministro, obra civil, montaje…», 798.848,2 × 88.760,8) el **53%** en 2025. Hay ítems con
   el monto en la cantidad y precio 1, y unidades «%». No se corrigen ni se descartan —no se sabe cuál
   es el valor real—: `resumen()` devuelve siempre los mayores ítems con su peso y su `ocid`, y la
   concentración. **Un total de este archivo no se cita sin mirarlos.**
5. **El archivo de adjudicaciones trae también llamados (1.005 en 2025) y anulaciones (3.146).**
   No son compras. Las anulaciones **no** apuntan a una adjudicación publicada (ninguna comparte
   `ocid` con una, ni en 2024 ni en 2025): son procedimientos que terminaron sin adjudicar.
6. **Las adjudicaciones tienen estado**: solo las `active` son gasto. En 2025 hay además 3
   `cancelled`, 5 `unsuccessful` y 8 `pending` (de 140.144 adjudicaciones, 140.128 activas; medido el
   14/10/2026 sobre el archivo bajado el 11/10). La primera versión de esta nota decía 360 y 110 para
   las dos primeras y no se pudo reproducir: la cifra que vale es la medida sobre el archivo.
7. **Las monedas están mezcladas**: pesos, dólares, euros, Unidades Indexadas (`UYI`), reales,
   francos suizos, rands, y 11.221 ítems de 2025 sin moneda. Cada moneda se suma aparte;
   `convertir()` las lleva a pesos con una cotización que le da quien llama.
8. **Hay adjudicaciones sin el campo `buyer`**: el comprador sale de `parties`. Algunas no lo traen
   en ningún lugar (96 en 2024, 53 en 2025) y otras no traen proveedor (4.151 en 2025): se leen, se
   suman y se cuentan aparte, en vez de rechazar el año entero por unos registros.

Sobre los proveedores: las adjudicaciones traen nombre e identificación de cada proveedor, que puede
ser una persona física. Este módulo los devuelve como los publica la ARCE; qué se expone de una
persona física es una decisión de quien los use.

Uso:
    python -m uydatos.compras bajar 2025 datos/compras2025.zip
    python -m uydatos.compras resumen datos/compras2025.zip --buscar ambulancia
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

from uydatos import catalogo, red
from uydatos.errores import DatosInvalidos

DATASET = "arce-datos-historicos-de-compras"
_ADJUDICACIONES = re.compile(r"^a-(\d{2})-(\d{4})\.json$")

# Código ISO de la moneda en OCDS -> código de la cotización del BCU (consultado en awsbcumonedas el
# 10/10/2026). Dólar y real: el billete, que es la serie que usa el resto del paquete; qué cotización
# corresponde para valuar un contrato no lo decide este módulo.
BCU_POR_MONEDA = {
    "USD": 2225,
    "EUR": 1111,
    "BRL": 1001,
    "UYI": 9800,
    "CHF": 5900,
    "ZAR": 1620,
}


class ComprasInvalido(DatosInvalidos):
    """El archivo no cumple el contrato de la ARCE."""


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper().strip()


def _numero(valor, donde: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ComprasInvalido(f"{donde}: {valor!r} no es un número")
    return float(valor)


def _comprador(r: dict) -> Optional[dict]:
    """El comprador, de `buyer` o de `parties`. Algunas adjudicaciones solo traen al proveedor (96 en
    2024, 53 en 2025): devuelven None y `resumen()` las cuenta."""
    b = r.get("buyer") or next((p for p in r.get("parties", []) if "buyer" in (p.get("roles") or [])), None)
    return {"id": str(b.get("id", "")), "nombre": str(b.get("name", "")).strip()} if b else None


def _items(award: dict, donde: str) -> tuple[list[dict], dict[str, float], float]:
    items, importes, sin_moneda = [], defaultdict(float), 0.0
    for it in award.get("items") or []:
        valor = (it.get("unit") or {}).get("value") or {}
        cantidad = _numero(it.get("quantity", 1), f"{donde} cantidad")
        precio = _numero(valor.get("amount", 0), f"{donde} precio")
        moneda = valor.get("currency")
        clas = it.get("classification") or {}
        importe = round(cantidad * precio, 2)
        items.append(
            {
                "descripcion": str(clas.get("description") or "").strip(),
                "catalogo": str(clas.get("id") or ""),
                "esquema": str(clas.get("scheme") or ""),
                "cantidad": cantidad,
                "precio_unitario": precio,
                "moneda": moneda,
                "importe": importe,
            }
        )
        if moneda:
            importes[moneda] += importe
        else:
            sin_moneda += importe
    return items, {m: round(v, 2) for m, v in importes.items()}, round(sin_moneda, 2)


def leer_adjudicaciones(ruta: Path) -> list[dict]:
    """Las adjudicaciones de un archivo anual. Una por proveedor adjudicado: `ocid`, `fecha`,
    `comprador`, `proveedor` (o None), `estado`, `items`, `importes` (por moneda) y `sin_moneda`.

    Saltea los llamados y las anulaciones, que no son compras. Devuelve todas las adjudicaciones
    con su estado: `resumen()` suma solo las activas.
    """
    ruta = Path(ruta)
    if not zipfile.is_zipfile(ruta):
        raise ComprasInvalido(
            f"{ruta.name}: no es un ZIP. El catálogo lo declara JSON y es un ZIP con un JSON por mes."
        )
    out = []
    with zipfile.ZipFile(ruta) as z:
        nombres = sorted(n for n in z.namelist() if _ADJUDICACIONES.match(n.rsplit("/", 1)[-1]))
        if not nombres:
            raise ComprasInvalido(f"{ruta.name}: ningún archivo a-MM-AAAA.json de adjudicaciones adentro")
        for nombre in nombres:
            try:
                datos = json.loads(z.read(nombre).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ComprasInvalido(f"{ruta.name}/{nombre}: JSON ilegible ({e})") from None
            for r in datos.get("releases") or []:
                if "award" not in (r.get("tag") or []):
                    continue
                fecha = datetime.fromisoformat(str(r["date"]).replace("Z", "+00:00")).date()
                comprador = _comprador(r)
                for a in r.get("awards") or []:
                    items, importes, sin_moneda = _items(a, f"{nombre} {r.get('ocid')}")
                    sup = (a.get("suppliers") or [None])[0]
                    out.append(
                        {
                            "ocid": r["ocid"],
                            "fecha": fecha,
                            "comprador": comprador,
                            "proveedor": {"id": sup.get("id"), "nombre": sup.get("name")} if sup else None,
                            "estado": a.get("status"),
                            "items": items,
                            "importes": importes,
                            "sin_moneda": sin_moneda,
                        }
                    )
    return out


def resumen(adjudicaciones: list[dict], organismo: str = "", buscar: str = "") -> dict:
    """Totales por moneda de las adjudicaciones activas, opcionalmente de un organismo (por nombre o
    id) y de los ítems cuya descripción contiene `buscar` (sin importar tildes ni mayúsculas)."""
    org, txt = _sin_tildes(organismo), _sin_tildes(buscar)
    excluidas: Counter = Counter()
    importes: dict[str, float] = defaultdict(float)
    por_comprador: dict[str, dict] = {}
    n, n_items, sin_moneda, sin_proveedor, sin_comprador = 0, 0, 0.0, 0, 0
    en_pesos: list[tuple[float, dict, dict, str]] = []
    for a in adjudicaciones:
        comp = a["comprador"] or {"id": "", "nombre": "(sin comprador en el archivo)"}
        if org and org not in (_sin_tildes(comp["nombre"]), _sin_tildes(comp["id"])):
            continue
        items = [i for i in a["items"] if not txt or txt in _sin_tildes(i["descripcion"])]
        if not items:
            continue
        if a["estado"] != "active":
            excluidas[a["estado"]] += 1
            continue
        n += 1
        n_items += len(items)
        sin_proveedor += a["proveedor"] is None
        sin_comprador += a["comprador"] is None
        clave = comp["id"]
        if clave not in por_comprador:
            por_comprador[clave] = {
                "id": clave,
                "nombre": comp["nombre"],
                "adjudicaciones": 0,
                "importes": defaultdict(float),
            }
        c = por_comprador[clave]
        c["adjudicaciones"] += 1
        for i in items:
            if i["moneda"] == "UYU":
                en_pesos.append((i["importe"], i, comp, a["ocid"]))
            if i["moneda"]:
                importes[i["moneda"]] += i["importe"]
                c["importes"][i["moneda"]] += i["importe"]
            else:
                sin_moneda += i["importe"]
    compradores = sorted(por_comprador.values(), key=lambda c: -c["importes"].get("UYU", 0.0))
    en_pesos.sort(key=lambda x: -x[0])
    total_uyu = importes.get("UYU", 0.0)
    mayores = [
        {
            "ocid": ocid,
            "comprador": comp["nombre"],
            "descripcion": i["descripcion"],
            "cantidad": i["cantidad"],
            "precio_unitario": i["precio_unitario"],
            "importe": i["importe"],
            "pct_del_total": round(100 * imp / total_uyu, 2),
        }
        for imp, i, comp, ocid in en_pesos[:5]
    ] if total_uyu else []  # fmt: skip
    concentracion = (
        {
            "mayor_item_pct": round(100 * en_pesos[0][0] / total_uyu, 2),
            "diez_mayores_pct": round(100 * sum(x[0] for x in en_pesos[:10]) / total_uyu, 2),
        }
        if total_uyu
        else None
    )
    return {
        "adjudicaciones": n,
        "items": n_items,
        "importes": {m: round(v, 2) for m, v in sorted(importes.items(), key=lambda kv: -kv[1])},
        "sin_moneda": round(sin_moneda, 2),
        "excluidas_por_estado": dict(excluidas),
        "sin_proveedor": sin_proveedor,
        "sin_comprador": sin_comprador,
        "mayores_items": mayores,
        "concentracion_uyu": concentracion,
        "por_comprador": [{**c, "importes": {m: round(v, 2) for m, v in c["importes"].items()}} for c in compradores],
    }


def convertir(importes: dict[str, float], fecha: date, cotizar: Callable[[int, date], Optional[float]]) -> dict:
    """Lleva importes por moneda a pesos uruguayos. `cotizar(codigo_bcu, fecha)` da la cotización (por
    ejemplo `bcu.cotizacion_del_dia(serie, fecha, hacia_atras=True)`). Lo que no tiene cotización queda
    en `sin_convertir`, sin inventarle un valor."""
    pesos, sin = 0.0, {}
    for moneda, monto in importes.items():
        if moneda == "UYU":
            pesos += monto
            continue
        codigo = BCU_POR_MONEDA.get(moneda)
        cot = cotizar(codigo, fecha) if codigo else None
        if cot is None:
            sin[moneda] = monto
        else:
            pesos += monto * cot
    return {"pesos": round(pesos, 2), "sin_convertir": sin}


def descargar(anio: int, destino: Path) -> Path:
    """Baja el archivo de un año (un ZIP de unos 30 MB). **Sale a la red.**"""
    recursos = {r["nombre"].strip(): r["url"] for r in catalogo.recursos(DATASET)}
    nombre = f"Compras {anio}"
    if nombre not in recursos:
        raise ComprasInvalido(f"{DATASET}: no hay «{nombre}». Hay: {sorted(recursos)}")
    p = red.bajar(recursos[nombre], Path(destino))
    if not zipfile.is_zipfile(p):
        raise ComprasInvalido(f"{p.name}: lo bajado no es un ZIP")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.compras", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("anio", type=int)
    b.add_argument("destino", type=Path)
    r = sub.add_parser("resumen")
    r.add_argument("archivo", type=Path)
    r.add_argument("--organismo", default="")
    r.add_argument("--buscar", default="")
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"bajado {descargar(args.anio, args.destino)}")
        return 0
    s = resumen(leer_adjudicaciones(args.archivo), args.organismo, args.buscar)
    print(f"{s['adjudicaciones']} adjudicaciones activas, {s['items']} ítems; excluidas: {s['excluidas_por_estado']}")
    print(f"importes por moneda: {s['importes']}; sin moneda: {s['sin_moneda']}")
    for c in s["por_comprador"][:10]:
        print(f"  {c['nombre'][:50]:50} {c['adjudicaciones']:>6}  {c['importes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
