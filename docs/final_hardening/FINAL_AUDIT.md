# Final hardening audit

**Date:** 2026-08-31  
**Branch:** `final-hardening`  
**Auditor:** automated + source inspection  

## 1. Git and evidence chain (verified)

| Item | Verified value |
|------|----------------|
| Current branch | `final-hardening` (created from `main` @ `4c9e25f`) |
| Latest `main` commit | `4c9e25f` — LaTeX appendices A–C |
| Tag `chapter5-rerun-20260824` | points to `be8c1ef6b39cb6aebcd937e2e6d98b4fe54ac564` ✓ |
| Remote | `git@github.com:Moana-ocean/UAV-Auth-Platform.git` |
| Valid Chapter 5 export | `results/chapter5_rerun_20260824T233552Z/export/` (53/53 steps) |
| Superseded export | `results/chapter5_export/` — retain only for traceability |
| Dissertation baseline | `c:\Users\lenovo\Downloads\FirstDraft (9).pdf` (111 pp, dated 2026-08-24) |

**Paper vs repo:** Dissertation cites tag/commit correctly. HEAD is now `4c9e25f` (appendices only); experiments remain bound to `be8c1ef` rerun export until a new matrix completes.

## 2. Repository structure

| Area | Path | Role |
|------|------|------|
| Smart contract | `contracts/contracts/UAVIdentityRegistry.sol` | On-chain identity registry |
| Contract compile | `app/auth/blockchain/compiler.py` | py-solc-x → artifact |
| GCS protocol | `app/auth/common/protocol.py` | Shared challenge–response |
| Nonce store | `app/core/nonce.py` | In-memory single-use nonces |
| X.509 PKI | `app/auth/x509/pki.py`, `validator.py` | CA, CRL, cert validation |
| Blockchain adapter | `app/auth/blockchain/adapter.py`, `registry.py` | eth_call + txs |
| Experiment runner | `app/experiments/runner.py`, `scripts/run_chapter5_matrix.py` | 53-step matrix |
| Export | `scripts/export_chapter5_bundle.py` | Evidence package |
| Besu | `besu/docker-compose.yml`, `besu/network/genesis.json` | 4-validator QBFT |
| Tests | `tests/test_*.py` (13 files) | unit + integration |
| LaTeX | `chapter3.tex`, `chapter4_proposed_authentication_scheme.tex`, `chapter5_evaluation.tex`, `docs/appendices/` | partial dissertation in repo |
| No `.bib` in repo | — | bibliography likely only in Overleaf |

**Node.js:** not used (Python + Solidity via py-solc-x only).

## 3. Confirmed issues (source-verified)

### 3.1 Smart contract — `reinstate()` allows Revoked → Active

**File:** `contracts/contracts/UAVIdentityRegistry.sol` lines 134–142  

```solidity
function reinstate(string calldata uavId) external onlyRegistrar {
    ...
    if (rec.status == Status.None) revert UnknownIdentity();
    rec.status = Status.Active;  // no check for Revoked or already Active
```

**Impact:** Terminal revocation policy violated. Revoked identities can be reactivated.  
**Fix required:** Only allow `Suspended → Active`; revert on `Revoked` and `Active`.  
**Risk:** Low (local test network); **paper claim** on permanent revocation is incorrect until fixed.

### 3.2 Smart contract — role upper bound not enforced

**File:** `UAVIdentityRegistry.sol` — `register()` / `updateRole()` check `role == 0` only (lines 85, 118).  

**Impact:** Roles 4–255 accepted on-chain; Python RBAC (`app/core/roles.py`) treats unknown roles as empty permission set → silent `UNAUTHORISED_OPERATION` at auth time, not at registration.  
**Fix required:** Reject `role > 3` (match `ROLE_OBSERVER` in `app/core/constants.py`).  
**Risk:** Medium for data-integrity; low for security battery (valid identities use 1–3).

### 3.3 Smart contract — no public-key length cap

**File:** `register()` / `updateKey()` — only `publicKey.length == 0` checked.  

**Impact:** Oversized keys can be stored; increases gas/storage. Full curve parsing is correctly delegated to RA/GCS (`public_key_from_uncompressed`).  
**Fix:** Add `MAX_PUBLIC_KEY_BYTES` (e.g. 128) as reasonable bound; document RA validates P-256 uncompressed (65 bytes) at application boundary.

### 3.4 Smart contract — duplicate public-key binding not enforced

**Design:** No uniqueness mapping `publicKeyHash → uavId`. Two identities may share a key.  
**Action:** Record as **documented limitation**, not a bug, unless policy requires uniqueness.

### 3.5 Besu RPC attack surface

**File:** `besu/docker-compose.yml` lines 25–28, 41–42  

- `--rpc-http-api=ETH,NET,WEB3,QBFT,ADMIN,TXPOOL,DEBUG`
- `--host-allowlist=*`, `--rpc-http-cors-origins=all`
- `ports: "8545:8545"` (all interfaces)

**Impact:** ADMIN/DEBUG/TXPOOL exposed on LAN; not needed for GCS `eth_call` + `eth_sendRawTransaction`.  
**Fix required:** Restrict APIs; bind `127.0.0.1:8545:8545`; tighten CORS/allowlist for research host.

### 3.6 Besu permissioning not enabled

No `--permissions-nodes-config-file-enabled` or account permissioning in compose.  

**Paper must say:** private QBFT network with fixed validator set; **node/account allowlisting not separately enabled or evaluated**.

### 3.7 Single RPC endpoint — no application failover

**File:** `app/core/constants.py` — `DEFAULT_RPC_URL` only.  

Fallback URLs exist on validators 2–4 (8555/8565/8575) but GCS does not rotate.  
**Fix:** Minimal endpoint list in `client.py`; test primary-down fallback.

### 3.8 Nonce store — in-memory, not persistent

**File:** `app/core/nonce.py` — `dict` + `threading.Lock`.  

- **Concurrency:** `consume()` is atomic under lock; check-and-mark-consumed is correct for replay.  
- **Restart:** All sessions lost; old nonces could be reissued with new session IDs (not replay of same session).  
**Action:** Document limitation in Ch4/Ch6; optional persistence out of scope unless required.

### 3.9 Nonce consumed before signature verification

**File:** `app/auth/common/protocol.py` line 130 — consume before lookup/verify.  

**By design:** Fail-closed replay protection; wrong signature after valid nonce consumes challenge (`test_nonce_mismatch_still_consumes`). Document in dissertation.

### 3.10 X.509 — CRL fail-closed

**File:** `app/auth/x509/validator.py` — `pki.load_crl()` required; no stale-CRL/nextUpdate check.  

**Gap:** Missing tests for stale CRL, wrong CRL signer, not-yet-valid cert.  
**Policy:** Fail-closed on missing CRL at validation time.

### 3.11 Missing contract unit/integration tests

Only `tests/test_contract_compile.py` (compile smoke). No lifecycle/RBAC matrix tests until added.

### 3.12 Integration test flake

`test_unauthorised_register_rejected` historically flaky with web3 error typing (noted in prior session).

## 4. Suspected but not yet confirmed

| Item | Notes |
|------|-------|
| Contract redeploy after fix changes address | Requires redeploy + update `var/deployment.json`; invalidates old on-chain state |
| Full 53-step rerun duration | Hours on single host; may block Day 5 |
| LaTeX master not in repo | Cannot compile full PDF locally without Overleaf export |
| `admin` retains registrar after `setRegistrar(admin, false)` | Admin bypasses `onlyRegistrar` via `msg.sender != admin` check |

## 5. Existing test coverage

| File | Coverage |
|------|----------|
| `test_nonce.py` | single-thread consume, expiry, mismatch |
| `test_x509.py` | valid, expired, revoked, untrusted, wrong key |
| `test_protocol.py` | GCS paths |
| `test_scenarios.py` | scenario wiring |
| `test_crypto_registration.py` | key round-trip, stale key |
| `test_key_sync_integration.py` | Besu key sync |
| `test_blockchain_integration.py` | register, auth, replay, revoke |
| `test_contract_compile.py` | compile only |
| `test_runner.py`, `test_export.py`, `test_config.py`, `test_ui_services.py` | platform |

**Missing:** contract lifecycle matrix, concurrent replay (2/10/50), role bounds, X.509 CRL edge cases, RPC namespace tests, ABBA batch runner, validator liveness.

## 6. Paper vs implementation consistency

| Claim (FirstDraft 9) | Implementation | Match? |
|----------------------|----------------|--------|
| 53-step matrix, 30+2 warm-ups | `scripts/run_chapter5_matrix.py` | ✓ |
| 750/750 normal auth accepted | rerun export quality report | ✓ (for `be8c1ef` run) |
| 360/330 adversarial rejections | `03_security_by_scenario.csv` | ✓ |
| QBFT, 4 validators, chain 20245 | genesis + compose | ✓ |
| Permanent revocation | `reinstate()` bug | **✗ until fixed** |
| Permissioned blockchain | validators fixed; no account permissioning | **partial — wording** |
| Ganache vs Besu | README/LIMITATIONS | ✓ (Ganache not in Ch5 path) |
| Git tag `chapter5-rerun-20260824` @ `be8c1ef` | verified | ✓ |
| Nonce replay protection | atomic consume | ✓ (needs concurrent test evidence) |

## 7. Modification risk assessment

| Change | Breaks prior results? | Requires full rerun? |
|--------|----------------------|----------------------|
| Fix `reinstate` + role bounds | Yes (contract bytecode) | **Yes** |
| Redeploy contract | Yes | **Yes** |
| Besu RPC hardening | No (operational) | No (unless matrix re-run for fairness) |
| RPC fallback client | No | Optional batch only |
| Nonce persistence | Behaviour change | Yes if implemented |
| New tests only | No | No |

## 8. Recommended execution order

1. Fix contract + redeploy locally  
2. Add and run tests (unit + integration)  
3. Harden Besu compose  
4. Freeze code → full 53-step matrix → `results/dissertation_final_<ts>/`  
5. ABBA independent batches  
6. Regenerate export → update LaTeX  
7. Tag final commit → update Appendix D  
