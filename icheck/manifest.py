"""Instruction manifests: the checkable form of written instructions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Instruction:
    """One named instruction set with its rules."""

    name: str
    description: str
    rules: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Instruction":
        if not data.get("name"):
            raise ValueError("Instruction manifest must have a 'name'.")
        rules = data.get("rules", [])
        if not isinstance(rules, list) or not rules:
            raise ValueError("Instruction manifest must have a non-empty 'rules' list.")
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict) or not rule.get("type"):
                raise ValueError(f"Rule {i} must be an object with a 'type' key.")
        return cls(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            rules=tuple(rules),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "rules": list(self.rules),
        }


def load_manifest(path: str | Path) -> Instruction:
    """Load and validate an instruction manifest from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Instruction manifest must be a JSON object.")
    return Instruction.from_dict(data)