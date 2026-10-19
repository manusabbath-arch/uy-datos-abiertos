"""Parlamento del Uruguay: asistencias, proyectos, leyes, pedidos de informes y nómina de Diputados.

El catálogo publica un archivo por legislatura: asistencias del Senado y de Diputados de la 46 (2005)
a la 50 (la actual), proyectos entrados de la 42 (1985) a la 50, y un único archivo de leyes
promulgadas desde 1985. La medición completa está en `docs/2026-10-10-datos-civicos.md`.

Las trampas, medidas el 10/10/2026
---------------------------------
1. **Todos los recursos de un dataset tienen la misma URL final, `csv`.** Quien los guarda por el
   nombre de la URL pisa una legislatura con otra. La legislatura sale del **título** del recurso.
2. **Hay muchas más personas que bancas**: 336 a 424 filas por legislatura en Diputados (99 bancas),
   ~110 en el Senado (31). Son los suplentes, con una o dos citaciones. Un ranking sin un mínimo de
   citaciones compara a quien fue citado 2 veces con quien fue citado 364.
3. **No hay identificador de persona**: dos filas con el mismo nombre en una legislatura (de 1 a 3 por
   legislatura) pueden ser dos períodos de la misma persona o dos personas. No se unen.
4. **Filas sin nombre** (`","`) con citaciones, en Diputados 49 y 50.
5. **Una columna trae un tabulador pegado** (`'Faltas c/Aviso\\t'`).
6. Lo que sí cierra siempre, y se exige: **citaciones = asistencias + faltas con aviso + faltas sin
   aviso**, en las 10 legislaturas. Las licencias no son citaciones: van aparte.
7. **311 proyectos aparecen en dos legislaturas** con el mismo número de asunto: sumar legislaturas
   los cuenta dos veces.
8. **Leyes**: 4.799 filas son 4.796 leyes (de la 15.736 a la 20.531, sin huecos), más **2 filas
   duplicadas** exactas y una **«ley 0»** (una pensión graciable de 1997). Las columnas
   `Leyes_Referenciadas` y `Leyes_que_referencia` son **cantidades**, no listas. Y el catálogo dice
   que el archivo se actualizó el 21/06/2024 cuando llega a octubre de 2026: la fecha del catálogo no
   dice de cuándo es el dato.

Pedidos de informes y nómina (medidos el 11/10/2026)
---------------------------------------------------
El pedido de informes es la herramienta de control del artículo 118 de la Constitución: un legislador
pide datos a un organismo, y la Ley 17.673 le da 45 días para contestar. El dataset
`crr-pedidos-de-informes` trae **cada pedido de Diputados** de la legislatura 50 (2.532, del 17/02/2025
al 08/10/2026, sha256 `aa6ebb5f…`): organismo, fecha, autores, tema, estado y los enlaces al oficio y a
la respuesta (una muestra de 30, todos PDF que responden). El Senado publica sólo totales.

9. **La metadata dice que el estado es «Contestado o No contestado»** y el archivo trae cuatro:
   CONTESTADO (1.726), VENCIDO (478), SIN CONTESTAR (281) y NO ENTREGADO (47). Un estado nuevo se
   rechaza: cambia lo que significa el total.
10. **«SIN CONTESTAR» no es «dentro del plazo»**: de 281, 166 tienen 45 días o menos y **115 tienen
    más** (hasta 227) sin figurar como vencidos; los VENCIDO tienen todos 67 días o más. No se
    reclasifica nada: se publica el estado tal cual y, aparte, la antigüedad, para que el porcentaje de
    respuesta se pueda calcular **sólo sobre los pedidos con el plazo ya cumplido**.
11. **No hay fecha de respuesta**: se sabe si un organismo contestó, no cuánto tardó.
12. **Los coautores vienen separados por `+`**, y la metadata lo deja trunco («separados por »): 63
    pedidos tienen de 2 a 4 autores. Un pedido con tres autores es **un** pedido, no tres.
10b. **La tasa de respuesta depende de la antigüedad del pedido**: de los presentados en el primer
    semestre de 2025 está contestado el 92,5%; de los del segundo de 2026, el 31,9%. Las respuestas
    siguen llegando después del plazo (un VENCIDO puede pasar a CONTESTADO), así que comparar
    organismos con pedidos de edades distintas es injusto. `resumen_pedidos` devuelve la tasa por
    **semestre de presentación** y acepta `presentados_hasta` para comparar una misma cohorte.
13. **242 pedidos CONTESTADO no tienen el enlace a la respuesta.** Se cuentan como contestados (es lo
    que dice la fuente) y se informan aparte.
14. **16 pares de pedidos repetidos** (mismo organismo, fecha, autor y tema) con oficios distintos: son
    pedidos distintos y se cuentan; se informan.
15. **El organismo es por donde se canaliza el pedido**: 21 valores, casi todos ministerios. Un pedido
    sobre UTE figura en el Ministerio de Industria.
16. **La nómina no trae identificador**: el nombre va como «APELLIDOS, NOMBRES» y en los pedidos como
    «Nombres Apellidos». `identificar()` une un autor con una persona sólo si **todas** sus palabras
    están en un único nombre de la nómina: 131 de 133 autores (2.622 de 2.630 menciones). Los otros
    dos no están en la nómina, que es de diciembre de 2025, y quedan sin identificar: no se adivinan.
    La nómina trae la edad: **no se lee**, porque este control no la necesita.

Uso:
    python -m uydatos.parlamento bajar asistencias-senado 50 datos/senado50.csv
    python -m uydatos.parlamento bajar pedidos-informes datos/pedidos.csv
    python -m uydatos.parlamento pedidos datos/pedidos.csv --nomina datos/nomina.csv
    python -m uydatos.parlamento asistencias datos/senado50.csv --minimo 10
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from uydatos import catalogo, red
from uydatos.errores import DatosInvalidos

DATASETS = {
    "asistencias-senado": "parlamento-del-uruguay-asistencias-a-la-camara-de-senadores",
    "asistencias-diputados": "parlamento-del-uruguay-asistencias-a-la-camara-de-representantes",
    "proyectos": "parlamento-del-uruguay-proyectos-entrados-al-parlamento",
    "leyes": "parlamento-del-uruguay-leyes-promulgadas-del-poder-ejecutivo",
    "pedidos-informes": "crr-pedidos-de-informes",
    "nomina": "crr-nominarepresentanteslegactual2",
}
# Los datasets que son un solo archivo, sin una legislatura por recurso.
_ARCHIVO_UNICO = ("leyes", "pedidos-informes", "nomina")

_COLUMNAS_PEDIDOS = ["Organismo", "Fecha", "Autores", "Tema", "Estado", "URLoficio", "URLcontestacion"]
_COLUMNAS_NOMINA = ["Nombre", "Genero", "Edad", "PartidoPolitico", "Departamento", "HojaVotacion"]
ESTADOS_PEDIDO = ("CONTESTADO", "VENCIDO", "SIN CONTESTAR", "NO ENTREGADO")
PLAZO_DIAS = 45  # Ley 17.673, artículo 1

_COLUMNAS_ASISTENCIA = {
    "nombre": "nombre",
    "citaciones": "citaciones",
    "asistencias": "asistencias",
    "faltasc/aviso": "faltas_con_aviso",
    "cantidaddefaltassinaviso": "faltas_sin_aviso",
    "nocitadoporlicencia": "licencias",
    "pasajesapresidentedelarepublica": "pasajes_a_presidente",
}
_CARPETA = re.compile(r"([A-Z.]+)\s*:\s*(\d+)\s*/\s*(\d{4})")
_TIPO = re.compile(r"\s*\(([^()]*)\)\s*$")


class ParlamentoInvalido(DatosInvalidos):
    """El archivo no cumple el contrato del Parlamento."""


def _clave(columna: str) -> str:
    sin = unicodedata.normalize("NFKD", columna).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", sin).lower()


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper().strip()


def _leer_csv(ruta: Path) -> tuple[list[str], list[list[str]]]:
    ruta = Path(ruta)
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.reader(f))
    except (OSError, UnicodeDecodeError) as e:
        raise ParlamentoInvalido(f"{ruta.name}: ilegible ({e})") from None
    if len(filas) < 2:
        raise ParlamentoInvalido(f"{ruta.name}: sin filas de datos")
    encabezado = filas[0]
    datos = [f for f in filas[1:] if any(c.strip() for c in f)]
    for n, f in enumerate(datos, start=2):
        if len(f) != len(encabezado):
            raise ParlamentoInvalido(f"{ruta.name} fila {n}: {len(f)} campos y el encabezado tiene {len(encabezado)}")
    return encabezado, datos


def _entero(texto: str, donde: str) -> int:
    t = texto.strip()
    if not t:
        return 0
    if not t.isdigit():
        raise ParlamentoInvalido(f"{donde}: {texto!r} no es un entero")
    return int(t)


def legislatura_del_titulo(titulo: str) -> Optional[int]:
    """`Asistencias al Senado - Legislatura 50` -> 50. La URL de todos los recursos termina en `csv`."""
    m = re.search(r"Legislatura\s+(\d+)", titulo or "")
    return int(m.group(1)) if m else None


# --- Asistencias -------------------------------------------------------------------------------------


def leer_asistencias(ruta: Path) -> list[dict]:
    """Una fila por persona y legislatura: nombre (None si viene vacío), citaciones, asistencias, faltas
    con y sin aviso, licencias, pasajes a presidente y `pct_asistencia` calculado. Rechaza una fila donde
    citaciones ≠ asistencias + faltas con aviso + faltas sin aviso."""
    ruta = Path(ruta)
    encabezado, datos = _leer_csv(ruta)
    claves = [_clave(c) for c in encabezado]
    faltan = [c for c in _COLUMNAS_ASISTENCIA if c not in claves]
    if faltan:
        raise ParlamentoInvalido(f"{ruta.name}: faltan columnas {faltan}: no parecen asistencias")
    i = {destino: claves.index(origen) for origen, destino in _COLUMNAS_ASISTENCIA.items()}
    out = []
    for n, fila in enumerate(datos, start=2):
        donde = f"{ruta.name} fila {n}"
        nombre = fila[i["nombre"]].strip()
        f = {"nombre": nombre if nombre.strip(" ,") else None}
        for campo in (
            "citaciones",
            "asistencias",
            "faltas_con_aviso",
            "faltas_sin_aviso",
            "licencias",
            "pasajes_a_presidente",
        ):
            f[campo] = _entero(fila[i[campo]], donde)
        if f["citaciones"] != f["asistencias"] + f["faltas_con_aviso"] + f["faltas_sin_aviso"]:
            raise ParlamentoInvalido(
                f"{donde}: citaciones {f['citaciones']} ≠ asistencias {f['asistencias']} + faltas con aviso "
                f"{f['faltas_con_aviso']} + faltas sin aviso {f['faltas_sin_aviso']}"
            )
        f["pct_asistencia"] = round(100 * f["asistencias"] / f["citaciones"], 1) if f["citaciones"] else None
        out.append(f)
    return out


def resumen_asistencias(filas: list[dict], minimo_citaciones: int = 10, nombre: str = "", cantidad: int = 10) -> dict:
    """La asistencia de una legislatura: menor y mayor asistencia entre quienes tuvieron al menos
    `minimo_citaciones` (los suplentes con una o dos citaciones no dicen nada), los nombres repetidos,
    las filas sin nombre y, con `nombre`, las filas que lo contienen (sin importar tildes)."""
    con_nombre = [f for f in filas if f["nombre"]]
    repetidos = sorted(k for k, v in Counter(f["nombre"] for f in con_nombre).items() if v > 1)
    elegibles = [f for f in con_nombre if f["citaciones"] >= minimo_citaciones]
    orden = sorted(elegibles, key=lambda f: (f["pct_asistencia"], -f["citaciones"]))
    buscado = _sin_tildes(nombre)
    return {
        "personas": len(filas),
        "filas_sin_nombre": len(filas) - len(con_nombre),
        "nombres_repetidos": repetidos,
        "minimo_citaciones": minimo_citaciones,
        "con_el_minimo": len(elegibles),
        "fuera_por_pocas_citaciones": len(con_nombre) - len(elegibles),
        "citaciones_totales": sum(f["citaciones"] for f in filas),
        "menor_asistencia": orden[:cantidad],
        "mayor_asistencia": list(reversed(orden[-cantidad:])) if orden else [],
        "encontrados": [f for f in con_nombre if buscado and buscado in _sin_tildes(f["nombre"])],
    }


# --- Proyectos ---------------------------------------------------------------------------------------


def leer_proyectos(ruta: Path) -> list[dict]:
    """Los proyectos entrados de una legislatura: fecha, asunto (número), carpetas (órgano, número,
    año), título sin el tipo, y tipo («PROYECTO DE LEY», «PROYECTO DE RESOLUCION»…)."""
    ruta = Path(ruta)
    encabezado, datos = _leer_csv(ruta)
    claves = [_clave(c) for c in encabezado]
    if claves[:4] != ["fecha", "asunto", "carpetas", "titulo"]:
        raise ParlamentoInvalido(f"{ruta.name}: columnas {encabezado}: no parecen proyectos entrados")
    out, vistos = [], set()
    for n, (fecha, asunto, carpetas, titulo, *_) in enumerate(datos, start=2):
        donde = f"{ruta.name} fila {n}"
        try:
            dia = date.fromisoformat(fecha.strip())
        except ValueError:
            raise ParlamentoInvalido(f"{donde}: fecha ilegible {fecha!r}") from None
        num = _entero(asunto, donde)
        if num in vistos:
            raise ParlamentoInvalido(f"{donde}: asunto {num} repetido en la misma legislatura")
        vistos.add(num)
        m = _TIPO.search(titulo)
        out.append(
            {
                "fecha": dia,
                "asunto": num,
                "carpetas": [{"organo": o, "numero": int(c), "anio": int(a)} for o, c, a in _CARPETA.findall(carpetas)],
                "titulo": titulo[: m.start()].strip() if m else titulo.strip(),
                "tipo": m.group(1).strip() if m else None,
            }
        )
    return out


# --- Leyes -------------------------------------------------------------------------------------------


def leer_leyes(ruta: Path) -> dict:
    """Las leyes promulgadas, sin duplicados exactos ni registros sin número.

    Devuelve `leyes` (ordenadas por número), `duplicadas` (filas idénticas descartadas), `sin_numero`
    (las filas con número 0) y `faltantes` (los números que no están entre el menor y el mayor). Un
    mismo número con dos contenidos distintos se rechaza: no se sabe cuál es el bueno."""
    ruta = Path(ruta)
    encabezado, datos = _leer_csv(ruta)
    claves = [_clave(c) for c in encabezado]
    req = ("fecha", "numero_de_ley", "texto_original", "texto_actualizado", "titulo", "asunto")
    if any(c not in claves for c in req):
        raise ParlamentoInvalido(f"{ruta.name}: columnas {encabezado}: no parecen leyes promulgadas")
    i = {c: claves.index(c) for c in claves}
    por_numero: dict[int, dict] = {}
    duplicadas, sin_numero = 0, []
    for n, fila in enumerate(datos, start=2):
        donde = f"{ruta.name} fila {n}"
        num = _entero(fila[i["numero_de_ley"]], donde)
        try:
            dia = date.fromisoformat(fila[i["fecha"]].strip())
        except ValueError:
            raise ParlamentoInvalido(f"{donde}: fecha ilegible {fila[i['fecha']]!r}") from None
        ley = {
            "numero": num,
            "fecha": dia,
            "titulo": fila[i["titulo"]].strip(),
            "asunto": fila[i["asunto"]].strip(),
            "texto_parlamento": fila[i["texto_original"]].strip(),
            "texto_impo": fila[i["texto_actualizado"]].strip(),
            "cantidad_que_cita": _entero(fila[i["leyes_referenciadas"]], donde) if "leyes_referenciadas" in i else None,
            "cantidad_que_la_citan": _entero(fila[i["leyes_que_referencia"]], donde)
            if "leyes_que_referencia" in i
            else None,
        }
        if num == 0:
            sin_numero.append(ley)
            continue
        if num in por_numero:
            if por_numero[num] != ley:
                raise ParlamentoInvalido(f"{donde}: la ley {num} aparece dos veces con contenido distinto")
            duplicadas += 1
            continue
        por_numero[num] = ley
    numeros = sorted(por_numero)
    faltantes = sorted(set(range(numeros[0], numeros[-1] + 1)) - set(numeros)) if numeros else []
    return {
        "leyes": [por_numero[k] for k in numeros],
        "duplicadas": duplicadas,
        "sin_numero": sin_numero,
        "faltantes": faltantes,
    }


# --- Descarga ----------------------------------------------------------------------------------------


# --- Pedidos de informes y nómina ---------------------------------------------------------------


def leer_nomina(ruta: Path) -> list[dict]:
    """La nómina de Diputados (titulares y suplentes con actuación). No sale a la red.

    Cada fila: `nombre` (tal cual), `partido`, `departamento` y `hoja` (la hoja de votación, entero).
    **La edad y el género no se leen** (trampa 16).
    """
    encabezado, datos = _leer_csv(ruta)
    if [c.strip() for c in encabezado] != _COLUMNAS_NOMINA:
        raise ParlamentoInvalido(f"{Path(ruta).name}: columnas {encabezado}, se esperaban {_COLUMNAS_NOMINA}")
    filas = []
    for n, f in enumerate(datos, start=2):
        nombre = f[0].strip()
        if "," not in nombre:
            raise ParlamentoInvalido(f"{Path(ruta).name} fila {n}: {nombre!r} no es «APELLIDOS, NOMBRES»")
        hoja = f[5].strip()
        try:
            hoja_n = int(float(hoja)) if hoja else None
        except ValueError:
            raise ParlamentoInvalido(f"{Path(ruta).name} fila {n}: hoja de votación {hoja!r}") from None
        filas.append({"nombre": nombre, "partido": f[3].strip(), "departamento": f[4].strip(), "hoja": hoja_n})
    return filas


def _palabras(texto: str) -> set[str]:
    return set(_sin_tildes(texto).replace(",", " ").replace(".", " ").split())


def identificar(autor: str, nomina: list[dict]) -> Optional[dict]:
    """La persona de la nómina que corresponde a `autor`, o `None` si no hay una sola.

    Exige que **todas** las palabras del autor estén en el nombre de la nómina, sin tildes. Dos
    candidatos o ninguno dan `None`: un nombre ambiguo no se asigna.
    """
    buscadas = _palabras(autor)
    if not buscadas:
        return None
    candidatos = [p for p in nomina if buscadas <= _palabras(p["nombre"])]
    return candidatos[0] if len(candidatos) == 1 else None


def leer_pedidos(ruta: Path) -> list[dict]:
    """Los pedidos de informes de Diputados, uno por fila. No sale a la red.

    Cada pedido: `organismo`, `fecha` (date), `autores` (lista, separada por `+`), `tema`, `estado`
    (uno de `ESTADOS_PEDIDO`), `url_oficio` y `url_contestacion` (`None` si no hay). Rechaza otras
    columnas, una fecha que no sea `AAAA/MM/DD`, un estado que no se midió y un pedido sin autor u
    oficio.
    """
    encabezado, datos = _leer_csv(ruta)
    if [c.strip() for c in encabezado] != _COLUMNAS_PEDIDOS:
        raise ParlamentoInvalido(f"{Path(ruta).name}: columnas {encabezado}, se esperaban {_COLUMNAS_PEDIDOS}")
    pedidos = []
    for n, f in enumerate(datos, start=2):
        donde = f"{Path(ruta).name} fila {n}"
        organismo, fecha, autores, tema, estado, oficio, contestacion = (c.strip() for c in f)
        m = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", fecha)
        if not m:
            raise ParlamentoInvalido(f"{donde}: fecha {fecha!r} no es AAAA/MM/DD")
        if estado not in ESTADOS_PEDIDO:
            raise ParlamentoInvalido(f"{donde}: estado {estado!r}; los medidos son {ESTADOS_PEDIDO}")
        lista = [a.strip() for a in autores.split("+") if a.strip()]
        if not lista or not oficio:
            raise ParlamentoInvalido(f"{donde}: un pedido sin autor o sin oficio")
        pedidos.append(
            {
                "organismo": organismo,
                "fecha": date(int(m.group(1)), int(m.group(2)), int(m.group(3))),
                "autores": lista,
                "tema": tema,
                "estado": estado,
                "url_oficio": oficio,
                "url_contestacion": contestacion or None,
            }
        )
    return pedidos


def _tasa(parte: int, total: int) -> Optional[float]:
    return round(100 * parte / total, 1) if total else None


def resumen_pedidos(
    pedidos: list[dict],
    hoy: date,
    nomina: Optional[list[dict]] = None,
    organismo: str = "",
    presentados_hasta: Optional[date] = None,
) -> dict:
    """Cuántos pedidos se contestaron, por organismo, sobre los que ya cumplieron el plazo.

    `pct_contestado_con_plazo_cumplido` se calcula sólo sobre los pedidos con más de `PLAZO_DIAS` días
    a `hoy` (trampa 10): un pedido de la semana pasada sin contestar no es un pedido incumplido. Con
    `nomina`, cuenta los pedidos por partido de sus autores (un pedido con autores de dos partidos
    cuenta en los dos) y los autores que no se pudieron identificar. Con `presentados_hasta`, sólo
    los pedidos presentados hasta esa fecha: para comparar organismos sobre una misma cohorte
    (trampa 10b). `por_semestre` muestra cómo cae la tasa en los pedidos más nuevos.
    """
    if organismo:
        clave = _sin_tildes(organismo)
        pedidos = [p for p in pedidos if clave in _sin_tildes(p["organismo"])]
        if not pedidos:
            raise ParlamentoInvalido(f"ningún pedido a un organismo que contenga {organismo!r}")
    if presentados_hasta is not None:
        pedidos = [p for p in pedidos if p["fecha"] <= presentados_hasta]
        if not pedidos:
            raise ParlamentoInvalido(f"ningún pedido presentado hasta {presentados_hasta}")

    def contar(grupo: list[dict]) -> dict:
        maduros = [p for p in grupo if (hoy - p["fecha"]).days > PLAZO_DIAS]
        estados = Counter(p["estado"] for p in grupo)
        return {
            "pedidos": len(grupo),
            **{e.lower().replace(" ", "_"): estados.get(e, 0) for e in ESTADOS_PEDIDO},
            "con_plazo_cumplido": len(maduros),
            "pct_contestado_con_plazo_cumplido": _tasa(sum(p["estado"] == "CONTESTADO" for p in maduros), len(maduros)),
        }

    por_organismo: dict[str, list[dict]] = {}
    for p in pedidos:
        por_organismo.setdefault(p["organismo"], []).append(p)
    repetidos = Counter((p["organismo"], p["fecha"], tuple(p["autores"]), p["tema"]) for p in pedidos)
    por_semestre: dict[str, list[dict]] = {}
    for p in pedidos:
        por_semestre.setdefault(f"{p['fecha'].year}-S{1 + (p['fecha'].month > 6)}", []).append(p)
    salida = {
        "desde": min(p["fecha"] for p in pedidos).isoformat(),
        "hasta": max(p["fecha"] for p in pedidos).isoformat(),
        "plazo_dias": PLAZO_DIAS,
        "total": contar(pedidos),
        "por_organismo": sorted(
            ({"organismo": o, **contar(g)} for o, g in por_organismo.items()), key=lambda x: -x["pedidos"]
        ),
        "por_semestre": [{"semestre": s, **contar(g)} for s, g in sorted(por_semestre.items())],
        "contestados_sin_enlace": sum(p["estado"] == "CONTESTADO" and not p["url_contestacion"] for p in pedidos),
        "con_varios_autores": sum(len(p["autores"]) > 1 for p in pedidos),
        "repetidos": sum(v - 1 for v in repetidos.values() if v > 1),
    }
    if nomina is not None:
        partidos: Counter = Counter()
        sin_identificar: Counter = Counter()
        for p in pedidos:
            vistos = set()
            for a in p["autores"]:
                persona = identificar(a, nomina)
                if persona is None:
                    sin_identificar[a] += 1
                else:
                    vistos.add(persona["partido"])
            for partido in vistos:
                partidos[partido] += 1
        salida["pedidos_por_partido"] = dict(partidos.most_common())
        salida["autores_sin_identificar"] = dict(sin_identificar.most_common())
    return salida


def recursos_por_legislatura(clave: str) -> dict[int, str]:
    """{legislatura: url} de un dataset por legislatura. **Sale a la red.**"""
    if clave not in DATASETS or clave == "leyes":
        raise ParlamentoInvalido(f"{clave!r}: asistencias-senado, asistencias-diputados o proyectos")
    out: dict[int, str] = {}
    for r in catalogo.recursos(DATASETS[clave]):
        leg = legislatura_del_titulo(r["nombre"])
        if r["formato"] != "CSV" or leg is None:
            continue
        if leg in out:
            raise ParlamentoInvalido(f"{DATASETS[clave]}: dos recursos para la legislatura {leg}")
        out[leg] = r["url"]
    return out


def descargar(clave: str, destino: Path, legislatura: Optional[int] = None) -> Path:
    """Baja un archivo: `leyes`, `pedidos-informes` o `nomina`, o `asistencias-senado`,
    `asistencias-diputados` o `proyectos` de una legislatura. **Sale a la red.**"""
    if clave in _ARCHIVO_UNICO:
        csvs = [r for r in catalogo.recursos(DATASETS[clave]) if r["formato"] == "CSV" and "etadato" not in r["nombre"]]
        if len(csvs) != 1:
            raise ParlamentoInvalido(f"{DATASETS[clave]}: {len(csvs)} CSV, se esperaba 1")
        return red.bajar(csvs[0]["url"], Path(destino))
    urls = recursos_por_legislatura(clave)
    if legislatura not in urls:
        raise ParlamentoInvalido(f"{clave}: no hay legislatura {legislatura}; hay {sorted(urls)}")
    return red.bajar(urls[legislatura], Path(destino))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.parlamento", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("bajar")
    b.add_argument("clave", choices=sorted(DATASETS))
    b.add_argument("legislatura_o_destino", nargs="+", help="[legislatura] destino")
    a = sub.add_parser("asistencias")
    a.add_argument("archivo", type=Path)
    a.add_argument("--minimo", type=int, default=10)
    a.add_argument("--nombre", default="")
    pe = sub.add_parser("pedidos")
    pe.add_argument("archivo", type=Path)
    pe.add_argument("--nomina", type=Path)
    args = ap.parse_args(argv)
    if args.orden == "pedidos":
        nomina = leer_nomina(args.nomina) if args.nomina else None
        r = resumen_pedidos(leer_pedidos(args.archivo), date.today(), nomina)
        t_ = r["total"]
        print(f"{t_['pedidos']} pedidos del {r['desde']} al {r['hasta']}")
        print(f"con el plazo de {r['plazo_dias']} días cumplido: {t_['con_plazo_cumplido']}")
        print(f"contestados, de los que ya cumplieron el plazo: {t_['pct_contestado_con_plazo_cumplido']}%")
        for o in r["por_organismo"]:
            print(f"  {o['organismo'][:45]:45} {o['pedidos']:>5} {o['pct_contestado_con_plazo_cumplido']}%")
        return 0
    if args.orden == "bajar":
        *leg, destino = args.legislatura_o_destino
        print(f"bajado {descargar(args.clave, Path(destino), int(leg[0]) if leg else None)}")
        return 0
    r = resumen_asistencias(leer_asistencias(args.archivo), args.minimo, args.nombre)
    print(f"{r['personas']} filas, {r['con_el_minimo']} con al menos {args.minimo} citaciones")
    print(f"sin nombre: {r['filas_sin_nombre']}; nombres repetidos: {r['nombres_repetidos']}")
    for f in r["encontrados"] or r["menor_asistencia"]:
        print(f"  {f['nombre']:35} {f['asistencias']:>4}/{f['citaciones']:<4} {f['pct_asistencia']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
