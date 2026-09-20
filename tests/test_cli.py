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


def test_cli_run_without_gates_fails(tmp_path: Path, capsys):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    res = main(["run", "--repo", str(empty_repo), "--task", "Implement feature"])
    assert res == 1
    captured = capsys.readouterr()
    assert "No verification gates configured" in captured.err


def test_cli_run_nonexistent_repo(capsys):
    res = main(["run", "--repo", "/path/that/does/not/exist", "--task", "Foo"])
    assert res == 1
    captured = capsys.readouterr()
    assert "Repository path does not exist" in captured.err
