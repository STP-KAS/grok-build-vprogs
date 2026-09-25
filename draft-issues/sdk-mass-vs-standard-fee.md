Title: TN10 minimum fee uses compute mass; calculate_transaction_mass returns storage mass

Body:

On TN10 (public node `vector-10.kaspa.green`, server 2.1.0, 2026-09-25) a 0.5 KAS payment with change is rejected at 200000 sompi:

```text
transaction has 200000 fees which is under the required amount of 203600 for compute mass 2036
```

The same shape is accepted at 500000 sompi. Storage mass of that tx is 20000 (KIP-9, C = 10_000 KAS). Storage mass does not raise the required fee. A 1-in-1-out of mass 1624 requires exactly 162400 sompi (`100 * compute mass`) and is rejected below that.

`kaspa` 2.1.0 `calculate_transaction_mass` returns 20000 for the payment (the storage dimension). Integrators who set `fee = 100 * calculate_transaction_mass(tx)` overpay about 10×. This run did that on 24 payments (paid 2000000 sompi, floor was 203600).

Please return compute, storage, and transient separately, and document that standardness prices compute mass.

Testnet only.
