---
icon: lucide/badge-check
---

# Testing and release

## Run the checks

The library supports Python 3.10 and newer. Development tools require Python
3.11 or newer; the repository pins Python 3.14 for local development. CI uses
the smaller `test` dependency group to test the library on Python 3.10 as well.

```bash
uv sync --locked --all-groups
uv run pip-audit --local --progress-spinner off
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --cov=anihmm --cov-report=term-missing --cov-fail-under=85
uv run python -m tools.generate_demo_gif --check
uv run zensical build --clean --strict
uv run rumdl check README.md docs
```

The GIF check fingerprints each animation against its example module, the
package source, and the generator. If it fails after an intentional example or
rendering change, regenerate the assets with
`uv run python -m tools.generate_demo_gif`.

Generation executes every example through the playback engine and records its
real frame timing before applying the shared documentation styling.

## Test map

| Area | Tests |
| --- | --- |
| Playback and sessions | `tests/playback/` |
| Random generation | `tests/presets/` |
| Geometry and rendering | `tests/render/` |
| Builder and compiler errors | `tests/sequence/` |
| End-to-end examples | `tests/integration/` |

Test observable behavior through the public API, with independent expected
results. Keep one test for each contract and failure mode; reuse existing coverage
instead of adding copies. Geometry changes need exact cell assertions; lifecycle
changes need timing, cancellation, and failure-path coverage. Avoid assertions
about private state, helper calls, or APIs that have been removed.

## Before release

1. Run every check above.
2. Confirm the CI matrix passes on Python 3.10 through 3.14, including the
   macOS and Windows jobs. Each job explicitly selects its Python version for uv.
3. Build and test the installed wheel in isolation, as shown below.
4. Confirm the version in `pyproject.toml` matches the intended `v`-prefixed tag.
5. Verify the public documentation and README asset URLs work before publishing.

### Validate the distributions

Build into a fresh directory so older versions or unrelated packages in `dist/`
cannot become release assets. Copy only the tests and examples into the isolated
check directory, then run them against the built wheel:

```bash
release_check="$(mktemp -d)"
uv build --out-dir "$release_check/dist"
cp -R tests examples "$release_check/"
(
    cd "$release_check"
    uv run --no-project --isolated --python 3.14 \
        --with "$release_check"/dist/anihmm-*.whl \
        --with pytest python -I -m pytest tests
)
```

This runs the entire suite, including the example workflow, without the checkout's
`src/` directory or pytest configuration on the import path. `python -I` also
ignores `PYTHONPATH`. Running pytest from the original checkout would use its
configured source path and could hide a broken wheel. CI and tagged releases run
the same isolated wheel check before their distribution artifacts are accepted.

Only use the distributions from the fresh output directory for a manual upload.

### Configure publishing

CI, documentation deployment, and tagged releases are defined in
`.github/workflows/ci.yml`, `.github/workflows/docs.yml`, and
`.github/workflows/release.yml`.

Before the first release, select **GitHub Actions** as the repository's Pages
source. On PyPI, configure a trusted publisher for `leightonpayne/anihmm`, the
`release.yml` workflow, and the `pypi` environment. Tags then publish the built
distributions without a long-lived API token.
