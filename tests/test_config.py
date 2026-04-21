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
    assert config.daily_slot_hour == 18
    assert config.daily_slot_minute == 0
    assert config.draft_generation_hour == 17
    assert config.draft_generation_minute == 30


def test_load_config_uses_project_root_state_dir_by_default(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.delenv("STATE_DIR", raising=False)
    monkeypatch.delenv("SOURCES_PATH", raising=False)

    config = load_config()

    assert config.state_dir == Path(__file__).resolve().parents[1] / "state"
    assert config.sources_path == Path(__file__).resolve().parents[1] / "sources.yaml"
