import os
import struct
import sys
import time

from addrmap import AddrMap


def find_game():
    """(pid, translate) of the running game; translate maps D3DPOPTB.EXE addresses to the running build."""
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().lower()
        except OSError:
            continue
        if not cmd.startswith(b"c:\\"):
            continue
        if b"d3dpoptb.exe" in cmd:
            return int(pid), lambda addr: addr
        if b"poptb.exe" in cmd:
            return int(pid), AddrMap.load().to_poptb
    return None, None


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: livemem.py D3D_ADDR:FMT[:LABEL] ... [--every SECONDS] [--pid PID]")
    args, every, pid = [], None, None
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--every":
            every = float(next(it))
        elif a == "--pid":
            pid = int(next(it))
        else:
            parts = a.split(":")
            args.append((int(parts[0], 16), parts[1], parts[2] if len(parts) > 2 else parts[0]))
    found, translate = find_game()
    if not found:
        sys.exit("neither D3DPOPTB.EXE nor POPTB.EXE is running")
    pid = pid or found
    args = [(translate(addr), fmt, label) for addr, fmt, label in args]
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        last = None
        while True:
            values = []
            for addr, fmt, label in args:
                mem.seek(addr)
                values.append(f"{label}={struct.unpack(fmt, mem.read(struct.calcsize(fmt)))}")
            line = "  ".join(values)
            if line != last:
                print(line, flush=True)
                last = line
            if every is None:
                return
            time.sleep(every)


if __name__ == "__main__":
    main()
