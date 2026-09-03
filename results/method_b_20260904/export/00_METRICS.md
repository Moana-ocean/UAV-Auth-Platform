# Metric definitions

These names are used in code, the Streamlit UI, CSV/JSON exports and dissertation reporting. All latency fields are measured with `time.perf_counter_ns()` on the GCS service path. UI render time is never used as protocol latency.

## Per-request observation fields

| Name | Meaning |
|------|---------|
| `run_id` | Unique identifier of the experimental run |
| `observation_id` | Unique identifier of one authentication attempt |
| `utc_timestamp` | UTC time the GCS began handling the request (`datetime.isoformat`) |
| `mechanism` | `x509` or `blockchain` |
| `scenario` | Stable scenario id (see below) |
| `repetition` | 0-based measured repetition index (warm-ups use negative or flagged rows) |
| `concurrency_level` | Number of concurrent workers configured for this batch |
| `uav_id` | Pseudonymous UAV identifier |
| `expected_outcome` | Reason code the scenario should produce |
| `observed_outcome` | Reason code actually returned |
| `expectation_met` | `true` iff expected and observed reason codes match |
| `decision_latency_ns` | GCS receipt of a complete request → accept/reject decision |
| `decision_latency_ms` | `decision_latency_ns / 1e6` |
| `challenge_generation_ns` | Time to create nonce + session record |
| `identity_lookup_ns` | Certificate/CRL load **or** registry retrieval only |
| `certificate_validation_ns` | X.509 path, expiry, key usage, CRL (0 on blockchain path) |
| `contract_call_ns` | Read-only `eth_call` duration (0 on X.509 path) |
| `signature_verification_ns` | Application-level ECDSA verify |
| `authorisation_check_ns` | Role vs requested operation |
| `audit_submission_ns` | Optional audit tx submit (blockchain only) |
| `audit_confirmation_ns` | Submit → configured confirmation (blockchain only) |
| `tx_hash` | Audit or setup transaction hash, else empty |
| `block_number` | Receipt block number, else empty |
| `gas_used` | EVM gas from receipt; not a monetary cost |
| `timeout_error_class` | `none`, `auth_timeout`, `rpc_timeout`, `rpc_unavailable`, `internal` |
| `worker_id` | Thread/worker name |
| `payload_size` | Configured application payload size in bytes |
| `warmup` | `true` if excluded from default summaries |
| `request_bytes` | Size of the signed application object |
| `response_bytes` | Size of the decision payload |
| `notes` | Optional machine note (never private keys) |

## Latency boundaries

- **`decision_latency`**: from receipt of a complete authentication request by the GCS service layer until an accept/reject decision is produced. Does **not** wait for blockchain audit confirmation.
- **`identity_lookup_latency`**: only the certificate/revocation retrieval or blockchain registry retrieval stage.
- **`audit_confirmation_latency`**: from audit transaction submission until the configured confirmation condition is met.
- **`completed_throughput`**: completed requests (including expected rejections) divided by the measured batch wall interval.
- **`offered_load`**: requests scheduled per second, recorded separately from completed throughput.

## Run-level summaries

Computed from raw observations with **warm-ups excluded by default**.

| Name | Method |
|------|--------|
| `n_observations` | Count after the stated filter |
| `n_warmup_excluded` | Warm-up rows omitted |
| `n_accepted` | `observed_outcome == ACCEPTED` |
| `n_expected_rejection` | Not accepted, and `expectation_met` |
| `n_unexpected` | `expectation_met` is false |
| `n_timeout` | `timeout_error_class` in `{auth_timeout, rpc_timeout}` |
| `n_internal_error` | `INTERNAL_ERROR` or `internal` |
| `failure_rate` | `(n_timeout + n_internal_error) / n_submitted × 100` — expected security rejections are **not** failures |
| `attack_rejection_rate` | malicious requests rejected / malicious requests submitted × 100 |
| `false_acceptances` | adversarial request with `observed_outcome == ACCEPTED` |
| `false_rejections` | valid scenario with non-`ACCEPTED` outcome |
| `mean, median, std, min, max, p95, p99` | of `decision_latency_ms` |
| `ci95_low`, `ci95_high` | Percentile bootstrap, `scipy.stats.bootstrap`, 10_000 resamples, `random_state` from the run seed, method `percentile`. If `n < 2`, CI is left empty. |
| `latency_filter` | Documented on every summary row, e.g. `warmup==false; include all finished decisions` |

A second summary block with `latency_filter=warmup==false AND observed_outcome==ACCEPTED` is also written. Failures are never dropped from the first block.

Gas is reported in **execution units**. No ETH/fiat conversion is performed unless a run explicitly supplies both a gas price and a conversion source (this platform does not).

## Scenario identifiers

| Id | Expected reason (typical) |
|----|---------------------------|
| `valid_active` | `ACCEPTED` |
| `unknown_uav` | `UNKNOWN_IDENTITY` |
| `impersonation_wrong_key` | `INVALID_SIGNATURE` |
| `replay` | `REPLAY_DETECTED` |
| `modified_nonce` | `INVALID_SIGNATURE` |
| `modified_uav_id` | `INVALID_SIGNATURE` |
| `modified_operation` | `INVALID_SIGNATURE` |
| `expired_challenge` | `EXPIRED_CHALLENGE` |
| `revoked_uav` | `REVOKED_IDENTITY` |
| `unauthorised_operation` | `UNAUTHORISED_OPERATION` |
| `malformed` | `MALFORMED_REQUEST` |
| `expired_certificate` | `CERTIFICATE_EXPIRED` (X.509) |
| `untrusted_issuer` | `UNTRUSTED_ISSUER` (X.509) |
| `rpc_unavailable` | `IDENTITY_SERVICE_UNAVAILABLE` (blockchain) |
| `concurrent_valid` | `ACCEPTED` |
| `concurrent_mixed` | mixed; per-request expected codes |

An expected rejection is a **passed security test** when `expectation_met` is true.
