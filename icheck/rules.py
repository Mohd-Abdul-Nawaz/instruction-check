"""Rule engine: check a text output against instruction rules.

Rule types:
    min_words / max_words / word_count, min_chars / max_chars,
    must_include / must_not_include / include_any / include_all,
    regex / not_regex, starts_with / ends_with,
    section (required markdown heading), min_bullets,
    format (json | email | markdown | bullet-list),
    code_fence (required fenced block, optional language),
    placeholder_free, max_exclamations
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RuleResult:
    rule_type: str
    passed: bool
    weight: float
    description: str
    details: str = ""


class RuleError(ValueError):
    """Raised when a rule spec is malformed."""


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _has(needle: str, haystack: str, case_sensitive: bool) -> bool:
    return needle in haystack if case_sensitive else needle.lower() in haystack.lower()


_RULES: dict[str, Callable[[dict[str, Any], str], tuple[bool, str]]] = {}


def _rule(name: str):
    def deco(fn):
        _RULES[name] = fn
        return fn

    return deco


@_rule("min_words")
def _min_words(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    n, minimum = len(_words(text)), int(spec["value"])
    return n >= minimum, f"{n} words (minimum {minimum})"


@_rule("max_words")
def _max_words(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    n, maximum = len(_words(text)), int(spec["value"])
    return n <= maximum, f"{n} words (maximum {maximum})"


@_rule("word_count")
def _word_count(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    n = len(_words(text))
    ok = (spec.get("min") is None or n >= spec["min"]) and (
        spec.get("max") is None or n <= spec["max"]
    )
    return ok, f"{n} words (allowed {spec.get('min')}..{spec.get('max')})"


@_rule("min_chars")
def _min_chars(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    return len(text) >= int(spec["value"]), f"{len(text)} chars (minimum {spec['value']})"


@_rule("max_chars")
def _max_chars(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    return len(text) <= int(spec["value"]), f"{len(text)} chars (maximum {spec['value']})"


@_rule("must_include")
def _must_include(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    value = str(spec["value"])
    ok = _has(value, text, bool(spec.get("case_sensitive", False)))
    return ok, f"{'found' if ok else 'missing'}: {value!r}"


@_rule("must_not_include")
def _must_not_include(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    value = str(spec["value"])
    found = _has(value, text, bool(spec.get("case_sensitive", False)))
    return not found, f"{'found (forbidden)' if found else 'absent (good)'}: {value!r}"


@_rule("include_any")
def _include_any(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    values = [str(v) for v in spec.get("values", [])]
    if not values:
        raise RuleError("include_any needs a non-empty 'values' list")
    cs = bool(spec.get("case_sensitive", False))
    hits = [v for v in values if _has(v, text, cs)]
    return bool(hits), f"matched: {hits}"


@_rule("include_all")
def _include_all(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    values = [str(v) for v in spec.get("values", [])]
    if not values:
        raise RuleError("include_all needs a non-empty 'values' list")
    cs = bool(spec.get("case_sensitive", False))
    missing = [v for v in values if not _has(v, text, cs)]
    return not missing, f"missing: {missing}"


@_rule("regex")
def _regex(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    flags = 0 if spec.get("case_sensitive", False) else re.IGNORECASE
    match = re.search(spec["pattern"], text, flags)
    return bool(match), f"matched: {match.group(0)!r}" if match else "no match"


@_rule("not_regex")
def _not_regex(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    flags = 0 if spec.get("case_sensitive", False) else re.IGNORECASE
    match = re.search(spec["pattern"], text, flags)
    return not match, f"matched (unexpected): {match.group(0)!r}" if match else "no match"


@_rule("starts_with")
def _starts_with(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    value = str(spec["value"])
    cs = bool(spec.get("case_sensitive", False))
    ok = text.startswith(value) if cs else text.lower().startswith(value.lower())
    return ok, f"prefix {'ok' if ok else 'mismatch'}: {value!r}"


@_rule("ends_with")
def _ends_with(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    value = str(spec["value"])
    cs = bool(spec.get("case_sensitive", False))
    tail = text.rstrip()
    ok = tail.endswith(value) if cs else tail.lower().endswith(value.lower())
    return ok, f"suffix {'ok' if ok else 'mismatch'}: {value!r}"


@_rule("section")
def _section(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    want = str(spec["value"]).lower()
    found = {ln.lstrip("#").strip().lower() for ln in text.splitlines() if ln.startswith("#")}
    return want in found, f"heading {spec['value']!r} {'present' if want in found else 'missing'}"


@_rule("min_bullets")
def _min_bullets(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    minimum = int(spec["value"])
    n = sum(1 for ln in text.splitlines() if re.match(r"\s*(?:[-*\u2022]|\d+[.)])\s", ln))
    return n >= minimum, f"{n} bullet line(s) (minimum {minimum})"


@_rule("code_fence")
def _code_fence(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    language = spec.get("language")
    fences = re.findall(r"```(\w*)\n", text)
    if not fences:
        return False, "no fenced code block found"
    if language and language not in fences:
        return False, f"no fenced block tagged '{language}'"
    return True, f"fenced block found ({', '.join(fences)})"


@_rule("placeholder_free")
def _placeholder_free(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    tokens = ("TODO", "TBD", "FIXME", "[INSERT", "XXX", "<insert", "PLACEHOLDER", "...")
    found = [tok for tok in tokens if tok in text]
    return not found, f"placeholders found: {found}" if found else "no placeholders"


@_rule("max_exclamations")
def _max_exclamations(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    limit = int(spec.get("value", 0))
    n = text.count("!")
    return n <= limit, f"{n} exclamation mark(s) (max {limit})"


def _check_json(_: dict[str, Any], text: str) -> tuple[bool, str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    if not isinstance(parsed, dict):
        return False, f"top-level value is {type(parsed).__name__}, expected object"
    return True, "valid JSON object"


def _check_email(_: dict[str, Any], text: str) -> tuple[bool, str]:
    lines = text.splitlines()
    problems = []
    if not any(re.match(r"(?i)\s*subject\s*:", ln) for ln in lines):
        problems.append("missing 'Subject:' line")
    if not any(re.match(r"(?i)\s*(hi|hello|dear|hey)\b", ln) for ln in lines):
        problems.append("missing greeting")
    if not any(re.match(r"(?i)\s*(best|regards|sincerely|thanks|thank you|cheers)\b", ln) for ln in lines):
        problems.append("missing sign-off")
    return not problems, "; ".join(problems) if problems else "subject, greeting, sign-off present"


def _check_markdown(_: dict[str, Any], text: str) -> tuple[bool, str]:
    has_heading = any(ln.startswith("#") for ln in text.splitlines())
    return has_heading, "has headings" if has_heading else "no markdown headings"


def _check_bullet_list(_: dict[str, Any], text: str) -> tuple[bool, str]:
    n = sum(1 for ln in text.splitlines() if re.match(r"\s*[-*\u2022]\s", ln))
    return n >= 1, f"{n} bullet line(s)"


_FORMAT_CHECKS = {
    "json": _check_json,
    "email": _check_email,
    "markdown": _check_markdown,
    "bullet-list": _check_bullet_list,
}


@_rule("format")
def _format(spec: dict[str, Any], text: str) -> tuple[bool, str]:
    wanted = str(spec["value"]).lower()
    checker = _FORMAT_CHECKS.get(wanted)
    if checker is None:
        raise RuleError(
            f"Unknown format {spec['value']!r}. Supported: {', '.join(sorted(_FORMAT_CHECKS))}"
        )
    return checker(spec, text)


def check_rule(spec: dict[str, Any], text: str) -> RuleResult:
    """Run one rule spec against a text output."""
    rtype = spec.get("type")
    if not rtype:
        raise RuleError("Rule spec is missing a 'type' key")
    impl = _RULES.get(rtype)
    if impl is None:
        raise RuleError(f"Unknown rule type {rtype!r}. Supported: {', '.join(sorted(_RULES))}")
    weight = float(spec.get("weight", 1.0))
    try:
        passed, details = impl(spec, text)
    except KeyError as exc:
        raise RuleError(f"Rule type {rtype!r} is missing required field {exc}") from exc
    return RuleResult(
        rule_type=rtype,
        passed=passed,
        weight=weight,
        description=f"{rtype}: {spec.get('value', spec.get('values', spec.get('pattern', '')))}",
        details=details,
    )
