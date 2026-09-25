Title: calc_storage_mass divides by zero on a zero-value output

Body:

`calc_storage_mass` (`consensus/core/src/mass/mod.rs` around line 463, tag v2.1.0 / `01b532e`) divides by `amount` with `/` after using `checked_mul`. The function comment requires non-zero amounts, but the Python SDK 2.1.0 `calculate_storage_mass` forwards user output values straight in.

Repro:

```python
from kaspa import calculate_storage_mass
calculate_storage_mass("testnet-10", [1_000_000_000], [0, 1_000_000_000])
```

Result: `PanicException: attempt to divide by zero` and a panicked Rust thread.

Suggested fix: `checked_div`, return `None` on zero, and reject zero values at the SDK boundary with a normal error.

Testnet only. No mainnet transaction involved.
