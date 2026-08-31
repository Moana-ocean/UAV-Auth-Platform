# Before / after validation (not a performance comparison)

Baseline package remains read-only. This file records **decision correctness** only.

## Blockchain security gate (n=10, c=1, 30 measured)

| Scenario | Baseline (old) | After key sync |
|----------|----------------|----------------|
| valid_active | 0/30 ACCEPTED (30× INVALID_SIGNATURE) | **30/30 ACCEPTED** |
| impersonation_wrong_key | 30/30 INVALID_SIGNATURE | 30/30 INVALID_SIGNATURE |
| replay | (setup often failed) | 30/30 REPLAY_DETECTED |
| modified_nonce | expected reject | 30/30 INVALID_SIGNATURE |
| modified_uav_id | expected reject | 30/30 INVALID_SIGNATURE |
| modified_operation | expected reject | 30/30 INVALID_SIGNATURE |
| unauthorised_operation | 0/30 correct reason (30× INVALID_SIGNATURE) | **30/30 UNAUTHORISED_OPERATION** |
| revoked_uav | 30/30 REVOKED_IDENTITY | 30/30 REVOKED_IDENTITY |

## Interpretation

- Old rejected-request latencies must **not** be used as successful blockchain authentication latency.
- Do not average baseline and corrected observations.
- Formal Chapter 5 numbers must come only from the corrective matrix under `results/chapter5_rerun_*/`.
