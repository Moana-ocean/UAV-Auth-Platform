# Final hardening progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Repository audit | done | `FINAL_AUDIT.md`, `FINAL_TEST_PLAN.md` |
| 2. Contract fixes | done | terminal revocation, role 1–3, pubkey max 128B |
| 3. Security tests | in_progress | **46 unit passed**; **25 integration skipped** (Besu unreachable) |
| 4. Besu RPC hardening | done | `127.0.0.1` bind; APIs `ETH,NET,WEB3,QBFT` only |
| 5. Code freeze + full matrix | blocked | requires Besu up + contract redeploy |
| 6. Independent ABBA batches | blocked | after code freeze |
| 7. Dissertation sync | blocked | after new export |
| 8. Clean-clone reproduction | blocked | after final tag |

## Test logs

- `docs/final_hardening/logs/pytest_unit.log` — 46 passed (2026-08-31)
- `docs/final_hardening/logs/pytest_integration.log` — 25 skipped (Besu down)

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
