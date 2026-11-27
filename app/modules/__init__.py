"""Vertical domain modules. Each sub-package's `__init__` is its public API:
other modules import `app.modules.<name>` only, never its internals.
Boundaries are enforced by import-linter (see `[tool.importlinter]` in pyproject.toml).
"""
