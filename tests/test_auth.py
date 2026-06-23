from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.auth import _remove_old_avatar
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

    assert response.status_code == 401
    assert response.json() == {"detail": "用户名或密码错误"}


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
    assert response.json() == {"detail": "用户名或密码错误"}


def test_remove_old_avatar_refuses_path_traversal(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads" / "avatars"
    upload_dir.mkdir(parents=True)
    outside_file = tmp_path / "uploads" / "keep.txt"
    outside_file.write_text("do not delete", encoding="utf-8")

    monkeypatch.setattr("app.api.auth.UPLOAD_DIR", str(upload_dir))

    _remove_old_avatar("avatars/../keep.txt")

    assert outside_file.exists()


def test_remove_old_avatar_deletes_only_avatar_file(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads" / "avatars"
    upload_dir.mkdir(parents=True)
    avatar_file = upload_dir / "old.png"
    avatar_file.write_text("old avatar", encoding="utf-8")

    monkeypatch.setattr("app.api.auth.UPLOAD_DIR", str(upload_dir))

    _remove_old_avatar("avatars/old.png")

    assert not avatar_file.exists()
