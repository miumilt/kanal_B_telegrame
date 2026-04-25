from __future__ import annotations

import requests

from ai_news_bot.models import BacklogItem


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


SYSTEM_PROMPT = (
    "Ты редактор Telegram-канала про AI. Пиши по-русски, просто и живо, без канцелярита. "
    "Не добавляй факты, которых нет во входных данных. Формат: короткий лид, блок 'Главное:' "
    "с 2-4 пунктами, затем строка где посмотреть или протестить и строка с источником."
)


def _build_user_prompt(item: BacklogItem, fallback_text: str) -> str:
    return "\n".join(
        [
            "Сделай аккуратный короткий пост для Telegram.",
            f"Заголовок: {item.source_title}",
            f"Краткое описание: {item.summary_candidate}",
            f"Категория: {item.category}",
            f"Ссылка: {item.source_url}",
            f"Источник: {item.source_name}",
            "",
            "Текущий черновик:",
            fallback_text,
            "",
            "Требования:",
            "- 500-900 знаков максимум.",
            "- Без сложных терминов без необходимости.",
            "- Если это инструмент или бесплатный доступ, используй 'Тестим здесь: <ссылка>'.",
            "- Иначе используй 'Где посмотреть: <ссылка>'.",
            "- Последняя строка: 'Источник: <название источника>'.",
        ]
    )


def rewrite_with_openrouter(
    item: BacklogItem,
    fallback_text: str,
    *,
    api_key: str,
    model: str | None = None,
    timeout_seconds: int = 45,
) -> str:
    payload: dict[str, object] = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(item, fallback_text)},
        ],
        "temperature": 0.35,
        "max_tokens": 450,
    }
    if model:
        payload["model"] = model

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "AI News Telegram Bot",
        },
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if not content or item.source_url not in content:
        raise ValueError("OpenRouter response did not include the source URL")
    return content


def maybe_rewrite_post(
    item: BacklogItem,
    fallback_text: str,
    *,
    api_key: str | None,
    model: str | None = None,
) -> str:
    if not api_key:
        return fallback_text
    try:
        return rewrite_with_openrouter(item, fallback_text, api_key=api_key, model=model)
    except Exception:
        return fallback_text
