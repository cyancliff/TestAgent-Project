from app.core import config


def test_deepseek_defaults_use_v4_flash_and_non_thinking(monkeypatch):
    for key in (
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_CHAT_MODEL",
        "DEEPSEEK_ANALYSIS_MODEL",
        "DEEPSEEK_RAG_MODEL",
        "DEEPSEEK_RAG_RETRIEVE_MODEL",
        "DEEPSEEK_CHAT_THINKING",
        "DEEPSEEK_ANALYSIS_THINKING",
        "DEEPSEEK_RAG_THINKING",
    ):
        monkeypatch.delenv(key, raising=False)

    assert config.get_deepseek_base_url() == "https://api.deepseek.com"
    assert config.get_deepseek_chat_model() == "deepseek-v4-flash"
    assert config.get_deepseek_analysis_model() == "deepseek-v4-flash"
    assert config.get_deepseek_rag_model() == "deepseek-v4-flash"
    assert config.get_deepseek_rag_retrieve_model() == "deepseek-v4-flash"
    assert config.get_deepseek_chat_thinking_mode() == "disabled"
    assert config.get_deepseek_analysis_thinking_mode() == "disabled"
    assert config.get_deepseek_rag_thinking_mode() == "disabled"
    assert config.build_deepseek_thinking_payload(config.get_deepseek_chat_thinking_mode()) == {
        "thinking": {"type": "disabled"}
    }


def test_deepseek_overrides_chain_across_chat_analysis_and_rag(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-pro")
    monkeypatch.delenv("DEEPSEEK_ANALYSIS_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_RAG_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_RAG_RETRIEVE_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_CHAT_THINKING", "enabled")
    monkeypatch.delenv("DEEPSEEK_ANALYSIS_THINKING", raising=False)
    monkeypatch.delenv("DEEPSEEK_RAG_THINKING", raising=False)

    assert config.get_deepseek_chat_model() == "deepseek-v4-pro"
    assert config.get_deepseek_analysis_model() == "deepseek-v4-pro"
    assert config.get_deepseek_rag_model() == "deepseek-v4-pro"
    assert config.get_deepseek_rag_retrieve_model() == "deepseek-v4-pro"
    assert config.get_deepseek_chat_thinking_mode() == "enabled"
    assert config.get_deepseek_analysis_thinking_mode() == "enabled"
    assert config.get_deepseek_rag_thinking_mode() == "enabled"


def test_invalid_thinking_mode_falls_back_to_disabled(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_CHAT_THINKING", "maybe")

    assert config.get_deepseek_chat_thinking_mode() == "disabled"
    assert config.build_deepseek_thinking_payload("maybe") == {"thinking": {"type": "disabled"}}


def test_production_secret_key_must_be_explicit(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    try:
        config.build_secret_key("production")
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("production without SECRET_KEY must fail")


def test_development_secret_key_uses_process_local_random_value(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    secret_key = config.build_secret_key("development")

    assert secret_key.startswith("dev-only-")
