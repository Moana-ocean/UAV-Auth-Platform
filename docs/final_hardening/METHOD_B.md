# Method B instrumentation fix (2026-09-03)

## Code changes

1. **Warm-up**: sequential, completed before measured ThreadPoolExecutor work.
2. **Throughput window**: `measured_batch_seconds` only (excludes setup + sampler join).
3. **Worker-pool saturation**: measured reps = `max(30, concurrency)` so c=50 yields ≥50 measured attempts.
4. **Population**: `--fresh-identities` clears local store; scale matrix grows n ascending; chain re-syncs after local growth.
5. **ABBA**: jobs ordered by ascending n; `ensure_population(n)` per job (not max_n).

## CPU / RSS (paper wording — no sampler rewrite in this pass)

`ResourceSampler` still uses `psutil.Process()` (Python runner). Paper must say **experiment-runner process**, not whole-host.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m scripts.besu_network up
.\.venv\Scripts\python.exe -m app.cli deploy-contract
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix --only-phases scale-valid --fresh-identities --output-root results/method_b_scale_20260903
.\.venv\Scripts\python.exe -m app.cli deploy-contract
.\.venv\Scripts\python.exe -m scripts.run_abba_batches --fresh-identities --output-root results/method_b_scale_20260903
.\.venv\Scripts\python.exe -m scripts.export_chapter5_bundle --runs-root results/method_b_scale_20260903/runs --export-dir results/method_b_scale_20260903/export
```

Security battery + audit numbers remain from `dissertation_final_20260831T015600Z` (instrumentation does not change adversarial outcomes).
