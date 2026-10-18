"""El manifiesto de las fuentes: una fila por lector, y si la fuente se movió desde la medición.

Los ids de dataset no se escriben dos veces: se importan de la constante del módulo que ya los
declara (`ancap.DATASET`, `inumet.DATASETS`, `elecciones.ELECCIONES`, ...). Los lectores que no
pasan por el catálogo declaran `datasets=()` y su `deriva()` dice «se mide a mano»; `mides` también,
porque el dataset lo elige quien llama (`mides-indicador-NNNNN`) y no hay uno fijo que vigilar.

Medido el 2026-10-17 con `package_show`: de los ocho lectores con datasets fijos, cinco declaran
varios recursos por dataset — INIA 57 CSV (uno por año), Compras 24 ZIP que el catálogo declara
JSON, Parlamento hasta 10 CSV (uno por legislatura), Elecciones 4, URSEA 3. Por eso, cuando la fila
no nombra un archivo, la fecha que se mira es la del recurso más nuevo del dataset. La deriva avisa
que hay que mirar, no que el dato cambió.

Uso:
    python -m uydatos.fuentes            # el manifiesto, sin red
    python -m uydatos.fuentes estado     # el catálogo, lector por lector
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence, TypedDict

from uydatos import (
    ancap,
    ancap_ventas,
    catalogo,
    compras,
    elecciones,
    inia,
    inumet,
    parlamento,
    sanciones,
    ursea,
)


class Fuente(TypedDict):
    """Lo que hay que saber para preguntar «¿se movió?», sin recordar una URL."""

    lector: str
    tipo: str  # "catalogo" | "url" | "offline" | "archivo"
    datasets: tuple[str, ...]
    recurso: Optional[str]  # el nombre del ARCHIVO a buscar entre los recursos, si el lector lo usa
    medido: str  # AAAA-MM-DD, hora de Montevideo
    trampa: str  # una línea, la de la tabla del README


FUENTES: dict[str, Fuente] = {
    "ancap": {
        "lector": "ancap",
        "tipo": "catalogo",
        "datasets": (ancap.DATASET,),
        "recurso": ancap.NOMBRE_CSV,
        "medido": "2026-10-17",
        "trampa": "Las columnas Unidad y Valor vienen invertidas, y el archivo apila publicaciones.",
    },
    "ancap_ventas": {
        "lector": "ancap_ventas",
        "tipo": "catalogo",
        "datasets": (ancap_ventas.DATASET,),
        "recurso": ancap_ventas.NOMBRE_CSV,
        "medido": "2026-10-17",
        "trampa": (
            "La columna Unidad mezcla miles de m³ con toneladas, y el archivo es una ventana móvil "
            "de cinco años con huecos en el medio, no sólo al final."
        ),
    },
    "bcu": {
        "lector": "bcu",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "Una respuesta de error se guarda igual y parece un mes sin cotización.",
    },
    "catalogo": {
        "lector": "catalogo",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "Las URLs de descarga cambian cuando el organismo resube un archivo.",
    },
    "compras": {
        "lector": "compras",
        "tipo": "catalogo",
        "datasets": (compras.DATASET,),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "Un solo ítem es el 77% de lo adjudicado en pesos en 2024 (y otro el 53% en 2025), con "
            "cantidad × precio imposible. El total es cantidad × precio; hay llamados y anulaciones "
            "mezclados; el ZIP cambia de estructura entre años."
        ),
    },
    "elecciones": {
        "lector": "elecciones",
        "tipo": "catalogo",
        "datasets": tuple(e["dataset"] for e in elecciones.ELECCIONES.values()),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "Los observados no están en cada mesa: se escrutan en mesas especiales sin habilitados "
            "ni localidad. Sumar todo da el definitivo; un mapa por localidad nunca cierra con el total."
        ),
    },
    "hojas": {
        "lector": "hojas",
        "tipo": "archivo",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "El formato que declara el catálogo miente: 23 de 24 recursos «XLS» son XLSX. El motor "
            "sale de la firma del archivo, no del metadato."
        ),
    },
    "ibge": {
        "lector": "ibge",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "La tabla trae varias variables; una variación leída como índice no da error.",
    },
    "ideuy": {
        "lector": "ideuy",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "Ante lo que no encuentra devuelve el centro de la localidad, una puerta vecina u otra calle, sin error."
        ),
    },
    "indec": {
        "lector": "indec",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "La API sigue sirviendo las bases 2003 y 2008, discontinuadas.",
    },
    "inia": {
        "lector": "inia",
        "tipo": "catalogo",
        "datasets": (inia.DATASET,),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "El día va de 9:00 a 9:00; un vacío es nulo, no cero.",
    },
    "inumet": {
        "lector": "inumet",
        "tipo": "catalogo",
        "datasets": tuple(v[0] for v in inumet.DATASETS.values()),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "La columna estacion_id trae el nombre y puede traer el texto de un error del servidor; "
            "la hora es UTC, no local."
        ),
    },
    "limites": {
        "lector": "limites",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "Hay 20 polígonos de departamentos: uno es el límite contestado con Brasil, con el "
            "código de Artigas. Sin srsName=EPSG:4326 la capa llega en metros y ningún punto cae adentro."
        ),
    },
    "mides": {
        "lector": "mides",
        "tipo": "catalogo",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": ("El CSV viene en cp1252, no en UTF-8: leerlo mal convierte la ñ en basura y no falla."),
    },
    "observatorio": {
        "lector": "observatorio",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "La copia del catálogo quedó en 2019; la página viva llega a 2024. Dos formatos de "
            "número (las páginas viejas usan punto decimal y se rechazan), `-` y `.` son «sin dato», "
            "las filas «Total» van mezcladas y los mapas por departamento muestran un solo año."
        ),
    },
    "parlamento": {
        "lector": "parlamento",
        "tipo": "catalogo",
        "datasets": tuple(parlamento.DATASETS.values()),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "Hay 3 a 4 veces más personas que bancas (los suplentes): un ranking sin un mínimo de "
            "citaciones no dice nada. No hay identificador de persona, así que los homónimos no se "
            "pueden separar. Todos los recursos se llaman csv."
        ),
    },
    "rut": {
        "lector": "rut",
        "tipo": "offline",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "Excel convierte el RUT en float y se come el cero inicial.",
    },
    "salto_grande": {
        "lector": "salto_grande",
        "tipo": "url",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "El arreglo SOAP encoded se llama item: buscar Estacion da lista vacía sin error.",
    },
    "sanciones": {
        "lector": "sanciones",
        "tipo": "catalogo",
        "datasets": (sanciones.DATASET,),
        # El lector elige el ÚNICO CSV del dataset: no hay nombre de archivo que vigilar.
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "El nombre del recurso no es el nombre del archivo, el `rut` viene con relleno y una "
            "fila tiene un RUT de 3 caracteres."
        ),
    },
    "semanas": {
        "lector": "semanas",
        "tipo": "offline",
        "datasets": (),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": "El 01/01/2027 es la 2026-W53.",
    },
    "ursea": {
        "lector": "ursea",
        "tipo": "catalogo",
        "datasets": tuple(dataset for dataset, _ in ursea.ARCHIVOS.values()),
        "recurso": None,
        "medido": "2026-10-17",
        "trampa": (
            "Se compara sin impuestos contra sin impuestos; el PPI de una ventana rige el mes "
            "siguiente; el archivo ex planta de ANCAP es un registro acumulado con tres formatos de "
            "fecha y 93 pares contradictorios (todos de gases); una ventana del PPI termina antes de "
            "empezar; el recurso «PPI al consumidor final» fue pisado con otro archivo."
        ),
    },
}


def deriva(lector: str) -> dict:
    """¿El recurso que este lector usa se modificó después de la última medición? **Sale a la red.**

    No compara URLs: compara la fecha que el catálogo declara hoy contra `medido`. Una URL se
    pregunta al catálogo (lección de ANCAP 0.12.1: la republicación del 12/10 cambió el id) y una
    fecha no. `movido` significa «hay que volver a medir», no «el dato cambió»: el catálogo mueve
    `last_modified` cuando alguien vuelve a subir el mismo archivo.
    """
    f = FUENTES.get(lector)
    if f is None:
        raise KeyError(f"{lector}: no está en el manifiesto")
    if not f["datasets"]:
        return {"lector": lector, "movido": False, "motivo": "sin datasets fijos: se mide a mano", "detalle": []}

    def fecha(r: dict) -> str:
        return (r["modificado"] or "")[:10]

    detalle, movido = [], False
    for dataset in f["datasets"]:
        try:
            lista = catalogo.recursos(dataset)
        except catalogo.CatalogoInvalido as e:
            raise catalogo.CatalogoInvalido(f"{lector}/{dataset}: {e}") from e
        if f["recurso"]:
            # El lector reconoce su archivo por el nombre: exigir exactamente uno es lo que ya
            # hace `ancap.descargar()`, y dos candidatos significan que la fuente cambió.
            elegidos = [r for r in lista if r["url"].split("?")[0].rsplit("/", 1)[-1] == f["recurso"]]
            if len(elegidos) != 1:
                raise catalogo.CatalogoInvalido(
                    f"{lector}/{dataset}: {len(elegidos)} recursos para {f['recurso']}, se esperaba 1"
                )
            elegido = elegidos[0]
        else:
            # Sin nombre de archivo, la unidad es el dataset: el lector que no filtra por nombre
            # consume varios recursos (inia: 57 CSV, uno por año; compras: 24 ZIP que el catálogo
            # declara JSON; parlamento: 6 CSV, uno por legislatura). Se mira el CSV más nuevo —es
            # lo que el lector lee— y, si el dataset no declara ningún CSV (compras), todo recurso.
            candidatos = [r for r in lista if r["formato"] == "CSV"] or lista
            elegido = max(candidatos, key=fecha)
        modificado = fecha(elegido)
        cambio = bool(modificado) and modificado > f["medido"]
        detalle.append(
            {
                "dataset": dataset,
                "recurso": elegido["nombre"],
                "modificado": modificado,
                "cambio": cambio,
                "recursos": len(lista),
            }
        )
        movido = movido or cambio
    return {"lector": lector, "movido": movido, "motivo": "", "detalle": detalle}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """`python -m uydatos.fuentes` lista el manifiesto; `... estado` pregunta al catálogo."""
    ap = argparse.ArgumentParser(prog="python -m uydatos.fuentes", description=__doc__.splitlines()[0])
    ap.add_argument("accion", nargs="?", default="lista", choices=["lista", "estado"])
    args = ap.parse_args(argv)
    if args.accion == "lista":
        for nombre in sorted(FUENTES):
            f = FUENTES[nombre]
            print(f"{nombre:<14} {f['tipo']:<9} {len(f['datasets']):>2} datasets  medido {f['medido']}")
        return 0
    for nombre in sorted(FUENTES):
        try:
            r = deriva(nombre)
        except (catalogo.CatalogoInvalido, OSError) as e:
            print(f"{nombre:<14} ERROR {e}")
            continue
        marca = "SE MOVIÓ" if r["movido"] else "igual"
        print(f"{nombre:<14} {marca:<9} {r['motivo']}".rstrip())
        for d in r["detalle"]:
            if d["cambio"]:
                print(f"    {d['dataset']}  catálogo dice {d['modificado']}, medido {FUENTES[nombre]['medido']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
