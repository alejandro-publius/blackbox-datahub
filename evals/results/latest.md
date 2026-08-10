# BlackBox eval run 9

- started: 2026-08-10T14:59:39.876638+00:00
- finished: 2026-08-10T15:28:03.830500+00:00
- full results: `evals/results/run_0009.json`

| scenario | status | key checks | notes |
|---|---|---|---|
| control_no_incident | passed | stage_no_incident ✓ no_patch ✓ transforms_unchanged ✓ no_false_positive ✓ | stage=NO_INCIDENT; 901.92s |

## control_no_incident — passed
- **final_summary**: `"The reported \"revenue feels slightly off\" is a day-of-week composition artifact, not a data defect.\n\n1) NO DIVERGENCE FROM BASELINE. All 14 most-recent days show revenue_ratio = 1.000 and aov_ratio = 1.000 against the committed healthy baseline, with order counts matching exactly [ev_1267f1dfd7]. The full invariant suite passes 32/32 with zero failures [ev_efacfdb817].\n\n2) THE HEADLINE DIP IS NORMAL VARIANCE. The KPI's anomaly_ratio of 0.9327 on 2026-08-09 is not an outlier: across 89 days of history the ratio of daily revenue to its own trailing-28d median has sd = 0.129, range 0.733-1`
