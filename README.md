# UAV-to-GCS authentication evaluation platform

Local experimental platform for an MSc Information Security dissertation (Chapter 5). It compares:

1. an **X.509 PKI** baseline (certificate + CRL); and
2. a **permissioned Ethereum-compatible identity registry** on Hyperledger Besu (QBFT, four local validators).

Both paths share one challenge–response protocol, ECDSA P-256 / SHA-256 application signatures, and the same UAV population. Ethereum secp256k1 keys are **only** validator/RA transaction accounts.

This is a **research/testing** deployment on one host. It is not production, not geographically decentralised, and not a Byzantine fault-tolerance experiment. See `LIMITATIONS.md`.

**Never treat UI charts as protocol latency.** Timing uses `time.perf_counter_ns()` in the GCS service. No results in this repository are fabricated; empty `results/runs/` is expected until you execute a run.

## 1. Prerequisites (Windows + Docker Desktop + WSL2)

- Windows 10/11 with Docker Desktop and the WSL2 backend enabled
- Python 3.11+ (this host was verified with 3.13)
- Git (optional)
- At least 8 GB RAM free for four Besu containers

Confirm:

```powershell
python --version
docker version
docker compose version
```

## 2. Environment creation

PowerShell, from this directory:

```powershell
python -m venv .venv
# Do NOT double-click Activate.ps1 in Explorer — it will flash and close.
# Either run this inside an already-open terminal:
.\.venv\Scripts\Activate.ps1
# Or skip activation and call the venv Python directly (recommended on Windows):
.\.venv\Scripts\python.exe --version
```

WSL2:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Dependency installation

```powershell
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m app.cli setup
```

Equivalent: `.\scripts\uav.ps1 setup` or `make setup`.

## 4. Besu network start and health

First start generates validator keys and genesis into `besu/network/` (gitignored, non-production).

```powershell
python -m scripts.besu_network up
python -m scripts.besu_network wait
python -m scripts.besu_network status
```

Healthy sign: `validator1.reachable` is true and `latest_block` increases. RPC: `http://127.0.0.1:8545` (nodes 2–4 on 8555/8565/8575).

## 5. Contract compilation and deployment

```powershell
python -m app.cli deploy-contract
```

Writes `var/deployment.json` with address, tx hash, chain ID, block number, bytecode hash and RA address.

## 6. PKI and UAV population

```powershell
python -m app.cli init-identities --count 10
```

Creates local certificates, CRL, software UAV keys (labelled non-production) and registers the same identities on-chain when a deployment exists.

## 7. Streamlit UI

```powershell
python -m streamlit run streamlit_app.py
```

or `python -m app.cli ui` / `.\scripts\uav.ps1 ui`.

Tabs: environment, identities, configuration, live execution, results, export.

## 8. CLI smoke test

```powershell
python -m app.cli smoke-test
```

Always runs X.509 scenarios. Runs blockchain scenarios only if Besu and the contract are available.

## 9. Full test suite

```powershell
python -m pytest tests -q
python -m ruff check app tests scripts
python -m black --check app tests scripts streamlit_app.py
```

Integration tests in `tests/test_blockchain_integration.py` skip automatically if Besu is down.

## 10. Results export

Each run writes `results/runs/<run_id>/`:

- `config.json`, `environment.json`, `observations.csv`, `summary.csv`, `events.jsonl`, `system_metrics.csv`, `blockchain_receipts.jsonl`, `charts/`, `checksums.sha256`

Download from UI tab F or zip with the Export button. Metric names: `docs/METRICS.md`.

## 11. Safe shutdown

```powershell
python -m scripts.besu_network down
```

## 12. Safe local reset

Deletes only project experiment data (not paths outside this repo):

```powershell
python -m app.cli reset-local --confirm
python -m app.cli reset-local --confirm --full
```

`--full` also removes Besu volumes/keys and generated PKI.

## 13. Troubleshooting

| Symptom | Check |
|--------|--------|
| `Besu RPC is not reachable` | Docker Desktop running; `besu-up`; wait until block 1 |
| `RA key missing` | `python -m scripts.besu_network generate` then `up` |
| solc download fails | Allow network for `py-solc-x` to fetch solc 0.8.24 once |
| Port 8545 in use | Stop another Ethereum client; compose maps 8545 |
| Permission error on key files | Compose runs Besu as root for local bind-mounts |
| Large-run ConfigError | Tick “Confirm large run” or pass `--confirm-large-run` |
| Charts empty | No completed run yet — do not invent numbers |
| `chain_id_match` false | Reset network; expected chain ID is 20245 |
| `Illegal static enode` | Enodes must use the compose IPs `172.28.45.11–14`, not DNS names |
| `Gas price below configured minimum` | The client now uses `eth_gasPrice`; recreate nodes if RPC still rejects |
| Blockchain smoke all `UNKNOWN_IDENTITY` | Run `init-identities` (or `smoke-test` after this fix) so UAVs exist on-chain |

## Convenience commands

| Task | PowerShell | Make |
|------|------------|------|
| setup | `.\scripts\uav.ps1 setup` | `make setup` |
| besu-up | `.\scripts\uav.ps1 besu-up` | `make besu-up` |
| besu-status | `.\scripts\uav.ps1 besu-status` | `make besu-status` |
| deploy-contract | `.\scripts\uav.ps1 deploy-contract` | `make deploy-contract` |
| init-identities | `.\scripts\uav.ps1 init-identities` | `make init-identities` |
| ui | `.\scripts\uav.ps1 ui` | `make ui` |
| smoke-test | `.\scripts\uav.ps1 smoke-test` | `make smoke-test` |
| test | `.\scripts\uav.ps1 test` | `make test` |
| lint | `.\scripts\uav.ps1 lint` | `make lint` |
| besu-down | `.\scripts\uav.ps1 besu-down` | `make besu-down` |
| reset-local | `.\scripts\uav.ps1 reset-local` | `make reset-local` |

## Fair comparison (do not break this)

- Same canonical authentication object, nonce rules, P-256 signatures, payload size and UAV IDs.
- X.509 decision path: parse cert, chain, expiry, CRL, signature, role store.
- Blockchain decision path: `eth_call` `getRecord`, signature, on-chain role.
- Optional audit transactions are **not** included in `decision_latency`.
