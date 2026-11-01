# Rhythm pack staged apply and recovery

`rhythm_pack_transaction.py` applies one explicitly selected READY schema-1 plan. It never launches StepMania or ITGmania. Apply requires runtime, profile, source, inventory, trusted validator source, Songs root, and `--game-stopped`. It reruns the live validator and preview before writing and compares the supplied plan with the fresh result, excluding only free-space telemetry. Edited, stale, blocked, report-only, and source-drifted plans are refused.

The destination pack directory must be absent. Existing packs are refused without merging or replacing content. Files are copied into a private staging directory under Songs, checked against preview hashes, then activated by same-filesystem atomic directory rename. Free space is rechecked before staging. Directory traversal uses `O_NOFOLLOW`; symlinks, traversal, and unsupported entries are rejected.

Each transaction writes a versioned receipt in `.rhythm-pack-transactions/`, recording runtime/profile/pack, prior destination state, and exact owned paths, sizes, and SHA-256 values. Stages and receipts survive interruption. Do not remove pending stages manually. Inspect or finish a transaction with:

```sh
python3 rhythm_pack_transaction.py recover --target "$SONGS_ROOT" --transaction TRANSACTION_ID
```

When recovery needs to activate a staged pack, provide the original live library and trusted validator source so recovery can rerun validation against the receipt's activation snapshot:

```sh
python3 rhythm_pack_transaction.py recover --target "$SONGS_ROOT" \
  --transaction TRANSACTION_ID --source "$LIBRARY_ROOT" \
  --validator-source "$VALIDATOR_SOURCE"
```

Recovery refuses activation if those inputs are missing, the live validator/source has drifted, or the receipt lacks the original activation validation provenance. The staged directory and ownership receipt are preserved for inspection or rollback. Rollback does not require these arguments. Recovery of an already-active transaction verifies the owned content and may refresh its durable receipt; it does not activate new content and remains idempotent.

Rollback removes only unchanged transaction-owned files. It preserves modified files and unrelated content, reports conflicts, and removes directories only when empty. Recovery around activation checks the receipt, stage, destination, and exact owned hashes; uncertain destinations are preserved as conflicts. Repeating recovery/rollback is safe.

Plans must come from `rhythm_pack_preview.py` with `--validator-source` and be stored outside source and target trees. Example:

```sh
python3 rhythm_pack_transaction.py apply \
  --plan /tmp/selected-plan.json --source "$LIBRARY_ROOT" \
  --inventory "$INVENTORY_JSON" --validator-source "$VALIDATOR_SOURCE" \
  --pack 'pack:Group' --runtime stepmania-flatpak \
  --profile stock-stepmania-flatpak --target "$SONGS_ROOT" --apply --game-stopped
```

Automated tests use synthetic text-only temporary roots and fixture-only interruption injection; they do not use a physical device, NAS, mount, or real media. Run `bash tests/test-pack-transaction.sh`, then `bash tests/test-fd-ancestry.sh`, `bash tests/test-versioned-extract.sh`, `bash tests/install-config-preservation.sh`, and `bash tests/test-pack-preview.sh`.
