import struct
import sys

SECTIONS = [(0x401000, 0x184A24, 0x400), (0x58F000, 0x8578, 0x18D800), (0x598000, 0x58600, 0x195E00)]
TABLE = 0x5AA60F
RECORD = 0x1F


def va2off(va):
    for base, size, raw in SECTIONS:
        if base <= va < base + size:
            return va - base + raw
    return None


def exe_constants(exe):
    d = open(exe, "rb").read()
    o, bad, rows = va2off(TABLE), 0, []
    while bad < 3:
        name = d[o:o + 25].split(b"\0")[0].decode(errors="replace")
        size, flags, ptr = d[o + 25], d[o + 26], struct.unpack_from("<I", d, o + 27)[0]
        po = va2off(ptr)
        if po is not None and size in (1, 2, 4):
            val = struct.unpack_from({1: "<b", 2: "<h", 4: "<i"}[size], d, po)[0]
            rows.append(f"{name:25s} sz={size} fl={flags:#x} ptr={ptr:#x} val={val}")
            bad = 0
        else:
            bad += 1
        o += RECORD
    return rows


def decode_constant_dat(path):
    b = open(path, "rb").read()
    return bytes(c ^ (~(1 << ((i + 5) % 8)) & 0xFF) for i, c in enumerate(b))[2:].decode("latin1")


def main():
    exe, dat, work = sys.argv[1:4]
    with open(f"{work}/consts.txt", "w") as f:
        f.write("\n".join(exe_constants(exe)) + "\n")
    with open(f"{work}/constant.txt", "w") as f:
        f.write(decode_constant_dat(dat))


if __name__ == "__main__":
    main()
