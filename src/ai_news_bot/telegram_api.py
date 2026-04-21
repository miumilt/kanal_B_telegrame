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

    def _post(self, method: str, payload: dict[str, object]) -> dict:
        response = requests.post(
            f"{self.base_url}/{method}",
            json=payload,
            timeout=30,
        )
        return self._parse_response(response)["result"]

    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        payload: dict[str, object] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._post("sendMessage", payload)

    def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        payload: dict[str, object] = {"chat_id": chat_id, "photo": photo_url}
        if caption is not None:
            payload["caption"] = caption
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._post("sendPhoto", payload)

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
        try:
            self._parse_response(response)
        except requests.HTTPError as exc:
            if not self._is_expired_callback_query(response):
                raise

    def _is_expired_callback_query(self, response: requests.Response) -> bool:
        if response.status_code != 400:
            return False

        try:
            payload = response.json()
        except ValueError:
            return False

        description = str(payload.get("description", "")).lower()
        return "query is too old" in description or "query id is invalid" in description
