"""Maps D3DPOPTB.EXE addresses to POPTB.EXE (software build of the same release).

Functions are matched on their first instructions with absolute addresses and rel32 branch targets masked;
data addresses are the absolute references read at the same offset in each matched pair (majority vote).

usage: poptb_map.py D3DPOPTB.EXE POPTB.EXE OUT.tsv   (needs objdump)
"""
import collections
import re
import struct
import subprocess
import sys


class PE:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        count = struct.unpack_from("<H", self.data, pe + 6)[0]
        opt = struct.unpack_from("<H", self.data, pe + 20)[0]
        self.sections = [struct.unpack_from("<8sIIII", self.data, pe + 24 + opt + 40 * i) for i in range(count)]

    def offset(self, va):
        for _, _, rva, raw_size, raw in self.sections:
            if rva <= va - 0x400000 < rva + raw_size:
                return va - 0x400000 - rva + raw
        return None

    def va(self, off):
        for _, _, rva, raw_size, raw in self.sections:
            if raw <= off < raw + raw_size:
                return off - raw + rva + 0x400000
        return None

    def dword(self, va):
        return struct.unpack_from("<I", self.data, self.offset(va))[0]

    def relocations(self):
        _, size, _, _, raw = next(s for s in self.sections if s[0].startswith(b".reloc"))
        out, off = set(), raw
        while off < raw + size:
            page, block = struct.unpack_from("<II", self.data, off)
            if not block:
                break
            for i in range((block - 8) // 2):
                entry = struct.unpack_from("<H", self.data, off + 8 + 2 * i)[0]
                if entry >> 12 == 3:
                    out.add(0x400000 + page + (entry & 0xFFF))
            off += block
        return out


def disassemble(path):
    text = subprocess.run(["objdump", "-d", "-M", "intel", "--no-show-raw-insn", path],
                          capture_output=True, text=True, check=True).stdout
    return [(int(m[1], 16), m[2], m[3] or "")
            for m in re.finditer(r"^\s+([0-9a-f]+):\s+(\S+)(?:[ \t]+(.*))?$", text, re.M)]


def signature(pe, relocs, ins, i, min_size=64):
    pattern, size = b"", 0
    while size < min_size and i + 1 < len(ins):
        addr, mnemonic, operand = ins[i]
        length = ins[i + 1][0] - addr
        raw = pe.data[pe.offset(addr):pe.offset(addr) + length]
        masked = set()
        for k in range(length - 3):
            if addr + k in relocs:
                masked |= set(range(k, k + 4))
        if mnemonic.startswith(("call", "j")) and length in (5, 6) and re.fullmatch(r"0x[0-9a-f]+", operand):
            masked |= set(range(length - 4, length))
        pattern += b"".join(b"." if k in masked else re.escape(raw[k:k + 1]) for k in range(length))
        size += length
        i += 1
        if mnemonic in ("ret", "jmp") and size >= 24:
            break
    return pattern


def match_functions(a, b, ins, relocs):
    index = {addr: i for i, (addr, _, _) in enumerate(ins)}
    targets = sorted({int(op, 16) for _, mn, op in ins if mn == "call" and re.fullmatch(r"0x[0-9a-f]+", op)})
    code = {}
    for target in (t for t in targets if t in index):
        hits = [m.start() for m in re.finditer(signature(a, relocs, ins, index[target]), b.data, re.S)][:2]
        if len(hits) == 1:
            code[target] = b.va(hits[0])
    return code, index


def match_data(a, b, ins, index, relocs, code, max_body=400):
    votes = collections.defaultdict(collections.Counter)
    for start, other in code.items():
        i = index[start]
        while i + 1 < len(ins) and ins[i][0] < start + max_body:
            addr, mnemonic, _ = ins[i]
            for k in range(ins[i + 1][0] - addr - 3):
                if addr + k in relocs:
                    votes[a.dword(addr + k)][b.dword(other + addr - start + k)] += 1
            if mnemonic == "ret":
                break
            i += 1
    return {va: counter.most_common(1)[0] for va, counter in votes.items()}


def main():
    d3d_path, poptb_path, out_path = sys.argv[1:4]
    a, b = PE(d3d_path), PE(poptb_path)
    relocs = a.relocations()
    ins = disassemble(d3d_path)
    code, index = match_functions(a, b, ins, relocs)
    data = match_data(a, b, ins, index, relocs, code)
    with open(out_path, "w") as out:
        out.write("# kind\td3d\tpoptb\tvotes\n")
        for va, other in sorted(code.items()):
            out.write(f"code\t{va:x}\t{other:x}\t1\n")
        text_end = 0x400000 + a.sections[0][2] + a.sections[0][1]
        for va, (other, count) in sorted(data.items()):
            if not 0x401000 <= va < text_end:
                out.write(f"data\t{va:x}\t{other:x}\t{count}\n")
    print(f"{len(code)} functions, {len(data)} data addresses -> {out_path}")


if __name__ == "__main__":
    main()
