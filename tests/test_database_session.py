import pytest

from app.core import database


class FakeSession:
    def __init__(self):
        self.rolled_back = False
        self.closed = False

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_get_db_rolls_back_on_exception(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    dependency = database.get_db()
    assert next(dependency) is fake_session

    with pytest.raises(RuntimeError):
        dependency.throw(RuntimeError("request failed"))

    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_get_db_closes_after_success(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    dependency = database.get_db()
    assert next(dependency) is fake_session

    with pytest.raises(StopIteration):
        next(dependency)

    assert fake_session.rolled_back is False
    assert fake_session.closed is True
