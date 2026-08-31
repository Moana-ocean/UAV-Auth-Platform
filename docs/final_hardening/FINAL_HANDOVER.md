# Final handover (2026-08-31)

## Evidence root

`results/dissertation_final_20260831T015600Z/`

| Artifact | Status |
|----------|--------|
| 53-step matrix | 53/53 complete |
| Export bundle | `export/` — **0 anomalies** |
| ABBA batches | `abba_runs/` — 24 runs, 720 observations |
| Quality report | `export/07_data_quality_report.md` |

## Key results (final export)

- Normal auth: X.509 **750/750** accepted; blockchain **750/750** accepted
- Security battery: **0** false acceptances (both mechanisms)
- Blockchain vs X.509 at $c=1$, $n=500$: **1.60 ms** vs **18.78 ms** mean latency
- Throughput at $n=500$, $c=50$: **59.65** vs **29.16 rps**

## Code changes (branch `final-hardening`)

- Contract: terminal revocation, role bounds 1–3, pubkey max 128 B
- Besu RPC: localhost bind, reduced API surface, 4-endpoint failover
- Scripts: `run_chapter5_matrix --only-steps`, `run_abba_batches`

## Dissertation LaTeX updated

- `docs/chapter5_drafts/batch*.tex` — numbers from final export
- `docs/appendices/appendix_{a,b,c}.tex` — new contract address, paths, checksums

## Remaining before submission

1. `git commit` + tag (e.g. `dissertation-final-20260831`) on `final-hardening`
2. Update Abstract and Chapters 6–7 if they cite old `be8c1ef` numbers
3. Compile full thesis PDF and verify no stale `??` references

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m scripts.besu_network up
.\.venv\Scripts\python.exe -m app.cli deploy-contract
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix --output-root results/dissertation_final_20260831T015600Z
.\.venv\Scripts\python.exe -m scripts.run_abba_batches --output-root results/dissertation_final_20260831T015600Z
.\.venv\Scripts\python.exe -m scripts.export_chapter5_bundle --runs-root results/dissertation_final_20260831T015600Z/runs --export-dir results/dissertation_final_20260831T015600Z/export
```
