"""El contrato de forma de las fuentes: se baja cada una, se lee entera y se informa su forma.

`fuentes.deriva()` dice si la fecha del recurso se movió. Esto dice otra cosa: si el lector todavía
la lee. Medido el 2026-10-17, INUMET republica sus seis CSV todos los días, así que su fecha cambia
siempre y no es una alarma; una columna que falta, o 98.000 filas que se vuelven 12, sí.

La forma se mide sobre lo que el lector **devuelve**, no sobre el archivo: si el lector cambió de
columnas, el informe habla de los datos, no del nombre del CSV.

Medido el 2026-10-19: `limites` da un sha256 distinto en dos bajadas seguidas, con los mismos bytes
(4.709.102) y las mismas 20 filas —el WFS no serializa igual dos veces—. Ahí el sello no se compara
entre semanas; la forma sí.

    python -m uydatos.verificar                      # las trece que se verifican sin parámetros
    python -m uydatos.verificar ancap sanciones      # solo esas
    python -m uydatos.verificar --json datos/fuentes-2026-10-18.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional, Sequence

from uydatos import (
    ancap,
    ancap_ventas,
    bcu,
    catalogo,
    compras,
    elecciones,
    errores,
    fuentes,
    ibge,
    indec,
    inia,
    inumet,
    limites,
    parlamento,
    sanciones,
    ursea,
)


def _forma(filas: list[dict]) -> dict:
    """La forma de una lista de filas. Cero filas no es una fuente sana: es una fuente vacía."""
    if not filas:
        raise errores.DatosInvalidos("leyó cero filas: una fuente vacía no es una fuente sana")
    return {"filas": len(filas), "columnas": list(filas[0])}


def _serie(serie: dict) -> dict:
    """Una serie `{fecha: valor}` tiene la misma forma que una lista, con dos columnas."""
    if not serie:
        raise errores.DatosInvalidos("la serie llegó vacía")
    return {"filas": len(serie), "columnas": ["fecha", "valor"]}


def _sha(ruta: Path) -> tuple[int, str]:
    """Bytes y sha256 de un archivo, o del conjunto si es un directorio (por nombre y contenido).

    El sello de un directorio no puede ser el del último archivo: tiene que cambiar si cambia
    cualquiera, y no cambiar si se baja dos veces el mismo conjunto.
    """
    if ruta.is_file():
        datos = ruta.read_bytes()
        return len(datos), hashlib.sha256(datos).hexdigest()
    if ruta.is_dir():
        h, total = hashlib.sha256(), 0
        for p in sorted(ruta.rglob("*")):
            if p.is_file():
                b = p.read_bytes()
                total += len(b)
                h.update(p.relative_to(ruta).as_posix().encode())
                h.update(hashlib.sha256(b).digest())
        return total, h.hexdigest()
    raise OSError(f"el adaptador no dejó nada en {ruta}")


# Un adaptador por fuente, con la API que esa fuente tiene. No se inventa una interfaz común: lo que
# se unifica es la SALIDA (filas, columnas, bytes, sha256), que es lo único que se compara entre
# semanas. Un lector nuevo agrega su adaptador o su motivo en PENDIENTES, y el test lo exige.


def _de_ancap(d: Path) -> dict:
    ruta = ancap.descargar(d / "ancap.csv")
    return {"ruta": ruta, **_forma(ancap.leer_publicaciones(ruta))}


def _de_ancap_ventas(d: Path) -> dict:
    ruta = ancap_ventas.descargar(d / "ventas.csv")
    return {"ruta": ruta, **_forma(ancap_ventas.leer(ruta))}


def _de_bcu(d: Path) -> dict:
    """Un mes cerrado: el corriente puede no tener datos todavía y el rojo sería del calendario."""
    ayer = date.today().replace(day=1) - timedelta(days=1)
    mes = f"{ayer.year}-{ayer.month:02d}"
    bcu.descargar(9800, mes, mes, d)  # 9800 = Unidad Indexada
    return {"ruta": d, **_serie(bcu.leer_serie(d, 9800))}


def _de_compras(d: Path) -> dict:
    """El año más nuevo que el catálogo declara, no el corriente.

    Medido el 2026-10-19: el dataset llega a «Compras 2025» y `date.today().year` da
    `ComprasInvalido: no hay «Compras 2026»`, un rojo del calendario y no de la fuente.
    """
    nombres = [r["nombre"].strip() for r in catalogo.recursos(compras.DATASET)]
    anios = sorted(int(n.split()[-1]) for n in nombres if n.startswith("Compras ") and n.split()[-1].isdigit())
    if not anios:
        raise errores.DatosInvalidos(f"{compras.DATASET}: el catálogo no declara ningún «Compras AAAA»")
    ruta = compras.descargar(anios[-1], d / "compras.zip")
    return {"ruta": ruta, **_forma(compras.leer_adjudicaciones(ruta))}


def _de_elecciones(d: Path) -> dict:
    ruta = elecciones.descargar("nacionales-2024", "totales", d / "totales.csv")
    return {"ruta": ruta, **_forma(elecciones.leer_totales(ruta))}


def _de_ibge(d: Path) -> dict:
    ruta = ibge.descargar(d / "ipca.csv")
    return {"ruta": ruta, **_forma(ibge.leer(ruta))}


def _de_indec(d: Path) -> dict:
    ruta = indec.descargar(d / "ipc.json")
    return {"ruta": ruta, **_forma(indec.leer(ruta))}


def _de_inia(d: Path) -> dict:
    """57 CSV, uno por año: el sello es del conjunto (ver `_sha`)."""
    inia.descargar(d)
    return {"ruta": d, **_forma(inia.leer_serie(d))}


def _de_inumet(d: Path) -> dict:
    ruta = inumet.descargar("temperatura", d / "inumet.csv")
    return {"ruta": ruta, **_forma(inumet.leer_archivo(ruta, inumet.DATASETS["temperatura"][1]))}


def _de_limites(d: Path) -> dict:
    ruta = limites.descargar("departamentos", d / "deptos.json")
    return {"ruta": ruta, **_forma(limites.leer("departamentos", ruta))}


def _de_parlamento(d: Path) -> dict:
    """`proyectos` va por legislatura, no en un solo archivo.

    Medido el 2026-10-19: `descargar("proyectos", ...)` sin legislatura da
    `ParlamentoInvalido: no hay legislatura None; hay [42, ..., 50]`. Se mide la última publicada.
    `asistencias` pide además una cámara y va en PENDIENTES.
    """
    urls = parlamento.recursos_por_legislatura("proyectos")
    if not urls:
        raise errores.DatosInvalidos(f"{parlamento.DATASETS['proyectos']}: no declara ninguna legislatura")
    ruta = parlamento.descargar("proyectos", d / "proyectos.csv", max(urls))
    return {"ruta": ruta, **_forma(parlamento.leer_proyectos(ruta))}


def _de_sanciones(d: Path) -> dict:
    ruta = sanciones.descargar(d / "sanciones.csv")
    return {"ruta": ruta, **_forma(sanciones.leer(ruta))}


def _de_ursea(d: Path) -> dict:
    """`leer_ppi` devuelve `{"filas", "descartadas"}`, no una lista: el adaptador indexa las filas.

    Medido el 2026-10-19: pasarlo a `_forma` tal cual da `KeyError: 0` (el dict pasa el control de
    vacío y `filas[0]` no existe), que `main` informa como si el lector no estuviera en el manifiesto.
    """
    rutas = ursea.descargar(d)
    return {"ruta": d, **_forma(ursea.leer_ppi(rutas["ppi"])["filas"])}


VERIFICAR: dict[str, Callable[[Path], dict]] = {
    "ancap": _de_ancap,
    "ancap_ventas": _de_ancap_ventas,
    "bcu": _de_bcu,
    "compras": _de_compras,
    "elecciones": _de_elecciones,
    "ibge": _de_ibge,
    "indec": _de_indec,
    "inia": _de_inia,
    "inumet": _de_inumet,
    "limites": _de_limites,
    "parlamento": _de_parlamento,
    "sanciones": _de_sanciones,
    "ursea": _de_ursea,
}

PENDIENTES: dict[str, str] = {
    "catalogo": "el catálogo no es una fuente: se mide con `python -m uydatos.catalogo --faltantes`",
    "hojas": "un archivo de planilla",
    "ideuy": "una dirección",
    "mides": "un número de indicador",
    "observatorio": "un slug de indicador",
    "rut": "no lee una fuente: calcula el dígito verificador",
    "salto_grande": "una estación y una variable",
    "semanas": "no lee una fuente: cuenta semanas ISO",
}


def verificar(lector: str, destino: Optional[Path] = None) -> dict:
    """Baja y lee una fuente; devuelve su forma y su sello. **Sale a la red.**

    `destino` deja los archivos en disco (para mirarlos); si no se pasa, se usa un directorio
    temporal que se borra. Nunca levanta: un rechazo del lector se informa con `ok: False` y el
    motivo, porque el informe semanal tiene que decir las trece aunque una esté rota.
    """
    if lector not in fuentes.FUENTES:
        raise KeyError(f"{lector}: no está en el manifiesto")
    base = {"lector": lector, "filas": 0, "columnas": [], "bytes": 0, "sha256": ""}
    if lector in PENDIENTES:
        return {**base, "ok": False, "motivo": f"requiere {PENDIENTES[lector]}"}
    if destino is not None:
        destino.mkdir(parents=True, exist_ok=True)
        return _en(lector, destino, base)
    with tempfile.TemporaryDirectory() as tmp:
        return _en(lector, Path(tmp), base)


def _en(lector: str, directorio: Path, base: dict) -> dict:
    try:
        forma = VERIFICAR[lector](directorio)
        if forma.get("filas", 0) <= 0:
            raise errores.DatosInvalidos("leyó cero filas: una fuente vacía no es una fuente sana")
        ruta = forma.pop("ruta")
        bytes_, sha = _sha(ruta)
    except (errores.DatosInvalidos, OSError) as e:
        return {**base, "ok": False, "motivo": f"{type(e).__name__}: {e}"}
    return {**base, **forma, "ok": True, "motivo": "", "bytes": bytes_, "sha256": sha}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.verificar", description=__doc__.splitlines()[0])
    ap.add_argument("lectores", nargs="*", help="por defecto, todas las del manifiesto")
    ap.add_argument("--json", type=Path, help="deja el informe en un archivo, para comparar semanas")
    ap.add_argument("--destino", type=Path, help="deja los archivos bajados en este directorio")
    args = ap.parse_args(argv)
    informe = []
    for lector in sorted(args.lectores or fuentes.FUENTES):
        try:
            r = verificar(lector, args.destino)
        except KeyError as e:
            print(f"{lector:<14} --  {e}")
            return 2
        informe.append(r)
        if r["ok"]:
            detalle = (
                f"{r['filas']:>7} filas  {len(r['columnas']):>2} columnas  {r['bytes']:>10} bytes  {r['sha256'][:12]}"
            )
        else:
            detalle = r["motivo"]
        print(f"{lector:<14} {'ok' if r['ok'] else '--':<3} {detalle}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        cuerpo = {"fecha": date.today().isoformat(), "fuentes": informe}
        args.json.write_text(json.dumps(cuerpo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fallaron = [r["lector"] for r in informe if not r["ok"] and r["lector"] in VERIFICAR]
    return 1 if fallaron else 0


if __name__ == "__main__":
    raise SystemExit(main())
