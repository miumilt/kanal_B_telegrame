from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


class _ImageUrlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.og_image: str | None = None
        self.first_img: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {name.lower(): value for name, value in attrs if value is not None}
        if tag.lower() == "meta":
            if attributes.get("property", "").lower() == "og:image":
                content = attributes.get("content", "").strip()
                if content and self.og_image is None:
                    self.og_image = content
        elif tag.lower() == "img" and self.first_img is None:
            src = attributes.get("src", "").strip()
            if src:
                self.first_img = src


def extract_image_url(html: str, page_url: str) -> str | None:
    parser = _ImageUrlParser()
    parser.feed(html)
    candidate = parser.og_image or parser.first_img
    if not candidate:
        return None
    return urljoin(page_url, candidate)
