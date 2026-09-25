# normal-pay

A normal vprog-shaped payment: lock a stake, record one recipient, release it. This folder is the specification and the L1 mass measurement. It is **not** a compiled RISC0 guest.

## Purpose

Show the cheapest honest payment the L1 will accept, and the KIP-9 cost of paying a small amount out of a large UTXO. The tic-tac-toe pot is this shape (many small outputs, one large change).

## How to run

Uses public TN10 wRPC. No local node.

```bash
export KASPA_SEED_FILE=/path/to/seed   # chmod 600, testnet phrase, not committed
python3 scripts/tn10_wallet_stress.py mass
python3 scripts/tn10_wallet_stress.py lane-a --seconds 30 --max-txs 8 --amount-kas 0.5
```

`lane-a` spends real testnet coins (0.5 TKAS plus fee) from receive index 0 to indexes 1..N.

## Expected vs actual

| | Expected from KIP-9 and v2.1.0 params | Actual on TN10, 2026-09-25 |
|---|---|---|
| Storage mass of 0.5 TKAS + large change | `C / 0.5 TKAS = 20_000` with `C = 10_000 KAS` | 20000 |
| Block packing if every tx looks like this | `10 BPS * 500_000 / 20_000 = 250 tx/s` | formula holds; we sent 24, all accepted |
| Minimum fee | unclear from the SDK | **203600 sompi**, priced on compute mass 2036, not on 20000 |
| SDK `calculate_transaction_mass` | compute mass, if used for fees | returned 20000 (storage). Blind `* 100` overpays |

The guest program was not built. `vprog-tictactoe` needs a simnet node (`demo-l1`), `ttd`, and a RISC0 ELF from the pinned vprogs branch. This run was wallet-only, on public TN10, and did not start `kaspad`.
