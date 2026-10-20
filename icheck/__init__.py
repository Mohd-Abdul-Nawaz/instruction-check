"""icheck: verify that a text output follows a set of written instructions.

A CLI for attention-to-detail QA on AI model outputs — describe the
instructions once as a JSON manifest, then check any number of outputs
against it and get a pass/fail report with a weighted score.
"""

from .manifest import Instruction, load_manifest
from .report import verdict_to_dict, verdict_to_markdown
from .rules import RuleError, RuleResult, check_rule

__version__ = "1.0.0"

__all__ = [
    "Instruction",
    "load_manifest",
    "verdict_to_dict",
    "verdict_to_markdown",
    "RuleError",
    "RuleResult",
    "check_rule",
    "__version__",
]