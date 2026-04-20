from ai_news_bot.discovery import normalize_title


def test_normalize_title_collapses_case_and_spacing():
    assert normalize_title("  New  Gemini CLI  ") == "new gemini cli"
