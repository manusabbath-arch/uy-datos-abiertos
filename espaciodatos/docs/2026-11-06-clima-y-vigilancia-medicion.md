# Clima espacial de NOAA y la vigilancia entre copias — lo medido el 06/11/2026

Lectores: `espaciodatos.clima`, `espaciodatos.vigilancia`, y la capa `espaciodatos.herramientas`.
Sigue a `2026-11-06-neo-medicion.md`, el mismo día.

## 1. La vigilancia: dos copias a 31 minutos

Se bajaron Sentry, sus retirados y la lista de la ESA a las 15:59 UTC y otra vez a las 16:30 UTC.

| Archivo | sha256 15:59 (16) | sha256 16:30 (16) | Qué cambió de verdad |
|---|---|---|---|
| `sentry.json` | `b7b9a4ad9406a71a` | `bdcad1865d29f6a4` | 2 de 2.239 objetos (2026 VX1, 2026 UL1) |
| `sentry_retirados.json` | `7673b5842d44971f` | `d4976d398655948d` | ningún retiro nuevo entre las dos |
| `esa_riesgo.txt` | `06195d4e7b555bcd` | `227d6b6eab8f3da7` | `Last Update` 14:58 → 15:33 UTC; 1 nuevo (2026 VF2) y 14 cambiados |

- **Un sha256 distinto no dice qué cambió**: las tres copias cambiaron, y en Sentry el cambio es
  2 objetos de 2.239. Por eso la vigilancia compara objeto por objeto y campo por campo.
- **2026 VX1 se movió en direcciones opuestas en media hora**: JPL subió su Palermo de −7,27 a
  −7,05 (probabilidad 2,73e-6 → 5,97e-6; 18 → 11 impactos virtuales); la ESA lo bajó de −6,72 a
  −9,09.
- **Los que se mueven son los recién descubiertos**: los 14 cambios de la ESA son designaciones
  de las quincenas T, U y V de 2026 (octubre y noviembre).
- **2026 VC3**: JPL lo retiró a las 15:29:58 UTC y la ESA lo actualizó a las 15:33, todavía en
  su lista.

La regla adoptada: una copia de la ESA más vieja que la anterior se rechaza (comparar al revés
convierte las altas en bajas), y cada cambio se informa con el valor de antes y el de después.

## 2. NOAA SWPC (16:32 UTC)

| Archivo | Bytes | sha256 (16) | Qué trae |
|---|---|---|---|
| `products/noaa-planetary-k-index-forecast.json` | 6.906 | `9d860df07200…` | 81 franjas de 3 h: 61 `observed`, 3 `estimated`, 17 `predicted` |
| `products/noaa-scales.json` | 1.106 | `88b949dfeece…` | R/S/G: ayer, hoy, y pronóstico de hoy + 2 días |
| `products/alerts.json` | 55.219 | `4dfd250c7525…` | 86 mensajes, 2026-10-08 a 2026-11-06 |

Medidos y no usados por el lector: `noaa-planetary-k-index.json` (61 franjas observadas, idénticas
a las `observed` del pronóstico), `planetary_k_index_1m.json` (358 minutos), viento solar,
flujo de 10,7 cm y el óvalo auroral (919.341 bytes).

### Las trampas

1. **La tormenta empieza en Kp 4,67, no en 5.** Franjas con escala: G1 con Kp 4,67 (×3) y 5,0
   (×2), G2 con 6,0 (×1). Un umbral `Kp >= 5` pierde 3 de 6. El lector calcula G con los "−" de
   cada entero y **rechaza** si no coincide con el rótulo de NOAA.
2. **`estimated` no es pasado.** A las 16:32 UTC, las franjas de 18:00 y 21:00 ya eran
   `estimated`, y la de las 21:00 con G1.
3. **El mismo Kp con tres nombres**: `kp`, `Kp`, y en el archivo de 1 minuto `kp_index` (entero),
   `estimated_kp` y `kp` (`"3M"`). `kp_index` redondea la notación: `"3M"` = 2,67 trae 3.
4. **`time_tag` sin zona** en el Kp y con `Z` en el viento solar; los dos son UTC.
5. **La clave `"1"` de las escalas es hoy**, con la misma fecha que la `"0"`. En el pronóstico,
   R y S traen probabilidades como strings (`"35"`) y no escala.
6. **`product_id` no es el código del mensaje**: `K04W` contra `WARK04`. Los mensajes mezclan
   `\r\n` y `\n` y vienen del más nuevo al más viejo.

El estado ese momento, como lo lee el lector: Kp máximo de 24 h 3,67 (estimado), G1 estimado
para las 21:00 UTC y pronosticado tres veces más hasta el 08/11, coherente con el `WATA20`
("Geomagnetic Storm Category G1 Predicted") del 05/11 17:45 UTC.

## 3. Las herramientas, corridas contra las fuentes reales

`herramientas.actualizar()` bajó las 8 fuentes a una carpeta a las 16:35 UTC, y las seis
herramientas respondieron sobre esa copia. Dos defectos que aparecieron sólo así y se
corrigieron, con su test:

- **Un numerado llega como entero** (`objeto=99942` desde JSON, o desde un cliente MCP), y
  `designacion.clave` esperaba texto.
- **El sello de los retirados decía "JPL Sentry 2.0"**, igual que el del resumen, con la misma
  URL. Ahora dice "(retirados)" y lleva su URL.

## 4. Lo que no se midió

- Si `noaa-scales.json` y el pronóstico de Kp alguna vez se contradicen (ese día no).
- G3 a G5: los umbrales siguen la convención medida en G1 y G2, sin haberse visto.
- DONKI (NASA): queda afuera a propósito; se declara "prototyping quality".
