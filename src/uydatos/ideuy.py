"""Geocodificación de direcciones uruguayas con la API pública de IDE.uy (direcciones.ide.uy).

Es la fuente oficial (Infraestructura de Datos Espaciales, IGM/SNC): número de puerta
georreferenciado, no interpolado, y entiende formatos uruguayos que otros geocodificadores manejan
mal, como las esquinas y los pueblos chicos. Gratuita y sin clave.

Las trampas: la API "encuentra" algo casi siempre
-------------------------------------------------
1. **v0 `BusquedaDireccion` ante una dirección que no encuentra devuelve el centroide de la
   localidad** (`idTipoClasificacion` 3, `error` = 'APROXIMADO POR LOCALIDAD'). Eso no es la
   coordenada de la dirección: se clasifica `localidad_descartada` y no se devuelve coordenada.
2. **La misma API ajusta la puerta a la existente más cercana** (se pide 1210, devuelve 1207,
   `error` = 'APROXIMADO POR CALLE'). Es `puerta_aproximada`; solo es `puerta_exacta` si la puerta
   devuelta coincide con la pedida.
3. **v0 también puede devolver OTRA calle.** Pedir una calle inexistente devolvió "CALLE N 2570"
   con el aviso 'APROXIMADO POR CALLE', idéntico al de una puerta ajustada. Se compara la calle
   devuelta con la pedida (`misma_calle`) y, si no comparten ninguna palabra, es `calle_distinta`.
4. **v1 `direcUnica` (texto libre) puede devolver otra ciudad sin avisar.** Por eso se usa solo
   para esquinas, y solo se acepta de ella una respuesta `ESQUINA`. Una esquina le gana al centro
   de una avenida larga, pero no a una puerta.
5. **v0 llama `puntoX` a la longitud y `puntoY` a la latitud.** Trasponerlas no da error: en
   Uruguay las dos son números negativos plausibles.

Calidades, de mejor a peor: `puerta_exacta` > `puerta_aproximada` > `esquina` > `calle_sin_numero`.
`calle_distinta`, `localidad_descartada` y `no_encontrado` no traen coordenada. Toda coordenada se controla contra el
rectángulo de Uruguay (`dentro_de_uruguay`).

El servicio no publica un límite de pedidos: para lotes, dejar al menos medio segundo entre
consultas.

Uso:
    python -m uydatos.ideuy "Avenida 18 de Julio 1360" --localidad Montevideo --departamento Montevideo
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from typing import Optional, Sequence

from uydatos import red

URL_V0 = "https://direcciones.ide.uy/api/v0/geocode/BusquedaDireccion"
URL_V1 = "https://direcciones.ide.uy/api/v1/geocode/direcUnica"

UY_BBOX = {"lat_min": -35.0, "lat_max": -30.0, "lon_min": -58.5, "lon_max": -53.0}

PUERTA_EXACTA = "puerta_exacta"
PUERTA_APROXIMADA = "puerta_aproximada"
ESQUINA = "esquina"
CALLE = "calle_sin_numero"
CALLE_DISTINTA = "calle_distinta"
LOCALIDAD = "localidad_descartada"
NO_ENCONTRADO = "no_encontrado"

_ORDEN = [PUERTA_EXACTA, PUERTA_APROXIMADA, CALLE, CALLE_DISTINTA, LOCALIDAD]
_CON_PUERTA = (PUERTA_EXACTA, PUERTA_APROXIMADA)

# Palabras que no identifican una calle: tipos de vía, títulos y conectores.
_GENERICAS = {
    "AVENIDA", "AVDA", "CALLE", "BULEVAR", "BLVR", "CAMINO", "PASAJE", "RAMBLA", "RUTA",
    "DOCTOR", "GENERAL", "GRAL", "INGENIERO", "PRESIDENTE", "CORONEL", "CNEL", "MAESTRO", "SANTA", "SAN",
    "DEL", "LAS", "LOS", "ESQ", "ESQUINA",
}  # fmt: skip


def extraer_numero_puerta(direccion: str) -> Optional[int]:
    """El número de puerta pedido, o None. Antes se quita lo que parece número y no es puerta:
    nombres de calle con fecha ('18 DE JULIO 1234'), paréntesis, número de local o vivienda
    ('Nº 5', 'B° 34') y rutas ('RUTA 3 KM 405', que es otro formato)."""
    if not direccion:
        return None
    d = direccion.upper()
    if re.search(r"\bRUTA\b|\bKM\b", d):
        return None
    d = re.sub(r"\b\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑÜ]+\b", " ", d)
    d = re.sub(r"\([^)]*\)", " ", d)
    d = re.sub(r"\bN[º°.]?\s*\d+\b", " ", d)
    d = re.sub(r"\bB[º°.]?\s*\d+\b", " ", d)
    numeros = re.findall(r"\b\d{1,5}\b", d)
    return int(numeros[-1]) if numeros else None


_SEPARADOR_ESQUINA = re.compile(r"\s*\bESQ(?:UINA)?\b\.?\s*|\s+Y\s+", re.IGNORECASE)


def calles_de_esquina(direccion: str) -> Optional[tuple[str, str]]:
    """Las dos calles de una esquina ('ESQ.', 'ESQUINA' o ' Y '), o None si no es una esquina."""
    partes = _SEPARADOR_ESQUINA.split(direccion or "", maxsplit=1)
    if len(partes) != 2 or not all(p.strip() for p in partes):
        return None
    return partes[0].strip(), partes[1].strip()


def es_esquina(direccion: str) -> bool:
    return calles_de_esquina(direccion) is not None


def _palabras(texto: str) -> set[str]:
    sin_tildes = unicodedata.normalize("NFKD", texto.upper()).encode("ascii", "ignore").decode()
    return {p for p in re.findall(r"[A-Z]+", sin_tildes) if len(p) >= 3 and p not in _GENERICAS}


def misma_calle(pedida: str, devuelta: str) -> bool:
    """¿La calle devuelta es la pedida? Compara las palabras significativas de la primera calle
    pedida (antes de una esquina) contra las de la devuelta. Sin palabras para comparar ('Calle 5'),
    no hay cómo verificar y no se descarta."""
    esquina = calles_de_esquina(pedida)
    buscadas = _palabras(esquina[0] if esquina else pedida)
    return not buscadas or bool(buscadas & _palabras(devuelta))


def url_v0(direccion: str, localidad: str = "", departamento: str = "") -> str:
    params = red.codificar({"calle": direccion, "localidad": localidad, "departamento": departamento})
    return f"{URL_V0}?{params}"


def url_v1(direccion: str, localidad: str = "", departamento: str = "") -> str:
    """v1 reconoce una esquina escrita con 'ESQ' y no con 'Y': '18 DE JULIO Y EJIDO' devuelve solo
    la avenida. Por eso la ' Y ' viaja como ' ESQ '."""
    direccion = re.sub(r"\s+Y\s+", " ESQ ", direccion, flags=re.IGNORECASE)
    partes = [p for p in (direccion, localidad, departamento, "Uruguay") if p]
    return f"{URL_V1}?{red.codificar({'q': ', '.join(partes)})}"


def coordenadas_v0(item: dict) -> Optional[tuple[float, float]]:
    """(lat, lon) de una respuesta v0. Ojo: `puntoX` es la LONGITUD."""
    try:
        return float(item["puntoY"]), float(item["puntoX"])
    except (KeyError, TypeError, ValueError):
        return None


def coordenadas_v1(item: dict) -> Optional[tuple[float, float]]:
    try:
        return float(item["lat"]), float(item["lng"])
    except (KeyError, TypeError, ValueError):
        return None


def _puerta(item: dict) -> Optional[int]:
    return ((item.get("direccion") or {}).get("numero") or {}).get("nro_puerta")


def _calle(item: dict) -> str:
    return ((item.get("direccion") or {}).get("calle") or {}).get("nombre_normalizado") or ""


def clasificar_v0(item: dict, numero_pedido: Optional[int], direccion: str = "") -> str:
    """'La API devolvió algo' no es 'encontró la dirección'. Con `direccion`, además se verifica que
    la calle devuelta sea la pedida."""
    if not item:
        return LOCALIDAD
    error = str(item.get("error") or "")
    if "APROXIMADO POR LOCALIDAD" in error or item.get("idTipoClasificacion") == 3:
        return LOCALIDAD
    if direccion and _calle(item) and not misma_calle(direccion, _calle(item)):
        return CALLE_DISTINTA
    numero = _puerta(item)
    if numero is not None:
        if numero_pedido is not None and numero == numero_pedido and "APROXIMADO" not in error:
            return PUERTA_EXACTA
        return PUERTA_APROXIMADA
    return CALLE


def clasificar_v1(item: dict) -> Optional[str]:
    """De v1 solo se acepta una ESQUINA: cualquier otra cosa puede ser otra calle u otra ciudad."""
    if not item or item.get("state") != 1:
        return None
    return ESQUINA if item.get("type") == "ESQUINA" else None


def elegir_v0(resultados: list, numero_pedido: Optional[int], direccion: str = "") -> tuple[str, Optional[dict]]:
    """La mejor respuesta v0. Si la mejor es descartable (otra calle o la localidad), no hay item."""
    if not resultados:
        return NO_ENCONTRADO, None
    clasificados = [(clasificar_v0(item, numero_pedido, direccion), item) for item in resultados]
    mejor = min((c for c, _ in clasificados), key=_ORDEN.index)
    if mejor in (CALLE_DISTINTA, LOCALIDAD):
        return mejor, None
    return mejor, next(item for c, item in clasificados if c == mejor)


def dentro_de_uruguay(lat: float, lon: float) -> bool:
    return UY_BBOX["lat_min"] <= lat <= UY_BBOX["lat_max"] and UY_BBOX["lon_min"] <= lon <= UY_BBOX["lon_max"]


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine: distancia en línea recta."""
    rad = math.radians
    dlat, dlon = rad(lat2 - lat1), rad(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def _consultar(url: str) -> list:
    """Una consulta a IDE.uy. **Sale a la red.** Los tests la reemplazan con `monkeypatch`."""
    datos = json.loads(red.pedir(url, timeout=30).decode("utf-8"))
    return datos if isinstance(datos, list) else []


def _vacio(direccion: str, localidad: str, departamento: str) -> dict:
    return {
        "direccion": direccion,
        "localidad": localidad,
        "departamento": departamento,
        "calidad": NO_ENCONTRADO,
        "lat": None,
        "lon": None,
        "dentro_de_uruguay": None,
        "puerta_pedida": extraer_numero_puerta(direccion),
        "puerta_devuelta": None,
        "direccion_devuelta": "",
        "metodo": "",
        "aviso_de_la_api": "",
    }


def interpretar(
    direccion: str, localidad: str, departamento: str, respuesta_v0: list, respuesta_v1: Optional[list] = None
) -> dict:
    """Arma el resultado a partir de las respuestas de la API, sin red. `geocodificar` lo usa; sirve
    también para reprocesar respuestas guardadas."""
    fila = _vacio(direccion, localidad, departamento)
    calidad, item = elegir_v0(respuesta_v0, fila["puerta_pedida"], direccion)
    fila["calidad"] = calidad
    if calidad not in _CON_PUERTA:
        for v1 in respuesta_v1 or []:
            if clasificar_v1(v1) == ESQUINA and misma_calle(direccion, str(v1.get("address") or "")):
                if coords := coordenadas_v1(v1):
                    fila.update(
                        calidad=ESQUINA,
                        lat=coords[0],
                        lon=coords[1],
                        dentro_de_uruguay=dentro_de_uruguay(*coords),
                        direccion_devuelta=str(v1.get("address") or ""),
                        metodo="IDE.uy v1 direcUnica (ESQUINA)",
                    )
                    return fila
    if item is not None and (coords := coordenadas_v0(item)):
        d = item.get("direccion") or {}
        partes = [
            (d.get("calle") or {}).get("nombre_normalizado"),
            str(_puerta(item) or "") or None,
            (d.get("localidad") or {}).get("nombre_normalizado"),
        ]
        fila.update(
            lat=coords[0],
            lon=coords[1],
            dentro_de_uruguay=dentro_de_uruguay(*coords),
            puerta_devuelta=_puerta(item),
            direccion_devuelta=" ".join(p for p in partes if p),
            metodo="IDE.uy v0 BusquedaDireccion",
            aviso_de_la_api=" ".join(str(item.get("error") or "").split()),
        )
    return fila


def geocodificar(direccion: str, localidad: str = "", departamento: str = "") -> dict:
    """Una dirección contra IDE.uy. **Sale a la red.**

    Primero v0, que respeta la localidad y el departamento y declara su propia calidad. Si la
    dirección es una esquina y v0 no encontró una puerta, prueba v1 y acepta solo una ESQUINA.
    v1 depende del orden: '18 DE JULIO ESQ EJIDO' no devolvió nada y 'EJIDO ESQ 18 DE JULIO' la
    esquina, así que si el primer orden no da una esquina se prueba el inverso.
    """
    v0 = _consultar(url_v0(direccion, localidad, departamento))
    v1, aviso = None, ""
    esquina = calles_de_esquina(direccion)
    if esquina and elegir_v0(v0, extraer_numero_puerta(direccion), direccion)[0] not in _CON_PUERTA:
        for pedido in (f"{esquina[0]} ESQ {esquina[1]}", f"{esquina[1]} ESQ {esquina[0]}"):
            try:
                v1 = _consultar(url_v1(pedido, localidad, departamento))
            except OSError as e:  # v1 tarda y corta seguido: no se pierde lo que dio v0
                aviso = f"la búsqueda de esquina (v1) no respondió: {e}"
                break
            if any(clasificar_v1(item) == ESQUINA for item in v1):
                break
    fila = interpretar(direccion, localidad, departamento, v0, v1)
    if aviso:
        fila["aviso_de_la_api"] = " | ".join(a for a in (fila["aviso_de_la_api"], aviso) if a)
    return fila


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.ideuy", description=__doc__.splitlines()[0])
    ap.add_argument("direccion")
    ap.add_argument("--localidad", default="")
    ap.add_argument("--departamento", default="")
    args = ap.parse_args(argv)
    r = geocodificar(args.direccion, args.localidad, args.departamento)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
