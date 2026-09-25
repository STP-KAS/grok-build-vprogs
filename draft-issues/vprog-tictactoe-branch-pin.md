Title: Demo runbook checks out a different vprogs branch than Cargo.toml

Body:

On `biryukovmaxim/vprog-tictactoe` master (read 2026-09-25):

- `Cargo.toml` pins `vprogs-*` to branch `fix/reorg-boundary-duplicate-bundles` and rusty-kaspa to `eb0a856d4e1ef9d884c5997bc43408091f5a5632`.
- `docs/demo/README.md` tells the reader to `git checkout fix/g2-access-read-enforcement` and says the Cargo pins currently use that branch.

The runbook itself says backend ELFs from any other rev silently mismatch the host. The two files cannot both be right.

`release-candidate` on `kaspanet/vprogs` is a third name, and `eb0a856d` is not rusty-kaspa v2.1.0 (`01b532e`).

Suggested fix: one commit pin, copied into the runbook from the lockfile, plus one sentence on whether `release-candidate` is that commit.
