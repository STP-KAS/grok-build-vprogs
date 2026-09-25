# Public TN10 resolver mixes rusty-kaspa 2.0.1 and 2.1.0

- Severity: low (operational)
- When: 2026-09-25, simultaneous `get_server_info` calls

## Summary

One resolver sweep returned nodes that all claimed `isSynced: true` on `testnet-10`:

| Endpoint | serverVersion |
|---|---|
| wss://muon-10.kaspa.blue/.../testnet-10/wrpc/borsh | 2.1.0 |
| wss://vector-10.kaspa.green/... | 2.1.0 |
| wss://boson-10.kaspa.red/... | 2.0.1 |
| wss://proton-10.kaspa.stream/... | 2.0.1 |

v2.1.0 is the current release (2026-09-22, P2P protocol 11). v2.0.1 is the 2026-06-15 release. Wallets that follow the resolver have no signal which code they reached. Several of eight connections landed on the same host (`vector-10`), so "spread across RPC connections" does not imply eight machines.

Virtual DAA scores taken in the same second differed by a few hundred (about half a minute at 10 BPS). That is lag, not a fork: the treasury balance on `proton-10` (2.0.1) matched `https://api-tn10.kaspa.org` exactly (`10118967448563` sompi).

## Suggested fix

Publish the node version in the resolver record and let clients pin a minimum version. Prefer the current release on the public TN10 names.
