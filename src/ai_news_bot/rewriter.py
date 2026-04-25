from __future__ import annotations

import requests

from ai_news_bot.models import BacklogItem


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


SYSTEM_PROMPT = (
    "Ты редактор Telegram-канала про AI. Пиши живой короткий Telegram-пост по-русски: "
    "просто, конкретно и без канцелярита. Не добавляй факты, которых нет во входных данных. "
    "не делай обязательный блок 'Главное:' и не превращай каждую новость в пресс-релиз. "
    "Формат выбирай по смыслу новости: 1-2 коротких абзаца, если этого достаточно; "
    "короткий список только если без него новость сложнее понять. В конце всегда оставляй "
    "строку с ссылкой и строку с источником."
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
            "- 300-750 знаков, если новость простая; длиннее только если иначе потеряется смысл.",
            "- 1-2 коротких абзаца; список используй только для моделей, тарифов, возможностей или бенчмарков.",
            "- Начинай сразу с сути: что появилось и зачем это человеку.",
            "- Не используй обязательный блок 'Главное:'.",
            "- Без сложных терминов без необходимости и без фраз вроде 'компания объявила инновационное решение'.",
            "- Игнорируй технический шум из changelog: issue numbers, commit hashes, fix(...), chore(...), deps, SVG/path d=, stack traces и внутренние пути.",
            "- Если это сервис, демка, бесплатный доступ или инструмент, используй 'Где попробовать: <ссылка>' или 'Тестим здесь: <ссылка>'.",
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
