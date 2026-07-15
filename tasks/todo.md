# TODO — Make TT99 the Default Accounting Everywhere (Miyano)

Prior phases (Tasks 1–20) complete. This phase wires module/master-data account
links to TT99 and switches the Miyano company onto the TT99 chart. See
`tasks/plan.md` for acceptance criteria and dependencies.

## Phase 6 — Default module wiring (reusable hook)
- [x] Task 21 — VN setup hook + Mode of Payment accounts (Cash 111, Bank 112)
- [x] Task 22 — Default Asset Categories on TT99 (211/2141/6424/2411, 213/2143)
- [x] Task 23 — Item accounts resolve to 511/632 via Company defaults (no separate wiring; verified in Task 24)
- [x] Task 24 — End-to-end invoice posting on TT99 (SI → 131/511/33311; PI → 331/632/1331)
- [ ] Task 25 — Idempotency + auto-dispatch on VN company creation

## Phase 7 — Reconfigure Miyano
- [ ] Task 26 — Switch empty Miyano to TT99 (guarded patch; confirm before applying to real Miyano)
