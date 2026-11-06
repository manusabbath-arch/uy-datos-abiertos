# Objetos cercanos a la Tierra: JPL y ESA — lo medido el 06/11/2026

Lectores: `espaciodatos.cad`, `espaciodatos.sentry`, `espaciodatos.bolidos`, `espaciodatos.esa`,
`espaciodatos.cruce`. El motivo de la medición: la investigación del 06/11 sobre proyectos de
datos espaciales recomendó empezar por objetos cercanos (APIs sin token, con versión declarada)
y planteó una pregunta de corte: **¿aparecen al menos 3 trampas reales y documentables?**
Respuesta medida: **sí, 20**, y el cruce entre agencias es un producto en sí mismo.

## 1. Las fuentes

| Fuente | URL | Formato | Versión |
|---|---|---|---|
| JPL CAD (acercamientos) | `https://ssd-api.jpl.nasa.gov/cad.api` | JSON, `fields` + `data` | 1.5 |
| JPL Sentry (riesgo de impacto) | `https://ssd-api.jpl.nasa.gov/sentry.api` (modos S, R, O) | JSON, lista de objetos | 2.0 |
| JPL Fireball (bólidos) | `https://ssd-api.jpl.nasa.gov/fireball.api` | JSON, `fields` + `data` | 1.2 |
| ESA NEOCC (riesgo de impacto) | `https://neo.ssa.esa.int/PSDB-portlet/download?file=esa_risk_list` | texto de ancho fijo con `\|` | — |

Las cuatro son abiertas, sin token y sin registro. Ninguna de JPL publica límites de uso; el
lector baja cada fuente una vez por corrida.

## 2. La medición (hora de Uruguay, 06/11/2026 12:59)

| Archivo | Consulta | Filas | Bytes | sha256 (16) |
|---|---|---|---|---|
| `cad.json` | 1900-01-01 a 2200-01-01, `dist-max=0.05`, `fullname`, `diameter` | 52.247 (20.248 objetos) | 10.740.795 | `691ce8c490321b7a` |
| `sentry.json` | modo S, sin filtros | 2.239 | 586.463 | `b7b9a4ad9406a71a` |
| `sentry_retirados.json` | `removed=1` | 3.596 | 184.663 | `7673b5842d447197` |
| `bolidos.json` | sin filtros | 1.074 | 76.456 | `6bfc721f21c85e2f` |
| `esa_riesgo.txt` | lista completa, `Last Update: 2026-11-06 14:58 UTC` | 2.205 | 300.322 | `06195d4e7b555bcd` |

## 3. Las trampas (cada una con el número que la prueba)

### Comunes a las APIs de JPL

1. **Los números llegan como strings**, en las tres APIs.
2. **`count` cambia de tipo**: entero en CAD (`52247`), string en Sentry (`"2239"`) y en Fireball
   (`"1074"`).
3. **La documentación y el API no coinciden**: Sentry documenta `"n_imp" : "9"` (string) y manda
   entero en los 2.239 registros (y en el modo O, también `ndel`, `ndop` y `nobs`).
4. **Un error viene con HTTP 200**: un objeto retirado de Sentry responde 200 con
   `"error": "specified object removed"`. Apophis: retirado el 2021-02-21 08:22:28. **2024 YR4:
   retirado el 2026-03-05 16:02:50.** Una designación mal escrita sí da 400.
5. **La versión**: la documentación pide revisar `signature.version`. La regla adoptada: se
   rechaza un cambio de versión **mayor**; el contrato real es la lista de campos, que se valida
   entera. Rechazar por cualquier versión convierte un campo nuevo en una caída.

### CAD

6. **`cd` no se ordena como texto**: el mínimo como string es `1900-Apr-03` y el primero real es
   del 4 de enero. **Le pasó a la medición misma**: "futuros a menos de 1 LD" contado con
   `cd > "2026"` dio 246; por `jd`, 107. Y `%b` de `strptime` depende del *locale*.
7. **TDB, no UTC**: `cd` y `jd` coinciden en las 52.247 filas (máx. 30 s, el redondeo), y TDB−UTC
   son ~69 s: **al minuto no importa**, pero el instante se etiqueta TDB.
8. **`t_sigma_f` en tres formatos**: `< 00:01` (19.886), `HH:MM` (19.042), `D_HH:MM` (13.319,
   hasta `9_17:20`).
9. **`dist_min = 0` en 14 filas**, varias en el pasado (2012 HA34 en 1945): es el mínimo 3σ
   recortado, no un impacto posible.
10. **`v_inf` nulo en 27 filas**, todas de minilunas o capturas temporales; pero 2020 CD3 lo trae
    nulo también en 2044 y 2061, fuera de su captura de 2017-2020. Se marca, no se explica.
11. **`h` nulo en 10 filas**, todas cometas.
12. **Diámetro nulo en el 97 %** (50.758 de 52.247).
13. **Ventana por defecto de 60 días**: una consulta sin fechas no trae "todo".

### Sentry

14. **El diámetro es una estimación** (albedo supuesto de 0,154, dice la documentación), presente
    en los 2.239 objetos. En CAD, 2.147 de esos objetos no tienen diámetro medido; donde los dos
    lo traen difieren hasta el doble (2015 XO129: 31 m contra 60 m).
15. **Torino nulo no es cero**: 2 objetos, los dos de mayor riesgo (1950 DA, Bennu), con impactos
    a más de 100 años, donde la escala no está definida.
16. **`last_obs` con día fraccionario** en 1 fila: Bennu, `2020-10-3.80160`.
17. **Los retirados traen cometas y relevamientos** (3 de 3.596): `P/2005 JQ5`, `P/2003 KV2` y
    `6344 P-L`. Leer `6344 P-L` como "número y lo que siga" da el asteroide 6344, que es otro.

### Fireball

18. **Latitud y longitud sin signo**, con el hemisferio aparte. En la caja de Uruguay, ignorando
    la dirección, hay 4 bólidos; con la dirección, **1**: 2008-04-07 01:02:28 UTC, 31,8 °S 58,5 °W,
    0,076 kt. Con signo positivo cae en Irán. Ubicación todo-o-nada (186 sin ubicación), altura
    nula en 472, velocidad nula en 711; orden por defecto descendente.

### ESA

19. **Designación sin espacio** (`2008JL3`) y numerado con quince espacios
    (`443104               2013XK22`): contra JPL, **0 coincidencias** por texto; con la clave
    normalizada, 1.974.
20. **Torino con dos ausencias**: `n/a` (20) y `n/d` (5), todas con impacto en 2126: los `n/a`
    hasta 2126-11-06 06:36, los `n/d` desde 2126-11-14. El archivo no documenta la diferencia:
    se conserva el código. Diámetro en **metros** (JPL: km), con marca de estimado (9 medidos).

## 4. El cruce JPL contra ESA

| | Objetos |
|---|---|
| En la lista de JPL | 2.239 |
| En la lista de la ESA | 2.205 |
| En las dos | 1.974 |
| Sólo en la ESA | 231, de los cuales **175 fueron retirados por JPL** (desde 2020) |
| Sólo en JPL | 265, de los cuales sólo 2 están fuera del horizonte de la ESA (2127) |
| Palermo acumulado distinto en más de 1 (×10) | 292 de 1.974 |
| … en más de 2 (×100) | 89 |

- **El primero de cada lista es otro**: 29075 (1950 DA, impacto posible en 2880) en JPL;
  2008 JL3 en la ESA. 1950 DA y Bennu no están en la ESA **por horizonte**, no por desacuerdo.
- **Lo que la ESA lista y JPL retiró**, por Palermo en la ESA: 2014 ML67 (−3,81; retirado por JPL
  el 2021-08-09), 2008 FF5 (−3,96; 2021-04-20), 2016 GU2 (−4,48; 2021-05-02), 2023 XJ2 (−5,37;
  2024-07-09).
- **Duende (367943, 2012 DA14)**, impactos 2116-2122, dentro del horizonte de la ESA, está en
  JPL y no en la ESA.
- **Las mayores diferencias**: 2026 TU8 (JPL −7,87, ESA −12,83), 2010 VQ (−4,41 contra −9,21),
  2025 KE4 (−8,61 contra −13,24).

El cruce no dice quién tiene razón. Dice dónde mirar, con la fecha de cada lista.

## 5. Lo que no se midió

- El modo V de Sentry (impactos virtuales de todos los objetos) y Scout (objetos sin confirmar
  del NEOCP): el segundo cambia cada hora y necesita otro diseño (copias fechadas).
- La lista de retirados de la ESA: el pedido `file=past_esa_risk_list` respondió 0 bytes.
- El significado de `n/a` contra `n/d` en el Torino de la ESA.
- La escala de tiempo del "VI Max Date/Time" de la ESA.

## 6. Cómo se repite

```bash
cd espaciodatos
uv run --with-editable .. --with-editable . python -m espaciodatos todo datos/   # baja y cruza
uv run --with pytest --with-editable .. --with-editable . pytest -q -m red      # contra las fuentes
```
