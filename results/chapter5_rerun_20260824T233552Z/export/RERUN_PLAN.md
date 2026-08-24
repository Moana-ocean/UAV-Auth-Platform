# Corrective re-run plan (Chapter 5)

## Declared before formal execution

**Decision:** Preferred dissertation-quality re-run — **complete 53-step matrix** for both X.509 and blockchain after the repair.

## Why not reuse old X.509 results

Change-impact assessment (`CHANGE_IMPACT_ASSESSMENT.md`):

- Shared path changed: `register_population_on_chain` (setup), `IdentityPopulation.load_key`, matrix `--output-root`.
- Although X.509 authentication logic was not altered, matched comparison on the same code revision, dependency set, machine state, and measurement period is required for Chapter 5.
- Therefore old X.509 cells are retained only as **baseline evidence of the failed iteration**, not as the corrected comparison set.

## Invalidated by the defect (must re-run)

- Blockchain security battery
- All 25 blockchain `valid_active` audit-off scale cells
- Blockchain audit-enabled run

## Formal scope (this re-run)

| Steps | Content |
|------:|---------|
| 1–2 | Security battery (x509, blockchain) |
| 3–52 | Scale `valid_active` for n∈{10,50,100,250,500} × c∈{1,5,10,25,50} × {x509,blockchain} |
| 53 | Blockchain audit-on |

Parameters unchanged from Chapter 3: 30 measured reps, 2 warm-ups, Besu 26.7.1 QBFT chain ID 20245.

## Output isolation

- **Baseline (read-only):** `results/runs/`, `results/chapter5_export/`
- **Corrected root:** `results/chapter5_rerun_<UTC_TIMESTAMP>/`
  - `runs/` — new timestamped run IDs
  - `chapter5_matrix_progress.json`
  - `export/` — new evidence package

## Pre-run gates (passed)

| Gate | Result |
|------|--------|
| Blockchain `valid_active` 30/30 accepted | PASS |
| Wrong key / replay / tamper / unauthorised / revoked | PASS (30/30 each) |
| Unit + registration regression tests | PASS |
| Besu healthy, chain ID 20245 | PASS |
| Special identity on-chain keys synced via `updateKey` | PASS |

## Commands

```powershell
# Sync any remaining Active identities (idempotent)
.\.venv\Scripts\python.exe -c "from app.experiments.identities import IdentityPopulation; from app.experiments.runner import data_dir, register_population_on_chain; print(len(register_population_on_chain(IdentityPopulation(data_dir()))))"

# Formal matrix into a new root
$ts = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix --output-root "results/chapter5_rerun_$ts"
```
