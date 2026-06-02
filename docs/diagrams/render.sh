#!/usr/bin/env bash
# Re-render all AEGIS workflow diagrams from the .mmd sources.
# Outputs: <name>.svg (vector, for PDFs) + <name>.png (3x, for screenshots),
# then rebuilds the HTML gallery's combined PDF.
#
# Usage:  ./render.sh
# Requires: node + npx (mermaid-cli is fetched on demand). Reuses the Playwright
# Chromium if present so puppeteer doesn't download its own.
set -euo pipefail
cd "$(dirname "$0")"

export PUPPETEER_SKIP_DOWNLOAD=1
BG="#0A0A0B"
MMDC=(npx -y @mermaid-js/mermaid-cli@11)

# Point Mermaid/puppeteer at an existing Chromium if one is cached.
CHROME="$HOME/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

for f in [0-9][0-9]-*.mmd; do
  base="${f%.mmd}"
  echo "rendering $base …"
  "${MMDC[@]}" -p puppeteer.json -c mermaid-config.json -b "$BG" -i "$f" -o "$base.svg"
  "${MMDC[@]}" -p puppeteer.json -c mermaid-config.json -b "$BG" -s 3 -i "$f" -o "$base.png"
done

if [ -x "$CHROME" ]; then
  echo "building combined PDF …"
  "$CHROME" --headless --no-sandbox --no-pdf-header-footer \
    --print-to-pdf="AEGIS-Workflow-Diagrams.pdf" "file://$PWD/index.html" >/dev/null 2>&1 || true
fi
echo "done."
