# Regression test report

## Unit tests

```text
pytest tests/test_crypto_registration.py tests/test_protocol.py -q
...............  (15 passed)
```

Coverage includes: public-key round trip, canonical vector file, wrong-key reject, stale-key reproducer + sync accept, tamper cases, unauthorised reason code.

## Smoke gate (live Besu, post `updateKey` sync)

| Scenario | Result |
|----------|--------|
| valid_active | 30/30 ACCEPTED |
| impersonation_wrong_key | 30/30 INVALID_SIGNATURE |
| replay | 30/30 REPLAY_DETECTED |
| modified_nonce / modified_uav_id / modified_operation | 30/30 INVALID_SIGNATURE |
| unauthorised_operation | 30/30 UNAUTHORISED_OPERATION |
| revoked_uav | 30/30 REVOKED_IDENTITY |

## Integration

`tests/test_key_sync_integration.py` and `tests/test_blockchain_integration.py` exercised against Besu. One pre-existing test (`test_unauthorised_register_rejected`) failed under current web3/Besu error typing and is unrelated to the signature/key-sync fix; key-sync and auth/replay paths passed in the smoke gate above.

## Gate decision

**PASSED** — formal 53-step matrix authorised to start.
