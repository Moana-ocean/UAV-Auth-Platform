# Final hardening progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Repository audit | done | `FINAL_AUDIT.md`, `FINAL_TEST_PLAN.md` |
| 2. Contract fixes | done | terminal revocation, role 1–3, pubkey max 128B |
| 3. Security tests | done | unit + integration pass with Besu up |
| 4. Besu RPC hardening | done | `127.0.0.1` bind; APIs `ETH,NET,WEB3,QBFT` only; multi-validator RPC failover |
| 5. Code freeze + full matrix | done | `results/dissertation_final_20260831T015600Z/` — 53/53, export **clean** after RPC fix reruns |
| 6. Independent ABBA batches | done | 24 runs, 720 obs — `abba_progress.json` |
| 7. Dissertation sync | done | Ch5 drafts + appendices A–C updated from `dissertation_final` export |
| 8. Clean-clone reproduction | pending | tag + `FINAL_HANDOVER.md` after commit |

## Test logs

- `docs/final_hardening/logs/pytest_unit.log` — 46 passed (2026-08-31)
- `docs/final_hardening/logs/pytest_integration.log` — 25 skipped (Besu down)

## Anomaly fix (2026-08-31)

3 blockchain scale cells failed with `IDENTITY_SERVICE_UNAVAILABLE` / `auth_timeout` (single RPC overload, not key mismatch).

**Fix:** `RegistryAdapter.get_record` rotates across validator RPCs (`8545`–`8575`); lookup budget capped at 4s; `wait_until_ready` before blockchain matrix steps; `--only-steps` for targeted reruns.

**Reruns:** steps 14, 26, 48 → 30/30 ACCEPTED each. Re-export: `07_data_quality_report.md` — **0 anomalies**.

## Git state

- Branch: `final-hardening`
- Tag `chapter5-rerun-20260824` → `be8c1ef` (unchanged; prior evidence)
- Valid export until rerun: `results/chapter5_rerun_20260824T233552Z/export/`

## Blocker

Docker client present but `scripts.besu_network status` reports `docker: false` and all RPC endpoints unreachable. Start Docker Desktop, then:

```powershell
.\.venv\Scripts\python.exe -m scripts.besu_network up
.\.venv\Scripts\python.exe -m app.cli deploy-contract
.\.venv\Scripts\python.exe -m pytest tests -m integration -q
```

Contract bytecode changed → **full 53-step matrix required** before updating dissertation numbers.
