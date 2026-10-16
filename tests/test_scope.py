"""Unit tests for dark_factory.verification.scope (DF-LIVE-06a)."""


def _check(paths, target_files=()):
    from dark_factory.verification.scope import check_patch_scope

    return check_patch_scope(list(paths), list(target_files))


def test_placeholder_path_is_flagged_even_without_target_files():
    # the exact shape of the winter-prognosis run: the real fix plus a copy under the prompt's example path
    assert _check(["frost_stats.py", "path/to/frost_stats.py"]) == ["path/to/frost_stats.py"]


def test_placeholder_is_flagged_below_a_prefix_directory():
    assert _check(["src/path/to/x.py"]) == ["src/path/to/x.py"]


def test_similar_looking_paths_are_not_placeholders():
    assert _check(["path/tomorrow.py", "a/path/b/to.py", "to/path/x.py", "path.py"]) == []


def test_normal_patch_without_target_files_has_no_violation():
    assert _check(["primes.py", "docs/notes.md"]) == []


def test_target_file_only_is_in_scope():
    assert _check(["frost_stats.py"], ["frost_stats.py"]) == []


def test_extra_file_outside_target_files_is_out_of_scope():
    assert _check(["frost_stats.py", "helper.py", "tests/test_x.py"], ["frost_stats.py"]) == [
        "helper.py",
        "tests/test_x.py",
    ]


def test_target_directory_prefix_covers_files_below_it():
    assert _check(["pkg/a.py", "pkg/sub/b.py", "pkgx/c.py"], ["pkg/"]) == ["pkgx/c.py"]


def test_deleted_file_outside_targets_is_reported_like_any_other_path():
    assert _check(["frost_stats.py", "README.md"], ["frost_stats.py"]) == ["README.md"]


def test_empty_patch_has_no_violation():
    assert _check([], ["frost_stats.py"]) == []


def test_both_rules_report_each_path_once_in_sorted_order():
    assert _check(["path/to/z.py", "a.py"], ["z.py"]) == ["a.py", "path/to/z.py"]


def test_bare_directory_target_covers_files_below_it():
    assert _check(["pkg/a.py", "pkg/sub/b.py", "pkgx/c.py", "pkg"], ["pkg"]) == ["pkgx/c.py"]


def test_dot_slash_prefixed_target_matches_the_plain_path():
    assert _check(["x.py", "y.py"], ["./x.py"]) == ["y.py"]


def test_dot_target_means_the_whole_repository_but_placeholders_still_fail():
    assert _check(["x.py", "a/b.py", "path/to/c.py"], ["."]) == ["path/to/c.py"]
    assert _check(["x.py"], ["./"]) == []


def test_empty_target_is_ignored():
    assert _check(["x.py"], [""]) == ["x.py"]


def _scope_violations(diff, target_files=()):
    from dark_factory.orchestrator.engine import scope_violations

    return scope_violations(diff, list(target_files))


def test_unparseable_diff_header_is_a_violation_not_a_silent_pass():
    ok = "diff --git a/ok.py b/ok.py\n--- a/ok.py\n+++ b/ok.py\n"
    weird = "diff --git a/x.py b/y.py z\n--- a/x.py\n+++ b/y.py\n"  # no parseable path in this header

    assert _scope_violations(ok, ["ok.py"]) == []
    assert _scope_violations(ok + weird, ["ok.py"]) == ["<unparseable diff header>"]


def test_gate_input_with_spaces_and_quotes_is_classified_by_its_real_path():
    diff = 'diff --git "a/sp ace/\\303\\251.py" "b/sp ace/\\303\\251.py"\n--- a/x\n+++ b/x\n'

    assert _scope_violations(diff, ["sp ace/é.py"]) == []
    assert _scope_violations(diff, ["other.py"]) == ["sp ace/é.py"]
