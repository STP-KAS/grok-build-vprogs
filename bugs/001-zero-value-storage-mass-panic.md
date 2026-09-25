# Zero-value outputs panic storage-mass calculation

- Severity: medium
- Component: `kaspa` Python SDK 2.1.0, wrapping rusty-kaspa `consensus/core/src/mass/mod.rs`
- Commit: `01b532e` (tag `v2.1.0`)
- Network: local call, no broadcast required

## Summary

`calculate_storage_mass("testnet-10", [1_000_000_000], [0, 1_000_000_000])` aborts the worker thread with `attempt to divide by zero` at `mass/mod.rs:463`. The public SDK does not reject a zero amount before the unchecked division.

## Why this is an inconsistency

`calc_storage_mass` documents that every input and output value must be non-zero, and it uses `checked_mul` for the product. The division by `amount` is unchecked (`/` rather than `checked_div`). A Python caller gets a `PanicException` instead of `None` or a normal error. A hostile or merely empty output can take down a wallet process.

## Repro

```python
from kaspa import calculate_storage_mass
calculate_storage_mass("testnet-10", [1_000_000_000], [0, 1_000_000_000])
```

Observed stderr:

```text
thread '<unnamed>' panicked at .../consensus/core/src/mass/mod.rs:463:38:
attempt to divide by zero
```

## Suggested fix

Use `checked_div` and return `None` when any amount is zero, and make the Python binding raise `ValueError` instead of panicking. Same guard belongs on the other language bindings.
