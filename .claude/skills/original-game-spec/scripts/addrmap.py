"""Translates D3DPOPTB.EXE addresses to POPTB.EXE with pop3-rev/docs/poptb_map.tsv."""
import bisect
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parents[4] / "docs" / "poptb_map.tsv"


def parse(lines, min_votes=2):
    exact, anchors = {}, []
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        kind, d3d, poptb, votes = line.split("\t")
        d3d, poptb = int(d3d, 16), int(poptb, 16)
        exact[d3d] = poptb
        if kind == "data" and int(votes) >= min_votes:
            anchors.append((d3d, poptb - d3d))
    anchors.sort()
    return exact, anchors


class AddrMap:
    def __init__(self, lines):
        self.exact, self.anchors = parse(lines)
        self.keys = [a for a, _ in self.anchors]

    @classmethod
    def load(cls, path=MAP_PATH):
        with open(path) as f:
            return cls(f)

    def to_poptb(self, addr):
        """Exact match, else the shift of the closest mapped data address below (fields inside a struct)."""
        if addr in self.exact:
            return self.exact[addr]
        i = bisect.bisect_right(self.keys, addr) - 1
        if i < 0:
            raise KeyError(f"{addr:#x} is below every mapped address")
        return addr + self.anchors[i][1]
