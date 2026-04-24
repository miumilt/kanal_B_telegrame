from ai_news_bot.media import extract_image_url, extract_media_urls


def test_extract_image_url_prefers_og_image_over_img_fallback():
    html = """
    <html>
      <head>
        <meta property="og:image" content="https://example.com/hero.png">
      </head>
      <body>
        <img src="https://example.com/fallback.png">
      </body>
    </html>
    """

    assert extract_image_url(html, "https://example.com/article") == "https://example.com/hero.png"


def test_extract_image_url_resolves_relative_urls():
    html = """
    <html>
      <head>
        <meta property="og:image" content="/images/hero.png">
      </head>
    </html>
    """

    assert extract_image_url(html, "https://example.com/article") == "https://example.com/images/hero.png"


def test_extract_image_url_falls_back_to_first_image():
    html = """
    <html>
      <body>
        <img src="/images/first.png">
        <img src="/images/second.png">
      </body>
    </html>
    """

    assert extract_image_url(html, "https://example.com/article") == "https://example.com/images/first.png"


def test_extract_media_urls_reads_og_video_and_og_image():
    html = """
    <html>
      <head>
        <meta property="og:image" content="https://example.com/hero.png">
        <meta property="og:video" content="https://example.com/clip.mp4">
      </head>
    </html>
    """

    assert extract_media_urls(html, "https://example.com/article") == (
        "https://example.com/hero.png",
        "https://example.com/clip.mp4",
    )
