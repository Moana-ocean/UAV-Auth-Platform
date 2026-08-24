# Root cause and fix report

## 1. Observed symptom

All blockchain `valid_active` measured requests in the baseline matrix were rejected with `INVALID_SIGNATURE` (750/750 scale cells; 30/30 security-battery positive control). Blockchain `unauthorised_operation` was also rejected as `INVALID_SIGNATURE` instead of `UNAUTHORISED_OPERATION`. X.509 `valid_active` accepted 750/750.

## 2. Confirmed root cause

**On-chain registry public keys did not match the local PEM signing keys** used by the experiment scenarios.

Live diagnosis (Besu chain ID 20245, contract `0x25629De856e42E1D2d52C8916622938C20A37Cc8`):

| UAV | Local pubkey prefix | On-chain prefix | Match |
|-----|---------------------|-----------------|-------|
| UAV-VALID | `0439edf2…` | `042b16fe…` | False |
| UAV-LIMITED | `0438f47b…` | `04af7dee…` | False |

- Local PEM ↔ `identities.json` `public_key_hex`: **match**
- Signature verifies with local key: **true**
- Signature verifies with on-chain key: **false**
- End-to-end GCS auth outcome: **`INVALID_SIGNATURE`**

Mechanism: `register_population_on_chain` only called `register` when `status == None`. After local identity regeneration (historical wipe/recreate), Active identities were skipped, leaving **stale keys** on-chain. X.509 continued to work because certificates were re-issued for the new PEM keys.

`revoked_uav` still returned `REVOKED_IDENTITY` because status is checked **before** signature verification in `GCSAuthService._authenticate_inner`.

## 3. Minimal reproducer

`tests/test_crypto_registration.py::test_stale_on_chain_key_causes_invalid_signature_then_sync_accepts`  
`tests/test_key_sync_integration.py::test_stale_key_then_updatekey_accepts` (Besu)

## 4. Affected components and datasets

- Setup: `app/experiments/runner.py::register_population_on_chain`
- All baseline blockchain valid/auth cells listed in `BASELINE_INVENTORY.md`
- Baseline package `results/chapter5_export/` — retain as failed-iteration evidence only

## 5. Code / schema changes

- **No Solidity schema change.** Used existing `updateKey` / `updateRole`.
- `register_population_on_chain`: if Active/Suspended and pubkey (or role) differs → `updateKey` / `updateRole`.
- `IdentityPopulation.load_key`: derive public bytes from PEM.
- Matrix: `--output-root` for isolated corrective runs.

## 6. Why this fixes the defect

Authentication verifies against the registry pubkey (`BlockchainIdentityBackend.lookup` → `verify_message`). Syncing the registry to the current local signing key restores verification; authorisation then runs and returns `UNAUTHORISED_OPERATION` for limited roles.

## 7. Regression tests added

- `tests/test_crypto_registration.py` (unit)
- `tests/test_key_sync_integration.py` (Besu)

## 8. Remaining limitations

Unchanged: single-host Besu, loopback, not a BFT experiment, Python 3.13 deviation (`LIMITATIONS.md`). Revoked identities cannot `updateKey` (contract); status-before-signature keeps revoked tests valid.

## 9. Git commit for new experiment

Record the commit hash after the repair commit is created (working tree dirty until commit). Baseline freeze commit was `10fca10e9c9c110e8b0ce842b790bd8a1a6e3a64`.

## 10. Chapter 3 / 4 updates?

- Chapter 3 factors: **unchanged**
- Chapter 4: note that registration must keep on-chain pubkey synchronized with the UAV signing key; evaluation uses Besu/QBFT (not Ganache)
