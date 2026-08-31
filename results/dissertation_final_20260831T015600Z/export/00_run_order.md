# Chapter 5 experiment order (Chapter 3 Table: Planned experimental factors)

All result folders are under `results/runs/` and are named:

`n{identities}-identities_c{concurrency}-conc_mech-{x509|blockchain}-{1|2}backend_{scenario}_r{reps}_audit-{on|off}_{timestamp}`

Execute:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix
```

Dry-run (print order only):

```powershell
.\.venv\Scripts\python.exe -m scripts.run_chapter5_matrix --dry-run
```

| Step | Phase | Identities | Concurrency | Mechanism | Scenarios | Reps | Audit tx |
|-----:|-------|-----------:|------------:|-----------|-----------|-----:|----------|
| 1 | security | 10 | 1 | x509 | security battery | 30 | off |
| 2 | security | 10 | 1 | blockchain | security battery | 30 | off |
| 3–12 | scale-valid | 10 | 1,5,10,25,50 | x509 then blockchain | valid_active | 30 | off |
| 13–22 | scale-valid | 50 | 1,5,10,25,50 | x509 then blockchain | valid_active | 30 | off |
| 23–32 | scale-valid | 100 | 1,5,10,25,50 | x509 then blockchain | valid_active | 30 | off |
| 33–42 | scale-valid | 250 | 1,5,10,25,50 | x509 then blockchain | valid_active | 30 | off |
| 43–52 | scale-valid | 500 | 1,5,10,25,50 | x509 then blockchain | valid_active | 30 | off |
| 53 | audit-commit | 10 | 1 | blockchain | valid_active | 30 | on |

Security battery (Chapter 3 request types): valid, unknown, wrong-key spoof, replay, three tamper cases, expired challenge, revoked, unauthorised, malformed; X.509-only expired/untrusted cert; blockchain-only RPC unavailable.

Warm-up: 2 (stored, excluded from default summaries).
