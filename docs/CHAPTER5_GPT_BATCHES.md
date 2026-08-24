# Chapter 5 GPT batch writing guide

This document implements the batch plan for generating Chapter 5 LaTeX from measured exports in `results/chapter5_export/`.

## Prerequisites

Run the export script once after the 53-step matrix completes:

```powershell
.\.venv\Scripts\python.exe -m scripts.export_chapter5_bundle
```

Read `results/chapter5_export/07_data_quality_report.md` before Batch 2.

## Batch overview

| Batch | Sections | Primary upload files |
|-------|----------|----------------------|
| 1 | 5.1–5.3 | `chapter3.tex`, `01_environment.json`, `00_run_order.md`, `00_LIMITATIONS.md`, `00_METRICS.md` |
| 2 | 5.4, 5.6, 5.7 | `02_all_summaries_enriched.csv`, `07_data_quality_report.md`, Batch 1 LaTeX |
| 3 | 5.5.1–5.5.5 | `03_security_observations.csv`, `03_security_by_scenario.csv`, security summary rows |
| 4 | 5.8–5.14 | `05_system_metrics_by_run.csv`, `04_comm_overhead_summary.csv`, `06_audit_*`, `01_environment.json` |

**Merge order in final chapter:** Batch 1 → Batch 2 (5.4) → Batch 3 (5.5) → Batch 2 (5.6–5.7) → Batch 4

Draft LaTeX already generated in this repository:

- `docs/chapter5_drafts/batch1_5_1_5_3.tex`
- `docs/chapter5_drafts/batch2_5_4.tex` / `batch2_5_6_5_7.tex`
- `docs/chapter5_drafts/batch3_5_5.tex`
- `docs/chapter5_drafts/batch4_5_8_5_14.tex`
- `chapter5_evaluation.tex` (merged)

---

## Batch 1 prompt (5.1–5.3)

```
Role: Academic LaTeX writer for an MSc Information Security dissertation.

Task: Write ONLY Sections 5.1–5.3 of Chapter 5: Experimental Evaluation and Performance Results.

Attached files:
- chapter3.tex (research questions RQ1–RQ4, experimental factors, scenarios)
- 01_environment.json (captured hardware/software/Besu/PKI snapshot)
- 00_run_order.md (53-step experiment matrix)
- 00_LIMITATIONS.md (platform scope and caveats)
- METRICS.md (field definitions — do not misinterpret)

STRICT RULES:
1. Do NOT invent any measured numbers. Use prose from Chapter 3 + environment JSON only.
2. Where a table needs future measured data, insert: % TODO: Add measured results here
3. Output valid LaTeX using \section{} and \subsection{} matching the outline in CHAPTER5_GPT_BATCHES.md
4. State explicitly: Besu 26.7.1 QBFT, 4 validators, chain ID 20245, Python 3.13 deviation per LIMITATIONS.md.
5. Cross-reference Chapter 3 research questions; do not pre-judge blockchain vs PKI.
6. Include one non-numeric Table (experimental factor levels) — values from Chapter 3 / run order only.

Tone: Formal, third person, past tense. Length: ~800–1200 words.
```

---

## Batch 2 prompt (5.4, 5.6, 5.7)

```
Role: Academic LaTeX writer — MSc dissertation Chapter 5.

Task: Write Sections 5.4, 5.6, and 5.7 ONLY (skip 5.5 adversarial — separate batch).

Attached:
- 02_all_summaries_enriched.csv
- 07_data_quality_report.md
- METRICS.md
- [Batch 1 LaTeX output]

DATA RULES:
1. Use ONLY attached CSV values. Never invent numbers.
2. Filter: valid_active, audit-off, exclude security-battery (steps 3–52).
3. Latency (5.6): latency_set=accepted_only; if n_accepted==0, mark % TODO and footnote anomaly.
4. 5.4: acceptance rate = n_accepted / n_measured.
5. 5.7: failure_rate_pct excludes expected security rejections.
6. If blockchain valid_active shows false_rejections>0, report honestly — do NOT infer comparative latency.

OUTPUT: LaTeX for 5.4, 5.6, 5.7 with tables, figure placeholders, run_id footnotes.
```

---

## Batch 3 prompt (5.5)

```
Role: Academic LaTeX writer — adversarial evaluation.

Task: Write Section 5.5 and subsections 5.5.1–5.5.5 ONLY.

Attached:
- 03_security_observations.csv
- 03_security_by_scenario.csv
- Security battery rows from 02_all_summaries.csv
- METRICS.md

SCENARIO MAPPING:
- 5.5.1 → unknown_uav, impersonation_wrong_key
- 5.5.2 → replay
- 5.5.3 → modified_nonce, modified_uav_id, modified_operation
- 5.5.4 → unauthorised_operation, malformed, rpc_unavailable (blockchain)
- 5.5.5 → revoked_uav, expired_certificate, untrusted_issuer (x509), expired_challenge

RULES:
1. Expected rejection with expectation_met=true = PASSED test.
2. Report false_acceptances and false_rejections per mechanism.
3. Never invent rejection rates.
4. Caveat blockchain valid_active false_rejections if present.
```

---

## Batch 4 prompt (5.8–5.14)

```
Role: Academic LaTeX writer — closing sections.

Task: Write Sections 5.8–5.14 ONLY.

Attached:
- 02_all_summaries_enriched.csv
- 05_system_metrics_by_run.csv
- 04_comm_overhead_summary.csv
- 06_audit_observations.csv, 06_audit_config.json
- 01_environment.json
- 07_data_quality_report.md
- METRICS.md, LIMITATIONS.md
- [Brief summaries from Batch 1–3]

RULES:
1. Never invent numbers.
2. 5.8: CPU/RSS comparative; note Docker Desktop overhead.
3. 5.9: request_bytes/response_bytes; contract_call_ms separate from decision_latency.
4. 5.10: gas in execution units only; distinguish eth_call vs audit tx.
5. 5.11–5.12: scalability and comparison; state blockchain valid_active data limitation.
6. 5.13: n=30, bootstrap CI from ci_method column.
7. 5.14: Answer RQ1–RQ4 conditionally; repeat limitations.
```

---

## Post-merge checklist

- [ ] Every table value traceable to `run_id` + CSV row
- [ ] Expected rejections not reported as failures
- [ ] Blockchain anomalies disclosed in 5.4, 5.12, 5.14
- [ ] Figure placeholders replaced with `results/runs/*/charts/*.svg`
- [ ] RQ1–RQ4 each addressed
