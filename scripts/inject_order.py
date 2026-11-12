#!/usr/bin/env python3
"""Inject an order into a live D3DPOPTB.EXE unit and log its execution turn by turn (see docs/cheat.md "Spy arson, live").

Run inside the pop3 container as root:  python3 -I inject_order.py PID auto X Z TRIBE SECONDS
"""
import sys, struct, time

PID = int(sys.argv[1])
MODE = sys.argv[2]
UNIT_BASE, STRIDE, NUNITS = 0x8E0428, 0xB3, 2000
GROUP_BASE, GSTRIDE = 0x938830, 10
LIVE_GROUPS = 0x96AA7A
TURN = 0x89D188

mem = open(f'/proc/{PID}/mem', 'r+b', buffering=0)

def r(a, n):
    mem.seek(a); return mem.read(n)

def w(a, d):
    mem.seek(a); mem.write(d)

def u16(b, o): return int.from_bytes(b[o:o+2], 'little')
def pos(rec): return (u16(rec, 0x3D), u16(rec, 0x3F), u16(rec, 0x41))

def wd(a, b):
    d = abs(a - b) % 65536
    return min(d, 65536 - d)

if MODE == 'auto':
    tx, tz, tribe, dur = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
    buf = r(UNIT_BASE, STRIDE * NUNITS)
    best_b = best_s = None
    for i in range(NUNITS):
        rec = buf[i*STRIDE:(i+1)*STRIDE]
        if rec[0xC] & 1: continue
        x, z, _ = pos(rec)
        if rec[0x2A] == 2 and rec[0x2F] == tribe:
            d = wd(x, tx) + wd(z, tz)
            if best_b is None or d < best_b[0]: best_b = (d, UNIT_BASE + i*STRIDE, (x, z))
    for i in range(NUNITS):
        rec = buf[i*STRIDE:(i+1)*STRIDE]
        if rec[0xC] & 1: continue
        x, z, _ = pos(rec)
        if rec[0x2A] == 1 and rec[0x2B] == 5 and rec[0x2F] == 0 and rec[0x2C] != 10:
            d = wd(x, best_b[2][0]) + wd(z, best_b[2][1])
            if best_s is None or d < best_s[0]: best_s = (d, UNIT_BASE + i*STRIDE, (x, z))
    print('target', best_b, 'spy', best_s, flush=True)
    sys.argv = [sys.argv[0], str(PID), 'inject', hex(best_s[1]), hex(best_b[1]), str(tribe)]
    MODE = 'inject'
    AUTO_WATCH = (hex(best_s[1]), hex(best_b[1]), dur)
else:
    AUTO_WATCH = None

if MODE == 'inject':
    spy = int(sys.argv[3], 16); bld = int(sys.argv[4], 16); tribe = int(sys.argv[5])
    b = r(bld, STRIDE)
    sp = r(spy, STRIDE)
    assert sp[0x2A] == 1 and sp[0x2B] == 5 and sp[0x2F] == 0 and not (sp[0xC] & 1), f'not our spy: cls{sp[0x2A]} typ{sp[0x2B]} tribe{sp[0x2F]}'
    assert b[0x2A] == 2 and b[0x2F] == tribe and not (b[0xC] & 1), f'bad target: cls{b[0x2A]} tribe{b[0x2F]}'
    bx, bz = u16(b, 0x3D), u16(b, 0x3F)
    gx, gz = (bx & 0xFE00) | 0x100, (bz & 0xFE00) | 0x100
    g = r(GROUP_BASE, GSTRIDE * 2048)
    gid = next(i for i in range(1, 2048) if g[i*GSTRIDE:(i+1)*GSTRIDE] == bytes(GSTRIDE))
    ga = GROUP_BASE + gid * GSTRIDE
    w(ga, bytes([0xF, 0x00]) + struct.pack('<H', 1) + bytes(2) + struct.pack('<HH', gx, gz))
    w(LIVE_GROUPS, struct.pack('<H', u16(r(LIVE_GROUPS, 2), 0) + 1))
    w(spy + 0xB2, bytes([(tribe << 6) & 0xC0]))
    w(spy + 0x9B, struct.pack('<H', gid))
    w(spy + 0x2D, bytes([0]))
    w(spy + 0x2C, bytes([0x0A]))
    f = int.from_bytes(r(spy + 0xC, 4), 'little')
    w(spy + 0xC, (f | 0x40000000).to_bytes(4, 'little'))
    print(f'group {gid} @{ga:#x} kind 0xF refcnt 1 target ({gx},{gz}); spy {spy:#x} disguised tribe {tribe}')

if MODE == 'watch' or AUTO_WATCH:
    if AUTO_WATCH:
        spy, bld, dur = int(AUTO_WATCH[0], 16), int(AUTO_WATCH[1], 16), float(AUTO_WATCH[2])
    else:
        spy = int(sys.argv[3], 16); bld = int(sys.argv[4], 16); dur = float(sys.argv[5])
    b0 = r(bld, STRIDE)
    bx, bz = u16(b0, 0x3D), u16(b0, 0x3F)
    print('BLD0', b0.hex(), flush=True)
    prev_key = None; prev_b = b0; last = -1; t0 = time.time()
    seen_fx = set()
    while time.time() - t0 < dur:
        turn = int.from_bytes(r(TURN, 4), 'little')
        if turn == last:
            time.sleep(0.01); continue
        last = turn
        s = r(spy, STRIDE); b = r(bld, STRIDE)
        key = (s[0x2A], s[0x2B], s[0x2C], s[0x2D], s[0xB2] >> 6, u16(s, 0x9B), b[0x2C], s[0x2F])
        if key != prev_key:
            print(f't{turn} SPY cls{s[0x2A]}/typ{s[0x2B]} st{s[0x2C]}/{s[0x2D]} pos{pos(s)} wind{u16(s,0x70)} '
                  f'b2={s[0xB2]:#x} grp{u16(s,0x9B)} anim{u16(s,0x33)} life{u16(s,0x6E)} | BLD st{b[0x2C]}', flush=True)
            prev_key = key
        diffs = [(o, prev_b[o], b[o]) for o in range(STRIDE) if prev_b[o] != b[o]]
        if diffs:
            print(f't{turn} BLDDIFF ' + ' '.join(f'+{o:#x}:{a:#x}->{c:#x}' for o, a, c in diffs), flush=True)
        prev_b = b
        buf = r(UNIT_BASE, STRIDE * NUNITS)
        for i in range(NUNITS):
            rec = buf[i*STRIDE:(i+1)*STRIDE]
            if rec[0xC] & 1 or rec[0x2A] not in (5, 7, 8):
                continue
            x, z, _ = pos(rec)
            if wd(x, bx) + wd(z, bz) > 3000:
                continue
            tag = (i, rec[0x2A], rec[0x2B])
            if tag not in seen_fx:
                seen_fx.add(tag)
                print(f't{turn} NEWOBJ slot{i} cls{rec[0x2A]} typ{rec[0x2B]} st{rec[0x2C]} pos{pos(rec)} tribe{rec[0x2F]}', flush=True)
    print('DONE', flush=True)
