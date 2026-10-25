"""Calidad del agua potable de OSE (CKAN propio de OSE, no el catálogo nacional).

OSE publica su propio CKAN en `https://datos.ose.com.uy/api/3/action/` con **28 datasets** que no
están en catalogodatos.gub.uy (medido el 2026-10-25). Este lector toma el dataset `calidad-de-agua`:
los análisis de laboratorio con que OSE declara el cumplimiento de los seis parámetros que exige el
Reglamento Bromatológico Nacional (Decreto 375/011, norma UNIT 833:2008).

Medido el 2026-10-25 sobre los dos CSV vigentes:

- `calidad_de_agua_bacteriologia_2017t1_2025t4.csv`: 152.967 filas, 31.259.384 bytes, sha256
  `0855acc69f06ca17a58f4e60a95bbeb357abaf49b46470d1ebea3c83ecc12709`.
- `calidad_de_agua_fisicoquimico_2017t1_2025t4.csv`: 531.679 filas, 96.317.443 bytes, sha256
  `ae052ae069d70bfec21348b6f36005436d1ba4448c4fad8885f36943a55b8781`.

UTF-8, delimitador `;`, todos los campos entrecomillados. Los **36 trimestres de 2017-T1 a 2025-T4
están completos**, sin un solo hueco (1.910 a 2.484 muestras por trimestre en bacteriología, 3.012 a
4.323 en fisicoquímico). El dataset declara frecuencia **anual**: no es una serie operativa.

Lo que devuelve `resumen()` sobre los archivos completos, y que fija el test contra la fuente real:
bacteriología 152.967 análisis / 76.784 muestras / 1.773 en más de un laboratorio / 38 localidades;
fisicoquímico 531.679 / 133.598 / 3.161 / 41, con 142.212 valores censurados (4 con el signo al
revés), 50.649 con punto decimal y 348.513 con coma.

Las trampas, medidas:

- **El separador decimal se parte por localidad, no por año.** pH: 98.215 valores con coma y
  **35.070 con punto**, y el punto es casi todo Montevideo (35.062; los otros 8 son de Florida), en
  los nueve años. Turbidez: 102.601 con coma y 12.678 con punto (12.677 de Montevideo). Un lector
  que asuma un solo separador pierde el 26% de las lecturas de pH del país **sin dar error**. Se
  aceptan los dos y se cuenta cuántos se vio de cada uno; un tercer formato se rechaza.
- **La censura a la izquierda es la mayoría del dato, no una excepción.** `COLOR VERDADERO`: 124.424
  de 132.745 valores son `<5` o `<2,5` (**93,7%**). `TURBIDEZ`: 17.788. Tratar `<5` como 5 o como 0
  cambia todos los promedios, así que el número y su condición van en **dos campos separados**
  (`valor` y `condicion`), y nunca se mezcla un límite de detección con una medición.
- **Y hay cuatro con el signo al revés.** En 531.679 filas de fisicoquímico aparecen 2 `>0,2`
  (turbidez) y 2 `>5` (color), una en Rivera, una en San Carlos, una en Artigas y una en Punta del
  Este, en 2017, 2021, 2022 y 2023. El número es **el mismo** que el límite de detección de esa
  columna (`<0,2`, `<5`), así que casi con seguridad es un error de carga. El lector **no lo da
  vuelta**: lo devuelve como `mayor_que` y `resumen()` lo cuenta aparte. Corregir el signo de un
  valor ajeno es inventar un dato, aunque la corrección parezca obvia. Esta trampa no se midió a
  mano: la encontró el propio lector al rechazar la fila 55.440.
- **Hay un valor imposible, y por eso pH queda sin rango.** El pH nacional va de 1,6 a **251,0**, en
  una escala de 0 a 14. El 251,0 es **una sola fila** (2017-T2, Melo, Lab. Reg. Treinta y Tres) y el
  siguiente valor más alto de las 133.287 lecturas es 10,5; el mínimo, 1,6, es de Salto (2021-T1,
  Laboratorio Central). Un rango 0-14 habría rechazado **531.679 filas por una**: los extremos se
  **declaran** en `resumen()` y la columna queda sin rango a propósito. Lo mismo turbidez (hasta
  98,0 NTU) y color (hasta 198,0 UC).
- **La bacteriología no es numérica, y aun así trae un número.** `COLIFORMES TOTALES` y
  `ESCHERICHIA COLI` tienen tres valores en nueve años: `Ausencia` (151.980), `Presencia` (985) y
  `<1` (**2**). Las dos filas con `<1` son de *Atlántida - Laguna del Cisne*, las dos de 2020. Un
  dominio de dos valores rechazaría 152.967 filas por 2; uno que convierta, miente. Se declara el
  dominio de tres y `resumen()` cuenta los `<1`.
- **No hay columna de unidad.** Está implícita en `PARAMETRO`: turbidez en NTU, color verdadero en
  UC, pH adimensional. Se declara en `UNIDADES`, no se infiere.
- **Una muestra no es un laboratorio.** 1.773 `ID_MUESTRA_M` de bacteriología y 3.161 de
  fisicoquímico aparecen con **más de un laboratorio**. Contar filas sobrecuenta muestras: las
  muestras únicas son 76.784 y 133.598, no 152.967 y 531.679. `resumen()` informa las dos cuentas.
- **Los dos archivos no cubren las mismas localidades.** 38 en bacteriología y 41 en fisicoquímico:
  Maldonado, Piriápolis y San Carlos sólo están en fisicoquímico, y Punta del Este tiene 29.042
  filas en fisicoquímico y **8** en bacteriología. Cruzar los dos por localidad no cierra.
- **El nombre del recurso lleva el rango de fechas adentro** («Bacteriología desde 2017-Trimestre 1
  a 2025-Trimestre 4»), así que cambia cada año: el recurso se identifica por el **nombre del
  archivo** en la URL. Y hay que hacerlo por prefijo, no por subcadena: el archivo de metadatos se
  llama `metadatos_calidad_agua_bacteriologia_y_fisicoquimico.csv` y contiene los dos nombres.
- **El metadato no coincide con el dato.** El CSV de metadatos describe el atributo `año`; la
  columna real se llama `ANIO`.
- **El trimestre es un string y no hay mes ni día.** `"trimestre 1"`, no un número. La resolución
  temporal más fina es el trimestre: `desde` y `hasta` son sus bordes, no la fecha de la muestra.
- **El datastore tipa todo como `text`.** Filtrar `{"ANIO": 2025}` con un entero devuelve **HTTP
  409**; con `"2025"` anda. Ver `catalogo.datastore_search(..., filtros=...)`.

Uso:
    python -m uydatos ose bajar datos/ose
    python -m uydatos ose resumen datos/ose/fisicoquimico.csv
    python -m uydatos ose filas datos/ose/fisicoquimico.csv --localidad Salto --limite 20
    python -m uydatos ose recursos
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Sequence

from uydatos import catalogo, procedencia, red
from uydatos.errores import DatosInvalidos

ACCIONES = "https://datos.ose.com.uy/api/3/action/"
DATASET = "calidad-de-agua"
CODIFICACION = "utf-8"
DELIMITADOR = ";"

COLUMNAS = [
    "ANIO",
    "TRIMESTRE",
    "DEPARTAMENTO",
    "LOCALIDAD",
    "LABORATORIO",
    "AREA_ANALISIS",
    "PARAMETRO",
    "METODO",
    "ID_MUESTRA_M",
    "VALOR",
]

# El nombre del recurso cambia cada año (lleva el rango de fechas adentro): se identifica por el
# nombre del archivo, y **por prefijo**, porque el de metadatos contiene los dos nombres.
ARCHIVOS = {
    "bacteriologia": "calidad_de_agua_bacteriologia",
    "fisicoquimico": "calidad_de_agua_fisicoquimico",
}

# La unidad no viene en el archivo: está implícita en PARAMETRO. pH es adimensional.
UNIDADES = {"PH": "", "TURBIDEZ": "NTU", "COLOR VERDADERO": "UC"}

# Dominios medidos sobre los nueve años completos. Un valor nuevo acá significa que la fuente
# cambió, y se rechaza: es lo único que distingue un parámetro nuevo de un dato mal leído.
CATEGORIAS = {
    "COLIFORMES TOTALES": {"Ausencia", "Presencia", "<1"},
    "ESCHERICHIA COLI": {"Ausencia", "Presencia", "<1"},
    "OLOR": {"Característico", "No Característico"},
}
NUMERICOS = set(UNIDADES)
PARAMETROS = NUMERICOS | set(CATEGORIAS)

ANIO_MIN, ANIO_MAX = 2000, 2100
_TRIMESTRE = re.compile(r"^trimestre\s*([1-4])$", re.I)
_NUMERO = re.compile(r"^([<>])?\s*(\d+(?:[.,]\d+)?)$")


class OseInvalido(DatosInvalidos):
    """El archivo no cumple el contrato de la fuente."""


def _bordes(anio: int, trimestre: int) -> tuple[date, date]:
    """Primer y último día del trimestre. El archivo no trae la fecha de la muestra: lo más fino
    que se puede afirmar es el trimestre, y se afirma como un intervalo, no como un día."""
    inicio = date(anio, 3 * (trimestre - 1) + 1, 1)
    fin_mes = 3 * trimestre
    fin = date(anio, fin_mes, 31) if fin_mes == 12 else date(anio, fin_mes + 1, 1) - timedelta(days=1)
    return inicio, fin


def _numero(crudo: str, ruta: Path, fila: int, parametro: str) -> tuple[float, str, bool]:
    """El valor, su condición y si venía con punto decimal. Acepta coma y punto; nada más."""
    m = _NUMERO.match(crudo.strip())
    if not m:
        raise OseInvalido(
            f"{ruta.name} fila {fila}: {parametro} con valor ilegible {crudo!r}; "
            "se esperaba un número con coma o punto, con '<' o '>' opcional"
        )
    signo, texto = m.group(1), m.group(2)
    condicion = {"<": "menor_que", ">": "mayor_que"}.get(signo, "exacto")
    return float(texto.replace(",", ".")), condicion, "." in texto


def recursos_vigentes() -> dict[str, dict]:
    """Los dos CSV del dataset, con lo que CKAN declara de cada uno. **Sale a la red.**

    Devuelve `{area: {"url", "nombre", "archivo", "bytes", "hash", "modificado", "recurso"}}`.
    `bytes`, `hash` y `modificado` son lo que **declara** CKAN, no lo medido: sirven para no bajar
    122 MB de un dataset que se actualiza una vez al año. El `hash` de CKAN es un md5 y no viene
    con `hash_algorithm`; la huella que vale es el sha256 del archivo bajado (`procedencia.sello`).
    """
    paquete = catalogo.accion("package_show", base=ACCIONES, id=DATASET)
    vigentes: dict[str, dict] = {}
    for r in paquete.get("resources") or []:
        archivo = (r.get("url") or "").rsplit("/", 1)[-1]
        for area, prefijo in ARCHIVOS.items():
            if archivo.startswith(prefijo):
                vigentes[area] = {
                    "recurso": r.get("id") or "",
                    "nombre": r.get("name") or "",
                    "archivo": archivo,
                    "url": r.get("url") or "",
                    "bytes": r.get("size"),
                    "hash": r.get("hash") or "",
                    "modificado": r.get("last_modified") or r.get("metadata_modified") or "",
                }
    faltan = sorted(set(ARCHIVOS) - set(vigentes))
    if faltan:
        nombres = [(r.get("url") or "").rsplit("/", 1)[-1] for r in paquete.get("resources") or []]
        raise OseInvalido(f"{DATASET}: no se encontró el CSV de {faltan}; los archivos del dataset son {nombres}")
    return vigentes


def descargar(destino: Path, *, areas: Sequence[str] = tuple(ARCHIVOS)) -> dict[str, Path]:
    """Baja los CSV a `destino/<area>.csv`. **Sale a la red.** Son 122 MB entre los dos.

    No decide si hace falta bajarlos: eso lo responde `hace_falta_bajar()`, que sólo mira metadatos.
    """
    destino = Path(destino)
    vigentes = recursos_vigentes()
    desconocidas = sorted(set(areas) - set(ARCHIVOS))
    if desconocidas:
        raise OseInvalido(f"área desconocida {desconocidas}; hay {sorted(ARCHIVOS)}")
    return {area: red.bajar(vigentes[area]["url"], destino / f"{area}.csv") for area in areas}


def hace_falta_bajar(area: str, ruta: Path, vigente: dict) -> tuple[bool, str]:
    """Si el archivo de disco ya es el que CKAN publica, con el motivo. **No sale a la red.**

    Compara el tamaño declarado contra el del disco. Es la única señal barata que da el CKAN de OSE:
    el `hash` que declara es un md5 del archivo subido y no hay con qué compararlo sin leer los
    122 MB. Un tamaño igual no prueba que el contenido sea igual, y por eso esta función responde
    si **hace falta** bajar, no si el archivo es correcto; lo que prueba la identidad es el sha256
    que deja `procedencia.sello()`.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return True, f"{area}: no está en el disco"
    declarado = vigente.get("bytes")
    if declarado is None:
        return True, f"{area}: CKAN no declara el tamaño del recurso"
    if int(declarado) != ruta.stat().st_size:
        return True, f"{area}: CKAN declara {int(declarado)} bytes y el disco tiene {ruta.stat().st_size}"
    return False, f"{area}: {ruta.stat().st_size} bytes, igual a lo que declara CKAN ({vigente['modificado'][:10]})"


def leer(ruta: Path, *, localidades: Optional[Sequence[str]] = None) -> list[dict]:
    """Los análisis, uno por fila, ya tipados. Con `localidades`, sólo esas (el archivo es grande).

    Cada fila trae `valor` (float) y `condicion` (`exacto` o `menor_que`) para los parámetros
    numéricos, y `categoria` (el texto tal cual) para los categóricos. **Nunca las dos cosas**: un
    límite de detección no es una medición y una presencia no es un número. `condicion` es
    `exacto`, `menor_que`, `mayor_que` o `categoria`; el signo se devuelve como vino.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise OseInvalido(f"{ruta}: el archivo no está en el disco")
    quiero = set(localidades) if localidades else None
    filas: list[dict] = []
    with ruta.open(encoding=CODIFICACION, newline="") as f:
        lector = csv.reader(f, delimiter=DELIMITADOR)
        try:
            encabezado = [c.replace("﻿", "").strip() for c in next(lector)]
        except StopIteration:
            raise OseInvalido(f"{ruta}: archivo vacío") from None
        if encabezado != COLUMNAS:
            raise OseInvalido(f"{ruta}: columnas inesperadas {encabezado}, se esperaban {COLUMNAS}")
        for n, campos in enumerate(lector, start=2):
            if not any(c.strip() for c in campos):
                continue
            if len(campos) != len(COLUMNAS):
                raise OseInvalido(f"{ruta} fila {n}: {len(campos)} columnas, se esperaban {len(COLUMNAS)}")
            cruda = dict(zip(COLUMNAS, (c.strip() for c in campos)))
            if quiero is not None and cruda["LOCALIDAD"] not in quiero:
                continue
            filas.append(_fila(cruda, ruta, n))
    if not filas:
        raise OseInvalido(
            f"{ruta}: ninguna fila de datos"
            + (f" para {sorted(quiero)}; ¿cambió el nombre de la localidad?" if quiero else "")
        )
    return filas


def _fila(cruda: dict[str, str], ruta: Path, n: int) -> dict:
    """Una fila cruda, tipada y validada. Levanta con el motivo; no completa ni corrige nada."""
    m = _TRIMESTRE.match(cruda["TRIMESTRE"])
    if not m:
        raise OseInvalido(f"{ruta.name} fila {n}: trimestre ilegible {cruda['TRIMESTRE']!r}, se esperaba 'trimestre N'")
    trimestre = int(m.group(1))
    try:
        anio = int(cruda["ANIO"])
    except ValueError:
        raise OseInvalido(f"{ruta.name} fila {n}: año ilegible {cruda['ANIO']!r}") from None
    if not ANIO_MIN <= anio <= ANIO_MAX:
        raise OseInvalido(f"{ruta.name} fila {n}: año imposible {anio}")

    parametro = cruda["PARAMETRO"]
    if parametro not in PARAMETROS:
        raise OseInvalido(
            f"{ruta.name} fila {n}: parámetro desconocido {parametro!r}; los medidos son {sorted(PARAMETROS)}"
        )
    valor = condicion = categoria = None
    punto = False
    if parametro in NUMERICOS:
        valor, condicion, punto = _numero(cruda["VALOR"], ruta, n, parametro)
    else:
        categoria = cruda["VALOR"]
        if categoria not in CATEGORIAS[parametro]:
            raise OseInvalido(
                f"{ruta.name} fila {n}: {parametro} con valor {categoria!r}; "
                f"los medidos son {sorted(CATEGORIAS[parametro])}"
            )
        condicion = "categoria"

    desde, hasta = _bordes(anio, trimestre)
    return {
        "anio": anio,
        "trimestre": trimestre,
        "desde": desde,
        "hasta": hasta,
        "departamento": cruda["DEPARTAMENTO"],
        "localidad": cruda["LOCALIDAD"],
        "laboratorio": cruda["LABORATORIO"],
        "area": cruda["AREA_ANALISIS"],
        "parametro": parametro,
        "metodo": cruda["METODO"],
        "muestra": cruda["ID_MUESTRA_M"],
        "unidad": UNIDADES.get(parametro, ""),
        "valor": valor,
        "condicion": condicion,
        "categoria": categoria,
        "punto_decimal": punto,
    }


def resumen(filas: list[dict]) -> dict:
    """Las cuentas que dejan ver las trampas sin romper la lectura.

    Declara los **extremos por parámetro** (es lo que deja ver el pH de 251,0 sin rechazar el
    archivo), cuántos valores venían censurados, cuántos con punto y cuántos con coma, las dos
    cuentas de muestras —filas y `ID_MUESTRA_M` únicos— y las muestras analizadas en más de un
    laboratorio.
    """
    if not filas:
        raise OseInvalido("resumen() necesita al menos una fila: el archivo vino vacío")
    por_muestra: dict[str, set[str]] = {}
    for f in filas:
        por_muestra.setdefault(f["muestra"], set()).add(f["laboratorio"])
    extremos = {}
    for p in sorted({f["parametro"] for f in filas} & NUMERICOS):
        v = [f["valor"] for f in filas if f["parametro"] == p]
        extremos[p] = {"min": min(v), "max": max(v), "n": len(v), "unidad": UNIDADES[p]}
    return {
        "filas": len(filas),
        "muestras": len(por_muestra),
        "muestras_con_mas_de_un_laboratorio": sum(1 for labs in por_muestra.values() if len(labs) > 1),
        "anio_min": min(f["anio"] for f in filas),
        "anio_max": max(f["anio"] for f in filas),
        "trimestres": len({(f["anio"], f["trimestre"]) for f in filas}),
        "localidades": len({f["localidad"] for f in filas}),
        "laboratorios": len({f["laboratorio"] for f in filas}),
        "por_parametro": dict(Counter(f["parametro"] for f in filas).most_common()),
        "censurados": sum(1 for f in filas if f["condicion"] == "menor_que"),
        "censurados_al_reves": sum(1 for f in filas if f["condicion"] == "mayor_que"),
        "con_punto_decimal": sum(1 for f in filas if f["punto_decimal"]),
        "con_coma_decimal": sum(1 for f in filas if f["parametro"] in NUMERICOS and not f["punto_decimal"]),
        "categorias": dict(Counter(f["categoria"] for f in filas if f["categoria"]).most_common()),
        "extremos": extremos,
    }


def verificar_contra_datastore(area: str, localidad: str, filas: list[dict]) -> dict:
    """Compara lo leído del CSV con lo que el datastore de CKAN dice que hay. **Sale a la red.**

    Son dos lecturas independientes de la misma fuente: el archivo completo y la API. Si no
    coinciden, la fuente se movió entre una y otra —o el archivo del disco quedó viejo— y eso es un
    rechazo, no un redondeo. El filtro va como texto a propósito (el datastore tipa todo `text`).
    """
    if area not in ARCHIVOS:
        raise OseInvalido(f"área desconocida {area!r}; hay {sorted(ARCHIVOS)}")
    recurso = recursos_vigentes()[area]["recurso"]
    if not recurso:
        raise OseInvalido(f"{area}: CKAN no declara el id del recurso, no se puede verificar")
    remoto = catalogo.datastore_search(recurso, base=ACCIONES, limite=1, filtros={"LOCALIDAD": localidad})
    local = sum(1 for f in filas if f["localidad"] == localidad)
    if remoto["total"] != local:
        raise OseInvalido(
            f"{area}/{localidad}: el CSV tiene {local} filas y el datastore declara {remoto['total']}; "
            "las dos lecturas tienen que coincidir"
        )
    return {"localidad": localidad, "filas": local, "total_datastore": remoto["total"]}


def sello(area: str, ruta: Path, filas: Optional[list[dict]] = None):
    """El sello de procedencia del archivo bajado: fuente, fecha, sha256, bytes y filas."""
    vigente = recursos_vigentes().get(area, {})
    return procedencia.sello(
        f"OSE — calidad de agua potable ({area})",
        ruta=Path(ruta),
        url=vigente.get("url"),
        filas=len(filas) if filas is not None else None,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.ose", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["bajar", "resumen", "filas", "recursos"])
    ap.add_argument("ruta", type=Path, nargs="?")
    ap.add_argument("--localidad", action="append", help="repetible; filtra por LOCALIDAD exacta")
    ap.add_argument("--limite", type=int, default=10)
    args = ap.parse_args(argv)

    if args.accion == "recursos":
        for area, r in sorted(recursos_vigentes().items()):
            print(f"{area:15} {r['bytes'] or '?':>10} bytes  {r['modificado'][:10]}  {r['archivo']}")
        return 0
    if args.ruta is None:
        ap.error(f"{args.accion} necesita una ruta")
    if args.accion == "bajar":
        for area, p in sorted(descargar(args.ruta).items()):
            print(f"{area:15} {p}")
        return 0

    filas = leer(args.ruta, localidades=args.localidad)
    if args.accion == "filas":
        for f in filas[: args.limite]:
            dato = f["categoria"] if f["categoria"] else f"{'<' if f['condicion'] == 'menor_que' else ''}{f['valor']}"
            print(f"{f['anio']}-T{f['trimestre']} {f['localidad']:<18} {f['parametro']:<20} {dato} {f['unidad']}")
        return 0
    r = resumen(filas)
    print(
        f"{r['filas']} análisis · {r['muestras']} muestras · {r['trimestres']} trimestres "
        f"de {r['anio_min']} a {r['anio_max']} · {r['localidades']} localidades"
    )
    print(
        f"  censurados: {r['censurados']} (con el signo al revés: {r['censurados_al_reves']}) · "
        f"con punto decimal: {r['con_punto_decimal']} · con coma: {r['con_coma_decimal']} · "
        f"muestras en >1 laboratorio: {r['muestras_con_mas_de_un_laboratorio']}"
    )
    for p, e in r["extremos"].items():
        print(f"  {p:<20} {e['n']:>7} valores · min {e['min']} · max {e['max']} {e['unidad']}")
    for k, v in r["categorias"].items():
        print(f"  {k:<20} {v:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
