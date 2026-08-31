# Final test plan

## A. Smart contract (`UAVIdentityRegistry.sol`)

| ID | Test | Type | Pass criteria |
|----|------|------|---------------|
| C-01 | `None → Active` via register | integration | status=Active, event emitted |
| C-02 | `Active → Suspended` | integration | status=Suspended |
| C-03 | `Suspended → Active` via reinstate | integration | status=Active |
| C-04 | `Active → Revoked` | integration | status=Revoked, terminal |
| C-05 | `Suspended → Revoked` | integration | status=Revoked |
| C-06 | `Revoked → reinstate` | integration | **reverts** AlreadyRevoked |
| C-07 | `Revoked → updateKey` | integration | **reverts** AlreadyRevoked |
| C-08 | `Revoked → updateRole` | integration | **reverts** AlreadyRevoked |
| C-09 | `Revoked → register` | integration | **reverts** AlreadyRevoked |
| C-10 | Role 0,4,255 on register | integration | **reverts** InvalidInput |
| C-11 | Role 1,2,3 on register | integration | accepted |
| C-12 | Empty public key | integration | **reverts** InvalidInput |
| C-13 | Non-registrar register | integration | **reverts** NotRegistrar |
| C-14 | Admin transfer zero address | integration | **reverts** InvalidInput |
| C-15 | `recordAuthAudit` does not change status | integration | status unchanged |
| C-16 | `publicKeyHash == sha256(publicKey)` | integration | hash match after register/updateKey |

Framework: `pytest` + Besu integration (`tests/test_contract_lifecycle.py`). Skipped when Besu unavailable.

## B. Nonce / replay (`app/core/nonce.py`, `protocol.py`)

| ID | Test | Concurrency | Pass criteria |
|----|------|-------------|---------------|
| N-01 | Single consume | 1 | OK then REPLAY_DETECTED |
| N-02 | Concurrent identical request | 2, 10, 50 | exactly 1 ACCEPTED, rest REPLAY_DETECTED |
| N-03 | Expiry boundary | 1 | EXPIRED_CHALLENGE at/after expiry |
| N-04 | Unknown session | 1 | MALFORMED_REQUEST |
| N-05 | Wrong nonce | 1 | INVALID_SIGNATURE then REPLAY_DETECTED |
| N-06 | GCS restart | 1 | document: in-memory store cleared (limitation) |

Framework: `tests/test_nonce.py`, `tests/test_concurrent_replay.py`

## C. X.509 (`app/auth/x509/validator.py`)

| ID | Test | Pass criteria |
|----|------|---------------|
| X-01 | Valid chain | ACCEPTED |
| X-02 | Expired cert | CERTIFICATE_EXPIRED |
| X-03 | Not-yet-valid cert | CERTIFICATE_EXPIRED |
| X-04 | Revoked on CRL | REVOKED_IDENTITY |
| X-05 | Untrusted issuer | UNTRUSTED_ISSUER |
| X-06 | CN mismatch | UNKNOWN_IDENTITY |
| X-07 | Missing keyUsage | MALFORMED_REQUEST |
| X-08 | Wrong signature key | INVALID_SIGNATURE |
| X-09 | Missing certificate | handled at adapter layer |

CRL policy: **fail-closed** — missing CRL file raises at load; revoked serials rejected.

## D. Besu / RPC

| ID | Test | Pass criteria |
|----|------|---------------|
| B-01 | RPC bound to 127.0.0.1 | docker-compose ports |
| B-02 | RPC APIs limited | ETH,NET,WEB3,QBFT only on validators |
| B-03 | Fallback endpoint list | secondary URLs 8555/8565/8575 tried |
| B-04 | ADMIN method unavailable from app | `admin_nodeInfo` fails or not exposed |
| B-05 | Validator stop 1/4 | blocks continue (manual/integration) |
| B-06 | Validator stop 2/4 | tx confirmation fails or stalls (manual) |

Permissioning: **not enabled** — paper must state "private QBFT with permissioned validator set; node/account allowlisting not separately enabled".

## E. Experiments (post code freeze)

| ID | Workload | Design |
|----|----------|--------|
| E-01 | Full 53-step matrix | same as Chapter 5, new timestamped root |
| E-02 | Independent ABBA batches | (10,c=1), (500,c=25), (500,c=50) × 2 mech × 4 batches × 30 = 720 obs |

Output: `results/dissertation_final_<UTC>/` with manifest, checksums, quality report.

## F. Dissertation QA

- Compile LaTeX twice; zero `??`, `[?]`, undefined refs
- All Ch5 numbers from new export scripts only
- Abstract updated last
- Git commit/tag matches paper Appendix D
