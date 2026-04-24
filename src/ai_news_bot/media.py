from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


class _ImageUrlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.og_image: str | None = None
        self.og_video: str | None = None
        self.first_img: str | None = None
        self.first_video: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {name.lower(): value for name, value in attrs if value is not None}
        if tag.lower() == "meta":
            property_name = attributes.get("property", "").lower()
            name = attributes.get("name", "").lower()
            content = attributes.get("content", "").strip()
            if property_name == "og:image" and content and self.og_image is None:
                self.og_image = content
            if property_name == "og:video" and content and self.og_video is None:
                self.og_video = content
            if name == "twitter:player:stream" and content and self.og_video is None:
                self.og_video = content
        elif tag.lower() == "img" and self.first_img is None:
            src = attributes.get("src", "").strip()
            if src:
                self.first_img = src
        elif tag.lower() == "video":
            src = attributes.get("src", "").strip()
            if src and self.first_video is None:
                self.first_video = src
        elif tag.lower() == "source":
            src = attributes.get("src", "").strip()
            source_type = attributes.get("type", "").lower()
            if src and self.first_video is None and source_type.startswith("video/"):
                self.first_video = src


def extract_media_urls(html: str, page_url: str) -> tuple[str | None, str | None]:
    parser = _ImageUrlParser()
    parser.feed(html)
    image_candidate = parser.og_image or parser.first_img
    video_candidate = parser.og_video or parser.first_video
    image_url = urljoin(page_url, image_candidate) if image_candidate else None
    video_url = urljoin(page_url, video_candidate) if video_candidate else None
    return image_url, video_url


def extract_image_url(html: str, page_url: str) -> str | None:
    image_url, _ = extract_media_urls(html, page_url)
    return image_url


def extract_video_url(html: str, page_url: str) -> str | None:
    _, video_url = extract_media_urls(html, page_url)
    return video_url
