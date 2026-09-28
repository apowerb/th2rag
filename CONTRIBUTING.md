# Contributing to th2rag

th2rag is the retrieval-augmented generation library of the
[apowerb](https://github.com/apowerb/apowerb) stack. Issues and pull requests
are welcome.

## Licence and CLA

Contributions are licensed under the [Apache License 2.0](./LICENSE), like the
rest of the project. You keep the copyright on what you write.

A **Contributor License Agreement** is required before a pull request can be
merged. It is the same agreement for every apowerb repository:
[CLA.md](https://github.com/apowerb/apowerb/blob/main/CLA.md), in the core
repository, which also explains what it does and does not do.

A bot comments on your first pull request and asks you to sign by replying to
it. One signature covers everything you contribute afterwards, here and in the
other apowerb repositories; if you have already signed in one of them, you will
not be asked again. Signatures are recorded in
[`signatures/cla.json`](https://github.com/apowerb/apowerb/blob/main/signatures/cla.json)
in the core repository.

The licence covers the code and not the marks: see
[TRADEMARK.md](https://github.com/apowerb/apowerb/blob/main/TRADEMARK.md)
before naming a fork or reusing the logo.

## Getting set up

Dependencies are managed with [uv](https://docs.astral.sh/uv/), and the
lockfile is committed — do not hand-edit `uv.lock`.

```bash
uv sync
```

Settings are validated at import time. `tests/conftest.py` gives the required
ones inert values; the older suite under `test/` expects them in the
environment. Inert values work — `DB_PORT` and `ACCESS_TOKEN_EXPIRE_MINUTES`
must be integers and `S3_ENDPOINT` a URL (e.g. `http://localhost:9000`); the
others can be any non-empty string.

```bash
PYTHONPATH=src uv run pytest test tests --no-cov
```

## Pull requests

- One concern per pull request, with a test that fails without the change.
- Conventional commit messages (`fix(converters): …`, `feat(chunkers): …`).
- Document conversion changes: say which Docling version you measured on, and
  include a reproducer when the behaviour depends on a particular document.
