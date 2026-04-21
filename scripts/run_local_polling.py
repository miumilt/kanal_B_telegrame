from __future__ import annotations

import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for candidate in (str(SRC_DIR), str(SCRIPT_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from ai_news_bot.config import load_config
from ai_news_bot.storage import JsonStateStore
from ai_news_bot.telegram_api import TelegramApi

from poll_telegram_updates import process_updates


def run_local_polling(store: JsonStateStore, telegram_api: TelegramApi, config, *, sleeper=time.sleep) -> None:
    try:
        while True:
            process_updates(store, telegram_api, config)
            sleeper(config.telegram_poll_interval_seconds)
    except KeyboardInterrupt:
        return


def main() -> None:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    run_local_polling(store, telegram_api, config)


if __name__ == "__main__":
    main()
