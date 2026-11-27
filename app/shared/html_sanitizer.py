"""HTML sanitization for bio templates.

The exact allowlist depends on each platform (Chaturbate / Stripchat publish
their own list). This default is a conservative superset drawn from the most
commonly permitted tags. Update via `CHATURBATE_ALLOWLIST` / `STRIPCHAT_ALLOWLIST`
once the official docs are confirmed by the team.
"""

from bleach.css_sanitizer import CSSSanitizer
from bleach.sanitizer import Cleaner

_BASE_TAGS = {
    "a",
    "b",
    "br",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "span",
    "strong",
    "u",
    "ul",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "div",
    "center",
    "font",
}

_BASE_ATTRS = {
    "*": ["class", "style"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "font": ["color", "size", "face"],
    "td": ["colspan", "rowspan", "align", "valign"],
    "th": ["colspan", "rowspan", "align", "valign"],
}

_BASE_CSS = [
    "color",
    "background-color",
    "font-size",
    "font-weight",
    "font-style",
    "text-align",
    "text-decoration",
    "margin",
    "margin-top",
    "margin-bottom",
    "padding",
    "border",
    "width",
    "height",
]

_BASE_PROTOCOLS = ["http", "https", "mailto"]


def _make_cleaner() -> Cleaner:
    return Cleaner(
        tags=_BASE_TAGS,
        attributes=_BASE_ATTRS,
        protocols=_BASE_PROTOCOLS,
        css_sanitizer=CSSSanitizer(allowed_css_properties=_BASE_CSS),
        strip=True,
        strip_comments=True,
    )


_cleaner = _make_cleaner()


def sanitize_bio_html(raw: str) -> str:
    """Remove any disallowed tag/attribute/CSS. Returns a safe HTML string."""
    return _cleaner.clean(raw)
