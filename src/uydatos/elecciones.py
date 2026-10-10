"""Resultados electorales de la Corte Electoral, por mesa: totales, votos por partido y plan circuital.

La unidad es la **mesa** (comisión receptora de votos, `CRV`). Por elección, el catálogo publica
los totales por mesa, el desglose de votos por hoja y por lema, y el plan circuital (localidad,
local, tipo y accesibilidad de cada circuito). La medición completa está en
`docs/2026-10-10-datos-civicos.md`.

Las trampas, medidas el 10/10/2026
---------------------------------
1. **Los observados se cuentan en mesas especiales.** En cada mesa común, los votos por opción
   excluyen los observados (balotaje 2024: opciones + anulados + en blanco = no observados en las
   7.234 mesas comunes). Los observados se escrutan después en **mesas de observados**, que se
   reconocen por **0 habilitados y 0 emitidos** (118 en las nacionales 2024, 114 en el balotaje, 199 en
   las departamentales 2025). **No por la serie**: en 2024 termina en `ZZ`, en Montevideo 2025 es `A1`
   o `A2`. **Sumar todas las mesas da el escrutinio definitivo**; sumar solo las comunes —lo que hace
   cualquier mapa por circuito o por localidad— deja afuera los observados, que no tienen localidad.
   Cada mesa lleva su `tipo`.
2. **Hay mesas comunes con más emitidos que habilitados** (quien vota observado fuera de su
   circuito). Se cuentan en `controles`, no se corrigen.
3. **El voto a un partido es hoja + lema** (`HOJA_*` + `VOTO_LEMA*`): `votos_por_lema()` suma los dos.
4. **Los nombres cambian entre elecciones**: columnas (`TipoRegistro` / `TIPO_REGISTRO`), partidos
   («Partido Frente Amplio» / «FRENTE AMPLIO»: ver `normalizar_lema`) y tipo de circuito (`U` /
   `URBANO`). El lector normaliza las columnas sin importar mayúsculas ni guiones bajos.
5. **La columna del local se llama `"Local "`**, con un espacio al final.
6. **El departamento viene en un código propio de dos letras** (`FD` Florida, `FS` Flores, `RV`
   Rivera, `RO` Rocha…). Un código fuera de los 19 se rechaza.
7. **Hay mesas de los totales que no están en el plan circuital** (127 en 2024): las 118 de
   observados y 9 mesas de departamentos de frontera con 0 habilitados en las que todo voto es
   observado.

**Este módulo no lee la integración de las hojas de votación**, que trae la credencial cívica de
cada candidato (ver el documento, §3).

Uso:
    python -m uydatos.elecciones bajar balotaje-2024 totales datos/balotaje.csv
    python -m uydatos.elecciones resumen datos/balotaje.csv --departamento Salto
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, Sequence

from uydatos import catalogo, red

ELECCIONES: dict[str, dict] = {
    "nacionales-2024": {
        "dataset": "corte-electoral-elecciones-nacionales-2024",
        "archivos": {"totales": "totales", "desglose": "desglose", "plan": "plan-circuital"},
    },
    "balotaje-2024": {
        "dataset": "corte-electoral-balotaje_2024",
        "archivos": {"totales": "balotaje"},
    },
    "departamentales-2025": {
        "dataset": "corte-electoral-elecciones_departamentales_y_municipales_2025",
        "archivos": {"totales": "totales", "desglose": "desglose", "plan": "plan-circuital"},
    },
}

DEPARTAMENTOS = {
    "AR": "ARTIGAS",
    "CA": "CANELONES",
    "CL": "CERRO LARGO",
    "CO": "COLONIA",
    "DU": "DURAZNO",
    "FS": "FLORES",
    "FD": "FLORIDA",
    "LA": "LAVALLEJA",
    "MA": "MALDONADO",
    "MO": "MONTEVIDEO",
    "PA": "PAYSANDU",
    "RN": "RIO NEGRO",
    "RV": "RIVERA",
    "RO": "ROCHA",
    "SA": "SALTO",
    "SJ": "SAN JOSE",
    "SO": "SORIANO",
    "TA": "TACUAREMBO",
    "TT": "TREINTA Y TRES",
}

TIPOS_REGISTRO = {
    "HOJA_EN": ("nacional", "hoja"),
    "VOTO_LEMA": ("nacional", "lema"),
    "HOJA_ED": ("departamental", "hoja"),
    "VOTO_LEMA_ED": ("departamental", "lema"),
    "HOJA_EM": ("municipal", "hoja"),
    "VOTO_LEMA_EM": ("municipal", "lema"),
}

TIPOS_CIRCUITO = {"U": "urbano", "URBANO": "urbano", "R": "rural", "RURAL": "rural"}
SIN_MUNICIPIO = ("", "SIN MUNICIPIO", "NO APLICA")

_FIJAS_TOTALES = {
    "departamento": "departamento",
    "crv": "crv",
    "serie": "serie",
    "municipio": "municipio",
    "totalhabilitados": "habilitados",
    "totalvotosemitidos": "emitidos",
    "totalvotosnoobservados": "no_observados",
    "totalvotosobservados": "observados",
    "totalanulados": "anulados",
    "totalenblanco": "en_blanco",
}
_NUMERICAS = ("habilitados", "emitidos", "no_observados", "observados", "anulados", "en_blanco")


class EleccionesInvalido(ValueError):
    """El archivo no cumple el contrato de la Corte Electoral."""


def _clave(columna: str) -> str:
    """`TIPO_REGISTRO`, `TipoRegistro` y `Local ` se comparan iguales."""
    return columna.strip().replace("_", "").replace(" ", "").lower()


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper().strip()


def _leer_csv(ruta: Path) -> tuple[list[str], list[list[str]], list[str]]:
    ruta = Path(ruta)
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.reader(f))
    except (OSError, UnicodeDecodeError) as e:
        raise EleccionesInvalido(f"{ruta.name}: ilegible ({e})") from None
    if len(filas) < 2:
        raise EleccionesInvalido(f"{ruta.name}: sin filas de datos")
    encabezado = filas[0]
    for n, fila in enumerate(filas[1:], start=2):
        if fila and len(fila) != len(encabezado):
            raise EleccionesInvalido(f"{ruta.name} fila {n}: {len(fila)} campos, el encabezado tiene {len(encabezado)}")
    return [_clave(c) for c in encabezado], [f for f in filas[1:] if any(c.strip() for c in f)], encabezado


def _departamento(codigo: str, donde: str) -> tuple[str, str]:
    codigo = codigo.strip().upper()
    if codigo not in DEPARTAMENTOS:
        raise EleccionesInvalido(f"{donde}: departamento {codigo!r} no es uno de los 19 códigos de la Corte")
    return codigo, DEPARTAMENTOS[codigo]


def _entero(texto: str, donde: str) -> int:
    t = texto.strip()
    if not t:
        return 0
    try:
        return int(t)
    except ValueError:
        raise EleccionesInvalido(f"{donde}: {texto!r} no es un número entero") from None


def _municipio(texto: str) -> Optional[str]:
    t = texto.strip()
    return None if t.upper() in SIN_MUNICIPIO else t


def leer_totales(ruta: Path) -> list[dict]:
    """Una mesa por fila: departamento, crv, serie, municipio (o None), habilitados, emitidos,
    no_observados, observados, anulados, en_blanco y `opciones` (las columnas restantes: candidatos
    del balotaje, plebiscitos, blanco parcial), con su nombre original."""
    ruta = Path(ruta)
    columnas, filas, originales = _leer_csv(ruta)
    faltan = [c for c in ("departamento", "crv", "totalhabilitados", "totalvotosemitidos") if c not in columnas]
    if faltan:
        raise EleccionesInvalido(f"{ruta.name}: faltan columnas {faltan}: no parecen totales por mesa")
    mesas, vistas = [], set()
    for n, fila in enumerate(filas, start=2):
        donde = f"{ruta.name} fila {n}"
        m: dict = {"opciones": {}}
        for col, original, valor in zip(columnas, originales, fila):
            destino = _FIJAS_TOTALES.get(col)
            if destino == "departamento":
                m["codigo_departamento"], m["departamento"] = _departamento(valor, donde)
            elif destino == "crv":
                m["crv"] = _entero(valor, donde)
            elif destino == "serie":
                m["serie"] = valor.strip()
            elif destino == "municipio":
                m["municipio"] = _municipio(valor)
            elif destino:
                m[destino] = _entero(valor, donde)
            else:
                m["opciones"][original.strip()] = _entero(valor, donde)
        m.setdefault("municipio", None)
        for c in _NUMERICAS:
            m.setdefault(c, 0)
        especial = es_mesa_de_observados(m["habilitados"], m["emitidos"])
        m["tipo"] = "observados" if especial else "comun"
        clave = (m["codigo_departamento"], m["crv"])
        if clave in vistas:
            raise EleccionesInvalido(f"{donde}: mesa repetida {clave}")
        vistas.add(clave)
        mesas.append(m)
    return mesas


def es_mesa_de_observados(habilitados: int, emitidos: int) -> bool:
    """Las mesas donde se escrutan los votos observados: sin habilitados ni emitidos propios.

    Medido el 10/10/2026 en las tres elecciones, sin falsos positivos: lo declarado como observado en
    las mesas comunes y lo escrutado en estas difiere entre 0,48% y 0,72%. Una mesa sin habilitados
    pero **con** emitidos (las 9 de frontera de 2024, donde todo voto es observado) es común."""
    return habilitados == 0 and emitidos == 0


def mesas_de_observados(mesas: list[dict]) -> set[tuple[str, int]]:
    """Las mesas de observados de unos totales, como `(codigo_departamento, crv)`: para pasarle a
    `votos_por_lema(excluir=...)`, porque el desglose no trae habilitados ni emitidos."""
    return {(m["codigo_departamento"], m["crv"]) for m in mesas if m["tipo"] == "observados"}


def resumen(mesas: list[dict], departamento: str = "") -> dict:
    """Totales de un conjunto de mesas (todo el país, o un departamento por nombre o código).

    `opciones` suma **todas** las mesas, incluidas las de observados: es el escrutinio definitivo.
    `observados` es lo declarado en las mesas comunes y `escrutados_en_mesas_de_observados` lo que se
    contó en las especiales; la diferencia son observados que no llegaron a contarse.
    """
    if departamento:
        d = _sin_tildes(departamento)
        mesas = [m for m in mesas if m["departamento"] == d or m["codigo_departamento"] == d]
        if not mesas:
            raise EleccionesInvalido(
                f"departamento {departamento!r}: sin mesas. Los nombres son {sorted(DEPARTAMENTOS.values())}"
            )
    tot = {c: sum(m[c] for m in mesas) for c in _NUMERICAS}
    opciones: Counter = Counter()
    for m in mesas:
        opciones.update(m["opciones"])
    comunes = [m for m in mesas if m["tipo"] == "comun"]
    de_observados = [m for m in mesas if m["tipo"] == "observados"]
    excluyen = bool(opciones) and all(
        sum(m["opciones"].values()) + m["anulados"] + m["en_blanco"] == m["no_observados"] for m in comunes
    )
    return {
        "mesas": len(mesas),
        "mesas_comunes": len(comunes),
        "mesas_de_observados": len(de_observados),
        **tot,
        "escrutados_en_mesas_de_observados": sum(m["no_observados"] for m in de_observados),
        "participacion_pct": round(100 * tot["emitidos"] / tot["habilitados"], 2) if tot["habilitados"] else None,
        "opciones": dict(opciones),
        "en_mesas_comunes_las_opciones_excluyen_observados": excluyen,
        "controles": {
            "mesas_comunes_con_mas_emitidos_que_habilitados": sum(
                1 for m in comunes if m["emitidos"] > m["habilitados"]
            ),
            "mesas_comunes_sin_habilitados": sum(1 for m in comunes if m["habilitados"] == 0),
        },
    }


def leer_desglose(ruta: Path) -> list[dict]:
    """Una fila por (mesa, hoja o lema): departamento, crv, nivel (nacional, departamental o
    municipal), clase (hoja o lema), lema, hoja, municipio y votos."""
    ruta = Path(ruta)
    columnas, filas, _ = _leer_csv(ruta)
    i = {
        c: columnas.index(c)
        for c in ("tiporegistro", "departamento", "crv", "lema", "descripcion1", "cantidadvotos")
        if c in columnas
    }
    if len(i) < 6:
        raise EleccionesInvalido(f"{ruta.name}: no parece un desglose de votos (columnas {columnas})")
    i_mun = columnas.index("descripcion2") if "descripcion2" in columnas else None
    out = []
    for n, fila in enumerate(filas, start=2):
        donde = f"{ruta.name} fila {n}"
        tipo = fila[i["tiporegistro"]].strip()
        if tipo not in TIPOS_REGISTRO:
            raise EleccionesInvalido(
                f"{donde}: tipo de registro {tipo!r} desconocido; los declarados son {sorted(TIPOS_REGISTRO)}"
            )
        nivel, clase = TIPOS_REGISTRO[tipo]
        codigo, nombre = _departamento(fila[i["departamento"]], donde)
        out.append(
            {
                "codigo_departamento": codigo,
                "departamento": nombre,
                "crv": _entero(fila[i["crv"]], donde),
                "nivel": nivel,
                "clase": clase,
                "lema": fila[i["lema"]].strip(),
                "hoja": fila[i["descripcion1"]].strip(),
                "municipio": _municipio(fila[i_mun]) if i_mun is not None else None,
                "votos": _entero(fila[i["cantidadvotos"]], donde),
            }
        )
    return out


def votos_por_lema(
    desglose: list[dict], nivel: str, departamento: str = "", excluir: Optional[set[tuple[str, int]]] = None
) -> list[dict]:
    """Votos por partido (hoja + lema) en un nivel, ordenados de mayor a menor.

    Por defecto suma todas las mesas, también las de observados: es el escrutinio definitivo. Con
    `excluir=mesas_de_observados(totales)` da lo que se puede repartir por circuito o localidad."""
    if nivel not in ("nacional", "departamental", "municipal"):
        raise EleccionesInvalido(f"nivel {nivel!r}: nacional, departamental o municipal")
    d = _sin_tildes(departamento) if departamento else ""
    por: dict[str, dict] = defaultdict(lambda: {"por_hoja": 0, "al_lema": 0})
    for f in desglose:
        if f["nivel"] != nivel or (d and d not in (f["departamento"], f["codigo_departamento"])):
            continue
        if excluir and (f["codigo_departamento"], f["crv"]) in excluir:
            continue
        por[f["lema"]]["por_hoja" if f["clase"] == "hoja" else "al_lema"] += f["votos"]
    filas = [{"lema": lema, "votos": v["por_hoja"] + v["al_lema"], **v} for lema, v in por.items()]
    return sorted(filas, key=lambda x: (-x["votos"], x["lema"]))


def normalizar_lema(nombre: str) -> str:
    """El nombre del partido para comparar elecciones: sin tildes, en mayúsculas y sin «PARTIDO»
    adelante. «Partido Frente Amplio» (2024) y «FRENTE AMPLIO» (2025) quedan iguales. Es una
    convención de este paquete, no un nombre oficial."""
    n = _sin_tildes(nombre)
    return n[len("PARTIDO ") :].strip() if n.startswith("PARTIDO ") else n


def leer_plan(ruta: Path) -> list[dict]:
    """Un circuito por fila: departamento, circuito, serie, municipio, localidad, local, tipo
    (urbano o rural) y accesible."""
    ruta = Path(ruta)
    columnas, filas, _ = _leer_csv(ruta)
    req = ("departamento", "nrocircuito", "localidad", "local", "accesibilidad", "tipocircuito")
    if any(c not in columnas for c in req):
        raise EleccionesInvalido(f"{ruta.name}: no parece un plan circuital (columnas {columnas})")
    i = {c: columnas.index(c) for c in (*req, "serie", "municipio") if c in columnas}
    out = []
    for n, fila in enumerate(filas, start=2):
        donde = f"{ruta.name} fila {n}"
        codigo, nombre = _departamento(fila[i["departamento"]], donde)
        tipo = fila[i["tipocircuito"]].strip().upper()
        if tipo not in TIPOS_CIRCUITO:
            raise EleccionesInvalido(f"{donde}: tipo de circuito {tipo!r} desconocido")
        acc = fila[i["accesibilidad"]].strip().upper()
        if acc not in ("S", "N"):
            raise EleccionesInvalido(f"{donde}: accesibilidad {acc!r}, se espera S o N")
        out.append(
            {
                "codigo_departamento": codigo,
                "departamento": nombre,
                "circuito": _entero(fila[i["nrocircuito"]], donde),
                "serie": fila[i["serie"]].strip() if "serie" in i else "",
                "municipio": _municipio(fila[i["municipio"]]) if "municipio" in i else None,
                "localidad": fila[i["localidad"]].strip(),
                "local": fila[i["local"]].strip(),
                "tipo": TIPOS_CIRCUITO[tipo],
                "accesible": acc == "S",
            }
        )
    return out


def descargar(eleccion: str, archivo: str, destino: Path) -> Path:
    """Baja un archivo (`totales`, `desglose` o `plan`) de una elección. **Sale a la red.**

    El recurso se elige por el nombre del archivo en su URL, no por su título (los títulos cambian
    de una elección a otra y alguno empieza con un espacio). Más de un candidato se rechaza.
    """
    if eleccion not in ELECCIONES:
        raise EleccionesInvalido(f"elección {eleccion!r}: {', '.join(ELECCIONES)}")
    e = ELECCIONES[eleccion]
    if archivo not in e["archivos"]:
        raise EleccionesInvalido(f"{eleccion} no publica {archivo!r}: {', '.join(e['archivos'])}")
    prefijo = e["archivos"][archivo]
    candidatos = [
        r for r in catalogo.recursos(e["dataset"])
        if r["formato"] == "CSV" and Path(r["url"].split("?")[0]).name.lstrip("-").startswith(prefijo)
    ]  # fmt: skip
    if len(candidatos) != 1:
        raise EleccionesInvalido(
            f"{e['dataset']}: {len(candidatos)} recursos CSV que empiezan con {prefijo!r}, se esperaba 1"
        )
    return red.bajar(candidatos[0]["url"], Path(destino))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.elecciones", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("eleccion", choices=sorted(ELECCIONES))
    b.add_argument("archivo", choices=["totales", "desglose", "plan"])
    b.add_argument("destino", type=Path)
    r = sub.add_parser("resumen", help="totales de un archivo de totales por mesa")
    r.add_argument("archivo", type=Path)
    r.add_argument("--departamento", default="")
    args = ap.parse_args(argv)
    if args.orden == "bajar":
        print(f"bajado {descargar(args.eleccion, args.archivo, args.destino)}")
        return 0
    s = resumen(leer_totales(args.archivo), args.departamento)
    for k, v in s.items():
        print(f"{k}: {v}")
    print(
        f"Incluye {s['escrutados_en_mesas_de_observados']} votos observados escrutados en "
        f"{s['mesas_de_observados']} mesas especiales, que no tienen localidad."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
