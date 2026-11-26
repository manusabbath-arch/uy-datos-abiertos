"""Resumen offline de informes de verificar; no mide disponibilidad actual."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path


def resumir(datos: dict) -> dict:
    fecha = datos["fecha"]
    if date.fromisoformat(fecha).isoformat() != fecha:
        raise ValueError("fecha no canónica")
    fuentes = datos["fuentes"]
    if not isinstance(fuentes, list):
        raise ValueError("fuentes debe ser lista")
    vistos = set()
    sellos = defaultdict(list)
    filas = []
    for f in fuentes:
        lector = f["lector"]
        if not isinstance(lector, str) or not re.fullmatch(r"[a-z0-9_]+", lector) or lector in vistos:
            raise ValueError("lector inválido o duplicado")
        vistos.add(lector)
        if type(f["ok"]) is not bool:
            raise ValueError("ok debe ser booleano")
        filas.append({"lector": lector, "estado": "lectura_ok" if f["ok"] else "sin_verificacion_ok"})
        if f["ok"]:
            digest = f["sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError(f"{lector}: sha256 inválido")
            if type(f["bytes"]) is not int or f["bytes"] < 0:
                raise ValueError(f"{lector}: bytes inválidos")
            sellos[digest].append(lector)
    alertas = [
        {"tipo": "sello_compartido", "sha256": sha, "lectores": sorted(nombres),
         "interpretacion": "Revisar alcance del sello; no demuestra error de la fuente."}
        for sha, nombres in sorted(sellos.items()) if len(nombres) > 1
    ]
    return {
        "version_esquema": 1, "fecha_informe_original": fecha,
        "registrados": len(filas), "lectura_ok": sum(f["ok"] for f in fuentes),
        "sin_verificacion_ok": sum(not f["ok"] for f in fuentes),
        "lectores": sorted(filas, key=lambda f: f["lector"]),
        "alertas": alertas,
        "alcance": "Informe histórico; no mide disponibilidad actual ni calidad integral.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("informe", type=Path)
    args = parser.parse_args(argv)
    bruto = args.informe.read_bytes()
    resultado = resumir(json.loads(bruto))
    resultado["sha256_informe_original"] = hashlib.sha256(bruto).hexdigest()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
