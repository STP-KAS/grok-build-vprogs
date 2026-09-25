# `RpcClient.get_metrics` fails: missing `processMetrics`

- Severity: low
- Component: `kaspa` Python SDK 2.1.0 `get_metrics` against live TN10 public nodes
- When: 2026-09-25

## Summary

```text
RuntimeError: missing field `processMetrics`
```

Reproduced on public nodes that report `serverVersion` `2.1.0` (`muon-10.kaspa.blue`) and `2.0.1` (`proton-10.kaspa.stream`). Both were `isSynced: true` with UTXO index enabled. Every other RPC used in this run (`get_server_info`, `get_block_dag_info`, `get_utxos_by_addresses`, `submit_transaction`, `get_fee_estimate`, `get_virtual_chain_from_block`) worked.

## Suggested fix

Make `processMetrics` optional in the SDK deserializer, or have every supported node version emit it. Add a fixture from a real `2.0.1` and `2.1.0` metrics response to the SDK tests.
