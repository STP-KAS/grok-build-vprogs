# vprog-tictactoe runbook and Cargo.toml pin different vprogs branches

- Severity: medium for anyone reproducing the demo
- Repo: `biryukovmaxim/vprog-tictactoe` master, read 2026-09-25
- Not filed upstream

## Summary

`Cargo.toml` workspace dependencies pin every `vprogs-*` crate to branch `fix/reorg-boundary-duplicate-bundles`, and pin `kaspanet/rusty-kaspa` to rev `eb0a856d4e1ef9d884c5997bc43408091f5a5632`.

`docs/demo/README.md` still says:

```text
currently branch fix/g2-access-read-enforcement
git -C ../vprogs checkout fix/g2-access-read-enforcement
```

The Kaspa org branch `release-candidate` is a third name. The runbook warns that ELFs from any other rev silently mismatch the host. Following the runbook checks out the wrong branch.

`eb0a856d` is not rusty-kaspa `v2.1.0` (`01b532e`, 2026-09-22). The public TN10 nodes in this test were 2.0.1 and 2.1.0.

## Suggested fix

Make the runbook read the branch from `Cargo.toml` (or pin a commit in both files from the lockfile). State that `release-candidate` is or is not that commit.
