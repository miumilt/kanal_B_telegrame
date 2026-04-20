from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    telegram_owner_chat_id: str
    telegram_channel_id: str
    state_dir: Path
    timezone_name: str = "Europe/Moscow"
    daily_slot_hour: int = 18
    daily_slot_minute: int = 0
    draft_generation_hour: int = 17
    draft_generation_minute: int = 30


def load_config() -> AppConfig:
    return AppConfig(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_owner_chat_id=os.environ["TELEGRAM_OWNER_CHAT_ID"],
        telegram_channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
        state_dir=Path(os.environ.get("STATE_DIR", PROJECT_ROOT / "state")),
    )
