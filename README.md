# grok-build-vprogs

Testnet-10 wallet load notes from 2026-09-25. Private on purpose. Testnet only. No mainnet keys, no seed in this tree.

Local `kaspad` and the miner were not started. The follow-up instruction was to use the wallet only. Transactions went through the public TN10 wRPC resolver (`kaspa` Python SDK 2.1.0).

## What, why, how

Maksim Biriukov's tic-tac-toe vprog is a small program on top of a Kaspa L1 that already prices storage (KIP-9) and packs blocks at 10 per second. The question for a core dev is not "can a wallet send". It is where a flood stops: signature CPU, UTXO parallelism, the RPC, the compute-mass limit, or the storage-mass limit.

This run answers that with a throwaway TN10 wallet:

- Phrase stays in `KASPA_SEED_FILE` (default `/root/.config/kaspa-tn10/wallet.seed`, mode `600`). The script refuses a looser mode. It never prints the phrase or a private key.
- Derivation `m/44'/111111'/0'/0/0` matches the funded address. Checked before any spend.
- Lane B: 1-input 1-output sweeps of already-confirmed UTXOs, lowest fee the node will accept, signed in-process, submitted across several resolver connections. No spend of an unconfirmed change output.
- Lane A: 0.5 TKAS payments that leave a large change output, which is the KIP-9 case.

The 10,000 TKAS and 999 TKAS UTXOs were left untouched.

## Metrics

Consensus numbers are `TESTNET_PARAMS` in rusty-kaspa v2.1.0 (`01b532e`): 10 blocks/second, compute mass limit 500,000, storage mass limit 500,000, transient mass limit 1,000,000, KIP-9 `C = 10,000 KAS` (`STORAGE_MASS_PARAMETER = 10^12` sompi).

| | Lane B, 1-in-1-out | Lane A, 0.5 TKAS + change |
|---|---|---|
| Measured mass | 1624 compute (storage 65) | storage 20000, compute 2036 |
| Minimum fee | 162400 sompi (0.001624 TKAS) | 203600 sompi (0.002036 TKAS) |
| What we paid | 162400 | 2000000 (SDK overpay, see bugs/002) |
| Packing ceiling | 10 × 500000 / 1624 = **3078.8 tx/s** | 10 × 500000 / 20000 = **250 tx/s** |
| Offered | 552 tx/s then **1162 tx/s** | 3.2 tx/s over 24 payments |
| RPC accepts | 320/320 and 340/340 | 24/24 |
| Included | yes, fee total matches | yes, 12 TKAS left the treasury |

Sign + build on this 2-core host: about **13,200 tx/s**. Signing is not the ceiling.

Network inclusion, from `getVirtualChainFromBlock` (selected chain, accepted tx ids):

| Window | DAA / s | Accepted tx/s | Notes |
|---|---|---|---|
| Quiet, 8 s, before the flood | 9.00 | 36.7 | 40 chain blocks, 298 txs |
| 20 s around wave 2 | 9.04 | 2064 | 94 chain blocks, 41532 txs |

Wave 2 itself was 340 transactions. The 2064 tx/s is the network, not this wallet. Tip moved at ~9 DAA/s the whole time (10 BPS is healthy). A quiet TN10 is nowhere near the 3079 ceiling; during that 20 s it was at about two thirds of the 1-in-1-out ceiling, mostly other traffic.

Money, sompi, treasury receive index 0:

| | sompi | TKAS |
|---|---|---|
| Start | 10120322632563 | 101203.22632563 |
| End | 10118967448563 | 101189.67448563 |
| Difference | 1355184000 | 13.55184 |

Of that, 12 TKAS sits on derived receive addresses (the 0.5 payments) and 1.55184 TKAS is fees: `660 × 162400 + 24 × 2000000`. The 660 sweeps are wave 1 (320) plus wave 2 (340). End balance matches the explorer REST balance for this address.

The prompt mentioned 500,000 TKAS. At the start of this run the address held 101,203.23 TKAS in 349 UTXOs.

### Timeline (UTC, 2026-09-25)

1. Address check against public wRPC. Match. Node examples: `muon-10` 2.1.0 synced, `boson-10` 2.0.1 synced.
2. Quiet network sample, ~37 tx/s.
3. Fee 20000 on a 1624-mass sweep rejected (need 162400). UTXO not spent.
4. Wave 1: 320 sweeps, 552 offered tx/s, all accepted by RPC, later included.
5. Wave 2: 340 sweeps, 1162 offered tx/s, all included. Network sample in the same minute: 2064 accepted tx/s.
6. 24 payments of 0.5 TKAS. Storage mass 20000 each. All included.
7. One more 0.5 TKAS payment at 500000 sompi accepted after 200000 was rejected for compute mass 2036.

## TPS peak, sustained, ceiling, bottleneck

- Ceiling for a minimum standard payment: **3078.8 tx/s**.
- Ceiling once every payment creates a 0.5 TKAS output next to a large change output: **250 tx/s**, because storage mass is 20,000 and the block storage limit is 500,000. The fee does not get bigger when storage mass does. The block just fills sooner.
- Peak we offered: **1162 tx/s** for 0.29 s (340 txs, 8 RPC connections, 256 in flight). All accepted, all included.
- Sustained: not 1162. There were only ~340 confirmed inputs, and the rule was not to chain an unconfirmed output. Sustained rate ≈ `confirmed_inputs / round_trip`. A two-hour run at 1162 tx/s would need a pre-split set this wallet did not have.
- Bottleneck, in order: **not enough confirmed UTXOs**, then **public wRPC latency** (552 tx/s at 96 in flight, 1162 at 256). Not CPU (13k sign/s). Not the 3079 mass ceiling. Not a local mempool, because there was no local node.

Getting past 3000 offered tx/s needs at least 3000 confirmed inputs and a submit path that holds that rate. The 10,000 TKAS UTXO can be fanned out in one transaction to ~300 outputs before storage mass nears the 100,000 standard-tx cap (`results/mass_table.json`). A second round turns those into thousands of inputs. That split was not broadcast; the reserve is intact.

A two-hour lane A at the measured 3.2 tx/s would be ~23,000 payments and ~46 TKAS of fees at the overpaid 0.02 TKAS, or ~4.7 TKAS of fees at the real 0.002036 TKAS floor. It was not run. Twenty-four payments are enough to pin the mass at 20,000.

## Joining the live tic-tac-toe test

The hosted game at `https://vprogs-tt.izio.fr` was joined from this wallet. The seed and the hex keys stayed in mode-600 files under `/root/.config/kaspa-tn10/`. They were not typed into the site. Carriers were built with the site's encoder wasm and submitted to public TN10 wRPC.

Version-1 inputs have to go out as `sigOpCount: 0` plus `computeBudget`. Sending `sigOpCount: 1` is rejected with `RpcTransactionInput.sig_op_count is inconsistent with transaction version 1`. That matches rusty-kaspa v2.1.0: for `version >= 1` a non-zero `sig_op_count` is the wrong mass arm.

Two games were already on the rollup for these keys (1 TKAS stake, one round):

| Game | Seats | API state while we submitted |
|---|---|---|
| `f8f4dcd4…` | 80 created, open | still Open, empty board |
| `fe3206cd…` | 81 created, 82 already joined | still Playing, empty board, `last_move_at` 580329997 |

Index 82 is the joiner of the second game, so both seats there are this seed. Its turn clock is `last_move_at + turn_ttl` (10,000 DAA). Chain virtual DAA was already past that (~580,346,000) before a center move landed, so the guest should reject that turn as expired. The published wasm has no `Timeout` builder, which is the permissionless forfeit.

The open game was played out on L1 by 80 and 82: join (1 TKAS covenant deposit), cells 0, 3, 1, 4, 2 so seat 0 takes the only round, then a 2 TKAS withdraw. Every one of those transactions was included. Txids are in `results/tictactoe_join.json`. Index 82 was funded with 2.5 TKAS from a mid-size treasury output. The 10,000 TKAS and 999 TKAS outputs were not spent.

The demo node did not execute any of it. `GET /api/state` stayed on `l2_tip` 566858 and settled DAA 580229488 for the whole session (same numbers as before these carriers) while L1 virtual DAA moved. The HTTP API itself is live. `ttd` is not advancing its canonical chain, so the boards did not change and there is no new exit leaf to claim.

## Conclusion

TN10 at 10 BPS has headroom in the quiet case (~37 tx/s) and was already near 2000 tx/s of other inclusion traffic while this wallet added a few hundred minimum-mass sweeps. The protocol ceiling for those sweeps is ~3079 tx/s. Small outputs cut that to ~250 tx/s via KIP-9 even though the minimum fee stays on compute mass. Public RPC plus a few hundred UTXOs cannot honestly claim 3000 tx/s; the signing CPU can.

## Solutions

- Pre-split to thousands of even confirmed UTXOs before a max-TPS run. Never spend the change of an unconfirmed tx.
- Price fees off **compute** mass (`100` sompi per gram on this TN10), not off `calculate_transaction_mass` when that value is the storage dimension.
- Treat storage mass as a packing limit, not a fee.
- Pin resolver clients to rusty-kaspa ≥ 2.1.0. Today the same resolver returns 2.0.1 and 2.1.0.
- For a real 3000 tx/s submit test, use your own node. This run deliberately did not.

## What you built

- `scripts/tn10_wallet_stress.py` — status, mass table, fee probe, lane A, lane B, adversarial probes, network sample.
- `vprogs/normal-pay` and `vprogs/adversarial-probes` — purpose, command, expected versus actual.
- `bugs/` — repros. `draft-issues/` — text to paste upstream. Nothing was filed.

## Ideas

- Return `{compute, storage, transient}` from the SDK mass call so fee and packing cannot be confused.
- `checked_div` in `calc_storage_mass` (bug 001).
- Optional `processMetrics` in `get_metrics` (bug 003).
- One commit pin shared by the tic-tac-toe runbook and `Cargo.toml` (bug 005). The branch names `release-candidate`, `fix/reorg-boundary-duplicate-bundles`, and `fix/g2-access-read-enforcement` are all in play, and they are not the same string.

## One command

Read-only:

```bash
export KASPA_SEED_FILE=/path/to/seed   # chmod 600
python3 scripts/tn10_wallet_stress.py status
python3 scripts/tn10_wallet_stress.py mass
```

Spends testnet coins (1-in-1-out sweeps back to the same address):

```bash
python3 scripts/tn10_wallet_stress.py burst --count 100 --connections 4 --inflight 64 --recycle
```

## Safety

Testnet-10 only. The script exits if free disk drops under 8 GB or available RAM under 1 GB. It does not delete node data (there is none). The seed file is outside the repo.
