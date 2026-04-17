---
name: python-style
description: >
  Use when writing, reviewing, or refactoring Python code in this project.
  Apply these conventions to all new code and flag violations when reviewing
  existing code. Also activate when the user asks to "check style", "review
  code quality", or "follow project conventions".
---

# Python style guide

Apply these rules to all Python code in this project. For full details on
any section, read ./style-details.md.

## Non-negotiable rules
- All functions and methods must have type hints on parameters and return type
- Use `black` formatting (line length 88)
- Use `ruff` for linting — fix all warnings before marking code as done
- No bare `except:` — always catch specific exception types

## Naming
- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods/attributes: prefix with single underscore `_name`

## Imports
- Standard library first, then third-party, then local — separated by blank lines
- Use absolute imports; avoid relative imports except within a package
- Never use `import *`

## Functions
- Keep functions focused — one clear responsibility
- Max ~30 lines; if longer, consider splitting
- Document with docstrings for any public function (Google style)

## Error handling
- Raise specific exceptions with helpful messages
- Use `pathlib.Path` for all file paths, never `os.path`

## Testing
- Tests live in `tests/` mirroring the source structure
- Use `pytest`; name test functions `test_<what_it_tests>`
- Aim for one assertion per test where practical

## When reviewing code
1. Check for missing type hints first
2. Flag any bare excepts or broad Exception catches
3. Note any functions over ~30 lines
4. Check import ordering
5. Suggest `pathlib` replacements for any `os.path` usage