Title: Python SDK 2.1.0 get_metrics fails on live TN10 nodes (missing processMetrics)

Body:

`RpcClient.get_metrics()` against public TN10 wRPC raises `RuntimeError: missing field processMetrics`.

Seen on:

- `wss://muon-10.kaspa.blue/kaspa/testnet-10/wrpc/borsh` serverVersion 2.1.0, isSynced true
- `wss://proton-10.kaspa.stream/kaspa/testnet-10/wrpc/borsh` serverVersion 2.0.1, isSynced true

SDK: `kaspa` 2.1.0 on PyPI. Other RPCs on the same connections succeeded.

Suggested fix: treat `processMetrics` as optional, and add a decode test from both 2.0.1 and 2.1.0 responses.
