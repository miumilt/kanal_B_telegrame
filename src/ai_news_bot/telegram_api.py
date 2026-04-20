from __future__ import annotations

import requests


class TelegramApi:
    def __init__(self, bot_token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def _parse_response(self, response: requests.Response) -> dict:
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") is not True:
            description = payload.get("description", "unknown Telegram API error")
            raise RuntimeError(f"Telegram API request failed: {description}")
        return payload

    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        payload: dict[str, object] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        response = requests.post(
            f"{self.base_url}/sendMessage",
            json=payload,
            timeout=30,
        )
        return self._parse_response(response)["result"]

    def get_updates(self, offset: int) -> list[dict]:
        response = requests.get(
            f"{self.base_url}/getUpdates",
            params={"offset": offset, "timeout": 0},
            timeout=30,
        )
        return self._parse_response(response)["result"]

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        response = requests.post(
            f"{self.base_url}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=30,
        )
        self._parse_response(response)
