# Como se trabaja en `uydatos`

Lectores estrictos de datos publicos de Uruguay y la region. **Sin dependencias**: biblioteca
estandar y nada mas.

## Los comandos

```bash
uvx ruff check src tests                                  # All checks passed!
uvx ruff format src tests                                 # o --check, si no queres que escriba
uv run --with pytest --with-editable . pytest -q          # la suite sin red, segundos
uv run --with pytest --with-editable . pytest -m red -q   # contra las fuentes reales, minutos
```

## Las reglas del paquete

1. **Un lector rechaza en vez de arreglar.** Si el dato no cumple el contrato, levanta con el
   motivo. Un numero plausible pero falso es peor que un error.
2. **Un vacio es nulo, nunca cero.**
3. **Toda cifra se puede citar**: de que archivo salio, de cuando es y con que sha256. Para eso
   esta `uydatos.procedencia`.
4. **Nada sale a la red si no es por `uydatos.red`.** Un solo lugar para el encabezado
   `User-Agent`, los timeouts y los reintentos.
5. **Si algo necesita una dependencia** (leer `.xlsx`, por ejemplo), entra como extra opcional
   (se instala con `uydatos[hojas]`) y el error explica como hacerlo. El paquete base no engorda.
6. **No ordenes los imports a mano**: los ordena `ruff`.
7. **Nada de re-tipear un numero de memoria.** Los numeros van medidos con su fecha, y los tests
   marcados como de red los fijan para que se note si el mundo cambio.

## Como se escribe un lector nuevo

Esta en `docs/plantilla-lector.md`, punto por punto, con el motivo medido de cada uno.

## Como se llaman las cosas

- Modulos y funciones en castellano: `resumen`, `valor_por_estacion`, `filas_sin_dato`.
- La excepcion de cada fuente lleva su nombre: `BcuInvalido`, `InumetInvalido`.
- Todo archivo abre con `from __future__ import annotations`.

## Commits

Chicos, en castellano, con el formato `tipo(alcance): que`, y el cuerpo diciendo **que se midio**,
no que se toco:

```
feat(inumet): observaciones horarias de INUMET, con la trampa del error del servidor
fix(catalogo): el 0 del filtro por etiqueta no es "no hay datos"
```

## El push y la publicacion los decide una persona

Las ramas y los commits locales son de quien trabaja; publicar una version no. Si el cambio toca la
version del paquete, mirar antes el `CHANGELOG.md` y el pin del servidor MCP: el MCP declara
`uydatos>=0.2.1,<0.3` y no resuelve una version nueva hasta que ese pin se mueva a mano.
