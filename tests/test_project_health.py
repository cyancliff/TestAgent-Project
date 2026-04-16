import importlib
import os

from app.api import auth
from app.core import config
from app.main import uploads_dir


def test_models_import_has_no_create_all_side_effect(monkeypatch):
    import app.models as models

    def fail(*args, **kwargs):
        raise AssertionError("create_all should not run during import")

    monkeypatch.setattr(models.Base.metadata, "create_all", fail)
    importlib.reload(models)


def test_avatar_upload_dir_matches_static_mount():
    assert auth.UPLOAD_DIR == os.path.join(uploads_dir, "avatars")


def test_remove_old_avatar_uses_single_avatars_segment(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "UPLOAD_DIR", str(tmp_path))
    avatar_path = tmp_path / "user_1.png"
    avatar_path.write_bytes(b"test")

    auth._remove_old_avatar("avatars/user_1.png")

    assert not avatar_path.exists()


def test_build_database_url_from_env_uses_db_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("USE_SQLITE_DEV", "0")
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "secret-pass")
    monkeypatch.setenv("DB_HOST", "dbhost")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "sample_db")

    assert (
        config.build_database_url_from_env()
        == "postgresql://postgres:secret-pass@dbhost:5433/sample_db"
    )
