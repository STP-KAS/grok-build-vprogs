# adversarial-probes

Probes the weak spots named in the brief: zero-value outputs, underfunded fees, malformed input. Reorg behaviour is taken from the tic-tac-toe pin, not from a live reorg we produced.

## Purpose

Break fee and mass handling without draining the wallet. Each probe is one transaction or one local call.

## How to run

```bash
export KASPA_SEED_FILE=/path/to/seed   # chmod 600
python3 scripts/tn10_wallet_stress.py adversarial
```

The zero-fee sweep and the malformed submit run inside that command. The storage-vs-compute fee probe is in `bugs/002-fee-uses-compute-mass-sdk-returns-storage.md`.

## Expected vs actual

| Probe | Expected | Actual |
|---|---|---|
| Zero-value output in `calculate_storage_mass` | A clean error (`None` / exception) | Rust panic, divide by zero, `mass/mod.rs:463` (`bugs/001`) |
| Fee 0 on a 1624-mass sweep | Reject | Reject: need 162400 sompi for compute mass 1624. UTXO not spent |
| Fee 20000 on that sweep | Reject | Same rule, required 162400 |
| Fee 200000 on a 0.5 TKAS payment (storage mass 20000) | Either reject for storage, or accept | Reject, but the text cites **compute mass 2036** and required **203600**, not 20000 |
| Fee 500000 on that payment | Accept if the floor is ~203600 | Accepted, tx `0ce729f91cc4957624d4c5ca95d0add877910acad9fb908cd3e0e3793a12805f` |
| Malformed `submit_transaction({"foo": 1})` | RPC error | Client `TypeError` before the RPC (`dict` cannot be cast as `Transaction`). The node never sees it |
| Reorg | A vprog settler handling a boundary with no batch metadata | Not executed. Demo pins branch `fix/reorg-boundary-duplicate-bundles` while the runbook still says `fix/g2-access-read-enforcement` (`bugs/005`) |

No adversarial guest ELF was compiled. Building one needs the RISC0 toolchain and the pinned vprogs checkout, which this wallet-only run did not start.
