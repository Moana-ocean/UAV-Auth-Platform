# Chapter 5 readiness decision

## Status: `READY_FOR_CHAPTER_5_ANALYSIS`

| Criterion | Result |
|-----------|--------|
| Mandatory smoke gate (valid + attacks) | PASS |
| Formal 53-step matrix present on disk | 53/53 |
| Manifest `present_on_disk` | 53/53 |
| X.509 valid scale acceptances | 750/750 |
| Blockchain valid scale acceptances | 750/750 |
| Blockchain security battery | 100% expectation met; 0 false acceptances |
| Export quality anomalies | **None** |
| Baseline package preserved | `results/runs/`, `results/chapter5_export/` untouched |

## Evidence package

`results/chapter5_rerun_20260824T233552Z/export/`

Use **only** this package for Chapter 5 measured tables. The earlier `results/chapter5_export/` package remains failed-iteration baseline evidence.

## Chapter 4 alignment notes (update dissertation text)

1. Application signatures: ECDSA P-256 / SHA-256 over canonical auth bytes; signature encoding is ASN.1 DER from `cryptography`.
2. Public keys on-chain: uncompressed SEC1 (`0x04 ‖ X ‖ Y`, 65 bytes), not Ethereum secp256k1 addresses.
3. Registration must keep registry pubkey synchronized with the UAV signing key (`updateKey` after local key rotation).
4. Check order at GCS: parse → freshness/nonce → identity lookup → binding → status → signature → authorisation.
5. Evaluation network: Hyperledger Besu 26.7.1 QBFT, 4 local validators, chain ID 20245 — not Ganache (Chapter 4 PoC).
6. Auth decisions use read-only `eth_call`; optional audit tx is separate (gas + confirmation latency).
7. Tests: `tests/test_crypto_registration.py`, `tests/test_key_sync_integration.py`, live smoke gate.

## Reproduce

```powershell
# Unit tests
.\.venv\Scripts\python.exe -m pytest tests/test_crypto_registration.py tests/test_protocol.py -q

# Formal matrix (new root)
$ts = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix --output-root "results/chapter5_rerun_$ts"

# Export
.\.venv\Scripts\python.exe -m scripts.export_chapter5_bundle --runs-root "results/chapter5_rerun_$ts/runs" --export-dir "results/chapter5_rerun_$ts/export"
```
