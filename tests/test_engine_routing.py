"""Routing and residency: which model is asked to load, and on which engine, for a whole run (DF-LIVE-01).

Uses fake Ollama/Prism HTTP engines (`engine_fakes`) that track loaded models, so no real model is needed. The Ollama
URL points at a closed port, as in the live reproduction that loaded an unintended default model.
"""

from pathlib import Path

import pytest
import requests
from engine_fakes import FakeOllama, FakePrism, loaded_models

from dark_factory.domain.types import RunStatus, TaskSpec
from dark_factory.eval.runner import run_scenario
from dark_factory.eval.scenarios import SCENARIOS
from dark_factory.harness.local_coder import LocalCoderHarness
from dark_factory.orchestrator.engine import DurableEngine

CLOSED_OLLAMA = "http://127.0.0.1:1"
EVAL_MODEL = "Phi-4-mini-instruct-cuda-gpu"
PLANNER_MODEL = "Qwen3-4B-cuda-int4-kld-block-128"


@pytest.fixture
def posted_urls(monkeypatch) -> list[str]:
    """Every URL the code under test POSTs to, so a request to a default endpoint cannot go unnoticed."""
    urls: list[str] = []
    original = requests.post

    def recording_post(url, *args, **kwargs):
        urls.append(url)
        return original(url, *args, **kwargs)

    monkeypatch.setattr(requests, "post", recording_post)
    return urls


def _only_configured_endpoints(urls: list[str], prism_url: str) -> bool:
    return all(u.startswith((prism_url, CLOSED_OLLAMA)) for u in urls)


def test_loaded_models_reports_what_each_engine_holds():
    with FakeOllama() as ollama, FakePrism() as prism:
        assert loaded_models(ollama.url, prism.url) == {"ollama": set(), "prism": set()}
        ollama.record("llama3.1:8b")
        prism.record(EVAL_MODEL)
        assert loaded_models(ollama.url, prism.url) == {"ollama": {"llama3.1:8b"}, "prism": {EVAL_MODEL}}


def test_loaded_models_treats_an_unreachable_engine_as_empty():
    assert loaded_models(CLOSED_OLLAMA, "http://127.0.0.1:2") == {"ollama": set(), "prism": set()}


def test_eval_run_asks_only_the_evaluated_model_to_load(tmp_path: Path, posted_urls: list[str]):
    with FakeOllama() as ollama, FakePrism() as prism:
        results = run_scenario(
            SCENARIOS["primes"],
            harness_factory=lambda: LocalCoderHarness(model=EVAL_MODEL, ollama_url=CLOSED_OLLAMA, prism_url=prism.url),
            storage_dir=tmp_path / ".factory",
            model=EVAL_MODEL,
        )

        assert results[0].converged
        assert set(prism.requested) == {EVAL_MODEL}
        assert len(prism.requested) == 3  # planner, coder and auditor, all on the configured engine
        assert _only_configured_endpoints(posted_urls, prism.url)
        assert loaded_models(ollama.url, prism.url) == {"ollama": set(), "prism": {EVAL_MODEL}}


def test_distinct_planner_model_loads_only_on_the_configured_engine(tmp_path: Path, posted_urls: list[str]):
    scenario = SCENARIOS["primes"]
    repo = tmp_path / "repo"
    scenario.build_repo(repo)
    spec = TaskSpec(
        repo_path=str(repo),
        task_prompt=scenario.task_prompt,
        verification_steps=scenario.verification_steps(),
        protected_paths=list(scenario.protected_paths),
        model=EVAL_MODEL,
        planner_model=PLANNER_MODEL,
    )
    with FakePrism() as prism:
        coder = LocalCoderHarness(model=EVAL_MODEL, ollama_url=CLOSED_OLLAMA, prism_url=prism.url)
        manifest = DurableEngine(storage_dir=tmp_path / ".factory").execute_run(spec=spec, harness=coder, run_id="r1")

        assert manifest.status == RunStatus.AWAITING_REVIEW
        assert prism.requested[0] == PLANNER_MODEL  # the planner ran first, on the coder's endpoint
        assert set(prism.requested) == {PLANNER_MODEL, EVAL_MODEL}
        assert _only_configured_endpoints(posted_urls, prism.url)
