"""Tests for the icheck package (rules, reports, CLI)."""

import json

import pytest

from icheck import Instruction, load_manifest
from icheck.cli import STARTER_FAIL, STARTER_MANIFEST, STARTER_PASS, main
from icheck.report import check_output, verdict_to_dict, verdict_to_markdown
from icheck.rules import RuleError, check_rule


def test_length_rules():
    short = "hello world"
    assert check_rule({"type": "min_words", "value": 2}, short).passed
    assert not check_rule({"type": "min_words", "value": 5}, short).passed
    assert check_rule({"type": "max_words", "value": 5}, short).passed
    assert check_rule({"type": "word_count", "min": 1, "max": 3}, short).passed


def test_inclusion_rules_case_insensitive():
    text = "Please include the API key in your reply."
    assert check_rule({"type": "must_include", "value": "api KEY"}, text).passed
    assert not check_rule({"type": "must_not_include", "value": "api key"}, text).passed
    assert check_rule({"type": "include_any", "values": ["nope", "API key"]}, text).passed
    assert not check_rule({"type": "include_all", "values": ["API key", "nope"]}, text).passed


def test_regex_and_anchors():
    text = "Order #12345 shipped."
    assert check_rule({"type": "regex", "pattern": r"#\d+"}, text).passed
    assert check_rule({"type": "not_regex", "pattern": r"refund"}, text).passed
    assert check_rule({"type": "starts_with", "value": "Order"}, text).passed
    assert check_rule({"type": "ends_with", "value": "shipped."}, text).passed


def test_structure_rules():
    text = "# Summary\n\n- one\n- two\n\n```python\nprint(1)\n```\n"
    assert check_rule({"type": "section", "value": "Summary"}, text).passed
    assert check_rule({"type": "min_bullets", "value": 2}, text).passed
    assert check_rule({"type": "code_fence", "language": "python"}, text).passed
    assert not check_rule({"type": "code_fence", "language": "rust"}, text).passed


def test_format_and_placeholder_rules():
    assert check_rule({"type": "format", "value": "json"}, '{"a": 1}').passed
    assert not check_rule({"type": "format", "value": "json"}, "not json").passed
    email = "Subject: Hi\n\nHello team,\n\nUpdate here.\n\nBest,\nSam"
    assert check_rule({"type": "format", "value": "email"}, email).passed
    assert check_rule({"type": "placeholder_free"}, "clean output").passed
    assert not check_rule({"type": "placeholder_free"}, "TODO later").passed
    assert check_rule({"type": "max_exclamations", "value": 1}, "Nice!").passed
    assert not check_rule({"type": "max_exclamations", "value": 1}, "Wow!!").passed


def test_unknown_rule_and_missing_field():
    with pytest.raises(RuleError):
        check_rule({"type": "nope"}, "text")
    with pytest.raises(RuleError):
        check_rule({"type": "min_words"}, "text")


def test_verdict_scoring_and_weights():
    instruction = Instruction(
        name="demo",
        description="",
        rules=(
            {"type": "min_words", "value": 2, "weight": 3.0},
            {"type": "must_include", "value": "missing", "weight": 1.0},
        ),
    )
    verdict = check_output(instruction, "hello world")
    assert not verdict.passed
    assert verdict.score == 0.75
    as_dict = verdict_to_dict(verdict)
    assert as_dict["verdict"] == "FAIL" and as_dict["passed"] == 1
    markdown = verdict_to_markdown(verdict)
    assert "FAIL" in markdown and "hello" not in markdown


def test_starter_manifest_passes_good_fails_bad():
    instruction = Instruction.from_dict(STARTER_MANIFEST)
    assert check_output(instruction, STARTER_PASS).passed
    assert not check_output(instruction, STARTER_FAIL).passed


def test_load_manifest_rejects_bad_files(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "x", "rules": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(bad)


def test_cli_check_exit_codes(tmp_path, capsys):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps(STARTER_MANIFEST), encoding="utf-8")
    good = tmp_path / "good.txt"
    good.write_text(STARTER_PASS, encoding="utf-8")
    assert main(["check", str(manifest), str(good)]) == 0
    bad = tmp_path / "bad.txt"
    bad.write_text(STARTER_FAIL, encoding="utf-8")
    assert main(["check", str(manifest), str(bad)]) == 1
    assert main(["check", str(manifest), str(bad), "--format", "json"]) == 1
    out = capsys.readouterr().out
    assert '"verdict": "FAIL"' in out


def test_cli_batch_and_init(tmp_path):
    assert main(["init", "--dir", str(tmp_path)]) == 0
    out_file = tmp_path / "results.json"
    code = main(["batch", str(tmp_path / "instruction.json"), str(tmp_path),
                 "--json-out", str(out_file)])
    assert code == 1  # bad.txt fails
    results = json.loads(out_file.read_text(encoding="utf-8"))
    assert {r["file"] for r in results} == {"good.txt", "bad.txt"}
