#!/usr/bin/env bash
# Run this once, locally, after downloading JetBrainsMono-Regular.ttf from
# https://github.com/JetBrains/JetBrainsMono/releases (SIL OFL 1.1 -- the
# font file lands in a public repo so licence matters; ship the licence
# file alongside it).
#
# Usage: ./scripts/subset_font.sh /path/to/JetBrainsMono-Regular.ttf
set -euo pipefail

SRC="${1:?usage: subset_font.sh /path/to/JetBrainsMono-Regular.ttf}"
mkdir -p assets/fonts

pip install fonttools brotli --break-system-packages 2>/dev/null || pip install fonttools brotli

# Only the 13 ramp characters used by the portrait / year-ramp -- this is
# what keeps the embedded font at ~1.3KB instead of ~4.5MB for a full TTF.
UNICODES=$(python3 -c "
ramp = \" .'\`:;-=+*#%@\"
print(','.join(f'U+{ord(c):04X}' for c in sorted(set(ramp))))
")

pyftsubset "$SRC" \
  --output-file=assets/fonts/jbmono-ramp.woff2 \
  --flavor=woff2 \
  --unicodes="$UNICODES"

echo "wrote assets/fonts/jbmono-ramp.woff2"
echo "don't forget to copy the JetBrains Mono LICENSE.txt into assets/fonts/ too"
