# Upstream risk: `adapya-base`

`adapya-adabas` depends on `adapya-base>=1.3.0` as a runtime dep. We do not
maintain `adapya-base` in this repo and the last upstream release
(`adapya-base 1.3.0`, 2023-12-28) has not seen activity since.

## Known issues we tolerate

- `adapya/base/stck.py` calls `datetime.utcnow()` in a function default
  argument. Python ≥ 3.12 raises a `DeprecationWarning` for this; Python
  ≥ 3.16 is expected to remove the function entirely. We suppress the
  warning in our test runs via `[tool.pytest.ini_options].filterwarnings`
  in `pyproject.toml`, scoped to `adapya.base.*`. Production code is
  unaffected today.
- Expect the same class of Python-2 vestiges we removed from this
  package (`sys.hexversion` guards against ancient interpreters, possibly
  `unicode` references in z/OS-only code paths) to still live in
  `adapya-base`.

## What would force a fork

- Python ≥ 3.16 ships and removes `datetime.utcnow()`. At that point
  `adapya-base` either gets a new upstream release or we fork.
- A transitive `adapya-base` dependency stops resolving on a supported
  Python.

## Where to watch

Upstream repo: <https://github.com/SoftwareAG/adapya-base>
