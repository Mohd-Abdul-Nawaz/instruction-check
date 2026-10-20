"""Verdicts and report rendering for icheck."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .manifest import Instruction
from .rules import RuleResult, check_rule


@dataclass
class Verdict:
    instruction: str
    output_chars: int
    results: list[RuleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def score(self) -> float:
        total = sum(r.weight for r in self.results)
        if total == 0:
            return 1.0
        earned = sum(r.weight for r in self.results if r.passed)
        return round(earned / total, 4)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    def to_dict(self) -> dict:
        return {
            "instruction": self.instruction,
            "verdict": "PASS" if self.passed else "FAIL",
            "score": self.score,
            "passed": self.passed_count,
            "total": len(self.results),
            "output_chars": self.output_chars,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "rules": [
                {
                    "type": r.rule_type,
                    "passed": r.passed,
                    "weight": r.weight,
                    "description": r.description,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


def check_output(instruction: Instruction, text: str) -> Verdict:
    """Check one text output against every rule in an instruction manifest."""
    return Verdict(
        instruction=instruction.name,
        output_chars=len(text),
        results=[check_rule(spec, text) for spec in instruction.rules],
    )


def verdict_to_markdown(verdict: Verdict) -> str:
    lines = [
        f"# icheck report: {verdict.instruction}",
        "",
        f"**Verdict: {'PASS' if verdict.passed else 'FAIL'}** "
        f"(score {verdict.score:.2f}, {verdict.passed_count}/{len(verdict.results)} rules passed)",
        "",
        "| # | Rule | Result | Details |",
        "|---|------|--------|---------|",
    ]
    for i, r in enumerate(verdict.results, 1):
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"| {i} | {r.description} | **{mark}** | {r.details} |")
    lines.append("")
    return "\n".join(lines)


def verdict_to_dict(verdict: Verdict) -> dict:
    return verdict.to_dict()
