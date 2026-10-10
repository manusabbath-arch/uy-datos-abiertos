# Plantilla: como se escribe un lector nuevo

Llenar cada punto en el docstring del modulo. **Un punto sin su medicion no se escribe**: si no se
midio, va como "sin medir", no como una suposicion.

## 1. La fuente

- Quien la publica, con la URL exacta de la API o del archivo.
- Si esta en el catalogo de datos abiertos: el identificador del dataset y el nombre del recurso.
- Cada cuanto cambia y si tiene fecha de corte.

Motivo: el 2026-10-09 el dataset de temperatura de INUMET cambio su fecha de modificacion el mismo
dia en que se midio. Una URL escrita en un README caduca; el catalogo, si se le pregunta, no.

## 2. La medicion

- La fecha en que se midio, en hora de Montevideo.
- El sha256 del archivo medido, su tamano y su cantidad de lineas.
- La codificacion y el delimitador.

Motivo: si el archivo cambia, el lector tiene que poder decir que la fuente se movio, y no devolver
una serie distinta sin avisar.

## 3. Las trampas (es lo que hace que el archivo valga la pena)

Cada una con el numero que la prueba:

- **Filas que no son datos**: subtotales, totales, y avisos del servidor dentro de una columna.
  Medido: en INUMET temperatura hay 332.070 filas de dato y 8 lineas sin dato, una con el texto de un
  error del servidor en la columna de la estacion. Agrupar por esa columna sin validarla crea una
  **octava estacion** y nada se pone rojo. La regla que quedo: fila sin fecha = no es fila de dato
  (se saltea y se cuenta); fila con fecha y fuera de contrato = se rechaza.
- **La cadencia real**: no todas las variables vienen hora a hora. Medido: el viento de INUMET
  publica **12 observaciones por dia** (10.841 de 11.690 dias-estacion). Medirlo contra 24 deja la
  variable entera vacia, en silencio.
- **El huso horario**: si la fuente publica en UTC, agregar "por dia" sobre la fecha cruda corta el
  dia local a las 21:00. El desfase va como parametro, no escondido en una constante.
- **Que significa un vacio**: nulo, nunca cero.
- **Si hay un valor imposible**: medido en la insolacion de INUMET, 4 valores por encima de 24 horas
  en 3.437 filas, tres el 01/08/2026 (Salto 63,2; Artigas 38,0; Mercedes 37,6), y ningun otro pasa de
  20. Un rango de 0 a 24 habria rechazado el archivo entero: se declara en los extremos del resumen
  y la columna queda **sin rango a proposito**.

## 4. El contrato

- Las columnas, con su tipo y su rango fisico. **Amplio**: atrapa un dato imposible, no uno raro
  (de -30 a 50 grados para temperatura en Uruguay).
- Las columnas que se dejan **sin** rango, y por que.
- Que hace el lector con una fila fuera de contrato: levanta, con el motivo.

La regla de fondo: **rechazar el archivo entero solo cuando el defecto cambia el dominio del dato**
(una estacion nueva, una columna mas); saltear y contar lo que no es un dato.

## 5. La salida

- Toda funcion publica que devuelve un numero cierra con el sello de `uydatos.procedencia`: fuente,
  fecha de la copia, sha256 y filas.
- El resumen declara los **extremos por columna**: es lo que deja ver el valor imposible sin romper
  la lectura.

## 6. La red

Se sale **solo** por `uydatos.red` (`pedir`, `bajar`). Nada de `urllib` suelto: el encabezado
`User-Agent`, los reintentos y los timeouts van en un solo lugar. Medido: el lector del BCU no
mandaba `User-Agent` hasta que se unifico, y nadie lo sabia.

## 7. Los tests

- Los de siempre: fixtures en `tmp_path` y la red reemplazada con `monkeypatch`.
- Y **uno contra el archivo real**, marcado con el marcador `red` de pytest, con el numero medido
  adentro y el por que de ese numero. Medido: 23 tests de unidad daban verde con un lector que no
  leia ningun archivo real.

## El ciclo

1. Medir el archivo real y anotar las trampas **antes** de escribir el lector.
2. Escribir el test y verlo en rojo.
3. Implementar lo minimo.
4. Correrlo contra el archivo real, no solo contra las fixtures.
5. `uvx ruff check src tests` y la suite entera.
6. Registrar lo medido en un documento con la fecha en el nombre, y commitear.
