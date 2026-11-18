---
icon: lucide/git-pull-request
---

# Contributing

Clone the project and install every dependency group:

```bash
git clone https://github.com/leightonpayne/anihmm
cd anihmm
uv sync --locked --all-groups
```

Keep changes focused and add regression coverage for changed behavior. The
[Codebase tour](../developer/codebase.md) explains where each kind of change
belongs. The [Testing and release guide](../developer/testing.md) is the single
checklist for validation and packaging.

Use `uv run ruff format .` to apply formatting and `uv run zensical serve` to
preview documentation changes.
