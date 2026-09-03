#!/usr/bin/env bash
# Publish output/ (website + results of every region) on the gh-pages branch of the repository.
# Usage: bash tools/publish.sh              (after `python -m birdrisk.cli run --region ...`)
# This is the manual route; the GitHub Actions workflow publishes Pages on its own. It is still useful to
# upload results computed locally with Movebank, which the workflow does not run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(git -C "$ROOT" remote get-url origin)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$ROOT"
# `index` rebuilds regions.es/en.html, the legacy redirects and the copy of web/ inside output/
.venv/Scripts/python.exe -m birdrisk.cli index >/dev/null 2>&1 || python -m birdrisk.cli index >/dev/null
cd output
# front pages, redirects and images
for f in index.html index.en.html regions.es.html regions.en.html regiones.html; do
  [ -f "$f" ] && cp "$f" "$TMP/"
done
[ -d img ] && cp -r img "$TMP/"
for region in */; do
  region="${region%/}"
  [ "$region" = "img" ] && continue
  [ -f "$region/report.es.html" ] && cp -r "$region" "$TMP/"
done
touch "$TMP/.nojekyll"

cd "$TMP"
rm -f run_*.log
git init -q -b gh-pages
git add -A
git -c core.autocrlf=false commit -q -m "Results of $(date +%Y-%m-%d)"
# gh CLI credentials (Git Credential Manager opens a window and blocks the push on this machine)
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -f "$REPO" gh-pages:gh-pages
echo "Published: https://asensio94.github.io/riesgo-tendidos-aves/"
