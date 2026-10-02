"""CLI entrypoint for Sovereign Dark Factory."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from dark_factory.domain.errors import RunNotFoundError
from dark_factory.domain.types import RunStatus, TaskSpec, VerificationStep
from dark_factory.eval.runner import format_summary, run_eval, save_report
from dark_factory.eval.scenarios import SCENARIOS
from dark_factory.harness.llm_text import clean_text
from dark_factory.harness.local_coder import LocalCoderHarness
from dark_factory.orchestrator.engine import DurableEngine


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check connectivity to local models, GPU, and git dependencies."""
    print("⚡ Sovereign Dark Factory System Diagnostics")
    print("=" * 50)

    # 1. Git
    git_path = shutil.which("git")
    if git_path:
        ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
        print(f"✅ Git:                   INSTALLED ({ver})")
    else:
        print("❌ Git:                   NOT FOUND")

    # 2. NVIDIA GPU
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                check=True,
            )
            print(f"✅ NVIDIA GPU:            {res.stdout.strip()}")
        except Exception:
            print("⚠️  NVIDIA GPU:            nvidia-smi error")
    else:
        print("ℹ️  NVIDIA GPU:            nvidia-smi not available (CPU/Metal mode)")

    # 3. Ollama
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=2.0)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            models_summary = ", ".join(models[:4]) if models else "None"
            print(f"✅ Ollama:                ONLINE ({ollama_url})")
            print(f"   Available models ({len(models)}): {models_summary}")
        else:
            print(f"❌ Ollama:                HTTP {r.status_code}")
    except Exception:
        print(f"❌ Ollama:                OFFLINE ({ollama_url})")

    # 4. Prism CUDA Accelerator
    prism_url = os.getenv("PRISM_URL", "http://127.0.0.1:5272/v1")
    try:
        r = requests.get(f"{prism_url}/models", timeout=2.0)
        if r.status_code == 200:
            print(f"✅ Prism CUDA:            ONLINE ({prism_url})")
        else:
            print(f"❌ Prism CUDA:            HTTP {r.status_code}")
    except Exception:
        print(f"❌ Prism CUDA:            OFFLINE ({prism_url})")

    # 5. Local Storage
    factory_dir = Path(".factory").resolve()
    print(f"📁 Factory Journal:       {factory_dir}")
    print("=" * 50)
    print("All tasks execute 100% locally with zero cloud token cost.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Submit an autonomous coding task."""
    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}", file=sys.stderr)
        return 1

    steps: list[VerificationStep] = []
    if args.test_cmd:
        for idx, cmd_str in enumerate(args.test_cmd):
            argv = shlex.split(cmd_str)
            steps.append(VerificationStep(id=f"gate-{idx + 1}", argv=argv))
    else:
        # Default fallback verification: check if repo has test.sh or pytest
        if (repo_path / "test.sh").exists():
            steps.append(VerificationStep(id="test.sh", argv=["./test.sh"]))
        elif (repo_path / "pytest.ini").exists() or (repo_path / "tests").exists():
            steps.append(VerificationStep(id="pytest", argv=[sys.executable, "-m", "pytest"]))

    if not steps and not args.no_verify:
        print(
            "Error: No verification gates configured (no test.sh, tests/, or --test-cmd).\n"
            "A dark factory run requires deterministic verification gates to prevent blind merges.\n"
            "To bypass verification explicitly, pass --no-verify.",
            file=sys.stderr,
        )
        return 1

    spec = TaskSpec(
        repo_path=str(repo_path),
        task_prompt=args.task,
        base_rev=args.base_rev,
        model=args.model,
        verification_steps=steps,
        max_healing_attempts=args.retries,
        allow_no_verify=args.no_verify,
        allow_gate_edits=args.allow_gate_edits,
        timeout_minutes=args.timeout_minutes,
        skip_adversarial=args.no_adversarial,
        mutate_adversarial=args.mutate_adversarial,
        planner_model=args.planner_model,
        skip_plan=args.no_plan,
    )

    print("🚀 Sovereign Dark Factory submitting task...")
    print(f"   Target Repo:  {spec.repo_path}")
    print(f"   Base Rev:     {spec.base_rev}")
    print(f"   Local Model:  {spec.model}")
    if spec.planner_model:
        print(f"   Planner:      {spec.planner_model}")
    if spec.mutate_adversarial:
        print("   Adversarial:  Active test mutation enabled")
    print(f"   Verification: {len(spec.verification_steps)} gate(s) configured")
    print(f"   Prompt:       {spec.task_prompt}")
    print("-" * 50)

    engine = DurableEngine(storage_dir=args.storage_dir)
    harness = LocalCoderHarness(model=spec.model, ollama_url=args.ollama_url, prism_url=args.prism_url)

    def on_status_change(st: RunStatus):
        print(f"   ➜ Transition: {st.value}")

    try:
        manifest = engine.execute_run(
            spec=spec,
            harness=harness,
            status_callback=on_status_change,
        )

        print("-" * 50)
        print(f"🏁 RUN FINISHED: {manifest.run_id}")
        print(f"   Status:       {manifest.status.value}")
        print(f"   Patch Size:   {manifest.patch_size_bytes} bytes")
        print(f"   Healing Runs: {manifest.healing_attempts}")

        if manifest.model_telemetry:
            telem = manifest.model_telemetry
            print(f"   Tokens:       {telem.completion_tokens} generated @ {telem.tokens_per_sec} tok/s")
            print("   Cloud Cost:   $0.00 (Zero Cloud Tokens)")

        if manifest.status == RunStatus.AWAITING_REVIEW:
            print("\n🎉 Task PASSED all deterministic verification gates!")
            print(f"To inspect the diff:     dark-factory describe {manifest.run_id}")
            print(f"To approve and commit:   dark-factory review {manifest.run_id} --approve")
            print(f"To reject:               dark-factory review {manifest.run_id} --reject")
            return 0
        else:
            print("\n❌ Task failed verification or generation.", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"\n💥 Factory execution error: {e}", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List runs recorded in the factory journal."""
    engine = DurableEngine(storage_dir=args.storage_dir)
    runs = engine.list_runs()

    if not runs:
        print("No runs recorded in factory journal.")
        return 0

    print(f"{'RUN ID':<30} {'STATUS':<18} {'BASE REV':<10} {'CREATED AT':<25}")
    print("-" * 85)
    for r in runs:
        print(f"{r['run_id']:<30} {r['status']:<18} {r['base_rev'][:8]:<10} {r['created_at'][:19]:<25}")
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    """Describe a run and display its diff and evidence."""
    engine = DurableEngine(storage_dir=args.storage_dir)
    try:
        manifest = engine.get_run(args.run_id)
        patch = engine.locker.load_patch(args.run_id)
    except RunNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"=== MANIFEST: {manifest.run_id} ===")
    print(f"Status:          {manifest.status.value}")
    print(f"Repository:      {manifest.repo_path}")
    print(f"Base Revision:   {manifest.base_rev}")
    print(f"Created At:      {manifest.created_at}")
    print(f"Completed At:    {manifest.completed_at or 'In Progress'}")
    print(f"Healing Retries: {manifest.healing_attempts}")
    if manifest.repeated_failure_streak:
        print(f"Stuck Detector:  repeated the same failure {manifest.repeated_failure_streak + 1} time(s)")
    if manifest.operator_notes:
        print(f"Operator Notes:  {clean_text(manifest.operator_notes)}")

    if manifest.model_telemetry:
        telem = manifest.model_telemetry
        print(
            f"Telemetry:       {telem.completion_tokens} tokens @ {telem.tokens_per_sec} tok/s ({telem.duration_sec}s) - Cost: $0.00"
        )

    print("\n--- EXECUTION PLAN ---")
    if manifest.execution_plan:
        plan = manifest.execution_plan
        print(f"Plan ID:      {clean_text(plan.plan_id)}")
        print(f"Summary:      {clean_text(plan.summary)}")
        if plan.target_files:
            print(f"Target Files: {clean_text(', '.join(plan.target_files))}")
        if plan.invariants:
            print("Invariants:")
            for inv in plan.invariants:
                print(f"  - {clean_text(inv)}")
        if plan.steps:
            print("Steps:")
            for step in plan.steps:
                print(f"  - {clean_text(step)}")
    else:
        print("No execution plan recorded.")

    print("\n--- VERIFICATION GATES ---")
    if manifest.verification_results:
        for res in manifest.verification_results:
            st = "PASSED" if res.passed else f"FAILED (exit {res.exit_code})"
            print(f"[{res.step_id}] {st} ({res.duration_sec:.2f}s)")
    else:
        print("No verification gates recorded.")

    print("\n--- PHASE TIMINGS ---")
    if manifest.phase_timings:
        for pt in manifest.phase_timings:
            print(f"[{pt.phase}] {pt.duration_sec:.2f}s (started {pt.started_at})")
    else:
        print("No phase timings recorded.")

    print("\n--- ADVERSARIAL AUDIT ---")
    if manifest.adversarial_report:
        adv = manifest.adversarial_report
        badge = adv.badge
        print(f"Status:  [{badge}]")
        print(f"Summary: {clean_text(adv.summary)}")
        if adv.findings:
            print("Findings:")
            for f in adv.findings:
                print(f"  - [{clean_text(f.severity)}] ({clean_text(f.category)}) {clean_text(f.summary)}")
                if f.details:
                    print(f"    Details: {clean_text(f.details)}")
        else:
            print("Findings: None")
    else:
        print("No adversarial audit recorded.")

    print("\n--- ADVERSARIAL MUTATION ---")
    if manifest.adversarial_test_code:
        print("Status:  Active Hostile Probe Synthesized")
        print("Generated Probe Code (test_adversarial_probe.py):")
        for line in manifest.adversarial_test_code.splitlines():
            print(f"  {clean_text(line)}")
    else:
        print("No active test mutation recorded.")

    print("\n--- UNIFIED DIFF ---")
    if patch.strip():
        print(clean_text(patch))
    else:
        print("(No diff generated)")

    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Approve or reject a run."""
    engine = DurableEngine(storage_dir=args.storage_dir)
    try:
        manifest = engine.get_run(args.run_id)
    except RunNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if manifest.adversarial_report:
        adv = manifest.adversarial_report
        badge = adv.badge
        print(f"--- ADVERSARIAL AUDIT: [{badge}] ---")
        print(f"Summary: {clean_text(adv.summary)}")
        if adv.findings:
            print("Findings:")
            for f in adv.findings:
                print(f"  - [{clean_text(f.severity)}] ({clean_text(f.category)}) {clean_text(f.summary)}")

    if manifest.adversarial_test_code:
        print("--- ADVERSARIAL MUTATION: hostile probe synthesized (see `describe` for the code) ---")

    if args.approve:
        approve = True
    elif args.reject:
        approve = False
    elif sys.stdin.isatty():
        try:
            ans = input("Approve and apply patch? [y/N]: ").strip().lower()
            if ans in ("y", "yes"):
                approve = True
            elif ans in ("n", "no"):
                approve = False
            else:
                print("Review cancelled.")
                return 0
        except (KeyboardInterrupt, EOFError):
            print("\nReview cancelled.")
            return 0
    else:
        print("Error: Specify either --approve or --reject", file=sys.stderr)
        return 1

    try:
        manifest = engine.review_run(
            run_id=args.run_id,
            approve=approve,
            target_branch=args.branch,
            note=args.note,
        )
        if approve:
            print(f"✅ Run '{args.run_id}' APPROVED.")
            if manifest.resulting_rev:
                print(f"   Committed revision: {manifest.resulting_rev}")
        else:
            print(f"🚫 Run '{args.run_id}' REJECTED.")
        return 0
    except Exception as e:
        print(f"Review error: {e}", file=sys.stderr)
        return 1


def cmd_recover(args: argparse.Namespace) -> int:
    """Recover orphaned runs and clean up dead sandboxes."""
    engine = DurableEngine(storage_dir=args.storage_dir)
    recovered = engine.recover()
    print(f"Recovered {len(recovered)} run(s) and pruned orphaned sandboxes.")
    for rid in recovered:
        print(f" - {rid}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch the local, read-only web dashboard (binds 127.0.0.1 only)."""
    from dark_factory.dashboard import run_dashboard

    try:
        run_dashboard(storage_dir=Path(args.storage_dir), port=args.port, open_browser=not args.no_browser)
    except OSError as e:
        print(f"Error: could not start dashboard on 127.0.0.1:{args.port}: {e}", file=sys.stderr)
        return 1
    print("Dashboard stopped.")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the repeatable real-model benchmark suite against one or more named scenarios."""
    if args.list:
        print("Available eval scenarios:")
        for name, scenario in sorted(SCENARIOS.items()):
            print(f"  {name:<12} {scenario.description}")
        return 0

    names = args.scenario or sorted(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(
            f"Error: unknown scenario(s): {', '.join(unknown)}. Available: {', '.join(sorted(SCENARIOS))}",
            file=sys.stderr,
        )
        return 1

    health = LocalCoderHarness(model=args.model, ollama_url=args.ollama_url, prism_url=args.prism_url).check_health()
    if not health["ollama"] and not health["prism"]:
        print(
            "Error: no local inference engine reachable (checked Ollama and Prism). Run 'dark-factory doctor' "
            "to diagnose.",
            file=sys.stderr,
        )
        return 1

    print(f"🧪 Running eval: {', '.join(names)} (x{args.repeat}) against {args.model}")

    def on_status(msg: str) -> None:
        print(f"   {msg}")

    report = run_eval(
        names,
        harness_factory=lambda: LocalCoderHarness(
            model=args.model, ollama_url=args.ollama_url, prism_url=args.prism_url
        ),
        model=args.model,
        ollama_url=args.ollama_url,
        prism_url=args.prism_url,
        storage_dir=Path(args.storage_dir),
        repeat=args.repeat,
        keep_repos=args.keep_repos,
        status_callback=on_status,
    )

    path = save_report(report, Path(args.storage_dir))
    print()
    print(format_summary(report))
    print(f"\nSaved report: {path}")

    summary = report.scenario_summary()
    all_converged_at_least_once = all(s["converged"] > 0 for s in summary.values())
    return 0 if all_converged_at_least_once else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dark-factory",
        description="Sovereign Dark Factory — 100% local, zero-cloud-token AI Software Factory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Check local models and GPU health")
    p_doctor.set_defaults(func=cmd_doctor)

    # run
    p_run = subparsers.add_parser("run", help="Submit an autonomous factory run")
    p_run.add_argument("--repo", default=".", help="Target repository directory (default: current directory)")
    p_run.add_argument("--task", required=True, help="Task description and acceptance criteria")
    p_run.add_argument("--base-rev", default="HEAD", help="Base git commit revision (default: HEAD)")
    p_run.add_argument("--model", default="qwen2.5-coder:14b", help="Local model (default: qwen2.5-coder:14b)")
    p_run.add_argument("--test-cmd", action="append", help="Verification command (can be repeated)")
    p_run.add_argument("--no-verify", action="store_true", help="Allow run without verification gates (DANGEROUS)")
    p_run.add_argument("--allow-gate-edits", action="store_true", help="Permit agent to modify test files/gates")
    p_run.add_argument("--retries", type=int, default=3, help="Max self-healing retries (default: 3)")
    p_run.add_argument("--timeout-minutes", type=float, default=30, help="Run deadline in minutes (default: 30)")
    p_run.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_run.add_argument(
        "--ollama-url", default="http://localhost:11434", help="Ollama endpoint (default: http://localhost:11434)"
    )
    p_run.add_argument(
        "--prism-url", default="http://127.0.0.1:5272/v1", help="Prism endpoint (default: http://127.0.0.1:5272/v1)"
    )
    p_run.add_argument(
        "--no-adversarial", action="store_true", help="Skip post-verification adversarial red-team audit"
    )
    p_run.add_argument(
        "--mutate-adversarial",
        action="store_true",
        help="Synthesize hostile dynamic unit tests and feed failures into self-healing loop",
    )
    p_run.add_argument(
        "--planner-model", default=None, help="Local model for reasoning and task planning (default: same as --model)"
    )
    p_run.add_argument("--no-plan", action="store_true", help="Skip pre-execution reasoning and planning session")
    p_run.set_defaults(func=cmd_run)

    # list
    p_list = subparsers.add_parser("list", help="List runs recorded in journal")
    p_list.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_list.set_defaults(func=cmd_list)

    # describe
    p_desc = subparsers.add_parser("describe", help="Inspect run manifest, diff, and evidence")
    p_desc.add_argument("run_id", help="Run identifier")
    p_desc.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_desc.set_defaults(func=cmd_describe)

    # review
    p_review = subparsers.add_parser("review", help="Human-in-the-loop review decision")
    p_review.add_argument("run_id", help="Run identifier")
    p_review.add_argument("--approve", action="store_true", help="Approve and apply patch")
    p_review.add_argument("--reject", action="store_true", help="Reject patch")
    p_review.add_argument("--branch", help="Target branch to checkout before applying patch")
    p_review.add_argument("--note", help="Operator feedback or review note")
    p_review.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_review.set_defaults(func=cmd_review)

    # recover
    p_recover = subparsers.add_parser("recover", help="Recover interrupted runs and clean dead sandboxes")
    p_recover.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_recover.set_defaults(func=cmd_recover)

    # eval
    p_eval = subparsers.add_parser("eval", help="Run the real-model benchmark suite against named scenarios")
    p_eval.add_argument("--scenario", action="append", help="Scenario name to run (repeatable; default: all)")
    p_eval.add_argument("--repeat", type=int, default=1, help="Repeats per scenario (default: 1)")
    p_eval.add_argument("--model", default="qwen2.5-coder:14b", help="Local model (default: qwen2.5-coder:14b)")
    p_eval.add_argument(
        "--ollama-url", default="http://localhost:11434", help="Ollama endpoint (default: http://localhost:11434)"
    )
    p_eval.add_argument(
        "--prism-url", default="http://127.0.0.1:5272/v1", help="Prism endpoint (default: http://127.0.0.1:5272/v1)"
    )
    p_eval.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_eval.add_argument("--keep-repos", action="store_true", help="Keep scaffolded scenario repos for inspection")
    p_eval.add_argument("--list", action="store_true", help="List available scenarios and exit")
    p_eval.set_defaults(func=cmd_eval)

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Launch a local, read-only web dashboard (127.0.0.1 only)")
    p_dash.add_argument("--port", type=int, default=8420, help="Port to listen on (default: 8420)")
    p_dash.add_argument(
        "--storage-dir", default=".factory", help="Directory for the factory journal (default: .factory)"
    )
    p_dash.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser tab")
    p_dash.set_defaults(func=cmd_dashboard)

    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
