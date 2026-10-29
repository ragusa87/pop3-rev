"""Find out what instruction writes a given live address, via a GDB hardware write-watchpoint
(ptrace debug registers) - for cases where static disassembly can't find a single recognizable
immediate for the address (e.g. it's only ever reached through a computed per-tribe base
register, tribe*0xC65+0x89D1C8, the way tribe_struct fields are - see docs/camera.md's own
"tribe_struct+0x2c" investigation, the first user of this tool).

Must run as root (ptrace), which is why this lives behind scripts/docker/watch_addr.sh's
`docker compose exec -u root` wrapper rather than needing host sudo - see that script and
docs/camera.md's Docker/Xvfb tooling notes for why that matters here.

Address forms:
  0xADDR            a literal live address in the running exe's own address space
  tribe+0xOFFSET     tribe_base + OFFSET, tribe_base read fresh (tribe*0xC65+0x89D1C8, tribe
                     index byte at 0x89C6F0) each time this tool is run - NOT re-read while
                     watching, so a save-point/reincarnation that changes the local player's
                     tribe index mid-session would need a fresh run against the new address.

Prints one line per hit: the watched value right after the write (decimal and hex) and the
EIP GDB stopped at, which is the instruction AFTER the one that wrote it (GDB watchpoints trap
post-write) - so look up EIP-1-ish (really: the previous instruction at that address in a
disassembly listing) to find the actual writing instruction, not EIP itself.

sudo python3 watch_addr.py 0x89D1F4 [--seconds N]
sudo python3 watch_addr.py tribe+0x2c [--seconds N]
"""
import os
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TRIBE_BASE = 0x89D1C8
TRIBE_STRIDE = 0xC65
PLAYER_TRIBE_ADDR = 0x89C6F0


def resolve_addr(spec, pid):
    m = re.fullmatch(r"tribe\+(0x[0-9a-fA-F]+)", spec)
    if not m:
        return int(spec, 16)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(PLAYER_TRIBE_ADDR)
        tribe = mem.read(1)[0]
    return TRIBE_BASE + tribe * TRIBE_STRIDE + int(m.group(1), 16)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec = sys.argv[1]
    seconds = None
    if "--seconds" in sys.argv:
        seconds = float(sys.argv[sys.argv.index("--seconds") + 1])
    if os.geteuid() != 0:
        sys.exit("must run as root (ptrace) - see scripts/docker/watch_addr.sh")

    pid, _ = find_game()
    if not pid:
        sys.exit("neither D3DPOPTB.EXE nor POPTB.EXE is running")
    addr = resolve_addr(spec, pid)
    print(f"watching 0x{addr:x} (pid {pid})", flush=True)

    gdb_script = f"""
set pagination off
set confirm off
attach {pid}
watch *(int*)0x{addr:x}
commands 1
  silent
  printf "HIT val=%d (0x%x)\\n", *(int*)0x{addr:x}, *(int*)0x{addr:x}
  p/x $pc
  continue
end
continue
"""
    with tempfile.NamedTemporaryFile("w", suffix=".gdb", delete=False) as f:
        f.write(gdb_script)
        path = f.name
    try:
        cmd = ["gdb", "-x", path, "-batch"]
        if seconds is None:
            subprocess.run(cmd)
        else:
            try:
                subprocess.run(cmd, timeout=seconds)
            except subprocess.TimeoutExpired:
                pass
    finally:
        os.unlink(path)


if __name__ == "__main__":
    main()
