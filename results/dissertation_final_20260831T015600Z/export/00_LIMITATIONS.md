# Limitations of the local Chapter 5 evaluation platform

This document states what the implemented prototype can and cannot demonstrate. It is part of the scientific record, not a disclaimer to be ignored when writing Chapter 5.

## What the platform can demonstrate

- Application-layer UAV-to-GCS challenge–response authentication with a shared message format and ECDSA P-256 / SHA-256 signatures.
- An X.509 baseline with a local root CA, issuing CA, certificate expiry, key usage, identifier binding and CRL revocation, all offline.
- A Solidity identity registry deployed on a **local** four-validator Hyperledger Besu QBFT network, with read-only status lookup during authentication.
- Repeatable negative tests (unknown identity, wrong key, replay, tampering, expiry, revocation, unauthorised operation, malformed input, untrusted issuer, RPC failure, concurrent batches).
- Instrumented `decision_latency` versus optional `audit_confirmation_latency`.
- Portable raw observations (CSV/JSON/JSONL) from which summaries and charts are derived.

## What it cannot demonstrate

- Organisational or geographic decentralisation. All four validator containers run on one Windows host.
- Byzantine fault tolerance. Starting four processes is not a BFT experiment. No malicious-validator or quorum-loss tests are included.
- Production permissioning, hardware security modules, or UAV onboard key protection. Test keys are software-held and labelled non-production.
- Public Ethereum performance, gas markets or monetary cost. `gas_used` is an EVM accounting unit on a gas-price-zero private chain.
- Wireless, radio, GPS, flight-control or physical-capture threats. Those are outside the authentication boundary (Chapter 3–4).
- That blockchain is inherently more secure or faster than PKI. That is an empirical question for measured runs; this platform does not pre-judge it.
- Real delivery-operations privacy compliance. On-chain data are limited, but a legal assessment is out of scope.

## Measurement caveats

- Latency is process-local on loopback. It does not include cellular/RF delay.
- Resource samples include Docker Desktop and the host OS; they are comparative under a shared workload, not a hardware datasheet.
- Warm-up rows are stored but excluded from default summaries.
- Failed, timed-out and rejected attempts are retained. Do not drop them when reporting tail latency without stating the filter.

## Environment deviations

- The evaluation prompt requested Python 3.11 or 3.12. The implementation host used **Python 3.13**. Dependencies are pinned for 3.11+.
- Chapter 4 discusses Ganache as a development PoC. Chapter 5 uses **Besu 26.7.1 + QBFT**, not Ganache.
