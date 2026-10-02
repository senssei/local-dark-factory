# Performance & Quality Analysis

After the deterministic gates pass and the patch is non-empty, the factory runs an **advisory** analysis of the run. It makes
no model calls, uses only the Python standard library, and never changes the run status. Skip it with `dark-factory run --no-analysis`.

## What is measured

- **Resources** (sampled every 2 s while the agent and gates run): peak VRAM and average GPU utilization via `nvidia-smi`, and peak
  host RAM via `/proc/meminfo`. A missing `nvidia-smi` or non-Linux host leaves the field empty; it is never an error.
- **Performance**: the slowest phase and its share of wall time, model throughput (tok/s), and self-healing attempts.
- **Quality**: files and lines changed, cyclomatic complexity and length of the changed Python functions, and whether source
  changed without any test file in the patch.

## Warning thresholds

Defaults target this workstation (RTX 5070 12 GB, 32 GB RAM); they are constants in `dark_factory/analysis/analyzer.py`.

| Finding | Threshold |
|---|---|
| Peak VRAM | > 90 % of total (risk of CPU offload) |
| Peak RAM | > 85 % of total |
| Model throughput | < 10 tok/s |
| Self-healing | all `max_healing_attempts` used |
| Function complexity | > 10 |
| Function length | > 60 lines |
| Tests | source changed, no test file in the patch |

## Where it appears

`.factory/runs/<RUN_ID>/analysis.md` and `manifest.json` (`analysis_report`), `dark-factory describe`, the summary shown by
`dark-factory review`, and the dashboard run detail.
