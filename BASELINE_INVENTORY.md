# Baseline inventory (pre-repair freeze)

Captured before code changes for the Chapter 5 blockchain `INVALID_SIGNATURE` repair.

## Git / tree

| Item | Value |
|------|-------|
| Commit | `10fca10e9c9c110e8b0ce842b790bd8a1a6e3a64` |
| Message | Initial archive of UAV-to-GCS authentication evaluation platform. |
| Branch | `main` tracking `origin/main` |
| Working tree at freeze | Clean relative to that commit (local `var/`, Besu network keys, and `results/runs/` remain gitignored) |
| Pre-existing user changes | None uncommitted in tracked files at inventory time |

## Formal evaluation context (unchanged)

- Hyperledger Besu 26.7.1, QBFT, 4 validators, chain ID `20245`
- Python 3.13 (documented deviation)
- Loopback only
- Mechanisms: X.509 PKI and permissioned blockchain
- Identity levels: 10, 50, 100, 250, 500
- Concurrency: 1, 5, 10, 25, 50
- 30 measured reps + 2 warm-ups
- 53 formal matrix steps

## Deployment snapshot (`var/deployment.json`)

| Field | Value |
|-------|-------|
| Contract address | `0x25629De856e42E1D2d52C8916622938C20A37Cc8` |
| Chain ID | 20245 |
| Registrar | `0x80970C02408d19cc3D8D504400F26Ccb6711DaB1` |
| RPC | `http://127.0.0.1:8545` |
| Image | `hyperledger/besu:26.7.1` |
| Solc | 0.8.24 |
| Deploy gas | 1298376 |
| Bytecode SHA-256 | `fece3e0d05ec63f0f71a2f2a1944f0efb0993b35a66b4de550a1aaeb30d8eec3` |

## Relevant source files and roles

| Path | Role |
|------|------|
| `app/auth/common/protocol.py` | Shared challenge–response GCS service; signature verify; RBAC |
| `app/core/crypto.py` | ECDSA P-256 / SHA-256 sign & verify; uncompressed public-key encoding |
| `app/core/canonical.py` | Canonical authentication object bytes |
| `app/auth/blockchain/adapter.py` | Blockchain identity lookup (`eth_call`) |
| `app/auth/blockchain/registry.py` | Web3 register / getRecord / revoke / audit |
| `contracts/contracts/UAVIdentityRegistry.sol` | On-chain identity registry |
| `app/auth/x509/*` | PKI baseline (cert + CRL) |
| `app/experiments/identities.py` | Local UAV key/cert population |
| `app/experiments/scenarios.py` | Attack / valid request builders |
| `app/experiments/runner.py` | Experiment runner + `register_population_on_chain` |
| `scripts/run_chapter5_matrix.py` | 53-step matrix |
| `scripts/export_chapter5_bundle.py` | Export package builder |
| `docs/METRICS.md` | Metric definitions |

## Existing result package (READ-ONLY baseline)

| Path | Notes |
|------|-------|
| `results/runs/` | 53 descriptive matrix run directories (gitignored; preserved on disk) |
| `results/chapter5_export/` | First export bundle used for dissertation drafting |
| `results/chapter5_matrix.log` | Matrix runner log |
| `results/chapter5_matrix_progress.json` | Last progress snapshot (may be incomplete across resumes) |

**Do not overwrite, delete, rename, or merge these directories.**

## Failing run IDs used for diagnosis (representative)

Security battery (blockchain):

- `n10-identities_c1-conc_mech-blockchain-1backend_security-battery_r30_audit-off_20260820T020051Z`
  - `valid_active`: 30/30 `INVALID_SIGNATURE` (false rejections)
  - `unauthorised_operation`: 30/30 `INVALID_SIGNATURE` (expected `UNAUTHORISED_OPERATION`)
  - `revoked_uav`: 30/30 `REVOKED_IDENTITY` (correct; status checked before signature)
  - `impersonation_wrong_key`: 30/30 `INVALID_SIGNATURE` (correct)

Scale cells (all 25 blockchain `valid_active` audit-off): every measured request false-rejected (`750/750`). Example:

- `n10-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020501Z`
- `n500-identities_c50-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T022747Z`

Audit-enabled:

- `n10-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-on_20260820T022802Z` (also `INVALID_SIGNATURE`)

X.509 contrast (working):

- All 25 X.509 `valid_active` scale cells: `750/750` accepted

## Offline key consistency (local only, pre-Besu)

Checked first 20 identities including `UAV-VALID` / `UAV-LIMITED` / `UAV-REVOKED`:

- PEM private key ↔ `public_key_hex` in `identities.json`: **match**
- Signature verifies against meta public key: **true**

Therefore the defect is **not** local PEM/meta drift. Leading hypothesis for on-chain confirmation: **registry public key bytes differ from the local signing key** (stale registration after identity regeneration), because `register_population_on_chain` skips UAVs with `status != None`.

## Environment note at inventory time

Docker Desktop was not running when inventory began; Besu RPC confirmation and on-chain `getRecord` comparison are deferred to Phase 1 live diagnosis after Docker/Besu recovery.
