#!/usr/bin/env bash
# Publica output/ (web + resultados de todas las regiones) en la rama gh-pages del repositorio.
# Uso: bash herramientas/publicar.sh            (tras `python -m riesgo.cli run --region ...`)
# Es la vía manual mientras el workflow de GitHub Actions no tenga permisos; también sirve para subir
# resultados calculados en local con Movebank, que el workflow no ejecuta.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(git -C "$RAIZ" remote get-url origin)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$RAIZ"
.venv/Scripts/python.exe -m riesgo.cli indice >/dev/null 2>&1 || python -m riesgo.cli indice >/dev/null
cd output
cp -r index.html regiones.html img "$TMP/"
for region in */; do
  region="${region%/}"
  [ -f "$region/informe.html" ] && cp -r "$region" "$TMP/"
done
touch "$TMP/.nojekyll"

cd "$TMP"
git init -q -b gh-pages
git add -A
git -c core.autocrlf=false commit -q -m "Resultados del $(date +%Y-%m-%d)"
# credenciales del CLI de gh (Git Credential Manager abre una ventana y bloquea el push en este equipo)
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -f "$REPO" gh-pages:gh-pages
echo "Publicado: https://asensio94.github.io/riesgo-tendidos-aves/"
