# Implementation Plan — Chapter 5 Evaluation Platform

## Repository inspection (stage 1)

Existing files before implementation:

- `chapter3.tex` — research design and metric definitions (authoritative)
- `chapter4_proposed_authentication_scheme.tex` — protocol, entities, requirements (authoritative)
- `cursor_prompt_chapter5_evaluation_platform.md` — build specification
- `chapter4_references.bib` — **not present**; citation keys are referenced by Chapter 4 only

The workspace had no prior application code, Docker network, or results store. Dissertation `.tex` files are preserved unchanged.

## Assumptions (explicit)

1. **Python version.** The host has Python 3.13. The prompt asked for 3.11/3.12. Code is written for 3.11+ and executed on 3.13. This is recorded as an environment deviation, not a protocol change.
2. **Blockchain client.** Chapter 4 discusses Ganache as a development PoC. The Chapter 5 platform uses **Hyperledger Besu 26.7.1 + QBFT, four local validator processes**, as specified by the evaluation-platform prompt. Ganache is not used.
3. **Application signatures.** Both mechanisms use **ECDSA P-256 + SHA-256**. Ethereum secp256k1 is used only for validator/RA *transaction* accounts. UAV authentication keys are never Ethereum accounts.
4. **PKI revocation.** Local **CRL** issued by the issuing CA. No public CA, no OCSP.
5. **Roles.** Identical role values are assigned during identity setup. X.509 roles live in an off-chain JSON store; blockchain roles live in the contract. The compared variable is identity-status lookup (cert+CRL vs `eth_call`), not RBAC policy.
6. **Local topology.** Four Docker containers on one Windows host. This is **not** organisational or geographic decentralisation and is **not** evidence of Byzantine fault tolerance.
7. **Chain ID.** `20245`. Block period: 2 seconds. `min-gas-price=0` (private research network).
8. **Restore.** `reinstate` on the contract and CRL regeneration are experimental helpers so negative tests can be repeated. They are not claimed as a production governance workflow.
9. **No fabricated results.** Charts and summaries are produced only from files under `results/runs/<run_id>/`.

## Task checklist

| Stage | Work | Tests |
|------:|------|-------|
| 1 | Inspect repo; this plan | — |
| 2 | Shared protocol, schemas, storage | `tests/test_canonical.py`, `test_nonce.py`, `test_protocol.py`, `test_storage.py` |
| 3 | X.509 PKI + adapter | `tests/test_x509.py` |
| 4 | Solidity registry | compile script; `tests/test_contract_compile.py` |
| 5 | Besu/QBFT Compose | `scripts` health checks |
| 6 | Web3 adapter | `tests/test_blockchain_adapter.py` (skip if Besu down) |
| 7 | Experiment runner | `tests/test_runner.py`, `test_scenarios.py` |
| 8 | CLI | `python -m app.cli --help`; smoke |
| 9 | Streamlit UI | service-layer tests |
| 10 | Exports, charts, checksums | `tests/test_export.py` |
| 11 | Format, lint, pytest | recorded in this file at close |
| 12 | README, LIMITATIONS, this plan | final state |

## Fair-comparison boundary

Shared: challenge–response object, canonical encoding, P-256 signatures, payload size, host, timeouts, role names, UAV population.

Different by design: how the GCS obtains the current public-key binding and status (X.509 path + CRL vs permissioned-registry `eth_call`).

Optional blockchain audit transactions are **never** folded into `decision_latency`.

## Verified final state (stage 11–12)

Executed on this Windows host, 2026-08-20:

| Check | Result |
|------|--------|
| `pytest tests -q` | **35 passed** (including Besu integration) |
| `ruff check` + `black --check` | passed |
| Besu 26.7.1 QBFT 4 validators | chain ID 20245, peers=3, blocks producing |
| Contract deploy | `0xAFE9A0C681DB4CE5d798BDcB361694451FEd9bF7` |
| CLI X.509 smoke | 10/10 measured `expectation_met` |
| CLI blockchain smoke after `init-identities` | 10/10 measured `expectation_met` |
| UI | `python -m streamlit run streamlit_app.py` |

Additional implementation decisions:

- Solidity compiled with `solc 0.8.24` (`var/tools/solc-windows.exe`); `solc-bin.ethereum.org` was unreachable.
- Besu genesis generated via `docker run --entrypoint /bin/bash` (PowerShell mangles `--to=`).
- Static nodes use fixed IPs `172.28.45.11–14` (DNS hostnames were rejected as illegal enodes).
- Transactions use `eth_gasPrice` (Besu 26 rejected `gasPrice=0` even with `--min-gas-price=0`).
- `smoke-test` now registers the UAV population on-chain before the blockchain scenarios.

No dissertation results were invented. Run artefacts live under `results/runs/` and are gitignored.

