# Change impact assessment

## Repair summary

| Change | Scope |
|--------|-------|
| `register_population_on_chain` | Blockchain setup: `updateKey` / `updateRole` when Active/Suspended key or role differs from local meta |
| `IdentityPopulation.load_key` | Derive `public_key_bytes` from PEM (shared load helper used by both mechanisms' scenarios) |
| `scripts/run_chapter5_matrix.py` | Add `--output-root` so corrective runs do not mix with baseline |
| New tests | `tests/test_crypto_registration.py`, `tests/test_key_sync_integration.py` |

## Shared vs blockchain-only

- **Blockchain-only behavioural fix:** on-chain key synchronisation.
- **Shared code touched:** `load_key` (read path for scenario builders) and matrix output routing.
- **Not changed:** canonicalisation, signature algorithms, X.509 validator, metric definitions, scenario expected outcomes, concurrency/identity levels, warm-up rules.

## Recommendation

Because shared setup/load and runner output paths changed, and to keep matched X.509/blockchain observations on one code revision and measurement window, **re-run the full 53-step matrix**. Do not merge old X.509 latency/throughput cells with new blockchain cells in Chapter 5 tables.
