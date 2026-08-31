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

## Git identifiers

- Branch: `final-hardening`
- Commit: `a920a35`
- Tag: `dissertation-final-20260831`

## Dissertation LaTeX updated

- `abstract.tex`, `chapter6_discussion.tex`, `chapter7_conclusion.tex`
- `docs/chapter5_drafts/batch*.tex` — numbers from final export
- `docs/appendices/appendix_{a,b,c}.tex` — new contract address, paths, checksums
- `main.tex` + `references.bib` for local compile

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m scripts.validate_thesis_tex
.\scripts\compile_thesis.ps1   # requires MiKTeX/TeX Live
.\.venv\Scripts\python.exe -m scripts.besu_network up
.\.venv\Scripts\python.exe -m app.cli deploy-contract
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix --output-root results/dissertation_final_20260831T015600Z
.\.venv\Scripts\python.exe -m scripts.run_abba_batches --output-root results/dissertation_final_20260831T015600Z
.\.venv\Scripts\python.exe -m scripts.export_chapter5_bundle --runs-root results/dissertation_final_20260831T015600Z/runs --export-dir results/dissertation_final_20260831T015600Z/export
```
