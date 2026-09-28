"""A test run that uses the async_db fixture must let the interpreter exit.

Measured on 2026-09-28: the suite printed its summary, then python sat at 0%
CPU forever. The only non-daemon thread left was aiosqlite's connection worker,
kept alive by a pooled connection of an engine that was never disposed, so
interpreter shutdown waited on it.

The run is checked in a subprocess because the hang happens at interpreter
exit. Only the exit is asserted: the async_db tests currently error on SQLite
(JSONB columns), which is a separate issue and must not affect this check.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_session_using_async_db_exits():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")])
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "test/users/test_service.py",
        "-q",
        "--no-cov",
        "-p",
        "no:cacheprovider",
    ]

    try:
        result = subprocess.run(
            command, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "pytest did not exit after its run: a non-daemon thread "
            "(e.g. an undisposed aiosqlite connection) is still alive"
        ) from exc

    lines = result.stdout.splitlines()
    assert lines and " in " in lines[-1], result.stdout[-2000:] + result.stderr[-2000:]
