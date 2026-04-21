from ai_news_bot.media import extract_image_url


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
