from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "App.vue"
HISTORY_COMPONENT = PROJECT_ROOT / "frontend" / "src" / "components" / "History.vue"


def test_formdata_uploads_do_not_set_multipart_content_type_manually():
    combined = "\n".join(
        [
            APP_COMPONENT.read_text(encoding="utf-8"),
            HISTORY_COMPONENT.read_text(encoding="utf-8"),
        ]
    )

    assert "Content-Type': 'multipart/form-data'" not in combined
    assert '"Content-Type": "multipart/form-data"' not in combined
