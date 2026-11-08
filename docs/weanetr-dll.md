# `weanetr.dll` import catalog

`D3DPOPTB.EXE` imports its multiplayer networking from an external library, `weanetr.dll`
(not present in `game/` - the game ships without it in this install, so these entries are only
known as *imports*: names, demangled signatures and IAT addresses, never the DLL's own code).
Found while chasing the chat "which tribe do I send this to" icons
(`docs/trace-backlog.md` "Notifications") - the single most useful lead that session, precisely
because a live memory check wasn't possible in that environment (no Wine/display): a networking
or file-I/O action that's indirect/callback-driven in the game's own UI code still has to cross a
DLL boundary somewhere, and that boundary shows up as a plain, inspectable import name.

## What this library is

Every exported name is a C++ instance method or static data member of one class, `MLDPlay`
(the lone exception, `options_to_parity_table`, is a free global). The shape of the API -
`StartupNetwork`/`ShutdownNetwork`, `CreateSession`/`JoinSession`/`DestroySession`,
`EnumerateSessions`/`EnumerateServices`/`EnumerateNetworkMediums`, `SendData`/`SendChat` - is a
thin, DirectPlay-flavoured multiplayer-session wrapper, almost certainly Bullfrog's own in-house
library built on top of Microsoft's DirectPlay (not DirectPlay itself - no `IDirectPlay4`-style
vtable or GUID names appear, and the 3 `_GUID` constants below are **Bullfrog's own**, not
Microsoft's standard DirectPlay service-provider GUIDs). `weanetr` plausibly reads as
"**W**estwood/**E**lectronic **A**rts **net**work **r**untime" or similar - not confirmed, no
version info/string resource was found for the DLL itself (it isn't present to inspect).

## How this catalog was built

No live memory, no Wine, no running the game - purely from the exe file already on disk:
1. `strings -n 4 game/D3DPOPTB.EXE` surfaced the mangled names directly (MSVC name-mangled C++
   symbols appear as plain ASCII in the import/export name table).
2. `objdump -x game/D3DPOPTB.EXE` listed the full import-by-DLL breakdown (hint/name-table RVAs,
   not runtime addresses).
3. `pip install pefile` (works - `pypi.org`/`files.pythonhosted.org` are allow-listed through this
   environment's proxy even when `github.com` itself is session-scoped and blocked) then a short
   script read `pe.DIRECTORY_ENTRY_IMPORT` for the real IAT slot address each import resolves to
   at runtime (`call DWORD PTR ds:0x<slot>` is how the exe's own code actually invokes it - the
   hint/name RVA from step 2 is a different address and won't appear in any `call` site).
4. `llvm-undname` (already installed in this container, part of the `llvm` package - handles MSVC
   mangling; GNU `c++filt` does not) demangled every name into a readable C++ signature.
5. `grep <IAT address> dis.txt` in the cached disassembly found every real call site per entry.

A future session without network/Wine access facing a similar "what does clicking X actually DO"
question should try this same recipe (`strings` + `objdump -x` + demangling) before spending a
long session on UI/callback disassembly alone - see the trace-backlog entry above for the context
this paid off in.

## Full import list (21 entries, IAT base `0xD0C968`)

All in `weanetr.dll`. `calls` is how many `call`/reference sites exist anywhere in
`D3DPOPTB.EXE`'s own code for that IAT slot (`dis.txt`, this session's build) - every entry is
genuinely used at least once, nothing here is dead-import cruft.

| IAT addr | Mangled name | Demangled signature | calls | Traced? |
|---|---|---|---|---|
| `0xD0C968` | `?BFAID_INet@@3U_GUID@@A` | `struct _GUID BFAID_INet` | 6 | data (a GUID constant), not a function - not traced |
| `0xD0C96C` | `?SendData@MLDPlay@@QAEHKPAXKKPAK@Z` | `int MLDPlay::SendData(unsigned long, void*, unsigned long, unsigned long, unsigned long*)` | 4 | not traced |
| `0xD0C970` | `?GetPlayerInfo@MLDPlay@@QAEHPAUMLDPLAY_PLAYERINFO@@@Z` | `int MLDPlay::GetPlayerInfo(struct MLDPLAY_PLAYERINFO*)` | 5 | not traced |
| `0xD0C974` | `?EnumerateServices@MLDPlay@@QAEHP6GXPAXPAGPAU_GUID@@K0@Z0@Z` | `int MLDPlay::EnumerateServices(void(__stdcall*)(void*,unsigned short*,struct _GUID*,unsigned long,void*), void*)` | 2 | not traced |
| `0xD0C978` | `?AreWeLobbied@MLDPlay@@QAEKP6GXKPAXKK0@ZPAU_GUID@@PAUMLDPLAY_LOBBYINFO@@PAKPAG5KK@Z` | `unsigned long MLDPlay::AreWeLobbied(void(__stdcall*)(unsigned long,void*,unsigned long,unsigned long,void*), struct _GUID*, struct MLDPLAY_LOBBYINFO*, unsigned long*, unsigned short*, unsigned short*, unsigned long, unsigned long)` | 1 | not traced |
| `0xD0C97C` | `?StartupNetwork@MLDPlay@@QAEHP6GXKPAXKK0@Z@Z` | `int MLDPlay::StartupNetwork(void(__stdcall*)(unsigned long,void*,unsigned long,unsigned long,void*))` | 1 | not traced |
| `0xD0C980` | `?ShutdownNetwork@MLDPlay@@QAEHXZ` | `int MLDPlay::ShutdownNetwork(void)` | 1 | not traced |
| `0xD0C984` | `?SendMSResults@MLDPlay@@QAEKPAD@Z` | `unsigned long MLDPlay::SendMSResults(char*)` | 1 | not traced |
| `0xD0C988` | `?EnumerateNetworkMediums@MLDPlay@@QAEKP6GXPAGPAX@Z1@Z` | `unsigned long MLDPlay::EnumerateNetworkMediums(void(__stdcall*)(unsigned short*,void*), void*)` | 2 | not traced |
| `0xD0C98C` | `?GetCurrentMs@MLDPlay@@QAEKXZ` | `unsigned long MLDPlay::GetCurrentMs(void)` | 28 | not traced (generic timestamp getter, called everywhere - not multiplayer-specific in effect, probably used as a general elapsed-time clock) |
| `0xD0C990` | `?CreateSession@MLDPlay@@QAEHPAKPAG1PAXK@Z` | `int MLDPlay::CreateSession(unsigned long*, unsigned short*, unsigned short*, void*, unsigned long)` | 1 | not traced |
| `0xD0C994` | `?EnumerateSessions@MLDPlay@@QAEHKP6GXPAUMLDPLAY_SESSIONDESC@@PAX@ZK1@Z` | `int MLDPlay::EnumerateSessions(unsigned long, void(__stdcall*)(struct MLDPLAY_SESSIONDESC*,void*), unsigned long, void*)` | 1 | not traced |
| `0xD0C998` | `?JoinSession@MLDPlay@@QAEHPAUMLDPLAY_SESSIONDESC@@PAKPAGPAX@Z` | `int MLDPlay::JoinSession(struct MLDPLAY_SESSIONDESC*, unsigned long*, unsigned short*, void*)` | 1 | not traced |
| `0xD0C99C` | `?CreateNetworkAddress@MLDPlay@@QAEHPAXK0PAK@Z` | `int MLDPlay::CreateNetworkAddress(void*, unsigned long, void*, unsigned long*)` | 1 | not traced |
| `0xD0C9A0` | `?options_to_parity_table@@3PAHA` | `int* options_to_parity_table` | 1 | data (a lookup table pointer, not a function) - not traced |
| `0xD0C9A4` | `?BFSPGUID_MODEM@@3U_GUID@@A` | `struct _GUID BFSPGUID_MODEM` | 1 | data (GUID constant) - not traced |
| `0xD0C9A8` | `?BFAID_MODEM@@3U_GUID@@A` | `struct _GUID BFAID_MODEM` | 6 | data (GUID constant) - not traced |
| `0xD0C9AC` | `?EnableNewPlayers@MLDPlay@@QAEXH@Z` | `void MLDPlay::EnableNewPlayers(int)` | 1 | not traced |
| `0xD0C9B0` | `?DestroySession@MLDPlay@@QAEHXZ` | `int MLDPlay::DestroySession(void)` | 3 | not traced |
| `0xD0C9B4` | `?SetupConnection@MLDPlay@@QAEHPAXPAU_GUID@@0@Z` | `int MLDPlay::SetupConnection(void*, struct _GUID*, void*)` | 3 | not traced |
| `0xD0C9B8` | `?SendChat@MLDPlay@@QAEHKPAGKPAK@Z` | `int MLDPlay::SendChat(unsigned long dest, unsigned short* text, unsigned long, unsigned long* out)` | 6 | **traced** - `docs/functions.tsv` row `0xD0C9B8`; the chat-recipient-icon send loop is `0x4AE5B0`'s own row |

## `_GUID` constants: Bullfrog's own service-provider/address IDs

`BFAID_INet` and `BFAID_MODEM`/`BFSPGUID_MODEM` ("BF" = Bullfrog) are Bullfrog-authored GUIDs, not
Microsoft's standard DirectPlay `DPAID_*`/`DPSPGUID_*` constants - consistent with `MLDPlay`
being Bullfrog's own wrapper layer registering its own connection-type identifiers (Internet,
Modem - a third, LAN/IPX-style medium would be expected too but wasn't found among these 21
entries; `EnumerateNetworkMediums`, own row, is the likely place a LAN medium would surface
instead of a fixed GUID constant). Raw GUID byte values were not extracted this session - only
the symbol names/addresses.

## `SendChat`: the one entry fully traced

See `docs/functions.tsv` (`0xD0C9B8`, `0x4AE5B0`, `0x49EB50`, `0x4A25B0`) and
`docs/trace-backlog.md` "Notifications" for the full write-up. Summary: the chat dialog's send
path reads a 4-byte per-UI-slot array (`0x96AAB6`-`0x96AAB9`) - one flag per tribe other than the
local player, plus a 4th "ALL" flag - and either sends one broadcast `SendChat(0xFFFFFFFF, text,
...)` or one call per individually-selected tribe. This is the real mechanism behind the
in-game chat's recipient-selection icons (confirmed from the exe alone, no live check run).

## Open leads for a future session

- The other 20 entries are each a single demangled signature and nothing more - any of them
  (`GetPlayerInfo`, `EnumerateSessions`/`EnumerateServices`/`EnumerateNetworkMediums`,
  `CreateSession`/`JoinSession`/`DestroySession`, `SendData`) would be a reasonable next target if
  a future question needs the multiplayer lobby/session-browser side of the game rather than
  in-game chat.
- `GetCurrentMs`'s own 28 call sites suggest it is used far more broadly than "multiplayer timing"
  - worth checking whether it is this exe's general wall-clock/elapsed-time source even in
  single-player, before assuming every caller is multiplayer-specific.
- The raw byte values of the 3 `_GUID` constants (`BFAID_INet`, `BFAID_MODEM`, `BFSPGUID_MODEM`)
  were not read from `.data` this session - trivial with the same `pefile`/raw-file-offset method
  as the rest of this catalog, if ever useful (e.g. cross-referencing against a known Populous:
  The Beginning community GUID list).
