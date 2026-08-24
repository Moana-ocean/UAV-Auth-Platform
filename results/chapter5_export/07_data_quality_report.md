# Chapter 5 data quality report

Generated from `results\chapter5_export`

## Summary

- Matrix summary rows analysed: 53
- Runs with anomalies (false accept/reject or unexpected): 27
- Total false_rejections on blockchain valid_active scale runs: 780

## Anomalous runs

- `n10-identities_c1-conc_mech-blockchain-1backend_security-battery_r30_audit-off_20260820T020051Z`: false_acceptances=0, false_rejections=30, n_unexpected=60
- `n10-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020501Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n10-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-on_20260820T022802Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n10-identities_c10-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020515Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n10-identities_c25-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020522Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n10-identities_c5-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020508Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n10-identities_c50-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020530Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n100-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020909Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n100-identities_c10-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020930Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n100-identities_c25-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020939Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n100-identities_c5-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020920Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n100-identities_c50-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020948Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n250-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T021458Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n250-identities_c10-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T021557Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n250-identities_c25-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T021613Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n250-identities_c5-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T021540Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n250-identities_c50-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T021632Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n50-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020643Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n50-identities_c10-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020659Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n50-identities_c25-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020706Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n50-identities_c5-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020651Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n50-identities_c50-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T020715Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n500-identities_c1-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T022510Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n500-identities_c10-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T022652Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n500-identities_c25-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T022719Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n500-identities_c5-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T022623Z`: false_acceptances=0, false_rejections=30, n_unexpected=30
- `n500-identities_c50-conc_mech-blockchain-1backend_valid-active_r30_audit-off_20260820T022747Z`: false_acceptances=0, false_rejections=30, n_unexpected=30

## Writing guidance

**Decision: report honestly in Chapter 5** — blockchain valid_active runs show systematic false rejections (likely implementation defect during scale matrix). Do not use blockchain accepted_only latency for comparative performance claims until re-run after fix. X.509 and adversarial (non-valid) scenarios remain usable.
