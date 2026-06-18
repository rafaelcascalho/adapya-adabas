# Migration plan: `uv` adoption + Python 3.13-only

Decisions confirmed by the maintainer:

1. **Python target:** narrow to `>=3.13` only. Drop 3.10–3.12 from CI, classifiers, and ruff target.
2. **tox:** delete `tox.ini`. CI matrix is the single source of truth.
3. **`adapya-base`:** keep this effort scoped to `adapya-adabas`. The known `datetime.utcnow()` `DeprecationWarning` from `adapya-base` will be filtered in tests with a note for a future follow-up.

This plan picks up after Phases 1–4 of the prior modernization (PEP 621 packaging, Py3 source fixes, lint/test tooling, lazy native-lib loading) which are already merged on this branch.

---

## Phase A — adopt `uv` as the project manager

| # | Step | Notes |
|---|------|-------|
| A1 | Install uv on the dev box | `curl -LsSf https://astral.sh/uv/install.sh \| sh`. Uv manages its own Python interpreters; no system Python changes needed. |
| A2 | Pin dev interpreter | New file `.python-version` containing `3.13`. uv reads this on `uv sync` / `uv run`. |
| A3 | Replace `[project.optional-dependencies] dev` with PEP 735 `[dependency-groups]` | The uv-idiomatic shape: `dev = ["pytest>=7", "pytest-cov", "ruff>=0.5", "mypy>=1.10", "build"]`. |
| A4 | Add `[tool.uv]` block | `package = true` (this *is* a publishable package), `default-groups = ["dev"]` so `uv sync` pulls dev tools by default. |
| A5 | Generate `uv.lock` | `uv lock` writes the resolved tree. Commit it — locks the transitive `adapya-base` resolution so dev/CI are reproducible. (For libraries, the lock is *not* shipped to PyPI but *is* committed.) |
| A6 | Delete `tox.ini` | CI matrix collapses to a single 3.13 lane (Phase B); tox no longer earns its keep. |
| A7 | Delete `setup.py` shim | PEP 517 build backend is fully declared in `pyproject.toml`. uv editable installs don't need a `setup.py`. Verify with `uv pip install -e .` before committing the delete. |
| A8 | Rewrite `.github/workflows/ci.yml` | Replace pip/build/pytest steps with uv equivalents (snippet below). |
| A9 | Update README install instructions | Recommend `uv pip install adapya-adabas` for end users and `uv sync && uv run pytest` for contributors. |

### A8 CI snippet target

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff check adapya

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv sync --frozen
      - name: Build sdist + wheel
        run: uv build
      - name: Install built wheel into the project env
        run: uv pip install --reinstall dist/*.whl
      - name: Pytest (smoke; ACL skipped)
        env:
          ADAPYA_SKIP_NATIVE_LOAD: "1"
        run: uv run pytest tests/ -q
```

No matrix block — single 3.13 lane (decided in Phase B).

### Verification gate A

- `uv sync` resolves cleanly from a fresh clone.
- `uv run pytest tests/ -q` — 5/5 smoke tests pass.
- `uv build` writes both `dist/*.tar.gz` and `dist/*.whl`.
- `uv lock --check` confirms `uv.lock` is current.
- `uv pip install -e .` works (editable install) — sanity check before deleting `setup.py`.

---

## Phase B — narrow Python target to 3.13

### B1. Metadata changes in `pyproject.toml`

```toml
[project]
requires-python = ">=3.13"
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "License :: OSI Approved :: Apache Software License",
    "Intended Audience :: Developers",
    "Natural Language :: English",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Operating System :: POSIX :: Other",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Database",
    "Topic :: Software Development",
]

[tool.ruff]
target-version = "py313"

[tool.mypy]
python_version = "3.13"
```

### B2. Bump the package version

`version = "1.4.0"` — the floor change is a breaking install-time change for anyone on older Pythons. Semver-minor on a fork is appropriate; the upstream remains at 1.3.0.

### B3. Code sweep — remove now-dead `sys.hexversion` branches

Every guard tests `sys.hexversion` against `0x03010100` (Py3.1.1) or `0x03030100` (Py3.3.1). With the floor at 3.13.0 these are all statically resolvable. Concrete sites to clean up:

| File | Line(s) | Action |
|------|---------|--------|
| `adapya/adabas/api.py` | 514 | `if sys.hexversion < 0x03010100` is unreachable — keep only the `else` body. |
| `adapya/adabas/api.py` | 559 | Same as 514. The block sits inside `if 0:` dead code; consider deleting the whole `if 0:` block while we're there. |
| `adapya/adabas/api.py` | 2686 | `if sys.hexversion < 0x03030100` is unreachable — keep only the `else` body. |
| `adapya/adabas/fields.py` | 134, 210, 288, 363, 394, 454 | `elif sys.hexversion > 0x03010100` is always taken — collapse to unconditional branch. |
| `adapya/adabas/fields.py` | 607, 638 | `if sys.platform == 'zos' and sys.hexversion < 0x03010100` — the hex test is always false, so the whole guard is false; delete the branch. (Confirm by reading context — the z/OS path may still be wanted unconditionally.) |
| `adapya/adabas/scripts/ticker.py` | 144 | `if sys.hexversion > 0x3010100` always true — unconditional. |

After the structural edits, run `ruff check --fix --select UP --target-version py313 adapya/` for any new pyupgrade hints (e.g. `Optional[X]` → `X | None` if any exist).

### B4. Stdlib removal audit

Python 3.12/3.13 dropped a long list of legacy modules. Re-grep before committing to be sure none crept in:

```bash
grep -rnE '\b(cgi|cgitb|imp|crypt|audioop|aifc|chunk|nis|nntplib|sndhdr|spwd|sunau|telnetlib|uu|xdrlib|msilib|mailcap|ossaudiodev|smtpd|distutils|pipes)\b' adapya/
```

Prior audit found only `distutils` in the old `setup.py` (deleted in A7). Re-confirm and document in the PR description.

### B5. `datetime.utcnow()` audit in our own code

```bash
grep -rn 'datetime\.utcnow\|\.utcnow()' adapya/
```

If any hits, replace with `datetime.now(datetime.UTC)`. The known offender lives in `adapya-base`, not here — see Phase C.

### Verification gate B

- `ruff check --target-version py313 adapya/` — no new findings beyond the two known pre-existing latent F821s (`safib` in `if 0:` dead block, `dot1` lambdas).
- `uv run pytest tests/ -q` — 5/5 green.
- `git diff` for B3 is pure deletion + unindent; no logic change. Verify each block manually by checking the surviving branch matches what Py3.13 would have taken.
- `uv build` produces `adapya_adabas-1.4.0` artifacts.

---

## Phase C — `adapya-base` containment

We are *not* forking `adapya-base` in this effort. We need to make its noise non-blocking.

### C1. Add a focused warning filter to pytest config

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore::DeprecationWarning:adapya.base.*",
]
```

This silences the `datetime.utcnow()` deprecation surfaced from `adapya-base/stck.py` without hiding warnings from our own code. If `adapya-base` later raises new deprecations, they show up in CI and we can decide whether to filter or fork.

### C2. Document the upstream risk

Add a short `UPSTREAM_RISK.md` (or a section in README) noting:

- `adapya-base 1.3.0` (last release 2023-12-28) is the runtime dep.
- It contains the same class of Py2 vestiges we removed here (`datetime.utcnow()`, likely `sys.hexversion` guards, possibly `unicode` references in untraversed paths).
- If Python ≥ 3.16 ships, `datetime.utcnow()` removal may force an `adapya-base` fork. Track upstream activity at https://github.com/SoftwareAG/adapya-base.

No `adapya-base` code is changed in this effort.

---

## Phase D — verification

| # | Step | Pass criterion |
|---|------|----------------|
| D1 | Cold-start reproducibility | `rm -rf .venv uv.lock && uv lock && uv sync` then `uv run pytest tests/ -q` — 5/5 pass. (Then commit the regenerated lock.) |
| D2 | Lint clean on 3.13 target | `uv run ruff check --target-version py313 adapya/` produces only the 2 known pre-existing F821s. |
| D3 | Build artifacts | `uv build` writes `dist/adapya_adabas-1.4.0.tar.gz` and `…-py3-none-any.whl`. |
| D4 | Install + import smoke | `uv pip install --reinstall dist/*.whl` then, from a tempdir with `ADAPYA_SKIP_NATIVE_LOAD=1`: `python -c "import adapya.adabas.api; print(api.adalink)"` — sentinel reported. |
| D5 | CI green | Push to a draft PR; the lint + test job pass on a single Python 3.13 runner. |
| D6 | (optional) Dep-bump dry-run | `uv lock --upgrade --dry-run` — eyeball whether any transitive updates are interesting; do not commit unintentionally. |

---

## Estimated diff size

- **Phase A:** `pyproject.toml` ~+15 lines / −5; `.github/workflows/ci.yml` rewritten (~−30/+25 lines); `tox.ini`, `setup.py` deleted; `.python-version`, `uv.lock` (~200 auto lines) added; README install block rewritten (~6 lines).
- **Phase B:** ~40 LOC removed across `api.py`, `fields.py`, `scripts/ticker.py`; `pyproject.toml` metadata flips (~10 lines).
- **Phase C:** ~3 lines added to `pyproject.toml`; new short `UPSTREAM_RISK.md`.

Net: tighter, single-target, faster CI, locked dev deps.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| `adapya-base` may itself fail to install or run on 3.13. | Verified in Phase D1: if `uv sync` resolves `adapya-base==1.3.0` and our smoke tests pass, runtime is fine. The known issue is a `DeprecationWarning`, not an error. |
| `setup.py` deletion breaks an unfamiliar IDE/editable-install path. | A7 includes a `uv pip install -e .` check before committing the delete. |
| CI matrix collapse hides regressions on Python 3.14 once released. | Add a 3.14 lane defensively *only* once 3.14 is released and we've validated. Not in this plan's scope. |
| Forks of `adapya-base` may diverge later. | Phase C2 documents the upstream-risk pointer so a future fork decision is not a surprise. |
| `uv.lock` churn on collaborators' first sync. | README contributor block instructs `uv sync` after pull. uv is fast enough that re-sync is sub-second. |

---

## Execution order

A1 → A2 → A3 → A4 → A5 → (verify gate A) → A6 → A7 → A8 → A9 → B1 → B2 → B3 → B4 → B5 → (verify gate B) → C1 → C2 → D1 → D2 → D3 → D4 → D5 → tag `v1.4.0`.

Steps A1, A8 (CI) and A9 (README) can be parallelized once A2–A5 land. Everything in Phase B is purely local and can land in one commit if reviewed carefully.
