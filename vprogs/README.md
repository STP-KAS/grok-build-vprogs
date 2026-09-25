# vprogs in this run

Wallet-only. No local node, so the tic-tac-toe demo was not booted and no guest ELF was built.

What the demo actually pins (`biryukovmaxim/vprog-tictactoe` master, 2026-09-25):

- vprogs branch in `Cargo.toml`: `fix/reorg-boundary-duplicate-bundles`
- runbook `docs/demo/README.md`: `fix/g2-access-read-enforcement`
- rusty-kaspa rev: `eb0a856d4e1ef9d884c5997bc43408091f5a5632` (not v2.1.0 `01b532e`)
- `kaspanet/vprogs` branch `release-candidate` exists and is a third name

The hosted board at `https://vprogs-tt.izio.fr/` was not used. The seed is not typed into a website.

Folders:

- [normal-pay](normal-pay/README.md) — 0.5 TKAS payment, mass and fee
- [adversarial-probes](adversarial-probes/README.md) — zero value, low fee, malformed submit
