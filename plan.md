# Implementation Plan: Sovereign Dark Factory (`plan.md`)

This plan defines the step-by-step development phases for **`local-dark-factory`** according to the AI-Native SDLC Playbook.

## Current backlog — realigned 2026-10-04

Status: documentation realignment authorized by operator request "Implement the plan" after choosing the whole backlog and reliability/validation first. This authorizes the documentation changes below; it does not authorize implementation or execution of the new backlog items. Existing task-specific authorizations remain recorded in their phases. No public API, invariant, release version or gate policy changes.

`plan.md` is the backlog source of truth. A checked implementation item records work and its gate evidence; it does not imply a clean re-review, live acceptance, commit or publication. Historical measurements below remain dated evidence, not current capability claims. Local ignored evidence must be accompanied by a sanitized reproducible fixture/procedure before it can support a portable regression. P0 runner-shadow protection is delivered (see `REVIEW.md` P0 runner integrity and `tests/test_runner_integrity.py`); the original bypass is historical, with transitive imports and host process isolation outside that fix.

| ID / priority | Implementation | Review / validation | Dependency | Next action |
|---|---|---|---|---|
| BL-01 / P1 | Existing fixes implemented | Independent re-review outstanding for post-review fixes in §10.7, §10.15, §14.5, Phase 15, DF-LIVE-01, 06a, Phase 18, 20 and 22 | Scoped final diffs and historical findings | Fresh local-model re-review; preserve accepted risks and operator deferrals |
| BL-02 / P1 | DF-LIVE-08 implemented | Phase 23 review clean; no post-fix full benchmark | BL-01; confirm served Prism BOS/load-guard revisions | Mistral: four scenarios × three attempts |
| BL-03 / P2 | Routing, scope and truncation fixes implemented | Residency test and Phi scope probe ran; Qwen calculator and post-parser winter validation remain open | BL-02; fixed model/runtime configuration | Separate remaining live proofs from full Phi/Qwen campaigns |
| BL-04 / P2 | Existing factory interfaces | Phase 16 real-task campaign incomplete; winter task is prior evidence | BL-02 | Two scratch-clone tasks with pre-recorded acceptance |
| BL-05 / P2 | Existing failure/recovery handling | Phase 16 controlled campaign not run | BL-04; DF-LIVE-05 implemented | Offline backend, timeout, interruption/recovery, oversized context |
| BL-06 / P2 | Manifest hash exists; independent journal anchor absent | Future regression required | Separate spec/implementation authorization | SQLite patch-integrity anchor (§10.5) |
| BL-07 / P2 | CLI discovers gates from host working tree | Future regression required | Separate spec/implementation authorization | Discover against `--base-rev` (§10.5) |
| BL-08 / P3 | Planner targets displayed only; foreign-harness mutator uses default local harness | Planner operator-deferred; mutator awaits decision | Operator decision on semantics and compatibility | Keep §14.5 finding 9 and DF-LIVE-01 finding 2 separate |
| BL-09 / P3 | Harness/CLI coverage expanded since original estimate | Current comparable coverage baseline needed | BL-01; deterministic suite | Measure gaps before adding tests (§10.5) |
| BL-10 / P3 | Phase 15 advisory analysis implemented | Threshold calibration deferred | BL-02–05 and adequate resource/quality measurements | Assess thresholds; convergence alone is insufficient |
| BL-11 / P3 | `TaskSpec.agent` / `metadata` remain public fields | Compatibility decision deferred | Operator API/version decision | Retain fields until decision (§10.3) |
| BL-12 / hold | Build/CI and historical GitHub v0.1.0 release recorded | PyPI publication pending; next version undecided | Explicit shipping authorization | §9.4 / §10.4 only when scheduled |

| BL-13 / P2 | Existing Prism routing/eval interfaces | Separate live suite pending; Prism offline in latest session | Reachable native Prism GPU model and sufficient VRAM | Phase 25: Prism-only smoke, residency, CLI and cleanup; separate from BL-02 benchmark |

### Phase 24: Documentation realignment

Status: documentation edits complete under operator request "Implement the plan", 2026-10-04. Gate: `python3 scripts/sdlc_check.py` exited 0 (370 passed, 7 local-engine tests deselected; lint, format, strict docs and changelog PASS); alignment tests separately 5 passed; `git diff --check` clean. Operator deferred live Ollama testing during the documentation session ("testy na zywej ollamie zrobimy potem"); no generation/review calls ran in that session. The later live-test session below resumed existing tests only. Independent local documentation review remains open as 24.3. Documentation-only: no new tests or code generation; verification uses the existing alignment tests and full gate. Historical review records are preserved; this phase does not re-review product changes.

- [x] **24.1 Reconcile backlog and dependencies.** Files: `plan.md`. Proof: each current row links to a single owning task below or an existing phase, historical IDs/evidence retained, no completed fix represented as unimplemented.
- [x] **24.2 Reconcile existing contracts and progress.** Files: `intent.md`, `spec.md`, `docs/sdlc/intent.md`, `docs/sdlc/spec.md`. Proof: `tests/test_docs_alignment.py::test_docs_sdlc_mirrors_match_root_files`, existing eval/dashboard tests and full gate; goals and invariants unchanged.
- [ ] **24.3 Independent documentation review and handoff.** Files: `REVIEW.md`, `docs/sdlc/review.md`, `plan.md`. Proof: fresh local-model review of this session's documentation diff, no actionable open findings, `python3 scripts/sdlc_check.py` exits 0. Record evidence and next step without ticking future backlog tasks.

### Live Ollama test session — 2026-10-04 18:42 UTC

Status: operator resumed live tests with "teraz jedz z testami"; existing `local_engine` suite complete: **6 passed, 1 skipped, 370 deselected in 82.86s**. Authoritative evidence: `pytest-live.log`, `junit-live.xml`, `inspection.json`; initial sandbox-only `pytest.log`/`junit.xml` contain seven socket-restriction skips, not a live validation pass. Ollama online, RTX 5070 available; Prism offline. Evidence: `.factory/live-ollama-20261004T184244Z/` (`protocol.json`, `pytest.log`, `junit.xml`, retained scratch evidence). All seven collected tests executed sequentially: six Ollama cases passed; Prism residency test skipped because Prism was offline. All six runs used `qwen2.5-coder:14b` through Ollama with cost_usd=0; five fixture runs reached APPROVED through test-controlled review, eval smoke reached AWAITING_REVIEW. CSV required 2 healing attempts; others required 0. All six preserved hashes/transcripts/telemetry inspected; five tracked source trees clean with only untracked Python caches, one primary worktree each, temporary eval scaffold removed. Full deterministic gate exited 0: 370 passed, 7 local-engine deselected; lint, format, strict docs and changelog PASS. These tests do not close BL-02–05 campaigns. Existing E2E approval/commit operations affect disposable fixture repositories only, not this product repository. No test/source edits, model policy changes, service restart or broader benchmark authorized by this session. Documentation review 24.3 remains separate and open.

### Phase 25: Separate live Prism test suite (BL-13)

Status: operator requested a separate plan entry ("dodaj testy na prismie to planu osobno"); planning only, not run. The latest suite tested Ollama; its Prism residency case was skipped. This suite is distinct from BL-02 Mistral repeated benchmark and BL-03 model diagnostics. Default native model: `Phi-4-mini-instruct-cuda-gpu`; endpoint `http://127.0.0.1:5272/v1`, coder Ollama URL `http://127.0.0.1:1` to prevent fallback. Existing generic E2E tests prefer Ollama and are not evidence of Prism execution. Use current CLI/eval interfaces; no new test/source implementation or service restart authorized.

- [ ] **25.1 Preflight and isolated evidence.** Files: `plan.md`, separate `.factory/live-prism-<timestamp>/` evidence directory. Record doctor, model inventory, served revision, model/context settings, available VRAM and baseline resident models. Proof: native GPU model available and Prism reachable; otherwise record blocked/not run, never a live pass. Preserve operator services and existing models.
- [ ] **25.2 Prism residency/routing regression.** Files: existing `tests/test_eval_runner.py::test_eval_real_prism_model_leaves_no_stray_model_loaded`, `plan.md`, separate log/JUnit and retained fixture evidence. Proof: test passes without a skip, no new Ollama resident model, configured Phi model only in Prism; inspect backend telemetry and confirm unload. The regression checks routing, not model convergence.
- [ ] **25.3 Prism-only functional smoke and CLI.** Files: `plan.md`, separate eval/run evidence and scratch repositories. Via current CLI run four scenarios (`primes`, `calculator`, `textutils`, `csvparse`) once each with explicit native model and disabled Ollama URL; exercise one scratch `run` plus `describe` round trip with explicit target/protected paths and argv gates. Proof: each attempt has a structured terminal result and Prism telemetry, mandatory gates/scope authoritative; record convergence, errors, truncation and healing independently. Failures remain outcomes, not successful acceptance. Do not assert a nondeterministic minimum healing count; do not approve/apply to the product repo. No repeats/model comparison: those belong to BL-02/03.
- [ ] **25.4 Evidence and cleanup acceptance.** Files: `plan.md`, separate inspection report and preserved manifests/patches/transcripts/telemetry. Proof: patch hashes match, zero cloud cost, original scratch sources unchanged (no apply), no orphan worktrees, unload test-loaded model through existing Prism API; full deterministic gate green. Report model failures separately from infrastructure defects and retain any unsupported case for a separate SDLC item.

### Follow-up acceptance and authorization

All items below are **backlog only, not newly authorized**. Existing deferrals require operator decisions; implementations require their own spec, red regression, local code/test generation, independent review and full gate. Operational tasks use existing interfaces and local models, with no host patch approval/apply or inference-service shutdown.

- [ ] **BL-01 Re-review outstanding fixes.** Files: `REVIEW.md`, `docs/sdlc/review.md`, `plan.md`; inspect the scoped source/tests named in the owning phases. Proof: fresh stateless local reviewer receives artifacts, final scoped diffs and original findings; reproducible findings triaged, accepted risks/deferrals distinguished, no actionable open finding and full gate green. Do not erase prior reviewers or claim their reviews covered later fixes.
- [ ] **BL-02 Post-DF-LIVE-08 Mistral benchmark.** Files: `plan.md`, separate `.factory/` evidence root. Procedure: confirm served Prism revision includes P24 BOS and P23 load guard, freeze scenario/model/runtime/context settings, disable Ollama routing via the existing URL option, run all four scenarios × three repeats sequentially, unload via existing Prism interface between models. Proof: 12 structured outcomes with reasons, hashes, transcripts/telemetry, patch-scope checks, clean scratch sources and no orphan worktrees. Model failure is a measured outcome, not an incomplete campaign. Current reports predate DF-LIVE-08.
- [ ] **BL-03 Remaining live proofs and diagnostics.** Files: `plan.md`, separate `.factory/` evidence root; existing `tests/test_eval_runner.py::test_eval_real_prism_model_leaves_no_stray_model_loaded` is prior passed residency evidence. Run Qwen3-4B `calculator` (Phase 18 optional proof) and the winter task again after DF-LIVE-08; Phase 16 already records the earlier scope rejection. Proof: complete evidence explains success, truncation or scope failure. Track full Phi/Qwen four-scenario × three-repeat campaigns separately, subject to scope authorization and resource availability. Diagnose reasoning/output budget with fixed settings first; no new budget API, `/no_think` policy or threshold adjustment presumed.
- [ ] **BL-04 Two real repository tasks.** Owning task: Phase 16 real repository tasks. Files: `plan.md`, scratch clones and separate evidence root. Before execution record two chosen tasks (one known failing test, one 2–3-file task), baseline revision, prompts, target/protected paths, argv gates and time limits. Proof: mandatory gates pass, human patch inspection, complete evidence, original source unchanged and sandbox cleanup; failure remains recorded and does not tick successful acceptance. Any test/code generation runs through LocalCoderHarness/local endpoints.
- [ ] **BL-05 Controlled exit-path campaign.** Owning task: Phase 16 controlled failures. Files: `plan.md`, scratch repositories and separate evidence root. Proof: offline endpoints produce structured errors/partial reports; deadline produces `TIMED_OUT`; interruption produces `CANCELLED` with preserved evidence; recovery after process interruption is repeatable; oversized context has explicit diagnostics. Inspect evidence appropriate to each path and repeated cleanup/recovery. Terminate only the campaign process, never the operator's inference service; document cases unsupported by existing interfaces before adding implementation.
- [ ] **BL-10 Threshold assessment.** Files: `dark_factory/analysis/analyzer.py`, `tests/test_analysis.py`, `spec.md`, mirrored spec, `plan.md` (future authorized change only). Proof: use post-fix benchmark plus real-task/failure data and actual resource samples; existing threshold-boundary tests remain green. Propose any calibration separately with rationale and boundary regressions. Missing adequate measurements keep tuning blocked; never tune mandatory gates to improve convergence.

---

## Phase 16: Real-live validation campaign (2026-10-03)

**Status:** baseline and repeated campaigns complete; 2026-10-04 winter task and pre-DF-LIVE-08 rerun/probes are recorded below. The two-task real repository campaign and controlled failures remain open (BL-04/05). Authorized by operator request "dodaj do planuj i jedziemy". Operational validation of existing behavior in spec.md §3.7; no source/test generation, invariant changes, shipping or threshold tuning authorized by this campaign. Start with smoke and 4 × 5 benchmark; retain evidence and record failures without changing implementation.

- [x] **Baseline and smoke.** Files: `plan.md`, `.factory/live-20261003/` evidence. Run `python3 scripts/sdlc_check.py`, `.venv/bin/dark-factory doctor`, and `eval --scenario primes --repeat 1`. Proof: green deterministic gate, reachable local engine, saved report and inspectable patch/manifest; verify source repository isolation and worktree cleanup.
- [x] **Repeated benchmark.** Files: `plan.md`, `.factory/live-20261003/` evidence. Run all four registered scenarios with `--repeat 5 --keep-repos`, sequentially against `qwen2.5-coder:14b`. Proof: 20 recorded attempts; per-scenario convergence, duration, healing attempts, stuck detection and token telemetry, plus evidence/cleanup inspection. CLI exit 0 means each scenario converged at least once, not that every attempt passed. Model failures remain measured outcomes.
- [x] **Prism-only comparison (operator authorized 2026-10-03).** Files: `plan.md`, `.factory/live-prism-20261003/`. Inventory `/v1/models`; select `Phi-4-mini-instruct-cuda-gpu` (3276.2 MB) and `mistral-7b-instruct-v0.2-cuda-int4-rtn-block-32` (4075.3 MB), both native ONNX Runtime GenAI GPU exports. Exclude `ollama:` proxy entries and CPU exports from this comparison. Smoke each model, then run four scenarios × three repeats per selected model (24 benchmark attempts). Force native Prism routing with `--ollama-url http://127.0.0.1:1`; verify telemetry engine, gates, evidence hashes, protected test paths and cleanup. Rerun deterministic gate this session before ticking. Measure failures as outcomes; do not alter inference services, source code or verification gates. Status: completed; 24 native benchmark attempts and two native smoke attempts; observations and owner backlogs recorded, no fixes.
- [x] Qwen3-4B native Prism benchmark (operator 2026-10-03: unload all models and return to tests). Files: plan.md and `.factory/live-prism-20261003/qwen3-4b-benchmark/`; run four existing scenarios × three attempts using retained run_native.py, explicit identical TaskSpec/planner/harness model, disabled Ollama URL and existing verification gates. Proof: 12 recorded attempts with backend telemetry, gate evidence, patch/cleanup inspection and full baseline gate. Release all server models before and after; do not change source/tests or resource guards. Status: complete: 12/12 FAILED in 660.87 seconds; manifests/telemetry/transcripts/patches and cleanup inspected, no issues. Native probes confirmed output truncation and empty-content diagnostics; remediation remains backlog only. Qwen unloaded after diagnostics.
Real repository tasks remain open, with one owning checkbox and acceptance procedure in **BL-04** above. Prior winter runs below are evidence, not completion of the two-task campaign.
Controlled failures remain open, with one owning checkbox and acceptance procedure in **BL-05** above.

Acceptance: mandatory verification gates determine successful runs; report model convergence separately from orchestrator defects. Require evidence for every completed attempt, inspect cleanup/isolation, and never equate a green model-written patch with operator approval. Five repeats are exploratory, not a reliability guarantee. Any fix follows a separate test-first SDLC item; independent review is required for implementation changes.

### Execution evidence (chronological)

**Ollama `qwen2.5-coder:14b` (baseline)**

- Baseline gate passed outside sandbox: 289 passed, 6 local-engine tests deselected; lint, format, docs, changelog passed. Restricted sandbox blocked sockets (not a product failure). Doctor: RTX 5070 and Ollama online, Prism offline.
- Smoke: `eval-primes-1-1791015059913`, AWAITING_REVIEW, 34.93 seconds, zero healing attempts; pytest exit 0, patch only changes primes.py, source scratch repo clean and only its primary worktree remains. Report: `.factory/live-20261003/evals/20261003T081134812801Z.json`.
- Benchmark completed, exit 0: 20/20 AWAITING_REVIEW, no stuck flag. Report: `.factory/live-20261003/benchmark/evals/20261003T081646320221Z.json`. Duration 260.98 seconds. Per scenario: calculator 5/5, mean 9.88s, healing 0; csvparse 5/5, mean 20.21s, healing 1; primes 5/5, mean 10.62s, healing 0; textutils 5/5, mean 16.54s, healing 2.2 (individual counts 2,3,0,2,4).
- Inspected all 20 manifests: patches match recorded SHA-256, telemetry files present, all scratch source repos clean, each has only its primary worktree. Patch paths contain only intended application files (calculator.py, cli.py, csvparse.py, primes.py, text_utils.py); no test edits. Retained scratch repos are deliberate (--keep-repos), not orphan sandboxes. Host git status contains only plan.md.
- Next session: select and record two real repository tasks and their acceptance gates before local execution; then controlled failure probes. These stages have not run. Model success in this small sample does not establish production reliability, and no implementation fixes, approval/apply, commits or shipping occurred.

**Native Prism: Phi-4-mini, Mistral-7B**

- Prism interim: deterministic gate green (289 passed, 6 deselected). Two CLI Phi smoke attempts raised LocalEngineOfflineError/Prism 503 because eval.run_scenario leaves TaskSpec.model at default qwen2.5-coder:14b; planner creates a default Ollama harness and reloads Qwen, exhausting VRAM. Read-only diagnosis confirmed; no product fix. Unloaded Qwen via keep_alive=0 and used existing DurableEngine API with TaskSpec.model=planner_model=selected model and the same Prism-only harness for planner/coder/auditor. Reproducible operational driver retained at `.factory/live-prism-20261003/run_native.py`, inventory at `models.json`.
- Native Phi smoke passed (1 healing), telemetry engine=prism. Patch has extraneous path/to/primes.py and raises ValueError for negative inputs; green scaffold test does not establish patch quality. Phi benchmark: 7/12 AWAITING_REVIEW (calculator 1/3, csvparse 0/3, primes 3/3, textutils 3/3); final report `.factory/live-prism-20261003/phi-benchmark/evals/20261003T082958685934Z.json`. Starting Mistral smoke.

**Native Prism: Qwen3-4B**

- Qwen interim: full gate passed (289 passed, 6 deselected; lint/format/docs/changelog green). Resource baseline after server unload: 8875.2 MB VRAM free, no resident Ollama/Prism models. First calculator attempt failed after five repairs; telemetry completion_tokens=3072 across six calls (512 each). Integration observation: LocalCoderHarness Prism payload omits max_tokens; Prism server defaults to 512 and harness discards finish_reason. Potential output truncation confounds model comparisons; confirm with raw response capture before remediation.

**Campaign summary**

- Native Prism campaign complete: Phi 7/12 (58.3%), Mistral 0/12. Mistral report `.factory/live-prism-20261003/mistral-benchmark/evals/20261003T083500449753Z.json`. All 24 manifests have Prism model telemetry, transcripts and clean retained source repos with no sandbox worktrees; non-empty patch hashes match. Ten Mistral patches are empty with patch_sha256=null (expected empty-patch representation, not hash corruption). Nine Phi benchmark patches contain extra path/to files, including six of seven green patches. Results measure scaffold gates, not patch acceptance.
- Operator asked to record work only: investigation DF-PRISM-20261003-01 appended to `../03-prism-local/plan.md` (Mistral fallback is intended under I7, not a confirmed Prism defect); cross-project defect-reporting design backlog appended to `../local-sdlc-kit/plan.md`. No source/test changes, commits or pushes in either project.

**Real repository task: `../winter-prognosis` (2026-10-04, Phi-4-mini native Prism, Ollama cut off)**

- Task: implement four functions in `frost_stats.py` (stubs, 4 red tests committed by the operator in `088e989`; factory edits only that file). Gate `pytest test_frost_stats.py`, `--target-file frost_stats.py`.
- Run 1, before the scope gate: `run-20261004-122826-580f74` AWAITING_REVIEW, 1 healing, 511 tokens. The functions were correct, but the patch also created `path/to/frost_stats.py` and dropped the module docstring (DF-LIVE-06 evidence). Not approved.
- Run 2, with the scope gate (DF-LIVE-06a): `run-20261004-125558-86b83a` **FAILED**, `out_of_scope_patch`, same patch (2475 bytes, 511 tokens, deterministic), `diff.patch` kept, notes name `path/to/frost_stats.py`. Ollama stayed empty in both runs (DF-LIVE-01 holds); the source repository stayed clean; model unloaded afterwards.
- Two Prism 503 `insufficient_resources` before run 2 (9.1-9.2 GB free < 9.49 GB required) were the Prism guard working, not a factory defect; the operator restarted `prism serve` (10.6 GB free).
- Observation: the CLI line after a scope failure is the generic "Task failed verification or generation."; the reason is only in `operator_notes`/`describe`. Candidate follow-up, not planned.
- The adversarial audit still ran before the scope check (one wasted model call); an early pre-check would save it.

**Prism CUDA repeated benchmark campaign (2026-10-04, post-BOS fix & Waves 1-2)**

- **Baseline & loaded-model residency**: Prism CUDA running on port 5272 with Phase 24 BOS fix active and Phase 19b Ollama load guard committed in `../03-prism-local`. RTX 5070 with 10.65 GB free VRAM baseline. Live test `test_eval_real_prism_model_leaves_no_stray_model_loaded` passed in 16.35s (Item 16.3b): Ollama resident set was empty and Prism unloaded cleanly.
- **DF-LIVE-05 campaign resilience in action**: When VRAM cache from a previous run held memory (PID 1278840, 8.37 GB free < 8.65 GB required for Mistral), Prism returned 503 `insufficient_resources`. Dark Factory caught the exception, recorded `EvalRunResult(converged=False, status="FAILED", error=...)`, printed summary table, saved `.factory/evals/20261004T174054761133Z.json`, and exited 1 without crashing or losing data.
- **Mistral-7B rerun (12 benchmark attempts)**:
  - Command: `dark-factory eval --repeat 3 --model mistral-7b-instruct-v0.2-cuda-int4-rtn-block-32 --ollama-url http://127.0.0.1:1`.
  - Report: `.factory/evals/20261004T174605518493Z.json`. Duration 224.0s. Result: 0/12 converged (0%). Average decode speed: 83.9 to 104.5 tokens/sec.
  - Per scenario:
    - `calculator` (3/3): Mistral generated code blocks for `cli.py` and `path/to/...`. Deterministic verification (pytest) executed and failed with `ImportError: cannot import name 'multiply' from 'calculator'` because `multiply` was defined in `path/to/calculator.py` instead of `calculator.py`. All 3 attempts exhausted 5 healing retries and triggered the repeated failure streak (`stuck: yes`). (DF-LIVE-06 scope gate would have rejected the `path/to/` and `factory.yml` files had pytest passed).
    - `textutils` attempt 2: DF-LIVE-02/03 truncation detection triggered on Prism (`finish_reason=length`, 640 completion tokens), rejecting partial generation without writing corrupted files.
    - `primes`, `csvparse`, and `textutils` (1 & 3): Mistral began completions with `" ```file:..."` (a single leading space after `[/INST]`). `_FILE_OPEN_RE` (`^(`{3,})file:(.*)$`) requires 0 leading spaces and failed to match the opening fence (unlike `_FENCE_RE` which permits `^ {0,3}`).
- **Qwen3-4B diagnostic probe (`primes`, 1 attempt)**:
  - Report: `.factory/evals/20261004T174737378442Z.json`. Duration 63.3s, 86.4 tokens/sec. Result: 0/1 (FAILED).
  - DF-LIVE-07 & DF-LIVE-02/03 in action: Telemetry recorded `reasoning_chars: 14469`, `completion_tokens: 4096` across 4 calls (1 initial + 3 repairs, exactly 1024 each), `finish_reason: length`. Qwen3's thinking tokens exhausted the 1024 budget before emitting complete code. The harness accurately reported truncation and never executed reasoning as code.
- **Phi-4-mini scope gate probe (`primes`, 1 attempt)**:
  - Report: `.factory/evals/20261004T174823341476Z.json`. Duration 11.5s, 134.1 tokens/sec. Result: 0/1 (FAILED).
  - DF-LIVE-06 scope gate in action: Pytest verification passed, but the patch created `path/to/primes.py` and `path/to/test_primes.py`. The scope gate rejected the patch with `out_of_scope_patch`, proving the gate prevents weak/extraneous patches from passing the benchmark.
- All manifests have Prism telemetry, preserved transcripts/patches, clean source repos and no orphan worktrees. Zero cloud tokens ($0.00). Models cleanly unloaded via `POST /v1/unload`.

**Superseded follow-ups** (kept as history; the work is tracked only by the defect backlog below)

- Output-budget integration follow-up -> **DF-LIVE-02 / DF-LIVE-03 / DF-LIVE-07**. Original wording: files `dark_factory/harness/local_coder.py`, `tests/test_harness.py`, `spec.md`, `CHANGELOG.md`; define explicit Prism completion budget and handling/reporting of finish_reason=length, preserving context/resource guards. Proof: red-first request/response regression and a controlled native Qwen rerun; do not silently increase production budgets during this baseline.
- Factory follow-up on eval model propagation -> **DF-LIVE-01**. Original wording: eval.run_scenario must propagate the selected local model to TaskSpec/planner without losing endpoint routing. Files: `dark_factory/eval/runner.py`, relevant planner wiring if needed, `tests/test_eval_runner.py`, `spec.md`, `CHANGELOG.md`. Proof: failing model/endpoint regression first, then full gate and independent review; reproduction evidence in this Prism campaign. Backlog only; no fix authorized by the operator latest clarification.
---

## Live-test defect backlog — Dark Factory / Prism integration (2026-10-03)

**Status:** initial backlog-only request was superseded by the recorded task-specific authorizations below. DF-LIVE-01…08 and DF-LIVE-06a are implemented and gate-green; post-review fix re-reviews and remaining live validation are tracked as BL-01…03. Original causes/evidence below describe the pre-fix behavior. IDs below refer to factory defects; expected Prism resource guards, documented template fallback and weak model-generated code are not automatically Prism defects.

Evidence root: `.factory/live-prism-20261003/`. Native results: Phi 7/12, Mistral 0/12, Qwen3-4B 0/12. Qwen report: `qwen3-4b-benchmark/evals/20261003T090109396586Z.json`; twelve manifests have Prism telemetry and preserved transcripts/patches, clean source repos and no orphan worktrees. Full gate green this session: 289 passed, 6 deselected, lint/format/docs/changelog. Ollama and Prism were empty before the Qwen run; Qwen was unloaded again after diagnostics. Evidence is local and ignored; preserve minimal sanitized reproductions with each regression test before relying on it across machines.

### Confirmed defects / reproducible integration failures

- [x] **DF-LIVE-01 — selected eval model propagation (P1, fixed)** (plan: "DF-LIVE-01 implementation" below). Historical failure: `eval --model Phi-4-mini-instruct-cuda-gpu --ollama-url http://127.0.0.1:1` caused planning with the default Qwen/Ollama harness: `run_scenario()` constructs TaskSpec without `model`, then `activity_plan_task()` creates a new harness with default endpoints when models differ. The unintended Qwen load consumes ~9 GB VRAM and Prism returns 503. Files: `dark_factory/eval/runner.py`, `dark_factory/orchestrator/activities.py`, `tests/test_eval_runner.py`, `tests/test_planner.py`, `tests/test_orchestrator.py`, `spec.md`, `CHANGELOG.md`. Proof: regression captures actual model and endpoint identity for planner, coder and auditor under a non-default eval model; explicit distinct planner model also preserves local endpoint/window/timeout configuration. Evidence: `phi-smoke/` and `phi-smoke-retry/` exception manifests, `run_native.py` workaround with explicit TaskSpec model.
- [x] **DF-LIVE-02 — Prism completion budget is unspecified and ignores calculated output reserve (P1)** (done as 18.1-18.5 below).
- [x] **DF-LIVE-03 — completion truncation is discarded and misdiagnosed as bad file formatting (P1)** (done as 18.1-18.5 below).
- [x] **DF-LIVE-04 — harness failures overcount healing attempts (P2)** (done as 19.1-19.4 below).
- [x] **DF-LIVE-05 — backend exceptions abort eval without a structured campaign result (P2)** (done as 20.1-20.4 below).
- [x] **DF-LIVE-08 — opening file code block regex rejects CommonMark-valid leading whitespace (`^ {0,3}`) (P2)** (done as 23.1-23.4 below). `_FILE_OPEN_RE = re.compile(r"^ {0,3}(`{3,})file:(.*)$")` in `dark_factory/harness/local_coder.py` allows up to 3 leading spaces matching `_FENCE_RE` and CommonMark specifications, preventing Mistral-7B leading space tokens after `[/INST]` from breaking file parsing.

### DF-LIVE-01 implementation (spec: §3.2.1 "Endpoint routing", §3.7 "Model propagation")

Status: spec written 2026-10-04; implementation authorized by operator request ("zatwierdzam", 2026-10-04). 16.1-16.5 done and gated. Review (fresh general-purpose Claude subagent, diff and artifacts only): 4 findings. Fixed test-first: planner without `planner_model` now uses the coder harness (not `TaskSpec.model`), `with_model` keeps the subclass (`copy.copy`), tests tightened (exact timeout, exact call count, every POST URL recorded instead of a vacuous fake-Ollama assertion, `<=` in the live test). Spec narrowed: mutator fallback for non-`LocalCoderHarness` harnesses is pre-existing and **deferred, pending operator yes** (finding 2). Fixes verified by tests, not re-reviewed independently. 16.3b ran and passed (recorded below). Historical root cause before the fix (2026-10-04): two separate gaps.
(a) `eval/runner.py` builds `TaskSpec` without `model`; (b) `orchestrator/activities.py:103,115` creates `LocalCoderHarness(model=planner_model)` with default
endpoints, dropping the operator's `ollama_url`/`prism_url`/`timeout`/`max_num_ctx` (this also affects `dark-factory run --planner-model ... --prism-url ...`).
Auditor and mutator already reuse the coder harness when it is a `LocalCoderHarness`; `activities.py:443` falls back to defaults only for foreign harness types.

- [x] **16.1 `LocalCoderHarness.with_model()`.** Files: `dark_factory/harness/local_coder.py`, `tests/test_harness.py`. Returns a new harness with the given model and the same
  `ollama_url`, `prism_url`, `timeout`, `max_num_ctx`; the original is unchanged. Proof: red test (method missing) asserting all five fields.
- [x] **16.2 Planner uses the derived harness.** Files: `dark_factory/orchestrator/activities.py`, `tests/test_planner.py` (or `tests/test_orchestrator.py`). When `spec.planner_model`
  differs from the coder model, `planner_harness = harness.with_model(planner_model)`. Proof: red test with a coder harness on non-default URLs and a distinct planner model;
  the planner harness must carry those URLs.
- [x] **16.3 Eval propagates the model.** Files: `dark_factory/eval/runner.py`, `tests/test_eval_runner.py` (`cmd_eval` already passes `model=`, so no CLI change or test is needed). `run_scenario(..., model=...)`
  sets `TaskSpec.model`; `run_eval` forwards its `model`. Proof: red test capturing the `TaskSpec` seen by a fake engine/harness under a non-default model; CLI test that `cmd_eval`
  with `--model X` yields `TaskSpec.model == X`.
- [x] **16.3a Loaded-model verification, hermetic.** Files: `tests/engine_fakes.py` (new test helper), `tests/test_engine_routing.py` (new). The helper starts stdlib `http.server`
  fakes on ephemeral localhost ports: a fake **Prism** (`POST /chat/completions` records the requested `model` and marks it loaded; `GET /status` returns `active_model` like the real
  `/v1/status`; `GET /models`) and a fake **Ollama** (`POST /api/generate` records and marks loaded; `GET /api/ps` returns the loaded list like the real endpoint). A function
  `loaded_models(ollama_url, prism_url)` reads `/api/ps` and `/status` and returns what is resident per engine. Test: run `run_scenario` (planner on, one attempt) with
  `model="Phi-4-mini-instruct-cuda-gpu"`, `ollama_url` pointing at a closed port (as in the live repro, `http://127.0.0.1:1`) and `prism_url` at the fake Prism; the fake replies
  with a minimal valid plan, then a `file:` block. Assert: (1) the set of models requested at the fake Prism is exactly `{Phi-4-mini-instruct-cuda-gpu}` for planner, coder and
  auditor calls; (2) `loaded_models(...)` after the run reports only that model; (3) a second test with a distinct `planner_model` shows both models were requested at the
  configured fake endpoints and none anywhere else (a derived harness on default endpoints would send the planner call to `localhost:11434`, so the planner request would be missing
  at the fake, which fails the assertion). Red first against the unfixed code: the planner call goes to the default Ollama and the fake Prism sees no planner request. Also unit-test
  the helper itself (empty engine -> empty set; one request -> that model).
- [x] **16.3b Loaded-model verification, live (opt-in).** *Run 2026-10-04 (`test_eval_real_prism_model_leaves_no_stray_model_loaded`, 1 passed in 16.35s).* Files: `tests/test_eval_runner.py` (marker `local_engine`, run by hand). Uses the real `loaded_models()` against the real
  Ollama `/api/ps` and Prism `/v1/status`. Skips unless Prism is reachable. Records the resident set before; runs `primes` once with a native Prism model and `--ollama-url
  http://127.0.0.1:1`; asserts the resident Ollama set is still empty (no stray Qwen) and Prism's `active_model` is the evaluated model (or `None` after an unload), then releases
  the model through `POST /v1/unload` (never stops the operator's service). Status: passed on RTX 5070; zero stray models in Ollama, Prism model cleanly unloaded.
- [x] **16.4 Docs and changelog.** Files: `CHANGELOG.md` (`### Fixed`), `docs/cli.md` or `docs/local-inference.md` if they describe planner routing. Move the two spec bullets out of "planned". Proof: `sdlc_check.py` docs and changelog checks.
- [x] **16.5 Independent review** (fresh `general-purpose` subagent, diff only), then full gate. Live proof (optional, needs hardware): `eval --scenario primes --repeat 1 --model Phi-4-mini-instruct-cuda-gpu --ollama-url http://127.0.0.1:1`
  without `run_native.py`; verify no Qwen load. Operator decides whether to run it.

- [ ] **BL-08b / Deferred foreign-harness mutator fallback (DF-LIVE-01 finding 2).** Files: `dark_factory/orchestrator/activities.py`, `tests/test_adversarial_mutator.py`, `tests/test_orchestrator.py`, `spec.md` and mirrored spec. The current fallback builds a default local harness for foreign types. Operator must choose configuration/extension semantics before implementation; proof: configured local routing preserved, supported foreign harness behavior explicit, no unintended model/backend requests. No third backend authorized.

Risks and open questions: the hermetic fakes prove routing and the loaded-model bookkeeping of the fake engines, not real VRAM use; the real residency check is 16.3b, run by hand. `with_model` is added on the
concrete class, not on `AgentHarness`; other harness types keep today's behavior. Not in scope: DF-LIVE-02..07, any `max_tokens` change, Prism changes.

### DF-LIVE-06a patch-scope gate (spec: §3.3 "Patch scope is a gate")

Status: spec written 2026-10-04 on the operator's request ("dodaj ocene do bramki", scope rule that blocks the run, chosen over an advisory-only evaluation); plan approved by the operator ("tak", 2026-10-04); 17.1-17.4 done and gated. Review (fresh general-purpose Claude subagent): 3 findings plus test gaps. Fixed test-first: fail-open on an unparseable `diff --git` header (now a violation), `--target-file` directory semantics (`pkg`, `pkg/` and `.` behave consistently), tests added (bare dir, `./x.py`, `.`, unparseable header, quoted/space path, >10 paths cap). Accepted risk: rule 1 blocks legitimate `.../path/to/...` directories and one opt-out disables both rules. Fixes verified by tests, not re-reviewed independently. Live evidence: winter run 2 and Phi `primes` scope rejection are recorded in Phase 16; post-DF-LIVE-08 winter validation remains BL-03. Trigger: the winter-prognosis live task (run `run-20261004-122826-580f74`, scratch evidence) passed all gates yet its patch added a placeholder `path/to/frost_stats.py` and removed the module docstring.

- [x] **17.1 Pure scope check.** Files: `dark_factory/verification/scope.py` (new), `tests/test_scope.py` (new). `check_patch_scope(paths, target_files)` per spec rules 1 and 2; the engine passes `parse_patch_files(diff)` (the function takes paths, not a diff, so the module does not import `orchestrator.activities`). Proof: red tests for the exact winter diff shape (`path/to/frost_stats.py` flagged), no target files and a normal patch (no violation), target file only, extra new file outside targets, target directory prefix, deleted file out of scope, `path/tomorrow.py` and `a/path/b/to.py` not flagged, empty diff.
- [x] **17.2 Engine integration and opt-out.** Files: `dark_factory/domain/types.py` (`TaskSpec.allow_out_of_scope: bool = False`), `dark_factory/orchestrator/engine.py`, `dark_factory/cli.py` (`--allow-out-of-scope`), `tests/test_orchestrator.py`, `tests/test_cli.py`. Proof: red orchestrator tests (a harness that writes `path/to/x.py` next to the fixed file ends `FAILED` with `reason out_of_scope_patch`, `diff.patch` preserved, notes list the path; with `allow_out_of_scope=True` it reaches `AWAITING_REVIEW` and the notes say the check was bypassed; a clean patch is unaffected; empty-patch still wins), CLI test that the flag sets the field.
- [x] **17.3 Docs and changelog.** Files: `CHANGELOG.md` (`### Added`), `docs/cli.md`, `spec.md` and `docs/sdlc/spec.md` (drop "planned"). Proof: `sdlc_check.py` docs and changelog checks.
- [x] **17.4 Independent review** (fresh subagent), then full gate. Optional live proof (operator): rerun the winter task; expect `FAILED out_of_scope_patch` for the stray file, evidence preserved. Also rerun the Phi `primes` eval to see how many former green results change (expected: many, DF-LIVE-06 evidence).

Risks and open questions: (1) a hard `FAILED` hides that the gates passed and the real fix was correct; the operator sees it in `operator_notes` and `diff.patch`, and can use the opt-out. An alternative is to strip stray new files before verification (like gate-protected paths); not chosen, because silently discarding model output hides the defect. (2) Rule 2 with `--target-file` forbids legitimate new helper or test files; the opt-out is the escape hatch. (3) The check cannot judge quality (removed docstring, weak edge cases): that stays with the adversarial audit and the operator.

### DF-LIVE-02 / 03 / 07 completion budget, truncation and reasoning (spec: §3.2 "Completion budget, truncation and reasoning")

Status: spec written 2026-10-04 (operator: "jedziemy" after the wave-1 order was agreed); plan approved by the operator ("tak", 2026-10-04); 18.1-18.5 done and gated (337 passed). Review (fresh general-purpose Claude subagent): 4 findings plus test gaps, all fixed test-first: `content: null` no longer crashes the no-answer branch (`or ""`), truncation repair prompt no longer says "unchanged files" or shows the operator hint, `max_tokens >= 1`, aggregated `finish_reason` is None when the last attempt has no telemetry; tests added for null/whitespace content and reasoning containing a `file:` block. Fixes verified by tests, not re-reviewed independently. Optional live proof (Qwen3-4B `calculator`) not run. Historical root cause before the fix: `_call_model` sent no `max_tokens` to Prism (server default 512, `prism/server.py:802,864`), read only `message.content` and `usage`, dropped `finish_reason`/`done_reason` and `reasoning_content`; `execute_task` then reported truncation as "no recognizable file code blocks", and the healing loop repeats the same request. Prism behaves as specified (it clamps to `window - prompt` and reports `length`), so nothing changes in Prism. DF-LIVE-04 (healing counting) is separate and untouched.

- [x] **18.1 Capture and budget.** Files: `dark_factory/domain/types.py` (`ModelTelemetry.finish_reason`, `max_tokens`, `reasoning_chars`), `dark_factory/harness/local_coder.py` (`_call_model`), `tests/test_harness.py`. Prism payload gets `max_tokens=output_reserve`; telemetry records `finish_reason` (Prism `finish_reason`, Ollama `done_reason`), `max_tokens` and `reasoning_chars` (`reasoning_content` / `thinking`). Proof: red tests with mocked `requests.post`: payload contains `max_tokens == output_reserve` (default 1024, and a larger reserve for a big context), telemetry carries `length` / `stop`, reasoning length counted, Ollama payload unchanged (no `num_predict`).
- [x] **18.2 Truncation and reasoning in `execute_task`.** Files: `dark_factory/harness/local_coder.py`, `tests/test_harness.py`. `finish_reason == "length"` returns `success=False`, writes no file, explicit error (tokens, budget, `--target-file` hint), `raw_response` kept; empty content plus reasoning gets its own error; reasoning is never parsed for `file:` blocks. Proof: red tests: a `length` reply that holds one complete `file:` block writes nothing; a multi-file `length` reply writes nothing; a `stop` reply with the same blocks still writes them; empty content with a Python block in `reasoning_content` writes nothing and says reasoning-only.
- [x] **18.3 Recovery prompt and telemetry aggregation.** Files: `dark_factory/verification/healing.py`, `dark_factory/storage/evidence.py` (only if the loader needs it), `tests/test_verification.py`, `tests/test_storage.py`. A truncated attempt gets the "reply was cut off, return only the changed files, no reasoning" repair prompt (not the generic format reminder); aggregated telemetry keeps the last `finish_reason`, the largest `max_tokens`, summed `reasoning_chars`. Proof: red tests with a scripted harness: first attempt returns `finish_reason=length`, the second prompt contains the truncation instruction and differs from the format reminder; aggregation test; a pre-change manifest JSON without the new fields still loads.
- [x] **18.4 Docs and changelog.** Files: `CHANGELOG.md` (`### Fixed`), `docs/local-inference.md` (budget, truncation, reasoning), `spec.md` and `docs/sdlc/spec.md` (drop "planned"). Proof: `sdlc_check.py` docs and changelog checks.
- [x] **18.5 Independent review**, then full gate. Optional live proof (operator, needs Prism and 10 GB free): rerun the Qwen3-4B `calculator` scenario; expect either a real result or an explicit truncation reason, never "no recognizable file blocks" with empty content. Uses `prism unload` between runs.

Risks and open questions: (1) `max_tokens = output_reserve` may still be too small for a reasoning model that spends its budget on reasoning; the failure is then explicit (`length`) rather than silent, and the operator can raise it by narrowing context or a future setting. A user-configurable budget is not added here. (2) Planner, auditor and mutator also get the explicit budget (1024 by default instead of Prism's 512) and their own fallbacks stay as they are; a truncated planner or auditor reply is not turned into a failure. (3) A test cannot prove that a given model fits the budget; only the live rerun can.

### DF-LIVE-04 healing attempt counting (spec: §3.3 "Self-Healing Loop")

Status: 19.1-19.4 done and gated (341 passed). Independent review (fresh stateless research subagent): NO FINDINGS. Historical root cause before the fix: `SelfHealingLoop.run_loop` incremented `healing_attempts` on the harness-failure branch before checking `healing_attempts > self.max_retries`, whereas gate failures check `healing_attempts >= self.max_retries` before incrementing. On exhaustion, harness failures report `max_retries + 1` (e.g. 6 with limit 5, or 2 with limit 1) instead of `max_retries`.

- [x] **19.1 Red regression tests.** Files: `tests/test_verification.py`. Add tests asserting exact `healing_attempts` and call counts when retries are exhausted by harness failures alone, gate failures alone, and mixed gate/harness failures with `max_retries=1`, `max_retries=2`, and `max_retries=0`. Proof: red test exits 0 on `python3 scripts/sdlc_check.py --red` showing `assert healing_attempts == 1` fails with actual value 2.
- [x] **19.2 Consistent retry budget check.** Files: `dark_factory/verification/healing.py`. Check `if healing_attempts >= self.max_retries:` before incrementing `healing_attempts` in the harness-failure branch, matching the gate-failure branch. Proof: all new and existing verification tests pass.
- [x] **19.3 Docs and changelog.** Files: `CHANGELOG.md` (`### Fixed`), `spec.md`, `docs/sdlc/spec.md`. Proof: `scripts/sdlc_check.py` docs and changelog checks pass.
- [x] **19.4 Independent review**, then full gate. Proof: fresh subagent review with no open findings and `scripts/sdlc_check.py` exiting 0.

Risks and open questions: (1) Does any existing test or dashboard expect `healing_attempts > max_retries`? No, grep confirmed all existing tests assert `healing_attempts <= max_healing_attempts` or specific expected integers. (2) Does this change the number of repair attempts? No: with `max_retries = N`, the model still gets 1 initial attempt plus up to N repair attempts (N + 1 total model calls if all fail).

### DF-LIVE-05 backend exception handling and campaign resilience (spec: §3.7 "Campaign resilience and backend error handling")

Status: 20.1-20.4 done and gated (350 passed, 7 deselected). Stage 6 independent review identified 4 findings (1 HIGH, 2 MEDIUM, 1 LOW); all 4 were reproduced with failing red tests and resolved test-first. Historical root cause before the fix: `run_scenario` and `run_eval` did not catch exceptions raised by `engine.execute_run()` (such as `LocalEngineOfflineError` on Prism 503 / engine disconnect), causing unhandled exceptions to crash the campaign without saving the `EvalReport`, losing completed run results and aborting subsequent attempts.

- [x] **20.1 Red regression tests.** Files: `tests/test_eval_runner.py`, `tests/test_cli.py`. Add tests for: (a) single backend exception on an attempt is captured in `EvalRunResult` (`converged=False`, `status="FAILED"`, `error` populated) and persisted in `EvalReport`; (b) bounded continuation: transient backend error allows subsequent attempts to run; 3 consecutive backend errors halt further attempts in the scenario/campaign; (c) CLI `cmd_eval` returns exit code 1 when backend exceptions occur, while still saving the report and printing the summary table; (d) `KeyboardInterrupt` / `SystemExit` propagates and is not swallowed as a normal failure. Proof: red tests fail on current code with unhandled `LocalEngineOfflineError` instead of structured report / exit code.
- [x] **20.2 Campaign resilience and bounded continuation.** Files: `dark_factory/eval/runner.py`, `dark_factory/cli.py`. Add `error: str | None = None` to `EvalRunResult`. In `run_scenario`, catch `Exception` from `execute_run` (excluding `KeyboardInterrupt`/`SystemExit`), extract status/notes/error, append `EvalRunResult`. Implement `MAX_CONSECUTIVE_BACKEND_ERRORS = 3` bounded continuation across attempts. In `cmd_eval`, ensure `save_report` is called on partial/final report, summary is printed, and return exit code 1 if any backend error occurred.
- [x] **20.3 Docs and changelog.** Files: `CHANGELOG.md` (`### Fixed`), `spec.md`, `docs/sdlc/spec.md`. Proof: `scripts/sdlc_check.py` docs and changelog checks pass.
- [x] **20.4 Independent review**, then full gate. Proof: fresh subagent review reported 4 findings (completed scenario attempts discarded on interruption, scenario-local error counter, missing tests, vacuous truth on empty summary); all reproduced red-first, fixed, and `scripts/sdlc_check.py` exited 0 (350 passed, 7 deselected).

Risks and open questions: (1) Does `save_report` overwrite previous reports if timestamps collide? No, timestamps include microseconds (`%Y%m%dT%H%M%S%fZ`). (2) What if `execute_run` crashes before creating `manifest` (e.g. sandbox creation failure)? `run_scenario` catches the exception and constructs a fallback `EvalRunResult` with status `"FAILED"` and the exception message. (3) Will `KeyboardInterrupt` lose completed runs? No: `run_eval` catches `KeyboardInterrupt`, saves completed results to `EvalReport`, and re-raises.

### DF-LIVE-06 scenario acceptance and patch-scope enforcement (spec: §3.7 "Scenario acceptance and patch-scope enforcement")

Status: 21.1-21.4 done and gated (357 passed, 7 deselected). Independent review reported NO FINDINGS. Historical root cause before the fix: eval scenarios lacked explicit `target_files` and `protected_paths`, allowing models to modify non-target files without failing the patch-scope gate, and scenario test suites lack edge-case coverage (e.g. `n <= 1` in `primes` allows invalid implementations that raise ValueError or return True on 0/1/negatives to pass).

- [x] **21.1 Red regression tests.** Files: `tests/test_eval_scenarios.py`, `tests/test_eval_runner.py`.
  - In `tests/test_eval_scenarios.py`:
    - Assert that every registered `EvalScenario` has non-empty `target_files` and `protected_paths`, and that all declared paths exist in the scaffolded repo.
    - Assert that the strengthened test suites in `build_primes_repo` (negatives, 0, 1 return False; primes return True; composites return False), `build_calculator_repo` (zero, negatives, unknown op raises ValueError), `build_textutils_repo` (tabs/newlines collapsed, casing preserved), and `build_csvparse_repo` (empty fields, trailing comma, single field) fail on baseline broken code and pass on correct implementations.
  - In `tests/test_eval_runner.py`:
    - Assert that `run_scenario` propagates `target_files` to `TaskSpec`.
    - Assert that an eval run with an out-of-scope file (outside `scenario.target_files`) fails with `status == "FAILED"` and `reason: out_of_scope_patch`.
  Proof: red tests fail on current code with missing `target_files` attribute / assertion failure.
- [x] **21.2 Scenario target files, gate protection, and edge-case test suites.** Files: `dark_factory/eval/scenarios.py`, `dark_factory/eval/runner.py`.
  - In `dark_factory/eval/scenarios.py`:
    - Add `target_files: list[str] = field(default_factory=list)` to `EvalScenario`.
    - Set `target_files` and `protected_paths` on all scenarios (`primes`: `["primes.py"]` / `["test_primes.py"]`; `calculator`: `["calculator.py", "cli.py"]` / `["test_calculator.py"]`; `textutils`: `["text_utils.py"]` / `["test_text_utils.py"]`; `csvparse`: `["csvparse.py"]` / `["test_csvparse.py"]`).
    - Update `build_*_repo` test suites with edge-case and boundary coverage.
    - Clarify task prompts to specify boundary behaviors.
  - In `dark_factory/eval/runner.py`:
    - Pass `target_files=list(scenario.target_files)` and `protected_paths=list(scenario.protected_paths)` to `TaskSpec`.
  Proof: all new and existing tests pass.
- [x] **21.3 Docs and changelog.** Files: `CHANGELOG.md` (`### Added` and `### Fixed`), `spec.md`, `docs/sdlc/spec.md`. Proof: `scripts/sdlc_check.py` docs and changelog checks pass.
- [x] **21.4 Independent review**, then full gate. Proof: fresh subagent review reported NO FINDINGS and `scripts/sdlc_check.py` exited 0 (357 passed, 7 deselected).

Risks and open questions: (1) Does strengthening scenario tests break `tests/test_e2e.py`? No: `_FIXED_PRIMES` already implements `if n < 2: return False` and composite checking; we will verify all end-to-end fixtures against the strengthened tests. (2) Does `target_files` propagation prevent the model from creating helper files? Yes: eval scenarios evaluate self-contained fixes within the declared target files. Creating unexpected files is considered an out-of-scope patch.

### Diagnostic and benchmark coverage gaps (not yet confirmed product defects)

- [x] **DF-LIVE-06 — weak green scenarios and extraneous patch paths (P2 investigation).** (Done as DF-LIVE-06a and Phase 21).
- [x] **DF-LIVE-07 — retain response metadata and separate reasoning diagnostics (P2 investigation).** (Done as Phase 18 alongside DF-LIVE-02/03). Raw `no-think-512.json` reports stop with 110 tokens, empty content and a Python block in reasoning_content; default and explicit-budget probes end with length. This is not proof that /no_think solves the problem or that Prism misclassified the raw generation: owner triage requires raw token/text and template reproduction. Files to inspect: `dark_factory/harness/local_coder.py`, `dark_factory/harness/base.py`, `dark_factory/storage/evidence.py`, corresponding harness/storage tests, `spec.md`; link a confirmed upstream finding to the Prism backlog rather than assigning ownership from empty content alone. Proof: preserve sanitized finish reason, effective output/context limits and empty-content/reasoning status so eval diagnostics explain failures without executing reasoning. Preserve minimal exact prompts and model/runtime revisions for cross-project reproduction.

These entries supersede the shorter model-routing/output-budget notes in Phase 16, which remain historical evidence. Product fixes were implemented under the subsequent authorizations below; backlog realignment makes documentation changes only.

## Priorities (realigned 2026-10-04; release on hold)

The current backlog table is the authoritative order: BL-01 re-review, BL-02 post-parser benchmark, BL-03 remaining live proofs, BL-04 real tasks, BL-05 controlled failures, then integrity/configuration work and deferred improvements. Existing task authorizations remain valid; re-ranking does not authorize new work.

Historical waves 1–2 delivered DF-LIVE-01…07; Phase 23 delivered DF-LIVE-08. Phase 22 delivered strict audit parsing and isolation-claim reconciliation. Their final review/live states remain separate in the table and owning phases. Mistral's 2026-10-04 0/12 rerun included the BOS fix but preceded DF-LIVE-08; Qwen/Phi probes are not full repeat campaigns. Phase 15 tuning waits for adequate post-fix measurements. Release remains last, with no presumed target version.

## Prism cross-project analysis (2026-10-04)

Read-only analysis of `../03-prism-local/plan.md`, `spec.md` and `prism/server.py`; nothing was changed in the Prism repository. Question:
which planned or in-flight Prism changes affect the factory roadmap, and which DF-LIVE items are really Prism's.

**Prism items that matter to the factory**

| Prism item | State (2026-10-04) | Effect on the factory |
|---|---|---|
| Phase 24, BOS token (DF-PRISM-20261003-01) | implemented, reviewed, gate green; uncommitted | The 2026-10-03 Mistral 0/12 predates BOS; the 2026-10-04 rerun includes BOS but predates DF-LIVE-08. BL-02 is the post-parser benchmark; do not merge these cohorts. Qwen3 and Phi were not affected by this fix. |
| Phase 3 backlog: unknown template families fall back to ChatML | open | Mistral `[SYSTEM_PROMPT]`, Llama 2 and Gemma without template still get ChatML. Keep in mind when interpreting any new 0/N result. |
| `prism unload` (spec P22) | done, reviewed | Replaces the manual `keep_alive=0` / endpoint calls in `run_native.py`. Use it between models in the repeat campaign. |
| Phase 19b, Ollama load guard | 19b.1–5 implemented/gated and hardware-tested; 19b.6 independent review open in upstream plan | Directly related to DF-LIVE-01: the historical stray Qwen load took ~9 GB before routing was fixed. DF-LIVE-01 is delivered; retain the guard as a served-runtime prerequisite. |
| Reasoning separation (Phase 2) | done | Prism already returns `reasoning_content` separately. DF-LIVE-07 is factory-side only (retain and never execute it). |
| `max_tokens` default 512 and clamp to `window - prompt` with `finish_reason=length` | documented behavior | Historical DF-LIVE-02/03 were factory defects; Phase 18 now sends the budget and retains the reason. Do not file those fixed defects against Prism. |
| Phase 25, fast-fail `prism pull` | implemented and reviewed; upstream gate recorded green | No factory impact. Only relevant when adding more models to the comparison. |
| Backlog: ONNX-vs-Ollama A/B with a coding model, quality not only speed | open | Related to BL-02/03, but an ONNX-versus-Ollama A/B is a separate deferred campaign. Run it **through the factory benchmark** (same scenarios, same gates) instead of building a second harness. |
| Phase 27: warn when a CPU export runs on CUDA | 27.1–5 complete; review findings resolved test-first; upstream gate recorded green | The Phase 16 comparison excluded CPU exports by hand; a Prism warning would make that check automatic. Low priority. |
| Phase 3 "Outward actions" (issues #5/#6, `0.2.x` release), U1 distribution | operator only / on hold | Independent of the factory. Do not couple the factory's undecided next version to Prism's release. |

**Current dependency order and authorization**

1. Factory integration fixes are implemented; outstanding re-review is BL-01.
2. Phase 16 records P24 BOS served and P23 guard present during the 2026-10-04 rerun. Upstream artifacts are development evidence, not proof of today's running server revision; reconfirm served revisions and model residency before BL-02. A commit/release is not a runtime prerequisite.
3. Run BL-02 after that confirmation and BL-01. Use the existing unload interface; no inference-service restart, upstream edits, commits or releases are authorized here.
4. BL-03 retains Qwen/Phi probes and remaining proofs separately; larger comparison campaigns require their recorded scope authorization. BL-04/05 complete operational validation before BL-10 threshold assessment.

Historical operator decisions (2026-10-04): initial rerun scope was Mistral only with the BOS fix and Ollama guard required. That rerun completed before DF-LIVE-08; this does not authorize a new campaign. Upstream Phase 19b.6 review and U1 distribution remain upstream-owned; neither is silently closed by factory measurements.

---

## Phase 1: Foundation & Domain Contracts
- [x] Initialize repository environment: `pyproject.toml`, `requirements.txt`, `.gitignore`.
- [x] Define immutable domain contracts in `dark_factory/domain/types.py`:
  - `TaskSpec`
  - `RunStatus`
  - `VerificationStep`
  - `StepExecution`
  - `EvidenceManifest`
- [x] Define error hierarchy in `dark_factory/domain/errors.py`.
- [x] Unit tests for domain contracts (`tests/test_domain.py`).

---

## Phase 2: Sandbox Execution Fabric
- [x] Implement `Sandbox` base protocol in `dark_factory/sandbox/base.py`.
- [x] Implement `GitWorktreeSandbox` in `dark_factory/sandbox/worktree.py`:
  - `git worktree add --detach`
  - Structured argv command execution with timeouts and sanitized environment
  - File reading/writing
  - `git diff` patch extraction
  - Idempotent cleanup (`git worktree remove --force`)
- [x] Unit tests for `GitWorktreeSandbox` (`tests/test_sandbox.py`).

---

## Phase 3: Local Agent Harness (Multi-Engine Router)
- [x] Implement `AgentHarness` base class in `dark_factory/harness/base.py`.
- [x] Implement `LocalCoderHarness` in `dark_factory/harness/local_coder.py`:
  - Connect to local Ollama (`http://localhost:11434`) and Prism (`http://127.0.0.1:5272/v1`)
  - Support model selection (`qwen2.5-coder:14b` for complex generation, `7b` / Prism for fast edits)
  - Telemetry capture (prompt tokens, completion tokens, latency, tokens/sec)
  - Spend tracking ($0.00 cloud token cost)
- [x] Unit tests for harnesses (`tests/test_harness.py`).

---

## Phase 4: Deterministic Verification & Self-Healing
- [x] Implement `VerificationRunner` in `dark_factory/verification/runner.py`:
  - Sequential gate execution
  - Non-zero exit code detection
  - Timeout enforcement
- [x] Implement `SelfHealingLoop` in `dark_factory/verification/healing.py`:
  - Failure trace extraction (stdout/stderr + compiler errors)
  - Feedback prompt generation for the local model
  - Up to `N` repair iterations
- [x] Unit tests for verification and healing (`tests/test_verification.py`).

---

## Phase 5: Durable Workflow Engine (Option C Architecture)
- [x] Implement stateless workflow activities in `dark_factory/orchestrator/activities.py`:
  - `activity_create_sandbox`
  - `activity_execute_task_and_verify`
  - `activity_preserve_evidence`
  - `activity_apply_patch`
  - `activity_cleanup_sandbox`
- [x] Implement SQLite schema and state manager in `dark_factory/orchestrator/engine.py`:
  - Atomic state transitions (`WAL` mode)
  - Durable run ledger (`.factory/factory.db`)
  - Crash recovery & cleanup of dangling sandboxes
- [x] Unit tests for state machine & recovery (`tests/test_orchestrator.py`).

---

## Phase 6: Evidence Locker & Storage
- [x] Implement evidence writer in `dark_factory/storage/evidence.py`:
  - Write `diff.patch`
  - Write `manifest.json`
  - Write `transcript.log`
  - Write `telemetry.json`
- [x] Unit tests for evidence storage (`tests/test_storage.py`).

---

## Phase 7: CLI & Human-in-the-Loop Operator Interface
- [x] Implement CLI commands in `dark_factory/cli.py`:
  - `dark-factory doctor` (health check for Ollama, Prism, GPU, Git)
  - `dark-factory run` (task submission with live transition streaming)
  - `dark-factory list` (runs list)
  - `dark-factory describe RUN_ID` (manifest, gate results, and patch)
  - `dark-factory review RUN_ID --approve [--branch <name>]` (apply and commit patch)
  - `dark-factory review RUN_ID --reject [--note <reason>]` (reject and archive)
  - `dark-factory recover` (recover crashed runs and prune dead sandboxes)
- [x] Create executable wrapper `bin/dark-factory`.
- [x] Full end-to-end integration test (`tests/test_e2e.py`).
- [x] Verification profiles in `profiles/default.toml` and `profiles/python.toml`.

---

## Phase 8: Hardening & Security Audit Remediation

### 8.1 Critical Verification & State Safety (Priority 1)
- [x] **Reject Zero Verification Gates**: If no verification steps are detected or provided, abort run with an error unless an explicit `--no-verify` flag is set.
- [x] **Protect `AWAITING_REVIEW` in `recover()`**: Exclude `AWAITING_REVIEW` runs from being marked as `FAILED` during engine recovery; only target truly dead runs; run `git worktree prune`.
- [x] **Fix Self-Healing Prompt & Telemetry**:
  - Preserve original `initial_prompt` alongside the error trace in repair iterations.
  - Properly aggregate tokens and durations across all attempts instead of overwriting `last_telemetry`.
  - Emit live status callbacks for `VERIFYING` and `SELF_HEALING`.
  - Treat missing file blocks as a counted healing retry rather than immediate failure.

### 8.2 Gate Tamper Resistance (Priority 2)
- [x] **Immutable Verification Gates**:
  - Restore gate definitions from `base_rev` before running verification.
  - Detect when agent touches protected test files and revert them so verification evaluates true application code.
  - Reject/warn patches that tamper with verification gates unless `--allow-gate-edits` is explicitly set.

### 8.3 Safe Host Application in `review --approve` (Priority 3)
- [x] **Safe Patch Application**:
  - Validate patch with `git apply --check` before creating branches or applying.
  - Store and verify SHA256 digest of `diff.patch` recorded at verification time.
  - Stage only files explicitly modified by the patch (never indiscriminate `git add .`).
  - Graceful rejection if patch does not apply cleanly.

### 8.4 Execution & Environment Robustness
- [x] **Sanitize Process Environment**:
  - Scrub factory's `VIRTUAL_ENV`, `PYTHONPATH`, and git variables from child process environments.
- [x] **Robust CLI Parsing**:
  - Use `shlex.split` for `--test-cmd` arguments to preserve quotes and flags.
- [x] **Engine Fallback Clarity**:
  - Distinguish 404 (missing model) from connection errors in Ollama client before falling back to Prism.
- [x] **Exception Preservation**:
  - Save full traceback and evidence transcript when unhandled exceptions occur in `execute_run`.

### 8.5 Code Hygiene
- [x] Ensure SQLite connection closing with `contextlib.contextmanager` and auto-close.
- [x] Single atomic transaction for status transition + operator notes in `review_run`.

---

## Phase 9: Packaging & Release (GitHub & PyPI)

### 9.1 Package Build & Metadata Validation
- [x] Configure package metadata in `pyproject.toml` with `name = "local-dark-factory"`.
- [x] Create `dark_factory/__init__.py` with `__version__ = "0.1.0"`.
- [x] Validate wheel and source distribution build locally via `python3 -m build`.
- [x] Verify distribution packages with `twine check --strict dist/*`.
- [x] Add standard MIT `LICENSE` file.

### 9.2 GitHub CI & Automation Workflows
- [x] Add `.github/workflows/ci.yml`: automated matrix tests (`pytest`) and lint (`ruff`) on Python 3.11 and 3.12.
- [x] Add `.github/workflows/publish.yml`: automated release workflow with PyPI Trusted Publishing (OIDC).

### 9.3 GitHub Remote & Repository Setup
- [x] Create GitHub repository `senssei/local-dark-factory`.
- [x] Push local `main` branch and verify remote repository.
- [x] Tag and publish release `v0.1.0` with assets on GitHub.

### 9.4 PyPI Publication
> **ON HOLD, DEPRIORITIZED (operator decision, re-ranked 2026-10-02):** no release for now; lowest priority, see "Priorities". Stale text: `v0.1.0` is already tagged on GitHub and the next version is undecided.

- [ ] Configure PyPI Trusted Publisher for repository `senssei/local-dark-factory`.
- [ ] Publish the operator-selected release to PyPI (version undecided; historical GitHub v0.1.0 is not proof of PyPI publication).
- [ ] Verify clean installation in isolated environment: `pip install local-dark-factory`.

---

## Phase 10: Post-Release Audit Remediation

**Status:** historical implementations/commits and gates are recorded in the subsections. §10.7 documentation alignment and its context-bloat follow-up are delivered (§10.15); review of later fixes remains BL-01. Open work: §10.3 compatibility decision, §10.5 integrity/configuration/coverage and deferred process isolation, plus release on hold. The former 145-test summary is historical, not the current gate count.

Source: code audit of `main` @ `73fb622`. Every fix ships with a regression test written first (red → green).
Release is **on hold** (operator decision): Phase 9.4 (PyPI) and the version bump stay open until the operator schedules a release; the next version is undecided and will be chosen by the operator at release time.

### 10.1 Verification Integrity (Priority 1)
- [x] **Fence-safe file block parser** (`harness/local_coder.py`): a `` ```file:`` block must not be truncated by inner
  code fences (e.g. `README.md`, docstrings). Parse with fence-length matching / line-anchored closing fence.
- [x] **Fix `lstrip("./")` gate-path bug** (`verification/runner.py`): use `removeprefix`, so `.github/...` and `.venv/...`
  are not mangled into `github/...` / `venv/...`.
- [x] **Protect test-runner configuration** by default: `pyproject.toml`, `setup.cfg`, `conftest.py` (any depth),
  `.coveragerc`, `sitecustomize.py`, `usercustomize.py` in `detect_default_gate_paths()`.
- [x] **Block sandbox writes to `.git*`** (`sandbox/worktree.py`): `write_file` must reject `.git` / `.git/**`
  (worktree `gitdir:` pointer hijack).
- [x] **No-op runs are not successes**: a passing run with an empty diff ends `FAILED` (reason `empty_patch`), never
  `AWAITING_REVIEW`.

### 10.2 Patch Extraction & Application (Priority 2)
- [x] **Deterministic `get_diff`**: `--no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ --binary`; check
  `git diff` / `git add -N` exit codes and raise `SandboxError` instead of returning a silent empty patch.
- [x] **Robust `parse_patch_files`**: handle paths with spaces and quoted (C-escaped) paths by parsing the `diff --git a/X b/X` header;
  `get_diff` passes `--no-renames` so every file appears once; staging uses `--literal-pathspecs`.
- [x] **Atomic `activity_apply_patch`**: on failure after `checkout -b`, return to the original branch and delete the
  new branch; wrap `CalledProcessError` in `DarkFactoryError`; refuse to apply on a dirty tree touching the same files.

### 10.3 Lifecycle & Durability (Priority 3)
- [x] **Run deadline**: enforce `TaskSpec.timeout_minutes` across harness + verification; terminal status `TIMED_OUT`.
- [x] **Cancellation**: `KeyboardInterrupt` / `SystemExit` → status `CANCELLED`, sandbox cleaned, evidence saved.
- [x] **Evidence before status**: persist `diff.patch` + `manifest.json` *before* the DB transition to `AWAITING_REVIEW`,
  so a crash can never leave an evidence-less review run.
- [ ] Remove dead `TaskSpec` fields (`agent`, `metadata`) or wire them up; drop the redundant `.git` check in
  `GitWorktreeSandbox.create`. **BL-11 / deferred:** these fields are public API of the historical `0.1.0`; retain them until the operator decides compatibility and version policy. Files: `dark_factory/domain/types.py`, `tests/test_domain.py`, `spec.md` and mirrored spec; proof: existing serialized task compatibility and explicit tests for the approved field semantics. Removing the redundant sandbox check is separate low-priority hygiene, not permission to remove API fields; files: `dark_factory/sandbox/worktree.py`, `tests/test_sandbox.py`; proof: repository validation and idempotent creation/cleanup still pass.

### 10.4 Release Hygiene
- [x] Update `spec.md` (§2, §3.1, §3.2, §3.3, §3.4) and `CHANGELOG.md` (`[Unreleased]`; next release label remains undecided).
- [x] CI: add `ruff format --check` and `mkdocs build --strict` jobs.
- [ ] **On hold, lowest priority (see "Priorities"):** bump version (`pyproject.toml`, `dark_factory/__init__.py`), rename `[Unreleased]` in `CHANGELOG.md`, tag. Operator gate; do not start without an explicit go.

### 10.5 Backlog (release scheduling undecided)

- [ ] **BL-06 Independent patch integrity anchor.** Files: `dark_factory/orchestrator/engine.py`, `tests/test_orchestrator.py`, `spec.md` and mirrored spec. Record `patch_sha256` in SQLite events and verify in `review_run`; the neighboring manifest is not an independent anchor. Proof: regressions for patch+manifest tampering, missing anchor and unchanged valid evidence; existing journal compatibility and recovery. Policy for legacy runs without an anchor must be specified and approved before implementation.
- [ ] **Deferred process isolation (linked to §11.B).** Files: `spec.md`, mirrored spec, `plan.md`; future driver/tests only after a separate decision. Current worktree/host-process limitation is documented and reproduced in Phase 22. `bwrap`/no-network remains a research proposal; container sandboxing is outside current intent. Proof for any future implementation: explicit filesystem/network boundary tests and idempotent cleanup, not merely a worktree test.
- [ ] **BL-09 Coverage baseline and targeted gaps.** Files: `tests/test_harness.py`, `tests/test_cli.py`, `plan.md`. Measure both modules from the same fresh deterministic run; the old ~55% estimate is obsolete and cached CLI-only data is not a comparable baseline. Proof: reproducible module/branch report and tests for uncovered meaningful error paths; retain ≥85% as the historical target, never substitute coverage for behavior checks.
- [ ] **BL-07 Gate discovery against base revision.** Files: `dark_factory/cli.py`, `tests/test_cli.py`, `spec.md` and mirrored spec. Proof: selected base contains gates absent from the dirty host tree, host-only gates absent from the base are ignored, invalid base gives a clear failure, explicit `--test-cmd` retains precedence; inspect via structured git argv without modifying host files.

---

### 10.6 Post-Implementation Adversarial Audit — Code Defects

**Status: done (2026-09-28).** Source: adversarial review of the uncommitted `git diff` (≈968 / -145 LOC,
20 files). Items below were **introduced-or-revealed-by** the Phase 10 changes and shipped with the
`0.1.1` cut alongside 10.1–10.4. Every item shipped with a regression test written first (red → green).

- [x] **Hard-bound run deadline** (`verification/runner.py:115-122`). The clamp
  `int(deadline - time.monotonic())` truncates toward zero and is then floored by `max(1, ...)`; the next gate
  still gets **≥1 second** even when the deadline has already passed. Before invoking the next `sandbox.execute`,
  short-circuit with `if deadline is not None and time.monotonic() >= deadline: return VerificationOutcome(passed=False, ..., failed_step=StepExecution(step_id="deadline", exit_code=124, ...))` (or a dedicated `VerificationTimeoutError`). **Test:** a step past deadline returns immediately, with `exit_code == 124` and no subprocess invocation.

- [x] **`CANCELLED` preserves `diff.patch`** (`orchestrator/engine.py`). The
  `except (KeyboardInterrupt, SystemExit)` branch now routes through `activity_preserve_evidence` with
  `_best_effort_diff(sandbox)` (falling back to a plain `locker.save_run` only when the sandbox was never
  created), so a cancelled run keeps the same evidence shape as any other terminal state. **Test:**
  `test_cancelled_run_preserves_partial_diff`.

- [x] **Reconciliation covers the review window** (`orchestrator/engine.py`, `_reconcile_review_completeness`
  + `recover()`). `recover()` now also scans rows already marked `APPROVED`/`REJECTED` and flags any whose
  on-disk manifest never caught up (crash between `transition_status` and the final `locker.save_run` in
  `review_run`) as `FAILED` with an explanatory note — the patch may already be committed, so the safe move
  is to surface the inconsistency rather than re-derive or re-apply it. **Tests:**
  `test_recover_flags_approved_transition_that_never_completed`,
  `test_recover_leaves_genuinely_completed_approval_alone`.

- [x] **Derive terminal-status list from the `RunStatus` enum** (`orchestrator/engine.py`). Replaced the
  hardcoded `WHERE status NOT IN (...)` string list with a module-level
  `_NON_ORPHAN_STATUSES = {s.value for s in RunStatus if s.is_terminal} | {AWAITING_REVIEW}`, used by
  `recover()` via a parameterized query. **Test:** `test_non_orphan_statuses_derived_from_run_status_enum`.

- [x] **Locale-safe git stderr/stdout** (`orchestrator/activities.py:_git`,
  `sandbox/worktree.py` — all `text=True` subprocess/Popen call sites). Added `errors="replace"` throughout
  so a non-ASCII path outside the host locale decodes instead of raising `UnicodeDecodeError` mid-operation.
  **Tests:** `test_git_helper_subprocess_calls_are_locale_safe`, `test_worktree_git_calls_are_locale_safe`.

- [x] **Tighten `restore_paths` pathspec handling** (`sandbox/base.py:Sandbox.restore_paths`). Documented
  the contract: implementations must honor `:(glob)` pathspec magic, not just literal filesystem paths, or
  gate protection silently stops covering nested files (`GitWorktreeSandbox` already does, via passing the
  pathspec straight through to `git diff`/`git checkout`). **Test (doc-level):**
  `test_sandbox_restore_paths_contract_documents_glob_pathspecs`.

---

### 10.7 Post-Implementation Adversarial Audit — Documentation & Operations Alignment

**Status:** implemented and gate-green 2026-09-30 (150 tests, ruff, mkdocs --strict, changelog); uncommitted; all listed alignment items are delivered; `_build_context` was subsequently fixed in §10.15, superseding the earlier document-only decision. Post-review fixes await BL-01 re-review. Review: independent subagent, 10 findings (7 fixed: 1-7; 3 not defects or out of scope: 8-10); fixes verified by tests and the gate only, not re-reviewed. Decisions 2026-09-30 (Foundry: remove; Docker: non-goal; Temporal: seam wording; <100ms: drop). Plan
approved by the operator, 2026-09-30 (including the `intent.md` edits). **Invariant:** `docs/sdlc/{intent,spec,claude,agents}.md` are byte-identical
copies of the root files and must be edited together. One new test module, `tests/test_docs_alignment.py`, guards the
grep-able decisions (red first); the remaining items are prose proven by `mkdocs build --strict`.

**Source:** adversarial review of `docs/*.md`, `intent.md`, `spec.md`, `README.md` against
`dark_factory/` + `pyproject.toml`. Items below are **doc / operational** drift; they do **not** block
`0.1.1` but should land before the next release that touches the affected surfaces.

- [x] **Foundry Local: remove references** (decided by the operator 2026-09-30: docs-only). Harness stays Ollama → Prism.
  Files: `spec.md:164`, `docs/local-inference.md:25`, `README.md:46`, `CLAUDE.md:74,76`, `AGENTS.md`,
  `dark_factory/harness/local_coder.py:20`, `dark_factory/domain/types.py:97`, `dark_factory/domain/errors.py:25`
  (docstrings/messages only), plus the `docs/sdlc/{spec,claude,agents}.md` copies. `foundry-coder` stays an operator skill,
  not a factory backend. **Test:** `tests/test_docs_alignment.py::test_no_foundry_backend_references`.

- [x] **DockerSandbox: move to Non-Goals** (decided 2026-09-30). **Edits `intent.md` (an invariant): needs explicit
  operator approval of the new text.** Files: `intent.md:39`, `spec.md:151`, `docs/architecture.md:60` and the
  `docs/sdlc/{intent,spec}.md` copies. **Test:** `tests/test_docs_alignment.py::test_docker_sandbox_is_non_goal`.

- [x] **Temporal Option C: reword as a seam** (decided 2026-09-30). Text: "Option C is a forward-looking seam; no
  Temporal worker is registered in this release." Files: `docs/architecture.md:3`,
  `dark_factory/orchestrator/activities.py:1-4` (docstring), `intent.md:42` (optional adapter wording, same approval as
  the DockerSandbox `intent.md` edit) and `docs/sdlc/intent.md`. **Test:** `tests/test_docs_alignment.py::test_temporal_is_described_as_seam`.

- [x] **Expose `--timeout-minutes`, `--storage-dir`, `--ollama-url`, `--prism-url` on `dark-factory run`**
  (done as part of 10.8, which needed `--storage-dir`/`--ollama-url` to make the CLI e2e test
  deterministic). `list`/`describe`/`review`/`recover` also gained `--storage-dir` for consistency.
  `--harness` and `--protected-paths` remain tracked in Phase 11 (protocol-level decisions). **Test:**
  `test_cli_run_respects_timeout_minutes_and_storage_dir`.

- [x] **Refresh `docs/cli.md:118-122` (`recover`)** (verify against `_reconcile_orphan` in `orchestrator/engine.py`; proof is
  `mkdocs build --strict`, no unit test) so the description matches `_reconcile_orphan`: it
  now adopts evidence-backed final statuses; only runs whose manifest is unreadable are escalated to
  `FAILED`. Update example output too.

- [x] **Document the auto-protected paths list** (`docs/verification-gates.md`,
  `dark_factory/verification/runner.py:13-24`). Today the default list includes `:(glob)**/conftest.py`,
  `sitecustomize.py`, `usercustomize.py`, plus `.coveragerc`. Users reading the docs see only the old
  `tests / test.sh / pytest.ini / tox.ini` set.

- [x] **Architecture-layer responsibilities** (`docs/architecture.md:52-78`). The mermaid and the
  prose currently place "Gate Restoration" inside the Sandbox layer's bullet list, but in code that
  responsibility is the `VerificationRunner`'s call into `Sandbox.restore_paths`. Reassign the
  responsibility bullets so the diagram and code match.

- [x] **`doctor` shows the offline path** (`docs/getting-started.md:55-66`). The example output is the
  happy path only; add a second example for "Ollama-only / no Prism" so the documented expectation
  matches what the operator sees when one backend is down.

- [x] **Apple Silicon / Metal compatibility matrix** (`docs/local-inference.md`). `prism` is
  DirectML/CUDA only; there is no `mlx` / Apple Foundation Models fallback. Add a small table clarifying
  which backend supports which GPU family.

- [x] **Drop the unverified "<100ms" worktree claim** (decided 2026-09-30: drop, no benchmark). Files: `README.md:41`,
  `intent.md:38`, `spec.md:144`, `docs/index.md:20,36`, `docs/architecture.md:60`, `docs/getting-started.md:87`,
  `dark_factory/sandbox/worktree.py:20` (docstring), `docs/sdlc/{intent,spec}.md`. **Test:**
  `tests/test_docs_alignment.py::test_no_unverified_performance_claims`.

- [x] **`detect_default_gate_paths()` can't tell a lint/type-check gate's *target* file from a *test/config*
  file** — found in 10.12, **fixed in 10.13** (see below), no longer open.

- [x] **(delivered in §10.15, 2026-10-02)** **`LocalCoderHarness._build_context()` auto-detects and inlines *any* file path mentioned in the task
  prompt, in full, with no size cap — including files mentioned only for reference/explanation, not files
  the agent is meant to edit.** Found 2026-09-29 during real dogfooding on this repo itself (not a
  synthetic eval scenario): a task asking to update `docs/cli.md`'s `recover` section, whose prompt also
  named `_reconcile_orphan()` in `dark_factory/orchestrator/engine.py` for context, caused the harness's
  regex path-scanner (`_build_context`, `re.findall(r"[\w/\.-]+\.[a-zA-Z0-9]+", task_prompt)`) to inline the
  **entire 519-line `engine.py`** alongside the 178-line `docs/cli.md`. With both files in context,
  `qwen2.5-coder:14b` abandoned the edit task entirely and produced a prose *explanation* of the
  `DurableEngine` class instead — zero `` ```file: `` blocks, `harness_result.success=False` every one of
  4 attempts (1 initial + 3 healing), `manifest.status=FAILED` with a 0-byte patch and no verification gates
  ever reached (the harness-parse-failure branch never gets to run verification). **Reproduced
  deterministically**: calling `_call_model` directly with just `docs/cli.md` in context succeeded 4/4
  times; adding `engine.py` to context reproduced the exact same derailment on the first try. Real run:
  `run-20260929-200445-95ae65`. **Operator decision (2026-09-29): document only, do not fix in this
  session** — a fix would need to cap/omit large auto-detected reference files (e.g. skip inlining a file
  above some line/byte threshold unless it's also named in `target_files`, or otherwise distinguish
  "files to edit" from "paths mentioned for context") without breaking legitimate small-file context
  auto-detection that the rest of this session's real-model tests already depend on. **Practical workaround
  for operators today**: describe referenced behavior in prose rather than naming the file path, or pass
  `target_files` explicitly instead of relying on prompt-text auto-detection.

---

### 10.8 Pre-Release Blocker — End-to-End Coverage Gaps

**Status: done (2026-09-28).** Source: operator review of `tests/test_e2e.py`. The single existing e2e
test (`test_full_factory_vertical_slice`) only exercised the happy path — `AWAITING_REVIEW` → `APPROVED`
with a deterministic stub harness — so none of the error/lifecycle paths added or touched by Phase 10 had
any full-stack coverage, only unit-level coverage in `test_orchestrator.py`. **Operator decision: this
blocks `0.1.1`**, ranked ahead of 10.7 (doc/ops alignment, non-blocking).

- [x] **e2e coverage for error/lifecycle paths.** `tests/test_e2e.py` now has one full-stack scenario per
  terminal path, each going through the real `DurableEngine.execute_run` (only the harness is a test
  double): `test_e2e_run_deadline_produces_timed_out`, `test_e2e_cancellation_preserves_partial_diff`,
  `test_e2e_empty_patch_ends_failed_not_awaiting_review`, `test_e2e_self_healing_repairs_failing_verification`
  (`healing_attempts == 1`, repaired code lands after approve), and
  `test_e2e_recover_after_crash_completes_full_review_flow` (recover → review → approve → tests green on
  the target repo, not just the DB row).

- [x] **Real local-model e2e call.** `test_e2e_real_local_model_smoke` exercises
  `LocalCoderHarness._call_model` against a real Ollama/Prism instead of a stub harness (closes the gap
  flagged in 10.5's coverage item). Gated behind `LocalCoderHarness.check_health()` (same check
  `dark-factory doctor` performs) — `pytest.skip`s cleanly when neither engine is reachable instead of
  failing CI. Marked `@pytest.mark.local_engine` (registered in `pyproject.toml`); run explicitly with
  `pytest -m local_engine` on a machine with a local model available. Only the wire-level integration and
  terminal-state/telemetry shape are asserted — not the model's output correctness, which is nondeterministic.

- [x] **CLI-level e2e.** `test_e2e_cli_run_and_review_round_trip` drives the real `dark-factory` console
  script as a subprocess (`run` then `review --approve`) against a stub HTTP server standing in for Ollama
  (bound to an ephemeral port passed via the new `--ollama-url`, so it can't collide with a real Ollama on
  the operator's machine) — closing the `cli.py` coverage gap from 10.5. This required adding
  `--storage-dir` (`run`/`list`/`describe`/`review`/`recover`) and `--timeout-minutes`/`--ollama-url`/
  `--prism-url` (`run`) to the CLI, which also closes that part of 10.7's flag-exposure item.

---

### 10.9 Lightweight Performance Tracing

**Status: done (2026-09-28).** Source: operator request ("dodaj tracing żeby policzyć performance"),
scoped via clarification to the lightweight/built-in option: no new dependency and no external tracing
backend (consistent with Zero Cloud Tokens / local-first) — durations are recorded straight onto the
existing `EvidenceManifest` alongside the rest of the evidence, not a separate tracing subsystem.

- [x] **`PhaseTiming` on `EvidenceManifest`** (`domain/types.py`). `PhaseTiming(phase: str,
  duration_sec: float, started_at: str)`; `EvidenceManifest.phase_timings: list[PhaseTiming]`. Populated
  by a module-level `_trace(manifest, phase)` context manager in `orchestrator/engine.py` wrapping:
  `sandbox_create`, `agent_and_verify` (the outer envelope of the harness+healing+verification loop —
  the loop's own internals are already broken down via `model_telemetry.duration_sec` and each
  `StepExecution.duration_sec`), `diff_extract`, and `evidence_preserve` in `execute_run` (including the
  `TIMED_OUT`/`CANCELLED` exit paths), plus `patch_apply` in `review_run`. A `save_run` call is itself the
  thing that would record `evidence_preserve`'s duration, so it can't include its own timing on the first
  write; `execute_run` does one cheap extra `locker.save_run` right after (same patch content, no
  `transcript` arg) so the completed `phase_timings` list actually lands in `manifest.json`. **Tests:**
  `test_execute_run_records_phase_timings`, `test_timed_out_run_records_phase_timings`,
  `test_cancelled_run_records_phase_timings`, `test_review_run_approve_records_patch_apply_phase_timing`.
- [x] **Serialize/deserialize `phase_timings`** in `storage/evidence.py` (`save_run` covers it via
  `asdict`; `load_manifest` reconstructs via `PhaseTiming(**pt)`, same pattern as `StepExecution`).
- [x] **`dark-factory describe` prints a `PHASE TIMINGS` section** (`cli.py`). **Test:**
  `test_cli_describe_prints_phase_timings`.
- [x] Mirrored the `PhaseTiming` addition in `spec.md` §2/§3.4 and `docs/sdlc/spec.md` (byte-identical
  copy, `mkdocs build --strict` green).

---

### 10.10 Correctness-Verified Real-Model E2E

**Status: done (2026-09-28).** Source: operator follow-up on 10.8's `test_e2e_real_local_model_smoke`
("co z kompleksowymi testami" → clarified to: more realistic e2e against the live local Ollama, actually
checking the generated code is correct, not just that the pipeline didn't raise). Both tests are
`@pytest.mark.local_engine` (skip cleanly when no engine is reachable) and confirmed green 4/4 runs against
this operator's real Ollama (`qwen2.5-coder:14b`, `localhost:11434`), ~6-12s total for both.

- [x] **Tightened `test_e2e_real_local_model_smoke`** to require actual success: asserts
  `manifest.status == RunStatus.AWAITING_REVIEW` (previously also accepted `FAILED`), then
  `review_run(approve=True)` and re-runs `pytest` on the target repo to confirm the fix genuinely works.
- [x] **Added a multi-file task e2e** (`test_e2e_real_local_model_multi_file_task`, `calculator_repo`
  fixture): `calculator.py` with `add`/`subtract` implemented and `multiply` missing, `cli.py`'s
  `dispatch()` missing the `"multiply"` branch, task prompt asks for both. Exercises multi-file
  `` ```file: `` block parsing and the self-healing loop against a real model. `max_healing_attempts=5`,
  `timeout_minutes=5` for inference variance headroom; asserts `AWAITING_REVIEW`, approves, confirms both
  files' tests pass on the target repo.

---

### 10.11 Concurrency / Load Tests

**Status: done (2026-09-28).** Source: operator request ("dodaj bardziej rozwiniete testy z loadem").
Scope: exercise `DurableEngine` under concurrent load within one process
(`concurrent.futures.ThreadPoolExecutor`), using fast deterministic harnesses/gates (not the real model —
that's 10.10's job) so the tests run in CI. Confirmed stable across 5 consecutive full-suite runs.

- [x] **Concurrent `execute_run` isolation** (`test_concurrent_execute_run_isolated_sandboxes`): 8 runs
  launched in parallel against one `DurableEngine`/one repo, each its own `run_id` and `GitWorktreeSandbox`.
  Asserts every run reaches `AWAITING_REVIEW` with its own correct, non-cross-contaminated patch and that
  SQLite (WAL mode) ends up with exactly 8 consistent rows.
- [x] **Concurrent `review_run(approve=True)` on the same host repo**
  (`test_concurrent_review_run_serializes_git_mutations`): 8 `AWAITING_REVIEW` runs approved in parallel
  against the *same* `manifest.repo_path` (unlike sandboxes, `activity_apply_patch` mutates the host repo's
  actual working tree directly — `git checkout -b` / `git apply` / `git commit`). **Found a genuine race**:
  with the lock removed, this reliably reproduced `fatal: Unable to create '.git/index.lock': File exists`
  (verified red, then green again after restoring the fix — not just "it passed once"). **Fixed**:
  `DurableEngine` gained a per-instance `threading.Lock()` (`self._review_lock`) serializing just the
  git-mutating section of `review_run`'s approve path. **Known limitation, documented, not fixed here**:
  the lock is per-process — two separate `dark-factory review` CLI invocations (separate OS processes)
  approving concurrently against the same repo are still racy. A cross-process fix (e.g. a flock on
  `.factory/review.lock`) is tracked as backlog, not required for the single-process/embedded-engine usage
  this release targets.

---

### 10.12 More Realistic Real-Model E2E Scenario

**Status: done (2026-09-28).** Source: operator request ("zrob testy bardziej realistyczne"), follow-up on
10.10. 10.10's two real-model tests were "implement this stub" / "add this obviously-missing branch" —
close to a from-scratch toy exercise, not the diagnose-and-fix-without-regressing shape of real usage
described in this project's own `AGENTS.md`/`CLAUDE.md` SDLC (which gates on both `pytest` AND `ruff check`).

- [x] **`test_e2e_real_local_model_realistic_bugfix`** (`textutils_repo` fixture): an existing `slugify()`
  function with a genuine bug (naive `.replace(' ', '-')` doesn't collapse repeated whitespace) — not a
  `TODO` stub. 1 of 3 tests already passes, so a correct fix must not regress it. **Two verification
  gates**, matching real operator usage: `pytest test_text_utils.py` and `python -m ruff check
  text_utils.py` — the fix must also be lint-clean. `@pytest.mark.local_engine`, confirmed 3/3 green
  against the operator's real Ollama (solved first-try, 0 healing attempts, every run).
  - **Found and fixed a real test-design bug in the process**: `VerificationRunner.detect_default_gate_paths()`
    treats every path-looking argv token of every verification step as a protected gate file. A `ruff check
    text_utils.py` gate's own argv names the file the agent is supposed to edit, so the auto-detector would
    protect it and silently revert the model's fix before every verification pass, making the task
    unsolvable. Worked around here with an explicit `protected_paths=["test_text_utils.py"]` on the
    `TaskSpec`. **This heuristic gap in `detect_default_gate_paths()` itself is a real, general limitation**
    (any lint/type-check gate whose argv includes the file being edited hits it) — tracked as a new 10.7
    item, not fixed in `detect_default_gate_paths()` itself here (no argv-position-based fix is obviously
    correct without a protocol change).
  - **Found a genuine model-behavior limitation, not a tool bug, and deliberately scoped around it**: an
    earlier, broader fixture version added an unrelated `truncate()` whose "obviously correct" behavior
    (always append `...`, even past `max_length`) conflicts with the much more common "capped at
    `max_length` including the ellipsis" convention. qwen2.5-coder:14b reliably "fixed" that already-correct
    function anyway across multiple runs — even when the prompt explicitly said not to touch it — evidently
    overriding the instruction with a strong training-data prior, and got stuck reproducing the identical
    (wrong) diff across all 5 healing attempts rather than converging. Real and worth knowing about
    (LLM-generated fixes can silently violate explicit negative constraints when they collide with a common
    convention), but it makes a *correctness* test flaky against a model judgment call, not an objective
    bug — so the fixture was narrowed to one function / one unambiguous root cause instead of "fixed" by
    over-specifying the prompt.

---

### 10.13 Gate-Path Heuristic Fix + Complementary Real-Model Tests

**Source:** operator request ("jedziemy dalej z bardziej kompletnymi/komplementarnymi testami"),
2026-09-29, follow-up on 10.12. Clarified via AskUserQuestion to 3 of 4 proposed items (coverage-% push
declined).

- [x] **Fix `detect_default_gate_paths()`'s lint-target-vs-gate-file heuristic gap** (`verification/runner.py`).
  Added a small denylist of linter/formatter/type-checker tool names
  (`ruff`, `flake8`, `pylint`, `mypy`, `pyright`, `black`, `isort`) in `_LINTER_LIKE_TOOLS`; when a step's
  argv contains one (matched on `Path(arg).stem`, so it catches `ruff`, `python -m ruff`, `/path/to/ruff`
  alike), that step contributes nothing to the auto-detected protected-path set (its target files are what
  the agent must edit, not gate/test files — `_DEFAULT_PROTECTED_PATHS`'s fixed baseline, e.g.
  `tests`/`pyproject.toml`, still applies regardless). Non-lint steps keep prior behavior unchanged.
  **Tests:** `test_default_gate_paths_does_not_protect_lint_target`,
  `test_default_gate_paths_lint_step_alone_still_protects_baseline`; existing
  `test_default_gate_paths_keep_leading_dots`/`test_default_gate_paths_protect_test_runner_config` stay
  green. 10.12's `protected_paths=[...]` workaround is no longer load-bearing but kept as explicit,
  more readable config for that test.

- [x] **Real-Ollama CLI e2e** (`test_e2e_cli_run_and_review_real_ollama`, extends 10.8's
  `test_e2e_cli_run_and_review_round_trip`, which only used a stub HTTP server standing in for Ollama).
  Drives the real `dark-factory` console script (`run` then `review --approve`) as a subprocess against the
  operator's actual Ollama — no stub server, no `--ollama-url` override — proving the CLI entrypoint itself
  (argument parsing, `LocalCoderHarness` wiring, stdout formatting) works with a real model end-to-end, not
  just via the `DurableEngine` library API (10.10/10.12) or a stub HTTP layer (10.8). `@pytest.mark.local_engine`,
  confirmed green.

- [x] **Multi-iteration real self-healing** (`test_e2e_real_local_model_multi_iteration_healing`,
  `csvparse_repo` fixture: quoted-CSV-field parsing, genuinely harder than 10.10/10.12's from-scratch
  tasks, which were all solved first-try). Asserts `manifest.healing_attempts >= 1`, not just
  `== 0`/"eventually AWAITING_REVIEW", so the test actually exercises the repair-prompt feedback loop
  against a real model. **Empirical result across 7 manual runs against qwen2.5-coder:14b: 6/7 converged
  at exactly `healing_attempts == 1`; 1/7 exhausted all 5 attempts and ended `FAILED`.** That ~85%
  convergence rate is genuine model variance on a task that requires real reasoning (a state-machine
  parser), not a test-design bug — verified by inspecting the actual diffs from all 7 runs, which were all
  reasonable attempts at the same correct approach. Documented honestly in the fixture's docstring rather
  than further simplifying the task into something less representative of real self-healing (10.12 already
  showed the failure mode of over-narrowing a task down to "always solved instantly"). This is exactly why
  the test is `@pytest.mark.local_engine` — exploratory/manual, not a CI gate.

---

### 10.14 Self-Healing "Stuck on One Idea" Detection

**Status: done (2026-09-29).** Source: operator follow-up on 10.13's 1/7 real-model healing failure
("popattrz w trace-y" → "w razie czego dodaj"). Forensic analysis of that exact failed run's on-disk
evidence (`manifest.json`, `transcript.log`, `diff.patch`, the SQLite `events` table — still present under
a pytest-retained `tmp_path`) found a precise root cause: the model reproduced the **exact same conceptual
bug on all 6 attempts** (a backward-look escaped-quote check that's dead code because quote characters are
never buffered in the first place), producing byte-identical pytest failures every time — while a
successful run's first retry used a structurally different, correct strategy (forward lookahead)
immediately. Ruled out: not a wire-level/parsing issue (every attempt produced valid file blocks — the
SQLite event sequence shows `SELF_HEALING → VERIFYING` every time) and not a token-budget/truncation issue
(comparable completion-token counts to the successful run). Root cause: `SelfHealingLoop.run_loop` had no
mechanism to detect "the last attempt failed in exactly the same way" and tell the model to abandon its
current approach — it just re-shows the same error, and a model with a subtly wrong mental model can
re-derive a similarly-flawed fix from scratch rather than trying something qualitatively different.

- [x] **Stuck-detection in `SelfHealingLoop.run_loop`** (`verification/healing.py`). Tracks
  `last_failure_signature` (`failed_step.step_id, .exit_code, .stdout, .stderr` — duration/timed_out
  excluded, those vary run to run) and `repeated_failure_streak` across iterations. When a verification
  failure is identical to the immediately preceding one, the next repair prompt gets a new `STUCK NOTICE`
  block (same pattern as the existing tamper `SECURITY NOTICE`): *"Your last fix resulted in the exact same
  test failure as the attempt before it — your current approach is not working. Do not make a small tweak
  to the same logic; use a fundamentally different algorithm or data structure to solve this problem."*
  `run_loop`'s return type grew a 5th field (`repeated_failure_streak: int`, 0 on success), threaded through
  `activity_execute_task_and_verify` (`orchestrator/activities.py`) and `engine.execute_run`.
- [x] **Lightweight evidence note, no new schema** (`engine.py`). A plain exhausted-retries `FAILED` run
  (previously left `operator_notes` unset) now gets: *"...the same failure repeated identically for the
  last N attempts (the model got stuck on one approach...)"* when `repeated_failure_streak >= 1`, or
  *"...each attempt failed differently"* otherwise.
- [x] **Tests**: `test_self_healing_stuck_notice_appears_only_after_a_repeat` and
  `test_self_healing_no_stuck_notice_when_failures_differ` (`tests/test_verification.py`, using
  `FakeSandbox` with prescribed identical/differing `StepExecution` sequences — deterministic, no real
  model needed to verify the mechanism); `test_exhausted_healing_notes_repeated_failure` and
  `test_exhausted_healing_notes_different_failures` (`tests/test_orchestrator.py`, engine-level
  `operator_notes` wiring); updated the 4 pre-existing `SelfHealingLoop.run_loop` call sites in
  `test_verification.py` for the new 5-tuple return (one of them, `test_self_healing_exhausts_budget`,
  already used identical failures both attempts — a perfect pre-existing fit, now also asserts
  `repeated_failure_streak == 1`).
- [x] **Verification**: 94/94 tests green (`ruff check`/`format --check` clean) including a full
  `-m local_engine` run against the real local Ollama. Re-ran the real-model healing test 3 more times
  post-fix: all 3 converged on the first retry (`healing_attempts == 1`), so none exercised the new notice
  — the failure this fix targets is inherently rare (~1/7 previously), so a handful of extra runs isn't
  enough to newly measure its effect either way. No regression; mechanism itself is deterministically
  covered by the `FakeSandbox` unit tests above.
- [x] **Follow-up fix, found while building Phase 12's eval harness (2026-09-29)**: the failure-signature
  comparison used raw `stdout`/`stderr`, but pytest's own summary line ("1 failed in 0.03s") embeds a
  wall-clock duration that differs run to run even when the real outcome is identical — this made
  `test_exhausted_healing_notes_repeated_failure` genuinely flaky (~3/4 failures reproduced locally: same
  code, same test failure, but the streak sometimes failed to increment because the duration substring
  didn't match). Fixed by normalizing `\d+\.\d+s` substrings out of both strings before comparing
  (`_normalize_for_signature` in `healing.py`). **Test**:
  `test_self_healing_treats_differing_only_in_duration_as_the_same_failure`. Re-ran the previously-flaky
  test 5/5 clean after the fix.

---

## Phase 10.15: Context Window Sizing, Truncation Detection & Explicit Target Files

**Status:** items 0-6 implemented 2026-10-02 (operator "jedziesz"); gate green (289 tests). Review (fresh general-purpose subagent): 6 findings (1 HIGH, 2 MEDIUM, 3 LOW). Fixed test-first: #1 uncapped gate output in the repair prompt (now 6000 chars, head+tail), #2 stale failure streak and misleading note after a harness failure, #3 auditor/mutator pre-flight on diffs over ~21 KB (diff capped at 12000 chars; auditor adds an INFO finding), #4 truncation heuristic now only explains a reply without `file:` blocks, #5 `max_num_ctx` is a true ceiling. #6 not changed: a rejected `--target-file` path already renders as an "unreadable" stub; the ~12 KB single-file limit is inherent to whole-file output and is documented. Fixes verified by tests only, not re-reviewed independently. Reverses the 2026-09-29 "document only" decision for the `_build_context` bug in §10.7.
**Correction found by the 2026-10-02 measurement (Ollama 0.34):** the default window here is **4096**, not 2048, and a prompt larger than the window is not cut to the window but to about **half** of it (`prompt_eval_count` = `num_ctx/2 + 2`: 2050 of 4096, 4098 of 8192). The 2050 in the root-cause text below is that half-window signature. So the planned truncation test (`prompt_eval_count >= num_ctx - 16`) would never have fired; the harness now uses the half-window signature (and the full-window one). The detection is a heuristic; the pre-flight estimate is the primary defense.
**Item 0 measurement** (`qwen2.5-coder:14b`, RTX 5070 12 GB, prompt `docs/cli.md` + `harness/local_coder.py` = 4823 real tokens, 3 runs each): default/4096 -> truncated to 2050, 7-16 s, 9.5/9.5 GB, `file:` block 1-2 of 3; **8192 -> 4823 tokens, 33 s, 10.3/10.3 GB in VRAM, 3/3**; 12288 -> 77 s, 10.5/11.6 GB (~1.1 GB on CPU), 3/3; 16384 -> 137 s, 10.2/12.4 GB (~2.2 GB on CPU), 3/3. Default `max_num_ctx` = **8192**. Estimate `len/3` overshoots by ~46% on this content (7065 vs 4823), as intended.
**Item 6 (real model through the CLI, scratch clone):** (a) no `--target-file`: `engine.py` stubbed, correct one-line edit to `docs/cli.md`, `num_ctx` 4869; (b) `--target-file docs/cli.md`: correct edit; (c) two large target files: no model call, `harness` step with "Prompt needs about 33473 tokens ... max_num_ctx is 8192. Narrow the context with --target-file". The real run also found two wiring defects the mocks missed (fixed test-first): healing's aggregated telemetry dropped `num_ctx`, and a harness failure left no reason in the evidence (now a `harness` step in `verification_results`).

**Root cause (measured 2026-09-30, real `qwen2.5-coder:14b`, this host):** not "too many files confuse the model". Ollama's
default context window is 2048 tokens and it silently drops the start of a longer prompt. The incident prompt (`docs/cli.md`
+ `engine.py`) is 6256 tokens; Ollama processed 2050 (`prompt_eval_count`), losing the `FORMAT RULES`, so the model explained the
code (2/2 runs, no `file:` block). Same prompt with `num_ctx=16384`: correct edit. `docs/cli.md` alone used 1888 of 2048, so the
margin is thin and **any task whose prompt exceeds ~2k tokens is affected, including every self-healing prompt that appends
failure output**. `_call_model` never sets `num_ctx`. Cost measured: `num_ctx=16384` needs 11.8 GB, of which 9.8 GB fits in
VRAM on the 12 GB card (~2 GB on CPU), and the run took 141 s vs ~40 s. The earlier "400-line budget" idea was wrong (400 lines
is ~3.5k tokens, still over 2048) and is dropped. Also: `target_files` exists on `AgentHarness.execute_task` and
`SelfHealingLoop.run_loop` but `TaskSpec`, the CLI and `activity_run_verification_loop` never supply it.

- [x] **0. Measure before choosing the ceiling (manual, no code).** For the incident prompt at `num_ctx` 4096, 8192, 12288,
  16384: `prompt_eval_count`, peak VRAM vs CPU spill (`/api/ps`), seconds, and whether a `file:` block comes back (3 runs each).
  Record the table in this phase's `Status:` and set the default `max_num_ctx` from it (constraint: no more than a small CPU
  spill on the operator's 12 GB card). Scratch script: `ctx_experiment.py` in the session scratchpad, to be promoted into
  `dark_factory/eval` only if the operator wants it repeatable. **Blocks item 1's default value, not its code.**
- [x] **1. Size the window, pre-flight, detect truncation** (`dark_factory/harness/local_coder.py`): add
  `estimate_tokens(text) = ceil(len(text) / 3)`; `LocalCoderHarness(max_num_ctx=<from item 0>)`; `_call_model` sends
  `options.num_ctx = clamp(estimate + output_reserve, 4096, max_num_ctx)`; `execute_task` fails before any model call when
  the estimate plus reserve exceeds `max_num_ctx` (error names the sizes and `--target-file`); after the call
  `prompt_eval_count >= num_ctx - 16` returns `HarnessResult(success=False, error=...)` naming the window (Prism: same check
  via `usage.prompt_tokens` when reported). **Tests (`tests/test_harness.py`, mocked `requests`, red first):**
  `test_call_model_sends_num_ctx_sized_to_prompt`, `test_num_ctx_is_clamped_to_ceiling_and_floor`,
  `test_execute_task_fails_before_model_call_when_prompt_exceeds_ceiling` (asserts `requests.post` not called),
  `test_execute_task_reports_truncation_when_prompt_eval_count_hits_num_ctx`.
- [x] **2. Record the window in the evidence** (`dark_factory/domain/types.py`, `dark_factory/harness/local_coder.py`):
  `ModelTelemetry.num_ctx: int | None = None` (additive), set from item 1. **Test (`tests/test_domain.py` or
  `tests/test_harness.py`):** `test_telemetry_records_num_ctx` and that an old telemetry JSON without the field still loads.
- [x] **3. Plumb `target_files` end to end.** `TaskSpec.target_files: list[str]` (additive, default empty);
  `dark-factory run --target-file PATH` (repeatable) (`dark_factory/cli.py`, `dark_factory/domain/types.py`);
  `activity_run_verification_loop` passes `spec.target_files or None` to `run_loop`
  (`dark_factory/orchestrator/activities.py`). Paths are not validated up front (a missing path is a file to create).
  **Tests (red first):** `tests/test_cli.py::test_cli_run_passes_target_files`,
  `tests/test_orchestrator.py::test_target_files_reach_harness` (seen on every attempt, including healing).
- [x] **4. Token-budgeted auto-detection** (`dark_factory/harness/local_coder.py:_build_context`): with non-empty
  `target_files` only those files, in full, no auto-detection; otherwise auto-detected files are inlined in prompt order while
  their estimated tokens stay within `max_num_ctx // 2`, over-budget files become stubs (text in `spec.md` §3.2). **Tests
  (red first):** `test_build_context_stubs_auto_detected_file_over_budget` (incident shape: 178-line file then 519-line
  file), `test_build_context_small_auto_detected_files_inlined`,
  `test_build_context_explicit_target_files_inlined_in_full_and_disable_detection`.
- [x] **5. Docs & changelog:** `docs/cli.md` (`run --target-file`), `docs/local-inference.md` (the 2048-token default, what the
  harness sets, the VRAM cost, Prism caveat), `spec.md` §2/§3.2/§3.6 (written in this plan step) mirrored to
  `docs/sdlc/spec.md`, `CHANGELOG.md` `[Unreleased]` "Fixed" (silent prompt truncation) and "Added"; tick the §10.7
  `_build_context` box and replace its workaround text with a pointer here. Proof: `mkdocs build --strict`.
- [x] **6. Real-model confirmation (manual, not a gate):** through the CLI against the real Ollama: (a) the original scenario
  without `--target-file` (expect: stub for `engine.py`, correct edit), (b) with `--target-file docs/cli.md` (expect: correct
  edit), (c) a deliberately oversize prompt (expect: the clear pre-flight error, no model call). Record in `Status:`. If (a) or
  (b) still derails, stop and report.
- **Open questions:** (1) Default `max_num_ctx`: decided from item 0; the trade-off is VRAM spill and speed on this GPU vs how
  large a task fits. (2) Should `max_num_ctx` be operator-settable from the CLI (`--max-num-ctx`) or env? Not planned; constructor
  argument only. (3) Prism's window behavior is unverified (no per-request setting); only the estimate pre-flight protects that
  path. (4) `TaskSpec` and `ModelTelemetry` gain public fields; the dead `agent`/`metadata` fields stay untouched.
  (5) Tests with mocked `requests` prove the plumbing, not that the model behaves; only item 6 (non-deterministic) does.

---

## Phase 11: Forward-Looking Capabilities (Post-`0.1.x` Decisions)

Items below are unresolved **strategic** decisions surfaced by the adversarial reviews. They are tracked
here so the strategy discussions stay attached to the plan; each item must graduate to a Phase (or be
formally moved to `Non-Goals` in `intent.md`) before work starts.

### 11.A Foundry Local backend — rejected direction

Operator chose removal as a factory backend on 2026-09-30 (§10.7); delivered and guarded by `tests/test_docs_alignment.py::test_no_foundry_backend_references`. The `foundry-coder` operator skill is distinct. No third-backend task remains active.

### 11.B Container isolation — outside current intent

DockerSandbox and other container sandboxes are non-goals (§10.7 decision and `intent.md` §4). Keep the worktree-only limitation visible. The non-container `bwrap` research proposal has one owner in §10.5; adopting it requires a separate spec/invariant decision. Do not reactivate containers through a cleanup task.

### 11.C Temporal adapter — deferred strategy

The seam wording is delivered (§10.7), not an open documentation defect. An actual adapter remains a future decision: files would include `dark_factory/orchestrator/temporal_adapter.py` and dedicated adapter tests. Acceptance before promotion: approved local deployment/dependency design, equivalent durable transitions, recovery and cleanup tests. No worker/dependency is authorized.

### 11.D Custom-harness extension — deferred strategy

Files: `dark_factory/harness/base.py`, `dark_factory/cli.py`, corresponding harness/CLI tests and spec. Future acceptance: operator-approved extension interface and local-only routing, existing harness compatibility, explicit error handling. Related foreign-harness mutator fallback is BL-08 / DF-LIVE-01 finding 2; adding a CLI flag is not already approved.

### 11.E Multi-tenant support — outside current intent

Single-tenant operation remains normative (`intent.md` §4). No active multi-tenant implementation task; reconsideration requires explicit intent approval. Shared-repository concurrency tests do not imply multi-tenancy.

### 11.F Hardware coverage matrix — deferred documentation

Files: `docs/local-inference.md`, `plan.md`. Proof: backend/GPU/model-size rows identify measured configurations, runtime/model revisions, evidence and unknown configurations; `mkdocs build --strict` passes. Do not infer supported hardware from an unmeasured model size. No new hardware campaign is authorized.

Strategy items require explicit scope approval under `AGENTS.md`; no version or next-release inclusion is presumed.

---

## Phase 12: Eval Harness & Read-Only Dashboard

**Status: done (2026-09-29).** Source: operator request ("dodajmy jakis frontend do tego, zrtob eval").
Scoped via AskUserQuestion to a **read-only** local dashboard, with eval/benchmark results surfaced
**inside** it (one combined feature). Approved via `/plan` after a Plan-agent design pass over the full
codebase. Follows this repo's own intent → spec → plan → test → code → review SDLC (`AGENTS.md`);
`intent.md` §5 and `spec.md` §3.7/§3.8 updated first.

### 12.1 Companion fix: expose `repeated_failure_streak` on `EvidenceManifest`
- [x] Added `repeated_failure_streak: int = 0` to `EvidenceManifest` (`domain/types.py`).
- [x] `engine.execute_run` assigns it onto `manifest` right after unpacking `activity_execute_task_and_verify`'s
  5-tuple, before any evidence is preserved.
- [x] `storage/evidence.py:load_manifest` deserializes it with `data.get("repeated_failure_streak", 0)` —
  confirmed backward-compatible with a hand-written legacy manifest missing the key entirely.
- [x] `dark-factory describe` prints it when non-zero.
- [x] **Tests:** `test_storage.py::test_evidence_locker_save_and_load` extended +
  `test_load_manifest_defaults_repeated_failure_streak_for_old_manifests`;
  `test_exhausted_healing_notes_repeated_failure` / `_different_failures` (`test_orchestrator.py`) now
  assert `manifest.repeated_failure_streak` directly, not just `operator_notes` text.
- [x] **Found and fixed a real latent flaky-test bug while extending these tests**: the 10.14
  stuck-detector's failure-signature comparison used raw `stdout`/`stderr`, but pytest's own summary line
  ("1 failed in 0.03s") embeds a wall-clock duration that differs run to run even when the real outcome is
  identical — reproduced ~3/4 locally. Fixed in `verification/healing.py` by normalizing `\d+\.\d+s`
  substrings out of both strings before comparing (`_normalize_for_signature`). **Test:**
  `test_self_healing_treats_differing_only_in_duration_as_the_same_failure`. 5/5 clean after the fix.

### 12.2 Eval harness (`dark_factory.eval`)
- [x] New package `dark_factory/eval/__init__.py`.
- [x] `dark_factory/eval/scenarios.py`: extracted `build_primes_repo`, `build_calculator_repo`,
  `build_textutils_repo`, `build_csvparse_repo` out of `tests/test_e2e.py`'s `target_repo`/
  `calculator_repo`/`textutils_repo`/`csvparse_repo` fixtures (mechanical extraction, no behavior change —
  the fixtures are now thin wrappers); `EvalScenario` frozen dataclass; `SCENARIOS` registry populated from
  the same prompts/gates already used by the 4 `@pytest.mark.local_engine` tests.
- [x] `dark_factory/eval/runner.py`: `EvalRunResult`, `EvalReport` (+ `scenario_summary()`), `run_scenario`,
  `run_eval` (drives a **separate** `DurableEngine(storage_dir / "eval-runs")`, never the main journal),
  `save_report`/`load_report`/`list_eval_reports` (JSON under `.factory/evals/<ts>.json`),
  `format_summary()` for CLI output.
- [x] `dark-factory eval` CLI subcommand (`cli.py`): `--scenario` (repeatable), `--repeat`, `--model`,
  `--ollama-url`, `--prism-url`, `--storage-dir`, `--keep-repos`, `--list`; gates on
  `LocalCoderHarness.check_health()`, exits 1 with a clear message if no engine is reachable; exits 1 if any
  scenario converged zero times.
- [x] **Tests (20 new, all green):** `tests/test_eval_scenarios.py` (each builder produces the expected
  repo/bug; registry completeness); `tests/test_eval_runner.py` (deterministic stub harnesses — repeat
  count, convergence/stuck flagging, aggregation math, JSON round-trip, sort order, confirmed eval runs land
  under `eval-runs/` and `.factory/runs/` is never created); `tests/test_cli.py` additions (`--list`,
  unknown-scenario error, health-gate short-circuit); `test_run_eval_real_model_smoke`
  (`@pytest.mark.local_engine`, confirmed green against the real local Ollama) asserting only that a
  well-formed `EvalReport` comes out — never a specific convergence rate (10.12/10.13/10.14 standard).
  Manually verified end-to-end: `dark-factory eval --list` and `--scenario primes --repeat 1` against the
  real engine, inspected the saved JSON report.

### 12.3 Read-only local dashboard (`dark_factory.dashboard`)
- [x] New package `dark_factory/dashboard/__init__.py`.
- [x] `dark_factory/dashboard/server.py`: `DashboardRequestHandler(BaseHTTPRequestHandler)` — `GET`-only
  dispatch (`/`, `/runs/<id>`, `/eval`, `/api/runs`, `/api/eval`); every other verb returns `405`.
  `run_dashboard(storage_dir, port=8420, open_browser=True)` binds `127.0.0.1` only, no host flag.
  **Design correction made during implementation**: reads from a plain `EvidenceLocker` (disk evidence
  only), *not* `DurableEngine`/SQLite — `EvidenceLocker.save_run()` never touches the SQLite journal, so
  seeding evidence directly (the natural way to test/populate a read-only view) left `DurableEngine.list_runs()`
  seeing nothing. Using the disk-based locker throughout is also simpler: no DB connection needed for a
  page that only ever reads (`spec.md` §3.8 updated to match).
- [x] `dark_factory/dashboard/views.py`: pure HTML-building functions — `render_layout`, `render_runs_list`
  (takes `list[EvidenceManifest]`), `render_run_detail` (mirrors `cmd_describe`'s content, including
  `phase_timings` and `repeated_failure_streak`), `render_eval_view` (latest + historical `EvalReport`s,
  plain HTML table). All interpolated values pass through `html.escape()`. `/api/*` endpoints use
  `dataclasses.asdict`.
- [x] **Diff visualization** (operator follow-up, "dodaj jakas vizualizacje diffa", 2026-09-29):
  `render_diff()` renders the unified diff with GitHub-style add/removed line highlighting — no
  syntax-highlighting library, just CSS classes (`diff-add`/`diff-del`/`diff-hunk`/`diff-file`/`diff-meta`/
  `diff-context`) keyed off the standard unified-diff line prefixes, each source line individually escaped.
  Replaces the plain `<pre>{escaped patch}</pre>` in `render_run_detail`. **Tests:**
  `test_render_diff_empty_shows_placeholder`, `test_render_diff_classifies_added_and_removed_lines`,
  `test_render_diff_escapes_line_content`. Manually verified via `curl` against a running dashboard.
- [x] `dark-factory dashboard` CLI subcommand: `--port` (default 8420), `--storage-dir`, `--no-browser`;
  prints the URL, opens a browser tab unless `--no-browser`, serves until `KeyboardInterrupt`.
- [x] Zero new runtime dependency — stdlib only (`http.server`), consistent with `pyproject.toml`'s single
  existing runtime dependency (`requests`) and `intent.md`'s stance against "Heavy, Unwieldy Infrastructure".
- [x] **Tests (21 new, all green):** `tests/test_dashboard_views.py` (render functions against hand-built
  `EvidenceManifest`/`EvalReport` fixtures, incl. HTML-escaping assertions for `<script>`-bearing
  `operator_notes` and diff content); `tests/test_dashboard.py` (a real `ThreadingHTTPServer` instance on an
  ephemeral `127.0.0.1` port, seeded via `EvidenceLocker.save_run(...)` + a saved eval report; real `GET`s
  to every route incl. 404s; one loop asserting `POST`/`PUT`/`DELETE`/`PATCH` all return `405`). No real
  model needed; runs in the default suite. Manually verified end-to-end: started the dashboard, `curl`ed
  every route (200s, one real 404, one real 405) and confirmed rendered HTML in a browser.

### 12.4 Documentation & release hygiene
- [x] `docs/cli.md` gained full `## dark-factory eval` / `## dark-factory dashboard` reference sections +
  summary table rows; `AGENTS.md` diagnostic-commands block gained both; `docs/sdlc/agents.md` mirror
  re-synced byte-identical. `README.md` Quick Start gained both commands. (`CLAUDE.md`'s CLI mentions are
  two illustrative dev-mode examples, not an exhaustive reference — left as-is.)
- [x] `CHANGELOG.md [Unreleased]` entries (Added: eval, dashboard, `repeated_failure_streak`; Fixed: the
  duration-normalization stuck-detector bug from 12.1).
- [x] `mkdocs build --strict` green.

**Verification:** 157 tests total, all green (`ruff check .` / `ruff format --check .` clean;
`pytest tests/ -m "not local_engine" -q` and the full suite including `-m local_engine` against the real
local Ollama both pass); manual checks as noted per-section above.

---

## Phase 13: Adversarial Red-Team Pipeline

**Status:** 13.1–13.5 implemented, including CLI/dashboard and active mutation; historical 157-test gate belongs to an earlier intermediate state. Subsequent review remediation is in §14.5; outstanding re-review of those fixes is BL-01.

Autonomous agents frequently produce code that passes naive unit test suites through hardcoded branches, shortcut logic, or missing boundary checks. The Adversarial Pipeline introduces an automated, local-first Red-Team critic into the factory lifecycle to stress-test patches before human review.

### 13.1 Domain Contracts & Evidence (`dark_factory.domain`)
- [x] Add `AdversarialFinding(severity: str, category: str, summary: str, details: str)` and `AdversarialReport(passed: bool, summary: str, findings: list[AdversarialFinding])` dataclasses to `dark_factory/domain/types.py`.
- [x] Add additive `adversarial_report: dict[str, Any] | None = None` to `EvidenceManifest` in `dark_factory/domain/types.py` (backwards-compatible with existing serialized manifests).
- [x] Persist `adversarial.md` human-readable summary in `EvidenceLocker.save_run()` (`dark_factory/storage/evidence.py`).
- [x] **Tests (`tests/test_domain.py`, `tests/test_storage.py`):** round-trip serialization of `AdversarialReport`, backwards compatibility of loading old manifests without the field.

### 13.2 Local Adversarial Auditor Engine (`dark_factory.verification.adversarial`)
- [x] Implement `AdversarialAuditor`: executes a structured red-team critic prompt via `LocalCoderHarness`.
- [x] Auditor evaluates `diff.patch` against `TaskSpec` across 4 categories: `anti-cheating`, `boundary`, `security`, and `regression`.
- [x] Prompt returns deterministic JSON parsing into `AdversarialReport`. Graceful fallback on malformed JSON to `severity="WARN", summary="Raw audit output"`.
- [x] Zero-VRAM-conflict sequential execution: runs only *after* the coder finishes its healing loop and passes deterministic gates.
- [x] **Tests (`tests/test_adversarial.py`):** audit on mock diffs with known anti-patterns (dummy return, path traversal, unbounded loop, clean fix); mock harness responses.

### 13.3 Orchestrator Integration & Activity Pipeline (`dark_factory.orchestrator`)
- [x] Add `activity_adversarial_audit(run_id, spec, sandbox, manifest)` in `dark_factory/orchestrator/activities.py`.
- [x] Hook into `execute_run`: immediately after `VerificationRunner` exits 0 (and patch is non-empty), invoke `activity_adversarial_audit` before transitioning to `RunStatus.AWAITING_REVIEW`.
- [x] Add optional task-level bypass `--no-adversarial` on CLI / `TaskSpec.skip_adversarial: bool = False`.
- [x] **Tests (`tests/test_orchestrator.py`):** verify `activity_adversarial_audit` is invoked on green runs, skipped on failing runs, and its report is recorded in the manifest.

### 13.4 Operator Surfaces: CLI & Dashboard Integration
- [x] Update `dark-factory describe <RUN_ID>` (`dark_factory/cli.py`) to render the Red-Team report with severity badges (`CRITICAL`, `WARN`, `PASS`).
- [x] Update `dark-factory review <RUN_ID>` to display the red-team findings summary prior to the approval prompt (`[y/N]`).
- [x] Update `dark_factory/dashboard/views.py` to render the Adversarial Audit card in the run detail view.
- [x] **Tests (`tests/test_cli.py`, `tests/test_dashboard_views.py`):** CLI and dashboard rendering of runs with clean vs warning adversarial reports.

### 13.5 Active Adversarial Test Mutation (Tier 2)

**Status:** 13.5.1–13.5.4 implemented (checked items below); later fixes and review limitations are tracked in §14.5 / BL-01.

Autonomous coding agents often produce code that passes naive unit test suites through hardcoded branches, shortcut logic, or missing boundary checks. Phase 13.5 extends the adversarial pipeline from passive diff analysis to active test mutation: synthesizing dynamic hostile unit tests (`test_adversarial_probe.py`), executing them against the sandbox, and feeding any failures into `SelfHealingLoop` so the coder must repair its implementation to satisfy both baseline and hostile edge cases.

#### 13.5.1 Domain Contracts & Evidence (`dark_factory.domain`, `dark_factory.storage`)
- [x] Add `TaskSpec.mutate_adversarial: bool = False` to `dark_factory/domain/types.py`.
- [x] Add additive `adversarial_test_code: str | None = None` to `EvidenceManifest` in `dark_factory/domain/types.py`.
- [x] Update `EvidenceLocker.save_run()` to persist `adversarial_test.py` when `manifest.adversarial_test_code` is present (`dark_factory/storage/evidence.py`).
- [x] Update `EvidenceLocker.load_manifest()` to deserialize `adversarial_test_code` backwards-compatibly (`dark_factory/storage/evidence.py`).
- [x] **Tests (`tests/test_domain.py`, `tests/test_storage.py`):** verify `TaskSpec.mutate_adversarial` defaults, `EvidenceManifest` serialization, and `EvidenceLocker` saving/loading `adversarial_test.py` and old manifests.

#### 13.5.2 Local Adversarial Mutator Engine (`dark_factory.verification.adversarial_mutator`)
- [x] Create `dark_factory/verification/adversarial_mutator.py` with `AdversarialMutator`.
- [x] Implement hostile probe synthesis prompt instructing local QA/tester model to generate pytest tests covering boundary invariants, malicious/adversarial inputs, edge cases, and anti-cheating assertions against the modified functions in `diff.patch`.
- [x] Implement `ast.parse` syntax validation to ensure generated test code is valid Python; safely return `None` or raise handled exception on malformed/invalid test code so the run degrades gracefully.
- [x] Strip markdown backticks (e.g. ```python ... ```) safely from LLM response.
- [x] **Tests (`tests/test_adversarial_mutator.py`):** test probe generation on mock diffs, syntax rejection of malformed code, clean parsing of markdown fences, and empty diff handling.

#### 13.5.3 Orchestrator & Self-Healing Feedback Integration (`dark_factory.orchestrator`)
- [x] Add `activity_adversarial_mutation(sandbox, harness, spec, manifest, status_callback, deadline)` in `dark_factory/orchestrator/activities.py`.
- [x] Hook into `DurableEngine.execute_run` under traced phase `adversarial_mutation`: when `spec.mutate_adversarial` is enabled, baseline verification passed, and diff is non-empty, synthesize `test_adversarial_probe.py`.
- [x] Run the adversarial probe in the sandbox. If probe fails (`exit_code != 0`), feed the failure into `SelfHealingLoop` with combined verification steps and `test_adversarial_probe.py` marked as protected.
- [x] Clean up `test_adversarial_probe.py` from sandbox worktree before diff extraction so the host repo patch remains clean while the probe code is preserved in evidence.
- [x] Plumb CLI flag `--mutate-adversarial` in `dark_factory/cli.py`.
- [x] **Tests (`tests/test_orchestrator.py`, `tests/test_cli.py`):** test orchestrator executing adversarial probe, healing on probe failure, preserving evidence, CLI flag passing.

#### 13.5.4 Operator Surfaces, Dashboard & Documentation
- [x] Update `dark-factory describe <RUN_ID>` (`dark_factory/cli.py`) to display adversarial test status and preview generated probe code.
- [x] Update `dark_factory/dashboard/views.py` to display the Mutated Adversarial Test card in run detail view with safe syntax highlighting/formatting.
- [x] Update `CHANGELOG.md` under `[Unreleased]` with Phase 13.5 capabilities.
- [x] Run full gate check (`python3 scripts/sdlc_check.py`).
- [x] **Tests (`tests/test_cli.py`, `tests/test_dashboard_views.py`):** verify CLI describe and dashboard rendering with mutated test evidence.

---

## Phase 14: Split-Model Architecture (Planner vs Executor)

Autonomous coding agents often make architectural errors or write premature/hacky code when a single model tries to perform high-level task decomposition, invariant discovery, and low-level code editing in a single prompt. Phase 14 splits the task into two sequential stages: a reasoning Planner session (`deepseek-r1:14b` or `qwen2.5-coder:14b`) followed by a code-specialized Executor session (`qwen2.5-coder:14b`).

### 14.1 Domain Contracts & Evidence (`dark_factory.domain`, `dark_factory.storage`)
- [x] Add `ExecutionPlan(plan_id: str, summary: str, invariants: list[str], steps: list[str], target_files: list[str], raw_plan: str)` dataclass to `dark_factory/domain/types.py`.
- [x] Add additive `TaskSpec.planner_model: str | None = None` and `TaskSpec.skip_plan: bool = False` to `dark_factory/domain/types.py`.
- [x] Add additive `execution_plan: ExecutionPlan | None = None` to `EvidenceManifest` in `dark_factory/domain/types.py`.
- [x] Persist `plan.md` in `EvidenceLocker.save_run()` and reconstruct in `load_manifest()` (`dark_factory/storage/evidence.py`).
- [x] **Tests (`tests/test_domain.py`, `tests/test_storage.py`):** round-trip serialization of `ExecutionPlan`, backwards compatibility with older manifests.


### 14.2 Local Planner Engine (`dark_factory.planning`)
- [x] Create `dark_factory/planning/planner.py` with `LocalPlanner`.
- [x] Implement reasoning system prompt extracting problem analysis, architectural invariants, step-by-step strategy, and target files.
- [x] Deterministic JSON parsing into `ExecutionPlan` with fail-safe fallback wrapping raw reasoning into a standard plan on malformed output.
- [x] **Tests (`tests/test_planner.py`):** plan generation on mock repository contexts, JSON extraction, and fallback handling.

### 14.3 Orchestrator Integration & Activity Pipeline (`dark_factory.orchestrator`)
- [x] Add `activity_plan_task(run_id, spec, sandbox, harness)` in `dark_factory/orchestrator/activities.py`.
- [x] Hook into `DurableEngine.execute_run`: execute `activity_plan_task` under traced phase `task_planning` before `activity_agent_execute`.
- [x] Augment `activity_agent_execute` / `LocalCoderHarness` to accept `ExecutionPlan` and inject it into the coder prompt.
- [x] Wire CLI flags `--planner-model` and `--no-plan` into `dark-factory run` (`dark_factory/cli.py`).
- [x] **Tests (`tests/test_orchestrator.py`, `tests/test_cli.py`):** verify `activity_plan_task` executes, plan is recorded in manifest, `--no-plan` bypass works.

### 14.4 Operator Surfaces: CLI & Dashboard Integration
- [x] Update `dark-factory describe <RUN_ID>` (`dark_factory/cli.py`) to render `--- EXECUTION PLAN ---` with invariants, steps, and target files.
- [x] Update `dark_factory/dashboard/views.py` to render the Execution Plan card with step checkboxes/badges and XSS-safe escaping.
- [x] **Tests (`tests/test_cli.py`, `tests/test_dashboard_views.py`):** verify CLI and dashboard rendering of execution plans.




## Phase 14.5: Review Remediation (Phase 13/14 independent review)

**Status:** R1-R19 implemented (R14-R19 address the first independent re-review). Review finding 7 (num_ctx spec vs. code) was subsequently delivered by §10.15; finding 9 (planner `target_files` unused) remains operator-deferred (BL-08). Review: round 1 = 13 findings (11 fixed, 2 open), round 2 = 13 findings on the fixes (R14-R19 fixed). R14-R19 were verified by tests only, not re-reviewed independently.

- [x] R1. Dashboard: allowlist finding severity (`INFO/WARN/CRITICAL`, default `WARN`) at parse time and `escape()` the badge class (`views.py`, `adversarial.py`). Test: hostile severity renders no attribute injection.
- [x] R2. Mutation phase: `cleanup_probe()` in `try/finally`; `RunTimeoutError` during mutation yields `TIMED_OUT` with diff/evidence preserved (`activities.py`, `engine.py`). Tests: exception and timeout mid-probe.
- [x] R3. `AdversarialReport.passed` derived from findings (no WARN/CRITICAL), model flag ignored; spec states the audit is advisory (`adversarial.py`, `spec.md`).
- [x] R4. Planner: strip `<think>...</think>`, extract the outermost JSON object, validate `steps`/`invariants`/`target_files` are lists of strings (`planner.py`).
- [x] R5. Re-run baseline verification after the adversarial probe so a probe cannot alter source unverified; document the host-run limitation (`activities.py`, `engine.py`, `spec.md`).
- [x] R6. Honour the deadline before planner/auditor/mutator model calls (`activities.py`).
- [x] R8. Prompt fences: use a fence longer than any backtick run in the diff; make JSON fence extraction greedy-safe (`adversarial.py`, `adversarial_mutator.py`, `planner.py`).
- [x] R10. Sanitise LLM text in `adversarial.md`/`plan.md` (table pipes, newlines) and strip ANSI/control chars in `describe`/`review` (`evidence.py`, `cli.py`).
- [x] R11. `load_manifest` ignores unknown keys on `AdversarialFinding` (`evidence.py`).
- [x] R12. Overall badge can be `CRITICAL`; `review` shows probe status (`cli.py`, `views.py`).
- [x] R13. Tests: each item above has a red-first test; probe-written-then-removed assertion; `mutate_adversarial` with `skip_adversarial` false.
- [x] R14. Engine: guard both `activity_adversarial_audit` call sites with `except RunTimeoutError` -> `finish_timed_out` (`engine.py`). Test through the engine.
- [x] R15. `extract_json_object(raw, keys=...)` prefers the dict carrying the expected keys and strips an unclosed `<think>`; a `passed: false` verdict without findings yields a WARN finding (`llm_text.py`, `adversarial.py`, `planner.py`).
- [x] R16. Mutator: dynamic fence, `<think>` stripping and line-anchored fence extraction (`llm_text.py`, `adversarial_mutator.py`).
- [x] R17. Sanitising gaps: `clean_text` drops `\r`, C1 controls and bidi/line separators; `md_cell` escapes backslashes first; `plan.md` fields single-line and `raw_plan` fenced; `adversarial.md` summary via `md_cell`; `describe` cleans diff, notes and plan fields (`llm_text.py`, `evidence.py`, `cli.py`).
- [x] R18. Deadline clamp works on a per-run copy of the harness instead of mutating the shared one (`activities.py`).
- [x] R19. Post-probe baseline re-verification failure is reported as such and its step ids are suffixed `:reverify` (`activities.py`, `engine.py`); strengthen test_r5/r2/r8 assertions.
- [x] **Delivered by §10.15 (2026-10-02); was deferred (operator, 2026-10-01), review finding 7:** `spec.md` describes `num_ctx` clamping, pre-flight failure and truncation detection that the code does not have yet; planner, auditor and mutator call `_call_model` without `num_ctx`. Delivered by §10.15 (items 1 and 4); until then a large diff can be silently truncated by Ollama's default window.
- [ ] **BL-08a / Deferred (operator, 2026-10-01), review finding 9:** planner `target_files` are displayed but not merged into `TaskSpec.target_files`. Files: `dark_factory/orchestrator/engine.py`, `dark_factory/orchestrator/activities.py`, `tests/test_orchestrator.py`, `spec.md` and mirrored spec. Before implementation decide operator-target precedence and how planner targets affect the mandatory scope gate. Proof: validated sandbox-relative paths (reject absolute paths and `..`), operator scope cannot silently widen, existing explicit targets remain effective.


## Phase 15: Performance & Quality Analysis (advisory, hardware-aware)

**Status:** 15.1–15.5 implemented, gate green (263 tests, ruff, docs, changelog) on 2026-10-02; plan approved by operator. Review (fresh general-purpose subagent, 2026-10-02): 7 findings. Fixed test-first (red then green): #1 stale telemetry/healing in analysis, #2 header-lookalike content lines, #3 deleted/renamed files, #4 quoted paths, #7 1 MB source cap. #6 resolved by correcting spec (metric dropped). #5 not a defect (spec scopes sampling to agent_and_verify; mutation/audit calls are unsampled). Fixes verified by tests only, not re-reviewed independently. Note: the analysis step lives in `DurableEngine.execute_run` (calls `analyze`, `collect_sources`) rather than a separate `activity_analysis`; `--no-analysis` and the sampler are wired there.

Goal: after green gates, report how the run used this machine (VRAM, GPU, RAM, tok/s, phase bottleneck) and the quality of the patch (size, complexity, missing tests). Deterministic, stdlib-only, no model calls, advisory.

### 15.1 Domain & evidence
- [x] Add `ResourceUsage`, `AnalysisFinding`, `AnalysisReport(summary, resources, findings, metrics)` to `dark_factory/domain/types.py` (+ export in `domain/__init__.py`); additive `EvidenceManifest.analysis_report`; `TaskSpec.skip_analysis: bool = False`. `EvidenceLocker.save_run` writes `analysis.md` (sanitised like `adversarial.md`); `load_manifest` backwards compatible. Tests: `tests/test_domain.py`, `tests/test_storage.py`.

### 15.2 Resource sampler (`dark_factory/analysis/resources.py`)
- [x] `ResourceSampler` (context manager, daemon thread, 2 s interval, argv-only `nvidia-smi`, `/proc/meminfo`), idempotent stop, never raises, `None` fields when unavailable. Tests (`tests/test_analysis_resources.py`): parsing with mocked subprocess/meminfo, missing `nvidia-smi`, failing sampler, stop twice.

### 15.3 Analyzer (`dark_factory/analysis/analyzer.py`)
- [x] `analyze(manifest, diff_text, spec, resources) -> AnalysisReport`: phase shares and bottleneck, tok/s, diff stats, AST complexity/length of changed functions, source-without-tests, hardware-fit findings with module-constant thresholds. Tests (`tests/test_analysis.py`): each rule fires and stays quiet at the boundary; unparseable file skipped; empty diff.

### 15.4 Orchestrator integration
- [x] `activity_analysis` in `activities.py`; `execute_run` starts the sampler around `agent_and_verify`, runs the analysis in a traced `analysis` phase on green non-empty runs (also after the mutation path), swallows exceptions, never changes status; `--no-analysis` CLI flag. Tests (`tests/test_orchestrator.py`, `tests/test_cli.py`): invoked on green, skipped on failure and with the flag, analysis crash leaves the run `AWAITING_REVIEW`, sampler stopped on timeout/cancel.

### 15.5 Operator surfaces & docs
- [x] `describe`/`review` print the analysis (WARN badges, resource line); dashboard run-detail card (`views.py`); `docs/` page and `CHANGELOG.md` `[Unreleased]`; full gate `python3 scripts/sdlc_check.py`. Tests: `tests/test_cli.py`, `tests/test_dashboard_views.py`.

## Phase 22: Adversarial Follow-ups P1 (Strict Audit Schema) & P2 (Host Isolation Reconciliation)

Status: 22.1-22.5 done and gated (368 passed, 7 deselected). Stage 6 independent review reported 3 findings (1 MEDIUM, 2 LOW), all reproduced red-first and fixed.

- [x] **22.1 Red regression tests for strict audit schema (P1).** Files: `tests/test_adversarial.py`.
  - Add regression tests covering:
    - Summary-only JSON (missing `passed` and `findings`)
    - String `"false"` or `"true"` for `passed` (non-boolean type)
    - Non-string `summary` (e.g. integer or list)
    - Non-list `findings` (e.g. dict or string)
    - Non-dict item inside `findings`
    - Finding item missing required fields (`severity`, `category`, `summary`, `details`) or having invalid `severity` value
  - Assert that all these malformed structures result in `AdversarialReport(passed=False, ...)` with a `WARN` finding in category `regression` detailing the schema error.
  - Proof: `python3 scripts/sdlc_check.py --red tests/test_adversarial.py::<test_name>` fails for the right reason against current parser.
- [x] **22.2 Strict schema validation implementation (P1).** Files: `dark_factory/verification/adversarial.py`.
  - Update `_parse_response` to strictly validate `data`:
    - `isinstance(data, dict)`
    - `isinstance(data.get("passed"), bool)`
    - `isinstance(data.get("summary"), str)` and non-empty
    - `isinstance(data.get("findings"), list)`
    - Every finding item is a dict with valid `severity` in `_SEVERITIES` and string `category`, `summary`, `details`.
  - Return `passed=False` with an explanatory `WARN` finding when schema validation fails.
  - Proof: all new and existing tests in `tests/test_adversarial.py` pass.
- [x] **22.3 Host isolation documentation reconciliation and evidence (P2).** Files: `docs/architecture.md`, `README.md`, `docs/index.md`, `REVIEW.md`.
  - Reconcile user-facing docs: explicitly document in `docs/architecture.md`, `README.md`, and `docs/index.md` that `GitWorktreeSandbox` provides repository-level worktree isolation, not host OS process or network isolation (process sandboxing tracked in §10.5).
  - Record the synthetic outside-worktree write reproduction in `REVIEW.md` as evidence.
  - Proof: `tests/test_docs_alignment.py` and `mkdocs build -s` pass.
- [x] **22.4 Docs and changelog.** Files: `CHANGELOG.md` (`### Fixed` and `### Added`), `spec.md`, `docs/sdlc/spec.md`.
  - Proof: `scripts/sdlc_check.py` docs and changelog checks pass.
- [x] **22.5 Independent review**, then full gate.
  - Proof: fresh subagent review reported 3 findings (finding item fields optional, empty summary allowed, masked hostile severity test); all reproduced red-first, fixed, and `python3 scripts/sdlc_check.py` exited 0 (368 passed, 7 deselected).

## Phase 23: DF-LIVE-08 (Opening file block indentation tolerance)

Status: 23.1–23.4 implemented and gate-green (370 passed, 7 local-engine tests deselected); independent review reported NO FINDINGS (see REVIEW.md). Post-fix full benchmark is open as BL-02; the previous Mistral 0/12 campaign predates this fix.

Historical root cause before the fix: `_FILE_OPEN_RE = re.compile(r"^(`{3,})file:(.*)$")` in `dark_factory/harness/local_coder.py` requires 0 leading spaces, whereas `_FENCE_RE = re.compile(r"^ {0,3}(`{3,})(.*)$")` and CommonMark code fence specifications permit up to 3 leading spaces. Models like Mistral-7B begin assistant responses after `[/INST]` with a leading space token, producing `" ```file:<path>"`. This caused 9/12 Mistral attempts in the 2026-10-04 rerun to be discarded as "no recognizable file code blocks" despite complete code.

- [x] **23.1 Red regression tests for opening fence indentation.** Files: `tests/test_harness.py`.
  - Add tests in `tests/test_harness.py`:
    - `test_parse_file_blocks_allows_up_to_three_leading_spaces()`: verify that ```` ```file:<path> ```` with 1, 2, or 3 leading spaces correctly parses `<path>` and the file contents.
    - `test_parse_file_blocks_rejects_four_or_more_leading_spaces()`: verify that 4 or more leading spaces (markdown indented code block) does not parse as a file block.
  - Proof: `python3 scripts/sdlc_check.py --red tests/test_harness.py::test_parse_file_blocks_allows_up_to_three_leading_spaces` exits 0 showing assertion failure.
- [x] **23.2 Indentation tolerance in `_FILE_OPEN_RE`.** Files: `dark_factory/harness/local_coder.py`.
  - Update `_FILE_OPEN_RE` to `re.compile(r"^ {0,3}(`{3,})file:(.*)$")`.
  - Proof: all new and existing tests pass.
- [x] **23.3 Docs and changelog.** Files: `CHANGELOG.md` (`### Fixed`), `spec.md`, `docs/sdlc/spec.md`.
  - Proof: `scripts/sdlc_check.py` docs and changelog checks pass.
- [x] **23.4 Independent review and full gate.**
  - Proof: fresh research subagent review (`d8e607b9-9ab0-4dd6-a1df-420fab32677e`) reported NO FINDINGS and `scripts/sdlc_check.py` exited 0 (370 passed, 7 deselected).


## Workspace SDLC unification — 2026-10-02

Status: migration verification complete (2026-10-02). Full gate exited 0 in this session with authorized local socket access: 219 tests passed, 6 local-engine tests deselected; lint, format, docs and changelog passed. Workspace distribution checks: 2 passed. Prior independent migration review and re-review recorded below; this session changed verification records only. Earlier product work remains separate and uncommitted.

- [x] U1. Install/update kit-owned runner, skills, hook and Cursor rule; normalize the process in `AGENTS.md` and harness adapters. Evidence: `.sdlc/test_unification.py` compares all eight projects to the kit.
- [x] U2. Configure `sdlc.toml` without dropping existing checks; preserve project-specific helpers and red-mode error handling. Evidence: migrated gate-helper tests where present, gate CLI smoke and configuration validation.
- [x] U3. Update process references, `REVIEW.md`, changelog and documentation mirrors where applicable. Run the full project gate; record pass/fail/skip evidence and obtain independent review. No checkbox closes on partial checks alone.

### Codex migration evidence — 2026-10-02

Status: shared process, kit distribution, project profiles, Codex adapters, review policy and CI implemented under the operator request. Existing product-version CI remains. Workspace distribution checks: 2 passed. Independent read-only review found two migration defects (legacy Python bootstrap and lint comparison-base forwarding); both reproduced red, fixed and re-reviewed with no new findings. Actual Python 3.8/3.9 was unavailable; bootstrap regression uses simulated old builtin typing behavior.

Verification: Gate exit 1: 210 passed, 6 local-engine tests deselected; one E2E failure and 8 dashboard errors from socket PermissionError. Lint, format, docs, changelog PASS; docs mirrors fixed and verified.

Follow-up verification (2026-10-02): `python3 scripts/sdlc_check.py` initially reproduced the socket restriction above, then exited 0 with explicitly authorized execution outside the sandbox: 219 passed, 6 local-engine tests deselected; lint, format, docs and changelog PASS. `python3 ../.sdlc/test_unification.py` exited 0 (2 passed). U1–U3 closed after this complete gate. Real-engine checks were not run; no commits, pushes or releases. Earlier adversarial remediation remains in its own plan phase.
