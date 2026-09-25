# Minimum fee is 100× compute mass, but `calculate_transaction_mass` returns storage mass

- Severity: medium (integrators overpay; throughput planning uses the wrong mass)
- Component: TN10 standardness vs `kaspa` 2.1.0 `calculate_transaction_mass`
- Nodes: `vector-10.kaspa.green` server `2.1.0`, also reproduced as a reject on `boson-10` / `muon-10`
- When: 2026-09-25

## Summary

A 1-in-1-out sweep has compute mass **1624**. The node rejects a lower fee with:

```text
transaction has 20000 fees which is under the required amount of 162400 for compute mass 1624
```

So the standardness floor is `fee >= 100 * compute_mass` (162400 sompi).

A 0.5 TKAS payment plus change has storage mass **20000** (KIP-9, `C = 10_000 KAS`) and compute mass **2036**. The same rule:

```text
transaction has 200000 fees which is under the required amount of 203600 for compute mass 2036
```

Storage mass does **not** raise the minimum fee. A fee of 500000 sompi (above 203600, far below `20000 * 100`) was accepted.

`calculate_transaction_mass("testnet-10", tx)` returned **20000** for that payment, i.e. the storage dimension, not the compute dimension the fee rule uses. A wallet that does `fee = feerate * calculate_transaction_mass()` overpays about 10× (we did: 2_000_000 sompi instead of 203_600 on 24 payments).

## Repro

1. Build a tx that pays 0.5 TKAS and sends the remainder minus `fee` back to the sender, from a large UTXO.
2. Submit with `fee = 200_000`. Observe the reject text quoting compute mass 2036 and required 203600.
3. Submit the same shape with `fee = 500_000`. Observe RPC accept.
4. Compare with `calculate_transaction_mass`, which reports 20000.

## Suggested fix

Expose compute, storage, and transient mass separately. Document that TN10 standardness prices **compute** mass at 100 sompi/gram. Point fee helpers at compute mass. Keep using storage mass for block-packing / TPS ceilings.
