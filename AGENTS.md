# AGENTS.md

Read `CONTEXT.md` first for a big-picture overview before diving into the exe, memory, or docs.

## Role: document only
Agents working from this repo analyse the original game and document it. They never implement anything:
- No code changes in `open-populous` (`crates/`, tests, tools): no fixes, even when asked to "fix" a difference.
- Write the findings to `open-populous/docs/specs/pop3-rev-analysis.md`, the matching spec, and `TODO.md`
  (the items describing what our code should change). The implementation is done in a separate session.
- No commits in `open-populous`: report what changed in each file.

## Clean-room boundary
The goal is a clean-room reimplementation: behaviour reimplemented without copying the
original's expression of it, so the result isn't a derivative work. Never produce or commit a
literal decompiled/transliterated C or C++ translation of the disassembly anywhere — not in
`pop3-rev`, not in `open-populous`, not even as a scratch/convenience artifact. Every output
stays at the level of behavioural description: pseudocode of control flow, exact
formulas/constants, data layouts, named functions and their one-line role. This applies to both
the function catalog (`pop3-rev/docs/functions.tsv`, via the `exe-function-map` skill) and the
implementable spec (`pop3-rev-analysis.md`, via the `original-game-spec` skill).
