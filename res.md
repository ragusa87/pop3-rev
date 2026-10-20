# Screen resolution handling in D3DPOPTB.EXE

Scratch research note, **not** part of the normal pop3-rev documentation pipeline
(functions.tsv / pop3-rev-analysis.md). Answers: how does the game build its list of
supported resolutions, and how does `SAVE/CONFIG00.DAT` byte 0 map to an actual
width/height? Goal: know enough to patch `CONFIG00.DAT` (or write a launcher/DLL) to force
a resolution reliably.

All addresses are `D3DPOPTB.EXE` virtual addresses (image base `0x400000`), derived this
session via `objdump` static disassembly of the real exe (`~/.wine/drive_c/Program Files
(x86)/Bullfrog/Populous - A l'aube de la création/D3DPOPTB.EXE`, sha256
`3a5065c7...8dfbe4f`). Several of the function names below are Ghidra's own prior guesses
(trustworthy here — they matched the traced behaviour); a few others are mine.

## TL;DR

- **`CONFIG00.DAT` byte 0 is NOT a fixed resolution code.** It is a plain array index into
  a list of `{width,height,bpp}` modes that the game *rebuilds from scratch every run* by
  calling `IDirectDraw::EnumDisplayModes`. The same byte value means a different resolution
  on every machine (or every Wine config) depending on what modes DirectDraw reports.
- Without the `-ALLRES` command-line switch, the game **throws away everything except
  640×480 and 800×600** before building that indexed list — regardless of what the OS/Wine
  actually offers. This is almost certainly the real explanation for "Wine only reports 2
  resolutions": it's the *game* doing that, not Wine.
- The list that does survive is sorted **best-first**: highest color depth, then widest,
  then tallest — index 0 is the best mode found, not the worst (contradicts the Populous
  Wiki's "ordered from lowest to highest" claim for this D3D build).
- `-ALLRES` is a real, working command-line flag (verified in the argv parser). There's also
  a `-SCREENRES <w> <h> <bpp>` flag that gets parsed and stored but is **never read by
  anything else in the exe** — looks dead/vestigial in this build, don't rely on it.

## 1. `CONFIG00.DAT` ⇄ in-memory config

`SAVE/CONFIG00.DAT` is read/written by a small **generic, table-driven field engine** (not
one-off code per field):

- `load_config00` — `0x49a9d0`–`0x49acf2`
- `write_config00` — `0x49ad20`–`0x49ae88`
- Field table — `0x5a9a60`, 20-byte records, terminated by a `0xff` sentinel type byte.
  Record layout (offsets relative to record start):
  - `+0x00` dword: pointer to the global variable this field reads/writes
  - `+0x04` dword: mask/threshold (used by flag-type fields)
  - `+0x08` dword: scratch (second mask / change-detect value)
  - `+0x0c` dword: cached "last known value" (used by the save-time dirty check)
  - `+0x10` word: field/key id (passed into the underlying profile read/write call,
    `0x526580`/`0x526280`/`0x5263b0`)
  - `+0x12` byte: type — `1`=BYTE, `2`=WORD, `3`=DWORD, `4`=bit-flag, `5`=other/blob
  - `+0x13` byte: condition flags (gates whether the field is read/written at all,
    depending on bits of a global engine-state flags dword at `0x89c661`)

  Fields are processed in table order and that order **is** the on-disk byte layout — I
  confirmed this against the real `SAVE/CONFIG00.DAT` (177 bytes, matches the Populous Wiki's
  "Populous Configuration File" byte-length exactly).

- **Record 0** (first field, file offset 0): pointer = `0x749cf0`, type = `1` (BYTE), key id
  = `1`. This is the RESOLUTION byte from the wiki. So:

  > `CONFIG00.DAT[0]` ⇄ global byte `ds:0x749cf0`, loaded/saved verbatim, no translation.

  The real file on this machine has byte 0 = `0x15` (21 decimal).

## 2. Building the resolution list

### 2.1 Raw enumeration — the actual `IDirectDraw::EnumDisplayModes` call

Call site: `0x4b0417`, inside an unnamed init routine at `0x4b0408`–`~0x4b04e6` (Ghidra:
`init_d3d_window`'s neighbourhood; the call itself isn't inside a function Ghidra named).

```
4b0415:  mov    eax, [esi]          ; esi = pointer to the IDirectDraw object
4b0417:  push   0x4b0e80            ; lpEnumModesCallback
4b041c:  mov    ebp, [eax]          ; ebp = vtable
4b041e:  push   ebx                 ; lpContext
4b041f:  push   0x0                 ; lpDDSurfaceDesc = NULL
4b0421:  push   0x0                 ; dwFlags = 0
4b0423:  push   eax                 ; this
4b0424:  call   [ebp+0x20]          ; vtable+0x20 = IDirectDraw::EnumDisplayModes (index 8)
```

`dwFlags=0` means no `DDEDM_REFRESHRATES` — the driver is not asked to enumerate multiple
refresh rates per resolution/bpp, so (in principle) each width×height×bpp combo should show
up once.

Vtable offset `0x20` was confirmed against `IDirect3D2`/`IDirectDraw` SDK headers: index
8 × 4 bytes = `0x20` = `IDirectDraw::EnumDisplayModes` on the **plain `IDirectDraw` (v1)**
interface (not 2/4/7) — consistent with the `DDSURFACEDESC` (not `DDSURFACEDESC2`) field
offsets used by the callback below.

If `EnumDisplayModes` returns `0` (`DD_OK`), the raw list collected by the callback is then
sorted in place with a CRT `qsort(base=0x98ea30, count, size=0xc, compar=0x4b0e20)` call at
`0x4b0432`–`0x4b0446`. If it returns non-zero, the sort is skipped (whatever the callback
collected is used as-is).

### 2.2 The enumeration callback — `0x4b0e80`

Signature matches `DDENUMMODESCALLBACK(LPDDSURFACEDESC lpDDSurfaceDesc, LPVOID lpContext) → HRESULT`,
with `esi = lpDDSurfaceDesc`, `ecx = lpContext` (the "DDraw manager"-ish object whose pointer
lives at `0xafc2f4`).

```
4b0e86:  cmp  [esi+0xc], 0x640     ; dwWidth  > 1600 ?
4b0e8d:  ja   0x4b0f52             ;   -> reject, return 1 (continue enum, don't store)
4b0e93:  cmp  [esi+0x8], 0x640     ; dwHeight > 1600 ?
4b0e9a:  ja   0x4b0f52             ;   -> reject
4b0ea0:  cmp  [ecx+0x510], 0x0     ; "check bpp against device caps" toggle
4b0eab:  je   0x4b0f0e             ;   if 0: skip the bpp-capability check entirely, ADD mode
  ... (bpp 1..32, from DDSURFACEDESC.ddpfPixelFormat at +0x54, mapped via a jump
       table to a bitmask 0x100..0x4000) ...
4b0efc:  test [eax+0x9c], edi      ; does the device's capability dword have this bpp's bit?
4b0f02:  jne  0x4b0f0e             ;   yes -> ADD mode
                                   ;   no  -> fall through, return 1 without storing
4b0f0e:  ; ADD MODE:
         mov  eax, ds:0x5cdc50          ; current raw-list count
         ... store width=[esi+0xc], height=[esi+8], bpp=[esi+0x54]
             into 12-byte record at 0x98ea30 + count*12 ...
         inc  ds:0x5cdc50               ; count++
         ; stop enumerating once count reaches 64 (hard cap on the raw table)
```

So the **only hard filters at the raw-enumeration stage** are: `width<=1600`,
`height<=1600`, and (optionally, only if `[ctx+0x510]!=0`) the mode's bpp must be a bit the
Direct3D device's capability bitmask (`[ctx+0x9c]`) actually supports. Raw table caps at 64
entries.

Raw list storage: dword array at **`0x98ea30`**, 12 bytes/record = `{u32 width, u32 height,
u32 bpp}`; live count at **`0x5cdc50`** (dword).

### 2.3 Sort — `0x4b0e20` (qsort comparator)

Three-level comparison, each level **descending**:

1. `bpp` (record offset `+8`) — higher bpp sorts first
2. `width` (offset `+0`) — wider sorts first (tie on bpp)
3. `height` (offset `+4`) — taller sorts first (tie on bpp and width)

**Net effect: index 0 of the sorted raw list is the single best mode found (highest
color depth, then largest resolution), and the list gets worse as the index grows.** This
directly contradicts the Populous Wiki page's claim that resolution indices go
"lowest possible to highest" — at least for this D3D build; the wiki's byte-offset table for
the file itself is correct (I verified it against the real file), just not its ordering claim.

### 2.4 The derived/filtered list and the `-ALLRES` gate — `init_screen_resolutions` (`0x49c570`)

This is the function Ghidra already named `init_screen_resolutions` (`0x49c570`–`0x49c715`).
It does **not** touch DirectDraw itself — it consumes the already-built raw list above
through a tiny begin/next/end wrapper:

- `set_screen_resolution0_to_struct` `0x4b2200` (seed/reset)
- `get_next_screen_resolution` `0x4b2230` (iterate)
- `0x4b2280` (end/cleanup, trivial stub)
- underlying accessors: `get_display_modes_number` `0x4b1d50` (reads count `0x5cdc50`),
  `get_screen_resolution` `0x4b1d60` (reads record `i` from `0x98ea30`)

Logic:

1. **First pass** — keep only entries with `bpp>=16 AND width>=512 AND height>=384`.
   Each kept entry is copied (width, height, bpp — same 12-byte layout) into a second table
   at **`0x89cf1c`**, with an 8-bit running count at **`0x89d15c`** (max 255 entries, so no
   cap issue vs. the raw table's 64). Each accepted mode is also logged via `0x4574d0` with
   format string `0x5ca920` (width/height/bpp args) — a debug log line, not otherwise
   consequential.

2. **Second pass — the big one.** Unless bit `0x4` of the flags dword at **`0x89c66d`** is
   set, the code then **compacts this list down to only the entries that are EXACTLY
   640×480 or 800×600** (any bpp), discarding everything else, in place at `0x89cf1c`
   (`0x49c637`–`0x49c698`):

   ```
   49c656:  cmp   [eax], 0x280        ; width == 640 ?
   49c65c:  jne   0x49c663
   49c65e:  cmp   [eax+4], 0x1e0      ; height == 480 ?
   49c661:  je    0x49c670            ; -> KEEP
   49c663:  cmp   [eax], 0x320        ; width == 800 ?
   49c669:  jne   0x49c688            ; -> drop
   49c66b:  cmp   [eax+4], 0x258      ; height == 600 ?
   49c66e:  jne   0x49c688            ; -> drop
   49c670:  ; KEEP: compact-copy this record forward, keep relative (sorted) order
   ```

   **This is, with very high confidence, the actual mechanism behind "Wine only shows 2
   resolutions."** It has nothing to do with what Wine's `EnumDisplayModes` actually
   returns — the game deliberately throws away every enumerated mode except 640×480 and
   800×600 unless this one flag bit is set.

3. After building the final list, the function unconditionally **resets the "current
   resolution" globals to the index of the 640×480 entry it finds in that final list**
   (`0x49c69e`–`0x49c710`): scans the final list for an exact 640×480 match and an exact
   512×384 match, records their positions in two one-byte globals (`0x89d15e` for 640×480,
   `0x89d15d` for 512×384), stores `final_count-1` into dword `0x5adc61` (max valid index),
   then copies the 640×480 index into **`0x984590`** and, crucially, back into
   **`0x749cf0`** — the very same global that `CONFIG00.DAT` byte 0 round-trips through.

   This means: **any code path that re-runs `init_screen_resolutions` resets the active
   resolution index to "640×480 in the current list," clobbering whatever was loaded from
   `CONFIG00.DAT`**, unless something reloads the saved value afterwards. Caller analysis
   below.

## 3. Applying the selected index

Found right after one of `init_screen_resolutions`'s two call sites (`0x4c58a7`, inside an
otherwise-unnamed handler — looks like a "video mode changed / device reset, rebuild list and
reapply" path, gated on a flag check and preceded by log string `0x5d482c`):

```
4c58a7:  call  0x49c570              ; init_screen_resolutions (rebuild + resets 0x749cf0!)
4c58c6:  xor   eax, eax
4c58c6:  mov   al, ds:0x749cf0       ; al = resolution index (the CONFIG00.DAT byte)
4c58cb:  lea   edx, [eax+eax*2]      ; edx = index*3
4c58ce:  mov   eax, [edx*4+0x89cf24] ; eax = list[index].bpp     (0x89cf1c + 8)
4c58d5:  lea   ecx, [edx*4+0]        ; ecx = index*12
4c58dd:  mov   edx, [ecx+0x89cf20]   ; edx = list[index].height  (0x89cf1c + 4)
4c58e4:  mov   ecx, [ecx+0x89cf1c]   ; ecx = list[index].width   (0x89cf1c + 0)
4c58eb:  call  0x500580              ; change_screen_mode(width, height, bpp)
```

So: **index × 12 into the table at `0x89cf1c`**, fields `{width, height, bpp}` in that
order, passed straight to `change_screen_mode` (`0x500580`, Ghidra-named, not traced further
this session).

The second caller of `init_screen_resolutions` is inside `init_hw_video` (`0x5002e0`–
`0x50053b`, Ghidra-named), itself guarded to run only once (`ds:0x89c6f3` flag) — this is
the "deferred, first time a game/level actually loads" hardware-video bring-up the game does
(matches your observation that the resolution machinery only engages once the simulation
starts, not at the front-end menus). Shortly after its own call to `init_screen_resolutions`
(`0x5003f0`), it explicitly sets the mode to a literal 640×480 via `0x4b2310` (`push 0x280,
0x1e0, 0x8, 0x1, ...`) rather than consulting `0x749cf0` at all — i.e. the very first
hardware video bring-up always starts at a hard-coded 640×480 safe default, independent of
the saved config index. I did not fully trace where/when `load_config00` runs relative to
this to re-establish the user's saved index afterwards — flagged as open if it matters later.

## 4. `-ALLRES` and friends — command-line parsing

Argv scanner: `0x4a5310`–`0x4a5586` (Ghidra's name for this, `read_reg_video`, is wrong —
it iterates `argv`/`argc` globals `0x89c699`/`0x89c6bf`, not the registry; classic
previous-analyst mis-guess).

Each arg (leading `-`/`/` stripped) is compared via `0x56bc60` (case-insensitive string
compare) against a chain of literal strings. Full set of switches recognized by this
function, in the order checked:

| string (file offset) | VA | effect |
|---|---|---|
| `HARDDRIVE` | `0x5cdb10` | — (not analysed) |
| `NAME` | `0x5cdb08` | — (not analysed) |
| `NOCONFIG` | `0x5cdafc` | — (not analysed) |
| `LEVEL` | `0x5cdaf4` | — (not analysed) |
| `SCREENRES` | `0x5cdae8` | reads next 3 args as width/height/bpp (via `0x55d4d0`, atoi-like); sets flag bit `0x80` in dword `0x89c665`, stores width→word `0x89c6bb`, height→word `0x89c6bd`. **Dead code**: nothing else in the exe reads `0x89c6bb`/`0x89c6bd` anywhere (checked the full disassembly). Don't rely on this switch. |
| `FP` | `0x5cdae4` | sets flag bit `0x1000000` in `0x89c665` |
| **`ALLRES`** | **`0x5cdadc`** | **ORs `0x4` into flags dword `0x89c66d`** — this is exactly the bit `init_screen_resolutions` checks (§2.4) to skip the 640×480/800×600-only collapse. **Confirmed, working.** |
| `FRAMERATEMOUSE` | `0x5cdacc` | sets dword `0x5d54d8` |
| `NOGAMMA` | `0x5cdac4` | sets dword `0x5d54e0` |
| `D3D_DEBUG` | `0x5cdab8` | ORs `0x400` into `0x89c66d` |

So: **`-ALLRES` (or `/ALLRES`) on the command line is a real, verified, zero-binary-patching
fix for "only 2 resolutions."** It does not by itself pick a resolution — it just lets the
real enumerated/sorted list survive instead of being collapsed to the two legacy modes.

## 5. Third-party tool: `popres.exe` ("PopRes" by ALACN, 2004)

`/home/laurent/Downloads/pop/popres.exe` — found in your `Downloads/pop` folder, a 39 KB GUI
tool, version info: "Populous Screen Resolution" / "PopRes" / ALACN 2004.

- It's UPX-packed with a **deliberately corrupted UPX header** (`upx -d` refuses: "file is
  modified/hacked/protected; take care!!!" — a common anti-easy-unpacking trick). Its own
  unpacking stub is intact and disassemblable though: entry `0x412ff0`, standard NRV
  depacker loop, IAT fixup via `LoadLibraryA`/`GetProcAddress`, final `popa; jmp 0x401a58`
  → **OEP = `0x401a58`**.
- Dynamic unpacking (gdb breakpoint/memory dump at OEP) was attempted but blocked by this
  sandbox (ptrace restricted) — didn't get a clean dump this session.
- What I *did* confirm safely (via `WINEDEBUG=+file` trace, pointed only at a throwaway
  sandbox copy, never writing to the real install): on launch, with **zero user
  interaction**, it auto-detects the game's real install path (from the registry path
  `...\Bullfrog\Populous - A l'aube de la création\D3DPopTB.exe`) and opens
  **`D3DPopTB.exe` itself** with `GENERIC_READ | GENERIC_WRITE`, then does two small
  `ReadFile`s (49 bytes, then 47 bytes) at two different file offsets before presumably
  populating its UI. It never touches `CONFIG00.DAT`.
- This confirms PopRes is an **EXE patcher**, not a config-byte tool. Given what we now know
  about §2.4, my working hypothesis (unconfirmed — would need the unpacked binary to verify)
  is that it patches the four `640/480/800/600` immediate comparison operands inside the
  collapse-filter at `0x49c656`–`0x49c66e` directly (letting the user pick an arbitrary
  "safe pair" of resolutions to preserve instead of 640×480/800×600), rather than toggling
  the `-ALLRES` bit. **Caveat: not verified, just the most likely explanation of the
  read/patch pattern observed.** No real exe was modified in testing this — all file access
  was redirected to a throwaway copy in `/tmp`, and the original install's sha256
  (`3a5065c7420b3fcde208bf220bc86dfbac95e025ab2492caf9c7ea5308dfbe4f`) was unchanged
  afterwards.

## 6. `POPTB.EXE` (software renderer) vs. `D3DPOPTB.EXE` (Direct3D) — same mechanism, one real difference

The install also ships `POPTB.EXE` (the "standard"/software-rendering build — the Start Menu
shortcut literally offers "Choisir version standard ou Direct3D"). I checked it since the two
builds are known to diverge elsewhere in the exe (see the existing `POPTB address map`
project note on D3D↔software-build address deltas) — worth confirming whether the resolution
logic differs too, rather than assuming §1–§5 apply unchanged to `POPTB.EXE`.

Short answer: **structurally identical mechanism, different addresses, one genuine
behavioural difference.** `POPTB.EXE` still links `DDRAW.dll` and goes through
`IDirectDraw::EnumDisplayModes` the same way (it just never queries `IDirect3D2`/does HAL
device search, since it has no hardware path to pick). Confirmed by direct comparison:

| role | `D3DPOPTB.EXE` | `POPTB.EXE` |
|---|---|---|
| config field table base | `0x5a9a60` | `0x5a2780` |
| resolution byte (record 0 ptr; `CONFIG00.DAT[0]`) | `0x749cf0` | `0x96cee0` |
| `init_screen_resolutions`-equivalent | `0x49c570` | `0x41efc2`–`0x41f0b2` (unnamed) |
| raw/derived mode list | `0x89cf1c` | `0x8854b4` (same `{width,height,bpp}`×12 layout) |
| final-list count byte | `0x89d15c` | `0x8856f4` |
| `-ALLRES` gate flag | bit `0x4` of `0x89c66d` | bit `0x4` of `0x884c05` (verified: `-ALLRES` parser ORs the same `0x4` into this dword right after matching the `ALLRES` string at `0x4bb57a`) |
| 640×480-only / 800×600-only collapse (non-ALLRES) | `0x49c637`–`0x49c698` | `0x41efc2`–`0x41f02c` — byte-for-byte the same `0x280/0x1e0` vs `0x320/0x258` comparisons |
| apply-by-index (`index*12` into the list, `{width,height,bpp}` → mode-set call) | `0x4c58c6`–`0x4c58eb` → `change_screen_mode` (`0x500580`) | `0x41fc0d`–`0x41fc34` → same pattern → call `0x4c46d0` |

**The one confirmed real difference:** after rebuilding the list, `D3DPOPTB.EXE` writes the
newly-found 640×480 index into *both* the mirror global (`0x984590`) *and* straight back into
the live `CONFIG00.DAT`-backed byte `0x749cf0` (`0x49c706`/`0x49c70b` — see §2.4). `POPTB.EXE`'s
equivalent code (`0x41f08e`) only updates its mirror (`0x96cb28`) — it does **not** touch
`0x96cee0`. So the "rebuilding the list resets your saved resolution choice to 640×480"
side-effect documented in §2.4/§3 is, as far as traced this session, **a D3D-build-only
quirk**; the software build's apply site (`0x41fbf7`-on) instead *compares* the saved byte
against the mirror and only takes a "fall back to 640×480" branch (via a gate call at
`0x41c2a0`, not traced) if they differ — i.e. it looks like it was written to *preserve* the
saved index rather than clobber it. Not fully traced (`0x41c2a0`, and exactly when/how often
this whole routine re-runs in `POPTB.EXE` vs. `D3DPOPTB.EXE`'s `init_hw_video`/`0x4c58a7`
call sites) — flagged as open if this build ever matters for the launcher.

Practical takeaway: **do the analysis in §2–§4 separately for whichever exe the launcher is
actually targeting** — the two builds are close enough that the same patching *strategy*
(`-ALLRES`, or a `ddraw.dll` proxy hooking `EnumDisplayModes`) works for both, but the literal
addresses above are not interchangeable between them.

## 7. Does Wine actually expose eDP/DP-4 as separate resolutions? (tested empirically)

Question: on a laptop+external-monitor setup (eDP-1 native 2256×1504, DP-4 native
1920×1080, confirmed via `xrandr --query`; no explicit RandR `primary` set at test time —
Wine picked `DP-4`, the output at origin `(0,0)`, as `\\.\DISPLAY1`/primary), does the game's
actual `IDirectDraw::EnumDisplayModes` call (§2.1) see both monitors' native resolutions, or
only one?

Tested directly rather than guessed: compiled a small Winelib diagnostic (`winegcc -o
ddtest.exe ddtest.c -lddraw -luser32 -lgdi32`, Win32 C calling `GetSystemMetrics`,
`EnumDisplaySettingsA`, `EnumDisplayDevicesA`, `EnumDisplayMonitors`, and
`DirectDrawCreate(NULL,...)` + `IDirectDraw::EnumDisplayModes` exactly like the game does) and
ran it under this session's Wine/Xwayland setup.

**Result: Wine's multi-monitor support (`EnumDisplayDevicesA`/`EnumDisplayMonitors`) correctly
reports both monitors as separate devices with their real native resolutions — but legacy
`IDirectDraw::EnumDisplayModes` only ever enumerates modes for whichever monitor is currently
the Win32/X11 *primary* display.**

- With `DP-4` primary: `EnumDisplayDevicesA` correctly listed `\\.\DISPLAY1`=1920×1080
  (DP-4) and `\\.\DISPLAY2`=2256×1504 (eDP-1) as separate devices — but
  `IDirectDraw::EnumDisplayModes` returned 84 modes topping out at **1920×1080**; 2256×1504
  was **not present at all**.
- Re-ran after `xrandr --output eDP-1 --primary` (reversible, host-level, instantly undone
  afterwards — confirmed back to `DP-4 connected primary` when done): `GetSystemMetrics`,
  `EnumDisplaySettingsA(NULL,...)` and `IDirectDraw::EnumDisplayModes` all flipped to the
  eDP-1 side — now 99 modes, topping out at **2256×1504** (and 1920×1080 was still present,
  since it's ≤ eDP-1's panel bounds and a mode the laptop panel also advertises).
- So: **whichever output is the X11/RandR "primary" monitor is exactly what plain
  `IDirectDraw::EnumDisplayModes` exposes to the game — never the non-primary one.** This
  matches real DirectDraw-on-Windows behaviour too (legacy DirectDraw was always
  primary-display-only; proper multi-adapter support only exists in Direct3D8+/IDirectDraw7
  territory this game doesn't use).
- Minor Wine rough edge noticed in passing, not relevant to DirectDraw itself: with `eDP-1`
  primary, `EnumDisplayMonitors`'s callback reported `\\.\DISPLAY2`'s rect as
  `(4294965376,0)-(0,1080)` (i.e. `-1920` wrapped to an unsigned `LONG`) instead of the
  expected negative-origin rect — a GDI-level multi-monitor display quirk, doesn't affect the
  DirectDraw path used by the game.

### What this means for "detect the screen and force 2256×1504 / 1920×1080"

Because the result is **exactly whichever monitor is primary**, there are two viable designs,
in order of how much is needed:

1. **No DLL needed at all, if the launcher may touch X11 state.** Have the launcher run
   `xrandr --output eDP-1 --primary` (or `DP-4`) right before `wine D3DPOPTB.EXE -ALLRES`,
   and restore the user's normal primary afterwards. With `-ALLRES` the game's own sort
   (§2.3: bpp desc, width desc, height desc) puts the monitor's native resolution at **index
   0** of the final list in both cases I tested (2256×1504@32bpp and 1920×1080@32bpp were
   each the widest 32bpp entry in their respective lists) — so the launcher's whole job
   becomes: set primary, write `CONFIG00.DAT[0] = 0`, launch with `-ALLRES`. No code
   injection required. The simplest and most robust option given what's actually been
   verified this session.
2. **DLL proxy, if you don't want to touch the user's X11 primary-monitor assignment** (e.g.
   other windows are open and reassigning primary causes window-manager reflow, or you want
   it to work independent of whatever's plugged in without any `xrandr` shelling-out).
   A thin `ddraw.dll` wrapper (forwards everything to the real `ddraw.dll` except
   `IDirectDraw::EnumDisplayModes`, which it answers itself with a synthetic one-entry
   `DDSURFACEDESC` for the desired width/height/bpp, called straight into the game's own
   callback) decouples the result entirely from X11's primary-monitor state. "Detecting the
   screen" in this design is better done **outside** the DLL — the launcher already knows
   which monitor it wants (user choice, or read from `xrandr --query`/a Wayland output
   enumerator on the host side, where connector names like `eDP-1`/`DP-4` are actually
   visible — Win32-side APIs inside Wine never expose RandR connector names, only
   `\\.\DISPLAYn` + a GPU description string, as seen above) and passes the chosen
   width/height to the DLL (e.g. via an environment variable the launcher sets before
   `wine start`), rather than having the injected DLL re-derive "which screen" from inside
   the Windows/Wine side.
   Writing and testing this DLL is implementation work and, per this repo's role
   (document-only, see `AGENTS.md`), belongs in a separate project, not inside `pop3-rev`.

### 7.1 Proposed design: `res.ini` + `ddraw.dll` proxy — corrected against the exe's actual filters

Sketch under discussion: a launcher writes a small `res.ini` with the desired width/height,
then runs `D3DPOPTB.EXE` with a proxy `ddraw.dll` dropped next to it (forwards everything to
the real system `ddraw.dll` except that it intercepts `IDirectDraw::EnumDisplayModes` and
answers with the resolution from `res.ini`, plus always including an 800×600 fallback entry).
Original exe file untouched; disabling the override is just removing/renaming the DLL. This
shape is sound and standard (it's exactly how most old-DirectDraw-game "widescreen fix" DLLs
work), **but two things found this session would make a naive version of it silently fail**,
specifically for resolutions like 1920×1080 or 2256×1504:

1. **The game's own `EnumDisplayModes` callback (`0x4b0e80`, §2.2) hard-rejects any mode
   wider or taller than 1600px**, *before* it ever reaches the raw list:
   ```
   4b0e86: 81 7e 0c 40 06 00 00    cmp DWORD PTR [esi+0xc], 0x640   ; width  > 1600 ?
   4b0e8d: 0f 87 bf 00 00 00       ja  0x4b0f52                     ; reject
   4b0e93: 81 7e 08 40 06 00 00    cmp DWORD PTR [esi+0x8], 0x640   ; height > 1600 ?
   4b0e9a: 0f 87 b2 00 00 00       ja  0x4b0f52                     ; reject
   ```
   If the DLL's fake `EnumDisplayModes` just calls the game's own `lpEnumModesCallback`
   (the normal, "polite" way to answer this COM method) with a synthetic `DDSURFACEDESC` for
   1920×1080 or 2256×1504, **the game's own callback throws it away** — both exceed 1600 in
   their largest dimension. This cap exists independent of `-ALLRES`/the 640×480-800×600
   collapse (§2.4); it runs earlier, inside the callback itself. Two ways around it, pick
   one in the DLL:
   - Patch those two 4-byte immediates (`40 06 00 00` → something ≥ the target resolution,
     e.g. `00 10 00 00` for 4096) in the process's own memory at DLL load time
     (`VirtualProtect` + overwrite at VA `0x4b0e89` and `0x4b0e96` — offsets computed above,
     specific to this exact `D3DPOPTB.EXE` build/version), then let the real
     `EnumDisplayModes`+callback flow proceed normally; **or**
   - Don't go through the callback at all for the injected modes — write directly into the
     exe's own raw-list globals (table `0x98ea30`, count `0x5cdc50`, §2.2) from the DLL, then
     return `DD_OK` without calling `DirectDrawCreate`'s real `EnumDisplayModes` at all. Also
     viable, but ties the DLL to these exact global addresses (already exe/build-specific
     either way).
2. **`-ALLRES` (or equivalently, the DLL ORing bit `0x4` into the flags dword `0x89c66d`
   directly — simpler and more reliable than relying on a command-line argument, since the
   DLL is already poking process memory) is still required**, independent of (1): without
   it, `init_screen_resolutions` (§2.4) throws away every mode except exact 640×480/800×600
   matches *after* the raw list is built, so even a successfully-injected 1920×1080 entry
   gets discarded at this second stage.
3. **Include an exact 640×480 entry too**, not just the target resolution + the 800×600
   fallback. `init_screen_resolutions` *unconditionally* resets the live `CONFIG00.DAT`-backed
   byte (`0x749cf0`) to "the index of 640×480 in the final list" every time it runs (§2.4) —
   if 640×480 isn't present at all, that reset writes the sentinel `0xFF` into `0x749cf0`
   instead (never overwritten, since nothing matched), which would then be used as an
   out-of-bounds index (`0xFF*12`) into the 12-byte-stride table the next time a resolution
   gets applied (§3) — undefined/garbage `width`/`height`/`bpp` passed to
   `change_screen_mode`. A list of `[target_resolution, 800×600, 640×480]` sidesteps this:
   after the game's own sort (§2.3, bpp desc/width desc/height desc) the target resolution
   still lands at index 0 as intended, while 640×480 and 800×600 are present and reachable
   (indices 2 and 1) as graceful degradation if something else goes wrong — and if `-ALLRES`
   is ever forgotten, the 640×480/800×600 collapse filter (§2.4) still leaves a perfectly
   valid non-empty list (just without the target resolution) rather than breaking anything.

With those two corrections, the overall design — write `res.ini`, launch with the proxy DLL,
no modification to the real exe, trivially disable by dropping the DLL — holds up and matches
how this class of fix is normally done for old DirectDraw titles.

Implementing/building this DLL is out of scope for this repo (document-only, `AGENTS.md`) —
say the word and I'll pick it up as a separate project/location.

## 8. Practical implications for a custom launcher / wrapper DLL

- **Cheapest fix, zero patching**: always launch with `-ALLRES` on the command line. This
  alone should fix "only 2 resolutions" and expose the real enumerated list (§2.4, §4).
- **The `CONFIG00.DAT[0]` byte cannot be mapped to a fixed resolution table across
  machines/Wine configs.** Its meaning is: "index N (0 = best) into whatever
  `IDirectDraw::EnumDisplayModes` reports *this run*, sorted bpp-desc/width-desc/
  height-desc, filtered to `bpp>=16, 512<=width<=1600, 384<=height<=1600`" (§2.2–§2.3). To
  reliably write "the right byte" for a desired WxH, you'd need to either:
  1. **Replicate the filter+sort** against whatever Wine currently reports for display
     modes and compute the matching index before writing `CONFIG00.DAT` — fragile, breaks if
     Wine's reported mode list ever changes (different X11/Xrandr state, different Wine
     version, virtual desktop toggle, etc).
  2. **(More robust) Intercept the enumeration itself** with a thin `ddraw.dll` proxy/wrapper
     DLL that hooks `DirectDrawCreate`/`IDirectDraw::EnumDisplayModes` and feeds the game a
     synthetic, launcher-controlled list (e.g. exactly one entry = the desired resolution, or
     a small fixed, known-order set). That makes the `CONFIG00.DAT` index fully
     deterministic and independent of the host's real display modes — the launcher always
     knows index 0 (or whichever fixed slot) means "my resolution," regardless of machine.
  3. A blunter variant of (2): hook/redirect `change_screen_mode` (`0x500580`) or the global
     `0x749cf0` directly at process start to force the desired width/height/bpp, bypassing
     the index/list mechanism entirely.
- Don't bother with `-SCREENRES` (§4) — it's parsed but provably unused elsewhere in this
  build.
- Building the actual DLL/launcher is implementation work and, per this repo's role
  (document-only, see `AGENTS.md`), is out of scope to write from inside `pop3-rev` — this
  file only records the research needed to build it elsewhere.
