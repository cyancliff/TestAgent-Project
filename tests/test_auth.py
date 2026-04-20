from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


def _build_client_with_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


def test_register_rejects_empty_password(mock_db):
    client = _build_client_with_db(mock_db)

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "review_user", "password": ""},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "密码不能为空"}
    mock_db.query.assert_not_called()
    mock_db.add.assert_not_called()


def test_register_rejects_whitespace_only_password(mock_db):
    client = _build_client_with_db(mock_db)

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "review_user", "password": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "密码不能为空"}
    mock_db.query.assert_not_called()
    mock_db.add.assert_not_called()


def test_register_rejects_short_password(mock_db):
    client = _build_client_with_db(mock_db)

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "review_user", "password": "1234567"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "密码至少需要 8 位"}
    mock_db.query.assert_not_called()
    mock_db.add.assert_not_called()


def test_register_rejects_invalid_username(mock_db):
    client = _build_client_with_db(mock_db)

    try:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "bad name", "password": "12345678"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "用户名需为 3-20 位字母、数字或下划线"}
    mock_db.query.assert_not_called()
    mock_db.add.assert_not_called()


def test_login_rejects_unknown_username(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    client = _build_client_with_db(mock_db)

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "missing_user", "password": "12345678"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "用户名不存在"}


def test_login_rejects_wrong_password(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=1,
        username="review_user",
        nickname="Review User",
        password_hash="hashed-password",
    )
    client = _build_client_with_db(mock_db)

    try:
        with patch("app.api.auth.verify_password", return_value=False):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "review_user", "password": "wrong-password"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {"detail": "密码错误"}
