# Cursor Agent Prompt: Build the Chapter 5 Evaluation Platform

You are a senior security engineer and research software developer. Build a complete, reproducible local experimental platform for an MSc Information Security dissertation concerning UAV authentication.

Do not stop after producing a plan, pseudocode, UI mock-up or empty project structure. Inspect the existing repository, preserve existing work, implement the system in working increments, run the tests available in the environment, and update the documentation as implementation decisions are made.

## 1. Dissertation context

The dissertation compares two authentication mechanisms for a UAV communicating with a Ground Control Station (GCS):

1. an X.509 PKI baseline; and
2. a proposed permissioned-blockchain identity mechanism.

The blockchain design uses an Ethereum-compatible private network. Hyperledger Besu with QBFT is the proposed experimental platform. The logical entities are:

- UAV nodes;
- Ground Control Station;
- Registration Authority;
- blockchain validator nodes; and
- system administrator.

If the repository contains the following dissertation files, read them before implementation and treat their stated scope, terminology, requirements and metric definitions as authoritative:

- `chapter3_research_design_methodology.tex`
- `chapter4_proposed_authentication_scheme.tex`
- `chapter4_references.bib`

Do not silently change the dissertation's authentication scope. The primary scenario is UAV-to-GCS authentication. UAV-to-UAV authentication, customer authentication, parcel verification, GPS integrity and flight-control safety are outside the core implementation.

## 2. Scientific-integrity requirements

This platform will generate evidence for Chapter 5. Therefore:

- Never generate, seed or display invented experimental results as though they were measured.
- Every displayed result must come from a completed local run and must be traceable to raw observations.
- Clearly label demonstration data, if any, as synthetic and keep it outside the real results directory. Prefer not to include demonstration results.
- Do not hard-code a conclusion that blockchain is better, faster or more secure.
- Record failed, timed-out and rejected operations; do not discard them from the dataset.
- Do not compare different operations under the same metric name.
- Keep immediate authentication-decision latency separate from optional blockchain audit-transaction confirmation latency.
- Do not describe a local multi-node deployment as organisationally or geographically decentralised.
- Do not claim Byzantine fault tolerance merely because four processes started. Report only the actual topology and tests that were executed.
- Preserve raw results. Derived summaries must be reproducible from the raw files.
- Use a monotonic high-resolution clock, such as `time.perf_counter_ns()`, for latency measurement. Do not use UI rendering time as protocol latency.
- Add a concise `LIMITATIONS.md` explaining what the local experiment can and cannot demonstrate.

## 3. Required technology stack

Use a practical stack that can be run on a Windows computer through Docker Desktop and WSL2:

- Python 3.11 or 3.12 for the experiment engine;
- Streamlit for the local operation and results interface;
- `cryptography` for X.509 certificates and application-level digital signatures;
- `web3.py` for blockchain RPC and contract interaction;
- Solidity for the UAV identity registry;
- Hyperledger Besu nodes in Docker Compose;
- QBFT consensus with four local validator nodes;
- SQLite for experiment history and metadata indexing;
- CSV and JSON/JSONL for portable raw-data exports;
- pandas, NumPy and SciPy for summaries;
- psutil for local process resource measurements;
- pytest for automated tests;
- Ruff or Flake8 plus Black for Python quality checks.

Use pinned dependency versions in a lock file or fully versioned requirements file. Pin Docker image versions rather than using `latest`.

Do not replace Besu with a mocked blockchain, Ganache or an in-memory dictionary for the final integration tests. Mocks may be used only in unit tests. If Docker or Besu cannot run in the current environment, still implement the real integration and provide exact commands, but clearly report which integration tests could not be executed.

## 4. Fair-comparison principle

The comparison must isolate the identity-status mechanism rather than accidentally comparing unrelated cryptographic algorithms.

Use the same challenge--response message format, hash function, signing algorithm, payload, hardware, concurrency configuration and timing boundary for both mechanisms whenever possible.

Default application-level signature configuration:

- ECDSA using NIST P-256;
- SHA-256;
- deterministic, canonical message serialization;
- cryptographically secure random nonce of at least 128 bits.

Make the algorithm configurable, but do not allow the two mechanisms in one comparative run to use different algorithms unless the UI explicitly marks the run as non-comparable.

The X.509 baseline should use an X.509 certificate to bind the UAV identity to the public key. The blockchain mechanism should bind the same type of UAV public key to a pseudonymous UAV identifier in the smart contract. Ethereum transaction accounts are administrative/validator credentials and must not be confused with the UAV's application-level authentication key.

Transport TLS is not the independent variable. If network transport protection is included, apply equivalent protection to both mechanisms and report it as a controlled condition.

## 5. Common authentication protocol

Implement one shared challenge--response protocol with mechanism-specific identity lookup.

The signed authentication object must contain, in a deterministic order:

- a fixed protocol/domain label;
- protocol version;
- pseudonymous UAV identifier;
- GCS identifier;
- fresh nonce;
- short-lived session identifier;
- issued timestamp;
- expiry timestamp;
- requested operation or role; and
- optional payload digest.

Required flow:

1. The UAV identifies itself to the GCS.
2. The GCS creates a fresh nonce and a short-lived session record.
3. The UAV signs the canonical authentication object.
4. The GCS checks the session, freshness and single-use nonce.
5. The GCS obtains the public-key binding and current status using the selected mechanism.
6. The GCS verifies the signature.
7. The GCS evaluates role-based authorisation for the requested operation.
8. The GCS returns an explicit accept/reject result with a machine-readable reason code.
9. The nonce is consumed regardless of success or failure.

Do not create two unrelated authentication implementations. Shared stages must use common code so that the measured difference is attributable to certificate/CRL validation versus blockchain state lookup.

## 6. X.509 PKI baseline

Implement a local test PKI containing:

- one offline-style root CA for the experiment;
- an optional issuing CA if this can be implemented without unnecessary complexity;
- one certificate per UAV;
- a GCS trust store;
- certificate serial-number tracking;
- certificate expiry validation;
- signature-chain and key-usage validation;
- a CRL-based revocation path, or another clearly documented local revocation mechanism;
- certificate generation, renewal and revocation commands.

The baseline authentication decision must include:

- certificate parsing;
- trust-chain validation;
- validity-period validation;
- revocation-status check;
- UAV identifier/certificate binding check;
- challenge-signature verification; and
- role-authorisation check using a controlled off-chain role store.

Do not contact a public CA or external OCSP service. The experiment must be reproducible offline.

## 7. Permissioned-blockchain mechanism

Create a Docker Compose Besu network with four QBFT validator nodes. Include:

- an explicit chain ID;
- a reproducible genesis configuration;
- separate node data directories and ports;
- health checks;
- restricted RPC exposure suitable for a local experiment;
- documented validator addresses;
- scripts to start, stop, inspect and reset the network;
- a clear warning that the local network is for research/testing rather than production.

Implement a Solidity identity-registry contract. At minimum, it must support:

- registrar/admin role management;
- registration of a pseudonymous UAV identifier;
- storage of public-key bytes or a public-key hash with a documented retrieval strategy;
- role/permission value;
- status such as active, suspended or revoked;
- registration and update timestamps or block references;
- key replacement;
- role update;
- revocation without deleting historical evidence;
- read-only retrieval of the current UAV record;
- events for registration, key update, role update and revocation;
- prevention of duplicate active registrations and unauthorised state changes.

Use checks-effects-interactions and least-privilege principles. Avoid placing customer details, delivery addresses, flight paths, private keys or complete authentication messages on-chain.

Compile and test the contract. Provide a deterministic deployment workflow that records:

- contract source and artifact hash;
- deployed address;
- transaction hash;
- chain ID;
- block number;
- administrator/registrar test account addresses; and
- software/image versions.

Routine blockchain authentication should use a read-only contract call for the current record. Add an optional `write audit transaction` experiment toggle. When enabled, measure and store separately:

- immediate authentication decision latency;
- transaction-submission latency; and
- transaction-confirmation latency.

Store `gasUsed` and transaction receipt fields for state-changing operations. Do not convert gas into a monetary value unless a real, explicitly configured gas price and currency-conversion source are supplied. A gas-free private network still has measurable EVM gas usage, but not necessarily a real financial charge.

## 8. Required attack and negative-test scenarios

Implement repeatable scenarios with explicit expected outcomes:

1. valid active UAV authentication;
2. unknown UAV identifier;
3. impersonation using the wrong private key;
4. replay of a previously accepted response;
5. modified nonce after signature creation;
6. modified UAV identifier after signature creation;
7. modified requested operation or role after signature creation;
8. expired challenge;
9. revoked UAV;
10. valid UAV requesting an unauthorised operation;
11. malformed or incomplete authentication object;
12. expired X.509 certificate;
13. certificate signed by an untrusted CA;
14. blockchain RPC unavailable or timed out;
15. concurrent valid requests;
16. concurrent mixture of valid and invalid requests.

Each result must contain an expected outcome, observed outcome and `expectation_met` boolean. Use stable reason codes such as:

- `ACCEPTED`
- `UNKNOWN_IDENTITY`
- `REVOKED_IDENTITY`
- `EXPIRED_CHALLENGE`
- `REPLAY_DETECTED`
- `INVALID_SIGNATURE`
- `UNAUTHORISED_OPERATION`
- `CERTIFICATE_EXPIRED`
- `UNTRUSTED_ISSUER`
- `IDENTITY_SERVICE_UNAVAILABLE`
- `MALFORMED_REQUEST`
- `INTERNAL_ERROR`

Do not treat an expected rejection as an experiment failure. It is a passed security test when the observed reason matches the expected reason.

## 9. Experiment controls

The UI and command-line runner must allow the researcher to configure:

- mechanism: X.509, blockchain or both;
- selected scenarios;
- number of registered UAV identities;
- number of repetitions per scenario;
- warm-up repetitions, stored separately and excluded from the default summary;
- concurrency level or a list such as `1, 5, 10, 25, 50`;
- requests per concurrency level;
- random seed;
- challenge lifetime;
- operation/role requested;
- application payload size;
- RPC and authentication time-outs;
- blockchain audit transaction on/off;
- blockchain confirmation policy or required confirmations;
- resource-sampling interval;
- output directory;
- optional free-text run notes.

Set safe defaults. Validate input ranges. Require a confirmation before a large run. Display an estimate of total requests before execution.

Support at least 1--10,000 repetitions, subject to an explicit warning for large runs. Runs must execute in a background worker so that the interface remains responsive. Provide cancellation that stops scheduling new work, marks the run as cancelled, and preserves completed observations.

## 10. Operation interface

Build a clear Streamlit interface with the following pages or tabs.

### A. Environment status

Display:

- Python and package versions;
- operating system and CPU information;
- total memory;
- Besu/Docker availability;
- status of each validator node;
- chain ID, latest block and peer/validator information where available;
- deployed contract address and artifact hash;
- PKI/CA status;
- number of registered and revoked UAVs;
- warnings when the environment is incomplete.

### B. Test-data and identity setup

Controls for:

- generating a chosen number of UAV identities;
- issuing X.509 certificates;
- deploying or connecting to the registry contract;
- registering the same UAV population in both mechanisms;
- revoking or restoring selected test identities where permitted;
- verifying that both mechanisms contain a comparable test population;
- resetting only experiment data or fully resetting the local environment.

Destructive reset actions must require confirmation and must never target directories outside this project.

### C. Experiment configuration

Provide validated widgets for every experiment control in Section 9. Show the resolved configuration as JSON before the run begins. Assign a unique run ID and record the exact configuration.

### D. Live execution

Display:

- run ID and status;
- current mechanism and scenario;
- completed/total requests;
- progress bar;
- elapsed time and estimated remaining time;
- success, expected-rejection, unexpected-result, timeout and internal-error counts;
- recent structured log messages;
- start, cancel and safe retry controls.

### E. Results and run history

Display only data read from stored run artifacts. Include:

- run configuration and environment metadata;
- raw-observation table with filtering;
- count of observations by mechanism, scenario and outcome;
- mean, median, standard deviation, minimum, maximum, p95 and p99 latency;
- 95% confidence interval with the method documented;
- completed throughput and offered load;
- timeout and error rates;
- process CPU and memory summaries;
- blockchain gas usage for applicable state-changing calls;
- box plots or violin plots for latency distributions;
- comparable X.509 versus blockchain plots with identical axes;
- a visible warning when the run configurations are not directly comparable.

Allow selection of two or more compatible runs for comparison. Never silently combine runs with different cryptographic algorithms, payload sizes, topology or timing definitions.

### F. Export

Provide downloads for:

- raw observations CSV;
- summary CSV;
- run configuration JSON;
- environment metadata JSON;
- structured event log JSONL;
- system-resource samples CSV;
- a ZIP containing the complete run directory;
- publication-quality charts as PNG or SVG where supported.

## 11. Metric definitions

Define all metrics in `docs/METRICS.md` and use the same names in code, UI and exported files.

At minimum, record per request:

- `run_id`;
- `observation_id`;
- UTC timestamp;
- mechanism;
- scenario;
- repetition number;
- concurrency level;
- anonymised/pseudonymous UAV ID;
- expected outcome;
- observed outcome;
- expectation met;
- end-to-end decision latency in nanoseconds and milliseconds;
- challenge-generation time;
- identity-lookup time;
- certificate validation or contract-call time;
- signature-verification time;
- authorisation-check time;
- audit transaction submission and confirmation time when applicable;
- transaction hash, block number and gas used when applicable;
- timeout/error classification;
- worker identifier;
- payload size;
- warm-up flag.

Use these boundaries:

- `decision_latency`: from receipt of a complete authentication request by the GCS service layer until an accept/reject decision is produced;
- `identity_lookup_latency`: only the certificate/revocation or blockchain registry retrieval stage;
- `audit_confirmation_latency`: from audit transaction submission until the configured confirmation condition is met;
- `completed_throughput`: completed requests divided by the measured batch interval;
- `offered_load`: requests scheduled per second, recorded separately from completed throughput.

Calculate summaries from raw observations, excluding warm-ups by default. Support a deterministic bootstrap 95% confidence interval or a clearly justified alternative. Never calculate latency percentiles after discarding failures without displaying the failure count and filter rule.

## 12. Run-artifact layout

Use a structure similar to:

```text
results/
  runs/
    <run_id>/
      config.json
      environment.json
      observations.csv
      summary.csv
      events.jsonl
      system_metrics.csv
      blockchain_receipts.jsonl
      charts/
      checksums.sha256
```

Use SQLite only as an index and convenience store. CSV/JSON files are the portable research record. Generate SHA-256 checksums after a run is finalised. Never overwrite a completed run directory.

Do not commit private keys, generated certificates, node keys, raw results or environment secrets. Supply safe `.gitignore` rules. Test credentials must be generated locally and must be clearly labelled as non-production.

## 13. Suggested project structure

Adapt this if the repository already has a sensible structure:

```text
app/
  ui/
  core/
  auth/
    common/
    x509/
    blockchain/
  experiments/
  metrics/
  storage/
contracts/
  contracts/UAVIdentityRegistry.sol
  test/
  scripts/
besu/
  docker-compose.yml
  config/
scripts/
tests/
docs/
results/
streamlit_app.py
pyproject.toml
.env.example
.gitignore
README.md
LIMITATIONS.md
IMPLEMENTATION_PLAN.md
```

Keep protocol logic out of Streamlit callbacks. The UI must call testable service classes. Provide a CLI using the same experiment engine so a complete run can be executed without the browser.

## 14. Testing requirements

Implement:

- unit tests for canonical serialization, nonce consumption, expiry, signature verification, role decisions and result aggregation;
- X.509 tests for valid chain, expiry, revoked certificate, untrusted issuer and wrong key;
- smart-contract tests for authorised registration, unauthorised registration, duplicate registration, revocation, key update and event emission;
- integration tests against the actual local Besu network when Docker is available;
- replay, tampering, impersonation and revoked-identity tests for both applicable mechanisms;
- a small end-to-end comparative smoke test;
- export-file schema and checksum tests;
- UI/service separation tests where practical.

Tests must assert outcomes rather than merely execute code. Do not weaken or delete a failing security test just to obtain a green suite.

## 15. Documentation and commands

Write a beginner-friendly `README.md` with exact commands for Windows + WSL2. Include:

1. prerequisites;
2. environment creation;
3. dependency installation;
4. Besu network start and health verification;
5. contract compilation and deployment;
6. PKI and UAV population generation;
7. Streamlit UI start;
8. CLI smoke test;
9. full test suite;
10. results export;
11. safe shutdown;
12. safe local reset;
13. common troubleshooting steps.

Provide convenient scripts or Make targets such as:

```text
setup
besu-up
besu-status
deploy-contract
init-identities
ui
smoke-test
test
lint
besu-down
reset-local
```

Every command must correspond to a real script or task. Do not put placeholder commands in the README.

## 16. Implementation sequence

Work in these stages:

1. Inspect the repository and dissertation files. Record assumptions and a concrete task checklist in `IMPLEMENTATION_PLAN.md`.
2. Create the shared protocol, typed configuration, result schemas, storage layer and unit tests.
3. Implement the X.509 baseline and its negative tests.
4. Implement the Solidity registry and contract tests.
5. Implement and validate the four-validator Besu/QBFT Docker environment.
6. Implement the Web3 registry adapter and blockchain authentication path.
7. Implement the common experiment runner, concurrency control, resource sampler and cancellation.
8. Implement the CLI.
9. Implement the Streamlit interface and run-history views.
10. Implement exports, charts, checksums and reproducibility metadata.
11. Run formatting, linting, unit tests and available integration tests.
12. Update `README.md`, `LIMITATIONS.md` and `IMPLEMENTATION_PLAN.md` with the verified final state.

After each stage, run the relevant tests before proceeding. Do not claim a stage is complete if its required tests have not passed.

## 17. Acceptance criteria

The task is complete only when:

- the X.509 baseline performs real certificate and challenge-signature validation;
- the blockchain path reads real identity state from a deployed Solidity contract on the local Besu network;
- the same UAV population and application-level signature configuration can be used by both mechanisms;
- valid authentication succeeds for both mechanisms;
- replay, tampering, wrong-key and revoked-identity tests produce the expected rejection codes;
- the researcher can choose repetitions and concurrency from the UI;
- a run can be cancelled without losing completed observations;
- every chart and summary is derived from stored raw observations;
- complete run artifacts can be exported;
- a CLI smoke test works without the UI;
- automated tests pass, apart from clearly reported environment-dependent tests;
- no secret or private key is committed;
- README commands have been exercised where the environment permits;
- no performance or security result is fabricated.

## 18. Required final response from Cursor

When implementation is complete, report:

- what was implemented;
- the resulting directory structure;
- exact commands to start the network and UI;
- exact commands to run the smoke test and complete tests;
- test results, including skipped or failed integration tests;
- any decisions that differ from this prompt and why;
- known limitations;
- the location and schema of generated experimental data;
- the next concrete action required before collecting dissertation results.

If a genuine blocker requires a research decision, ask one focused question and explain its effect. For ordinary implementation details, make a defensible choice, document it and continue.
