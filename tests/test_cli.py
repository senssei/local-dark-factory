"""Unit tests for dark_factory.cli."""

from pathlib import Path

from dark_factory.cli import main


def test_cli_doctor():
    res = main(["doctor"])
    assert res == 0


def test_cli_list_empty(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = main(["list"])
    assert res == 0


def test_cli_review_invalid_args():
    res = main(["review", "run-fake"])
    assert res == 1


def test_cli_describe_not_found(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = main(["describe", "run-nonexistent"])
    assert res == 1
