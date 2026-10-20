# ✅ icheck

**Verify that a text output follows a set of written instructions — a CLI for attention-to-detail QA on AI model outputs.**

Describe the instructions once as a JSON manifest, then check any number of outputs against it and get a pass/fail report with a weighted score. Built for the exact skill micro1 hires for: following complex instructions with precision and consistency.

## Quick start

```bash
git clone https://github.com/Mohd-Abdul-Nawaz/instruction-check.git
cd instruction-check
pip install -e .
icheck init --dir samples
icheck check samples/instruction.json samples/good.txt
icheck check samples/instruction.json samples/bad.txt
icheck batch samples/ --json-out results.json
```

## Example

```
$ icheck check samples/instruction.json samples/good.txt
[PASS] support-reply (score 1.00, 7/7)
  1. [ok] min_words: 20 — 52 words (minimum 20)
  ...
$ icheck check samples/instruction.json samples/bad.txt
[FAIL] support-reply (score 0.29, 2/7)
  1. [FAIL] min_words: 20 — 17 words (minimum 20)
  ...
```

## Rule types

Length (`min_words`, `max_words`, `word_count`, `min_chars`, `max_chars`), inclusion (`must_include`, `must_not_include`, `include_any`, `include_all`), patterns (`regex`, `not_regex`, `starts_with`, `ends_with`), structure (`section`, `min_bullets`, `code_fence`), formats (`json`, `email`, `markdown`, `bullet-list`), quality (`placeholder_free`, `max_exclamations`). Every rule supports a `weight` for weighted scoring.

See [`samples/instruction.json`](samples/instruction.json) for a full example.

## Commands

| Command | Purpose |
|---|---|
| `icheck check MANIFEST OUTPUT [--format text\|json\|markdown] [--strict-placeholders]` | Check one file (exit 0 = pass, 1 = fail, 2 = error) |
| `icheck batch MANIFEST DIR [--json-out FILE]` | Check every `.txt` in a directory |
| `icheck init --dir DIR` | Scaffold a starter manifest + good/bad examples |

## Tests

```bash
pytest -q
```

## License

MIT
