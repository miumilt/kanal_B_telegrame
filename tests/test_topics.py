from ai_news_bot.topics import build_topic_fingerprint, canonicalize_url


def test_canonicalize_url_removes_tracking_params_and_fragment():
    assert canonicalize_url("https://Example.com/post/?utm_source=x&ref=telegram&id=1#comments") == (
        "https://example.com/post?id=1"
    )


def test_build_topic_fingerprint_groups_same_model_release_with_different_titles():
    first = build_topic_fingerprint("OpenAI releases GPT-5.5", "New model is available today")
    second = build_topic_fingerprint("ChatGPT 5.5 beats competitors", "OpenAI rollout starts")

    assert first == second


def test_build_topic_fingerprint_keeps_different_models_separate():
    assert build_topic_fingerprint("OpenAI releases GPT-5.5", "") != build_topic_fingerprint(
        "OpenAI releases GPT-5.4",
        "",
    )
