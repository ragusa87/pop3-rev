import os
import sys

WORK = os.environ.get("WORK", "/tmp/pop3-spec")


def function_of(addr):
    for line in open(f"{WORK}/fn.tsv"):
        start, end, name = line.rstrip("\n").split("\t")
        if int(start, 16) <= addr <= int(end, 16):
            return name, int(start, 16), int(end, 16)
    return None


def main():
    if sys.argv[1] == "fn":
        for a in sys.argv[2:]:
            print(a, function_of(int(a, 16)))
        return
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16) if len(sys.argv) > 2 else (function_of(lo) or (0, 0, lo + 0x100))[2] + 1
    for line in open(f"{WORK}/dis.txt"):
        head = line.split(":", 1)[0].strip()
        try:
            a = int(head, 16)
        except ValueError:
            continue
        if lo <= a < hi and "int3" not in line:
            print(line.rstrip()[2:])


if __name__ == "__main__":
    main()
