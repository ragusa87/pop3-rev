#!/usr/bin/env bash
# Builds the working files in $WORK (default: /tmp/pop3-spec): dis.txt, fn.tsv, consts.txt, constant.txt.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
DEFAULT_GAME="$HOME/.wine/drive_c/Program Files (x86)/Bullfrog/Populous - A l'aube de la création"
GAME="${GAME:-$DEFAULT_GAME}"
EXE="$GAME/D3DPOPTB.EXE"
WORK="${WORK:-/tmp/pop3-spec}"
mkdir -p "$WORK"

[ -s "$WORK/dis.txt" ] || objdump -d -M intel --no-show-raw-insn "$EXE" > "$WORK/dis.txt"

python3 - "$REPO/backup/backup.xml" "$WORK/fn.tsv" <<'EOF'
import re, sys
x = open(sys.argv[1], encoding="utf-8", errors="replace").read()
pat = r'<FUNCTION ENTRY_POINT="([0-9a-f]+)" NAME="([^"]+)".*?<ADDRESS_RANGE START="[0-9a-f]+" END="([0-9a-f]+)"'
with open(sys.argv[2], "w") as out:
    for start, name, end in re.findall(pat, x, re.S):
        out.write(f"{int(start, 16):x}\t{int(end, 16):x}\t{name}\n")
EOF

python3 "$HERE/consts.py" "$EXE" "$GAME/levels/constant.dat" "$WORK"
echo "ready in $WORK: dis.txt fn.tsv consts.txt constant.txt"
