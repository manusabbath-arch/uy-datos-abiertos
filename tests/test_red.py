"""La unica salida a la red del paquete: `User-Agent`, timeout y reintentos en un lugar."""

from __future__ import annotations

import http.client
import tracemalloc
import urllib.error

import pytest

from uydatos import USER_AGENT, red


class _Respuesta:
    def __init__(self, datos: bytes):
        self._datos = datos
        self._leido = False

    def read(self, n=None) -> bytes:
        # `HTTPResponse.read(n)` consume: con `n=None` da el cuerpo entero una vez
        # y luego vacio; con `n` entrega trozos. La fake imita ese contrato.
        if self._leido:
            return b""
        self._leido = True
        return self._datos

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestUserAgentYTimeout:
    def test_toda_peticion_lleva_el_user_agent_del_paquete(self, monkeypatch):
        visto = {}

        def abrir(pedido, timeout):
            visto["ua"] = pedido.get_header("User-agent")
            visto["timeout"] = timeout
            return _Respuesta(b"ok")

        monkeypatch.setattr(red, "_abrir", abrir)
        assert red.pedir("https://ejemplo.uy/x") == b"ok"
        assert visto["ua"] == USER_AGENT
        assert visto["timeout"] == red.TIMEOUT

    def test_las_cabeceras_propias_ganan_sobre_la_del_paquete(self, monkeypatch):
        visto = {}

        def abrir(pedido, timeout):
            visto["ct"] = pedido.get_header("Content-type")
            return _Respuesta(b"")

        monkeypatch.setattr(red, "_abrir", abrir)
        red.pedir("https://ejemplo.uy/x", datos=b"<x/>", cabeceras={"Content-Type": "text/xml"})
        assert visto["ct"] == "text/xml"


class TestReintentos:
    def test_reintenta_un_error_de_red_y_termina_bien(self, monkeypatch):
        intentos = []

        def abrir(pedido, timeout):
            intentos.append(1)
            if len(intentos) < 3:
                raise urllib.error.URLError("sin ruta al host")
            return _Respuesta(b"ok")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        assert red.pedir("https://ejemplo.uy/x") == b"ok"
        assert len(intentos) == 3

    def test_un_404_no_se_reintenta(self, monkeypatch):
        intentos = []

        def abrir(pedido, timeout):
            intentos.append(1)
            raise urllib.error.HTTPError("https://ejemplo.uy/x", 404, "Not Found", {}, None)

        monkeypatch.setattr(red, "_abrir", abrir)
        with pytest.raises(OSError, match="404"):
            red.pedir("https://ejemplo.uy/x")
        assert len(intentos) == 1

    def test_si_se_agotan_los_intentos_el_error_dice_cuantos(self, monkeypatch):
        def abrir(pedido, timeout):
            raise urllib.error.URLError("sin ruta al host")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        with pytest.raises(OSError, match="3 intentos"):
            red.pedir("https://ejemplo.uy/x")

    def test_reintenta_una_lectura_truncada_y_termina_bien(self, monkeypatch):
        """Medido el 2026-11-16: el archivo de compras de 27 MB llego cortado a
        `mcp-uruguay` y el cron se cayo. `IncompleteRead` no es un `OSError`, asi
        que salia del bucle sin reintentar."""
        intentos = []

        class _Cortada(_Respuesta):
            def read(self, n=None) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        def abrir(pedido, timeout):
            intentos.append(1)
            if len(intentos) == 1:
                return _Cortada(b"")
            return _Respuesta(b"ok")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        assert red.pedir("https://ejemplo.uy/x") == b"ok"
        assert len(intentos) == 2

    def test_si_todas_las_lecturas_se_truncan_el_error_nombra_la_causa(self, monkeypatch):
        class _Cortada(_Respuesta):
            def read(self, n=None) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _Cortada(b""))
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        with pytest.raises(OSError, match="IncompleteRead"):
            red.pedir("https://ejemplo.uy/x")


class TestBajar:
    def test_una_respuesta_vacia_no_se_escribe(self, monkeypatch, tmp_path):
        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _Respuesta(b""))
        destino = tmp_path / "x.csv"
        with pytest.raises(OSError, match="vacia"):
            red.bajar("https://ejemplo.uy/x", destino)
        assert not destino.exists()

    def test_lo_bajado_se_escribe_tal_cual_vino(self, monkeypatch, tmp_path):
        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _Respuesta(b"a;b\n1;2\n"))
        destino = red.bajar("https://ejemplo.uy/x", tmp_path / "sub" / "x.csv")
        assert destino.read_bytes() == b"a;b\n1;2\n"

    def test_un_archivo_cortado_se_rebaja_entero(self, monkeypatch, tmp_path):
        intentos = []

        class _Cortada(_Respuesta):
            def read(self, n=None) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        def abrir(pedido, timeout):
            intentos.append(1)
            if len(intentos) == 1:
                return _Cortada(b"")
            return _Respuesta(b"a;b\n1;2\n")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        destino = red.bajar("https://ejemplo.uy/x", tmp_path / "compras.csv")
        assert destino.read_bytes() == b"a;b\n1;2\n"

    def test_una_bajada_grande_no_pasa_el_cuerpo_por_memoria(self, monkeypatch, tmp_path):
        """Medido el 2026-11-16 con `pedir` y `bajar`: 27 MB de archivo dan 27 MB de
        pico. `bajar` escribe en trozos: el pico queda en un trozo y el buffer, no
        en el archivo entero. El contenido de la fake se preasigna antes de trazar
        para que los trozos no cuenten en la medicion."""
        trozos = [b"x" * red.CHUNK for _ in range(48)]  # 48 * 64 KiB = 3 MiB
        cuerpo = b"".join(trozos)

        class _EnTrozos:
            def __init__(self, trozos):
                self._trozos = list(trozos)

            def read(self, n=None) -> bytes:
                return self._trozos.pop(0) if self._trozos else b""

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _EnTrozos(trozos))
        destino = tmp_path / "grande.csv"
        tracemalloc.start()
        try:
            red.bajar("https://ejemplo.uy/x", destino)
            pico = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert destino.read_bytes() == cuerpo
        assert pico < 1024 * 1024  # menos de un tercio del cuerpo; la bajada entera en memoria daba >= 3 MiB

    def test_dos_bajadas_a_la_vez_no_publican_un_archivo_mezclado(self, monkeypatch, tmp_path):
        """El parcial era `.<destino>.parcial`: dos bajadas al mismo destino compartían el temporal."""
        import threading
        from concurrent.futures import ThreadPoolExecutor

        barrera = threading.Barrier(2, timeout=10)

        class _EnDosTandas(_Respuesta):
            def __init__(self, trozos):
                self._trozos, self._i = trozos, 0

            def read(self, n=None) -> bytes:
                if self._i >= len(self._trozos):
                    return b""
                trozo = self._trozos[self._i]
                self._i += 1
                if self._i == 2:  # entre la primera tanda y la segunda, el otro escribe la suya
                    barrera.wait()
                return trozo

        letras = iter("AB")
        tandas = {"A": [b"A" * 400, b"A" * 400], "B": [b"B" * 400, b"B" * 100]}
        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _EnDosTandas(tandas[next(letras)]))
        destino = tmp_path / "x.csv"
        una, otra = b"A" * 800, b"B" * 500

        def bajar(_):
            try:
                red.bajar("https://ejemplo.uy/x", destino)
            except Exception as e:  # noqa: BLE001 - el fallo es lo que se está midiendo
                return e
            return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            salidas = list(pool.map(bajar, range(2)))
        assert all(s is None for s in salidas), salidas
        # Se lee recién cuando los dos terminaron: en Windows, leer mientras el otro hace el
        # `os.replace` es un `PermissionError` del sistema, no una copia mezclada.
        assert destino.read_bytes() in {una, otra}
        assert list(tmp_path.iterdir()) == [destino]  # tampoco quedan parciales

    def test_bajar_que_falla_no_deja_archivo_ni_parcial(self, monkeypatch, tmp_path):
        """El `destino` nunca queda parcial: se baja a un temporal en la misma
        carpeta y se publica con `os.replace` solo si la bajada salio entera."""

        class _CortadaSiempre(_Respuesta):
            def read(self, n=None) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _CortadaSiempre(b""))
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        with pytest.raises(OSError, match="IncompleteRead"):
            red.bajar("https://ejemplo.uy/x", tmp_path / "compras.csv")
        assert not (tmp_path / "compras.csv").exists()
        assert list(tmp_path.iterdir()) == []  # tampoco queda el temporal
