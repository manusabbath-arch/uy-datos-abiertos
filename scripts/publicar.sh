#!/usr/bin/env bash
# Publica la versión de pyproject.toml: crea la Release v<versión> en GitHub con las notas del
# CHANGELOG, y eso dispara .github/workflows/publicar.yml, que corre los tests y sube a PyPI.
#
# Publicar lo decide una persona (CONTRIBUTING.md): este script no corre en el CI. Existe porque
# la 0.17.0 quedó una semana en `main` sin Release (medido el 2026-11-04), y el MCP no la veía.
#
# Uso: scripts/publicar.sh            # muestra lo que haría
#      scripts/publicar.sh --de-verdad
set -euo pipefail
cd "$(dirname "$0")/.."

version=$(grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2)
etiqueta="v$version"

[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || { echo "no estás en main"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "hay cambios sin commitear"; exit 1; }
git fetch -q origin main --tags
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "main no coincide con origin/main"; exit 1; }
if git rev-parse -q --verify "refs/tags/$etiqueta" >/dev/null; then
  echo "$etiqueta ya existe"; exit 1
fi

# Las notas son la sección del CHANGELOG, sin el título.
notas=$(awk -v v="$version" '
  index($0, "## " v " — ") == 1 { adentro = 1; next }
  adentro && /^## / { exit }
  adentro { print }
' CHANGELOG.md)
[ -n "$(echo "$notas" | tr -d '[:space:]')" ] || { echo "CHANGELOG.md no tiene notas para $version"; exit 1; }
titulo="$version — $(echo "$notas" | grep -m1 -o '\*\*[^*]*\*\*' | tr -d '*' || true)"

uvx ruff check src tests
uvx ruff format --check src tests
uv run --with pytest --with openpyxl --with xlrd --with-editable . pytest -q

echo "Release: $etiqueta  ($titulo)"
echo "$notas" | head -20
if [ "${1:-}" != "--de-verdad" ]; then
  echo "(simulación: agregá --de-verdad para crearla)"
  exit 0
fi
gh release create "$etiqueta" --target main --title "$titulo" --notes "$notas"
