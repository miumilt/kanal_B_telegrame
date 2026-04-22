from __future__ import annotations

import subprocess
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


STATE_FILENAMES = (
    "backlog.json",
    "current_draft.json",
    "owner_drafts.json",
    "published.json",
    "telegram_cursor.json",
)


def _state_paths(project_root: Path) -> list[str]:
    state_dir = project_root / "state"
    return [
        str(path.relative_to(project_root))
        for path in (state_dir / name for name in STATE_FILENAMES)
        if path.exists()
    ]


def _run_git(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )


def sync_repo_before_poll(project_root: Path) -> None:
    _run_git(project_root, "pull", "--rebase", "origin", "master")


def sync_repo_after_poll(project_root: Path) -> None:
    state_paths = _state_paths(project_root)
    if not state_paths:
        return

    status = _run_git(project_root, "status", "--porcelain", "--", *state_paths)
    if not status.stdout.strip():
        return

    _run_git(project_root, "add", "--", *state_paths)
    _run_git(project_root, "commit", "-m", "chore: update bot state after local telegram poll")
    _run_git(project_root, "pull", "--rebase", "origin", "master")
    _run_git(project_root, "push", "origin", "master")


def run_local_polling(
    store: JsonStateStore,
    telegram_api: TelegramApi,
    config,
    *,
    sleeper=time.sleep,
    sync_before=None,
    sync_after=None,
) -> None:
    try:
        while True:
            if sync_before is not None:
                sync_before()
            process_updates(store, telegram_api, config)
            if sync_after is not None:
                sync_after()
            sleeper(config.telegram_poll_interval_seconds)
    except KeyboardInterrupt:
        return


def main() -> None:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    run_local_polling(
        store,
        telegram_api,
        config,
        sync_before=lambda: sync_repo_before_poll(PROJECT_ROOT),
        sync_after=lambda: sync_repo_after_poll(PROJECT_ROOT),
    )


if __name__ == "__main__":
    main()
