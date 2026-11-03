#!/usr/bin/env bash
# Builds the working files in $WORK (default: /tmp/pop3-spec): dis.txt, fn.tsv, consts.txt, constant.txt.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
WORK="${WORK:-/tmp/pop3-spec}"
mkdir -p "$WORK"

# Find the game directory. Priority: explicit $GAME env var, then the repo's own persistent
# cache (survives /clear and fresh sessions in this same container - see AGENTS.md "Where the
# exe lives"), then a local Wine install - a non-default $WINEPREFIX if set, else the default
# ~/.wine, under either of two install paths seen across this project's own history (the
# Makefile's GOG path and this skill's older Bullfrog path) - then a bounded filesystem search
# (which also covers ~/.wine and any other prefix under $HOME, in case the install path is yet
# another variant of the two above) for a Wine prefix holding it anywhere else.
WINE_C="${WINEPREFIX:-$HOME/.wine}/drive_c"
if [ -n "${GAME:-}" ]; then
	: # explicit override, use as given
elif [ -s "$REPO/game/D3DPOPTB.EXE" ]; then
	GAME="$REPO/game"
elif [ -s "$WINE_C/GOG Games/Populous 3/D3DPopTB.exe" ]; then
	GAME="$WINE_C/GOG Games/Populous 3"
elif [ -s "$WINE_C/Program Files (x86)/Bullfrog/Populous - A l'aube de la création/D3DPOPTB.EXE" ]; then
	GAME="$WINE_C/Program Files (x86)/Bullfrog/Populous - A l'aube de la création"
else
	FOUND="$(find "$HOME" /opt /mnt /media -maxdepth 8 -iname 'D3DPOPTB.EXE' -print -quit 2>/dev/null || true)"
	if [ -n "$FOUND" ]; then
		GAME="$(dirname "$FOUND")"
	fi
fi

if [ -z "${GAME:-}" ] || [ ! -s "$GAME/D3DPOPTB.EXE" ]; then
	echo "No D3DPOPTB.EXE found (checked \$GAME, $REPO/game, known Wine install paths, and a" >&2
	echo "filesystem search). Ask the user to re-upload the game zip, extract it, copy" >&2
	echo "D3DPopTB.exe to $REPO/game/D3DPOPTB.EXE (uppercase - case matters) so it persists" >&2
	echo "for future sessions (gitignored, never committed), then re-run this script." >&2
	exit 1
fi
EXE="$GAME/D3DPOPTB.EXE"
echo "using game dir: $GAME" >&2

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
