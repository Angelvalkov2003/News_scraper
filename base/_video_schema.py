"""
Shared video component helpers per scraped_article_json_schema.
Video properties: url (required), name, caption, description, thumbnail_image_url (all optional).
"""

import re
from urllib.parse import urljoin


def make_video_component(
    url: str,
    *,
    name: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    thumbnail_image_url: str | None = None,
) -> dict:
    """Build video component dict. url required; other fields optional."""
    props = {"url": url}
    if name:
        props["name"] = name
    if caption:
        props["caption"] = caption
    if description:
        props["description"] = description
    if thumbnail_image_url:
        props["thumbnail_image_url"] = thumbnail_image_url
    return {"type": "video", "properties": props}


def extract_video_from_iframe(iframe_tag, base_url: str) -> tuple[str | None, str | None]:
    """
    Extract (url, thumbnail_url) from an iframe. thumbnail_url is None for non-YouTube.
    Returns (None, None) if src is not a known video embed.
    """
    src = (iframe_tag.get("src") or "").strip()
    if not src:
        return None, None
    if src.startswith("//"):
        src = "https:" + src
    elif src.startswith("/"):
        src = urljoin(base_url, src)
    thumb = None
    if "youtube.com/embed/" in src or "youtu.be/embed/" in src:
        m = re.search(r"(?:embed/|/)([a-zA-Z0-9_-]{11})(?:[?&]|$)", src)
        if m:
            thumb = f"https://i.ytimg.com/vi_webp/{m.group(1)}/maxresdefault.webp"
    if "yukle.donanimhaber.com/Embed" in src or "youtube.com/embed" in src or "youtu.be/" in src or "vimeo.com" in src or "player." in src or "embed" in src.lower():
        return src, thumb
    return None, None
