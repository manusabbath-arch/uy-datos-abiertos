# Purga de datos de terceros: qué está expuesto y qué lo elimina

- **Fecha:** 2026-11-17
- **Origen:** paquete A3 del plan de portafolio. Cierra el caso del RUT y el nombre real de una
  empresa sancionada que llegaron a `tests/` y a `docs/`.
- **Estado del árbol:** `HEAD` está limpio desde `2a38d9b`. Lo que sigue expuesto son la historia
  publicada, las versiones ya publicadas y los clones/forkes.

## 1. Medición

Todo verificado el 2026-11-17 sobre este repositorio y sobre PyPI.

| Dónde | Qué contiene | Estado |
|---|---|---|
| `HEAD` de cualquier rama publicada | nada: nombres ficticios en la fixture | limpio |
| historia de git (81 commits) | el RUT real en blobs de commits anteriores a `9228b9e` y el nombre en los anteriores a `2a38d9b` | **expuesto** |
| sdists de PyPI 0.3.0 – 0.12.1 | el RUT real | **expuesto** |
| sdists de PyPI 0.14.0 – 0.17.0 | el nombre real | **expuesto** |
| wheels de PyPI (todas) | nada: no incluyen `tests/` | limpio |

El dato es información pública del archivo de sanciones del DSS. Lo que se corrige es el
incumplimiento de la regla del repo ("publica código, no datos"), no un secreto.

## 2. Opción A: purgar la historia (verificada)

Probado sobre un clon espejo, no sobre el repositorio de trabajo. Resultado: **81 commits
reescritos, 0 blobs con los valores, la suite en 508 passed, ningún commit perdido**.

```sh
# 1. Clon espejo y archivo de reemplazos generado desde la historia (no se versiona)
git clone --mirror git@github.com:manusabbath-arch/uy-datos-abiertos.git /tmp/espejo
cd /tmp/espejo
python3 - <<'PY'
import re, subprocess
from pathlib import Path
permitidos = {"012345678919", "210000000019", "219000000004", "210000000018"}
vals = set()
for spec in ("9228b9e^:tests/test_sanciones.py", "9228b9e^:docs/2026-10-09-fuentes-candidatas.md"):
    t = subprocess.run(["git", "show", spec], capture_output=True, text=True, check=True).stdout
    vals |= {m.group(1) for m in re.finditer(r"(?<!\d)(\d{12})(?!\d)", t)} - permitidos
lineas = [f"{v}==><RUT_REMOVIDO>" for v in sorted(vals)]
lineas += ["A PURA MANO LTDA==><EMPRESA_REMOVIDA>", "NUEVA ESTAMPA==><MARCA_REMOVIDA>"]
Path("/tmp/reemplazos.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
PY

# 2. Reescribir y borrar el archivo de reemplazos (tiene los valores)
python3 -m venv /tmp/gfr && /tmp/gfr/bin/pip install -q git-filter-repo
/tmp/gfr/bin/git-filter-repo --replace-text /tmp/reemplazos.txt --force
rm /tmp/reemplazos.txt

# 3. Empujar. Esto reescribe la historia pública: todos los hashes cambian.
git push --force --all
git push --force --tags
```

Consecuencias que hay que aceptar antes de correrlo: los clones existentes tienen que re-clonarse,
los enlaces a commits dejan de resolver, y cualquier PR abierto desde un fork viejo se vuelve
inmanejable. No hay tags con el dato (el primer tag es `v0.2.1` y el RUT entró después), así que
los tags no necesitan cirugía más allá del push forzado.

**Lo que la purga no resuelve:** los sdists de PyPI, las copias en caché de terceros y los fork
del repo en GitHub. Por eso el orden correcto es PyPI primero y después historia, o las dos cosas
en la misma ventana.

## 3. Opción B: sacar las versiones de PyPI

No hay API: PyPI no permite borrar ni yankear desde `twine`, `uv` ni la API JSON/XML-RPC. Se hace
desde la interfaz web, con la cuenta dueña del proyecto, versión por versión:

```
https://pypi.org/manage/project/uydatos/release/0.3.0/
https://pypi.org/manage/project/uydatos/release/0.4.0/
... hasta 0.17.0
```

- **Yank** (`Options → Yank release`): saca la versión de la resolución de `pip`, pero los archivos
  siguen descargables por URL directa. **No elimina el dato.**
- **Delete** (`Options → Delete release`): borra los archivos. Es lo único que elimina el contenido.
  PyPI no reutiliza el número de versión después de borrar, y el proyecto se puede recrear.
- Si se opta por borrar las 15 versiones afectadas, el paquete queda sin historial utilizable:
  conviene dejar publicada la 0.17.1 limpia antes.

## 4. Opción C (recomendada, no excluyente): publicar 0.17.1 y no reescribir

El dato ya es público en el archivo del DSS. Reescribir 81 commits y romper todos los hashes
compra poco frente a dos acciones con el mismo efecto práctico y sin daño colateral:

1. Publicar `0.17.1` con el árbol limpio. No se adelantó el bump acá: `uv` no está instalado en esta máquina y `uv.lock` quedaría desincronizado. El workflow `.github/workflows/publicar.yml` exige que el tag coincida con `pyproject.toml`, así que el bump, el lock y la Release van juntos.
2. Borrar o yankear en PyPI solo las versiones cuyo sdist trae el dato.

Si además se quiere que el historial de git deje de mostrarlo, la Opción A queda verificada y lista.

## 5. Medida estructural

El dato llegó por las fixtures de `tests/`, que viajan en el sdist. Mientras el sdist incluya
`tests/`, cualquier fixture real vuelve a publicarse aunque `HEAD` esté limpio. Excluir `tests/` del
sdist cierra esa clase; no se hizo porque cambia cómo se empaqueta el proyecto y la guarda de
privacidad ya se declara "saltada en un sdist" a propósito. Decisión del dueño.
