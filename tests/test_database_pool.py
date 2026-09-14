"""A pooled connection closed by the server must not reach a request.

Measured on 2026-09-11 in dev: the first request after an idle period got a
connection PostgreSQL had already closed, and POST /auth/token answered 500
("connection is closed"). apowerb, which calls that route before indexing a
file, reported the upload as a configuration error. pool_pre_ping checks the
connection before handing it out and transparently replaces a dead one.
"""

from th2rag.database import DatabaseSessionManager


def test_pool_checks_connections_before_use():
    manager = DatabaseSessionManager("postgresql+asyncpg://user:pass@localhost:5432/db")

    assert manager.engine.pool._pre_ping is True


def test_pool_recycles_connections_before_server_side_timeouts():
    manager = DatabaseSessionManager("postgresql+asyncpg://user:pass@localhost:5432/db")

    assert 0 < manager.engine.pool._recycle <= 300
