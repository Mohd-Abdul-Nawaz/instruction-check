"""icheck command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .manifest import Instruction, load_manifest
from .report import check_output, verdict_to_dict, verdict_to_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icheck",
        description="Check a text output against a JSON instruction manifest.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check one output file against a manifest.")
    check.add_argument("manifest", help="Path to instruction manifest JSON.")
    check.add_argument("output", help="Path to the text output file to check.")
    check.add_argument(
        "--format",
        choices=("text", "json", "markdown"),
        default="text",
        help="Report format (default: text).",
    )
    check.add_argument(
        "--strict-placeholders",
        action="store_true",
        help="Also fail if placeholder tokens (TODO, TBD, ...) appear.",
    )

    batch = sub.add_parser("batch", help="Check every .txt file in a directory.")
    batch.add_argument("manifest", help="Path to instruction manifest JSON.")
    batch.add_argument("directory", help="Directory of .txt outputs.")
    batch.add_argument("--json-out", default="", help="Write JSON results to this file.")

    init = sub.add_parser("init", help="Write a starter manifest + example outputs.")
    init.add_argument("--dir", default=".", help="Directory to write samples into.")
    return parser


def _print_text_report(verdict, stream=sys.stdout) -> None:
    status = "PASS" if verdict.passed else "FAIL"
    print(f"[{status}] {verdict.instruction} "
          f"(score {verdict.score:.2f}, {verdict.passed_count}/{len(verdict.results)})",
          file=stream)
    for i, r in enumerate(verdict.results, 1):
        mark = "ok" if r.passed else "FAIL"
        print(f"  {i:>2}. [{mark}] {r.description} - {r.details}", file=stream)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        instruction = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: cannot load manifest: {exc}", file=sys.stderr)
        return 2
    try:
        text = Path(args.output).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read output file: {exc}", file=sys.stderr)
        return 2

    rules = list(instruction.rules)
    if args.strict_placeholders and not any(
        isinstance(r, dict) and r.get("type") == "placeholder_free" for r in rules
    ):
        rules.append({"type": "placeholder_free"})
        instruction = Instruction(
            name=instruction.name, description=instruction.description, rules=tuple(rules)
        )

    verdict = check_output(instruction, text)
    if args.format == "json":
        print(json.dumps(verdict_to_dict(verdict), indent=2))
    elif args.format == "markdown":
        print(verdict_to_markdown(verdict))
    else:
        _print_text_report(verdict)
    return 0 if verdict.passed else 1


def cmd_batch(args: argparse.Namespace) -> int:
    try:
        instruction = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: cannot load manifest: {exc}", file=sys.stderr)
        return 2
    directory = Path(args.directory)
    files = sorted(directory.glob("*.txt"))
    if not files:
        print(f"error: no .txt files in {directory}", file=sys.stderr)
        return 2
    results = []
    failures = 0
    for path in files:
        verdict = check_output(instruction, path.read_text(encoding="utf-8"))
        results.append({"file": path.name, **verdict_to_dict(verdict)})
        _print_text_report(verdict)
        failures += 0 if verdict.passed else 1
    passed = len(files) - failures
    print(f"\nBatch: {passed}/{len(files)} passed.")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote JSON results to {args.json_out}")
    return 0 if failures == 0 else 1


STARTER_MANIFEST = {
    "name": "concise-summary",
    "description": "Summary must be short, structured, and placeholder-free.",
    "rules": [
        {"type": "min_words", "value": 30},
        {"type": "max_words", "value": 150},
        {"type": "section", "value": "Summary"},
        {"type": "min_bullets", "value": 2},
        {"type": "placeholder_free"},
        {"type": "must_not_include", "value": "as an AI"},
    ],
}

STARTER_PASS = (
    "# Summary\n\nThe model consolidates the quarterly findings into three themes.\n\n"
    "- Revenue grew in all regions except one.\n"
    "- Support tickets fell after the new help center launched.\n"
    "- Churn improved among annual-plan customers.\n\n"
    "Overall the quarter shows steady progress with clear next steps.\n"
)

STARTER_FAIL = "TODO write the summary later... As an AI I will expand this soon."


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "instruction.json").write_text(
        json.dumps(STARTER_MANIFEST, indent=2), encoding="utf-8"
    )
    (target / "good.txt").write_text(STARTER_PASS, encoding="utf-8")
    (target / "bad.txt").write_text(STARTER_FAIL, encoding="utf-8")
    print(f"Wrote instruction.json, good.txt, bad.txt to {target}")
    print("Try: icheck check instruction.json good.txt")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "batch":
        return cmd_batch(args)
    if args.command == "init":
        return cmd_init(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
