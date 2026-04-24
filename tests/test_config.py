from pathlib import Path

from ai_news_bot.config import load_config


def test_load_config_reads_env_state_dir_and_uses_defaults(monkeypatch, tmp_path: Path):
    sources_path = tmp_path / "sources.yaml"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    monkeypatch.setenv("SOURCES_PATH", str(sources_path))

    config = load_config()

    assert config.telegram_bot_token == "token"
    assert config.telegram_owner_chat_id == "123"
    assert config.telegram_channel_id == "@channel"
    assert config.state_dir == tmp_path
    assert config.sources_path == sources_path
    assert config.daily_slot_hour == 6
    assert config.daily_slot_minute == 0
    assert config.draft_generation_hour == 17
    assert config.draft_generation_minute == 30
    assert config.telegram_poll_interval_seconds == 30
    assert config.daily_slot_preview_limit == 10


def test_load_config_uses_project_root_state_dir_by_default(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.delenv("STATE_DIR", raising=False)
    monkeypatch.delenv("SOURCES_PATH", raising=False)

    config = load_config()

    assert config.state_dir == Path(__file__).resolve().parents[1] / "state"
    assert config.sources_path == Path(__file__).resolve().parents[1] / "sources.yaml"


def test_load_config_prefers_current_working_directory_for_project_root(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.delenv("STATE_DIR", raising=False)
    monkeypatch.delenv("SOURCES_PATH", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\nversion='0.0.0'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.state_dir == tmp_path / "state"
    assert config.sources_path == tmp_path / "sources.yaml"


def test_load_config_reads_poll_interval_override(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.setenv("TELEGRAM_POLL_INTERVAL_SECONDS", "45")
    monkeypatch.delenv("STATE_DIR", raising=False)
    monkeypatch.delenv("SOURCES_PATH", raising=False)

    config = load_config()

    assert config.telegram_poll_interval_seconds == 45


def test_load_config_reads_daily_preview_limit_override(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.setenv("DAILY_SLOT_PREVIEW_LIMIT", "7")
    monkeypatch.delenv("STATE_DIR", raising=False)
    monkeypatch.delenv("SOURCES_PATH", raising=False)

    config = load_config()

    assert config.daily_slot_preview_limit == 7


def test_load_config_rejects_non_positive_poll_interval(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.setenv("TELEGRAM_POLL_INTERVAL_SECONDS", "0")

    try:
        load_config()
    except ValueError as exc:
        assert "TELEGRAM_POLL_INTERVAL_SECONDS must be a positive integer" in str(exc)
    else:
        raise AssertionError("Expected non-positive poll interval to fail")


def test_load_config_rejects_non_positive_daily_preview_limit(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.setenv("DAILY_SLOT_PREVIEW_LIMIT", "0")

    try:
        load_config()
    except ValueError as exc:
        assert "DAILY_SLOT_PREVIEW_LIMIT must be a positive integer" in str(exc)
    else:
        raise AssertionError("Expected non-positive daily preview limit to fail")
