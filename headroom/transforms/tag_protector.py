"""Protect custom workflow tags from compression, with an optional Rust fast path."""

from __future__ import annotations

import logging
import re
from typing import cast

logger = logging.getLogger(__name__)

try:
    from headroom._core import (
        is_html_tag as _rust_is_html_tag,
    )
    from headroom._core import (
        known_html_tag_names as _rust_known_html_tag_names,
    )
    from headroom._core import (
        protect_tags as _rust_protect_tags,
    )
    from headroom._core import (
        restore_tags as _rust_restore_tags,
    )
except ImportError:
    _rust_is_html_tag = None
    _rust_known_html_tag_names = None
    _rust_protect_tags = None
    _rust_restore_tags = None

_PYTHON_HTML_TAGS = frozenset(
    """
    html base head link meta style title body address article aside footer h1 h2 h3 h4 h5 h6
    header hgroup main nav section search blockquote dd div dl dt figcaption figure hr li menu
    ol p pre ul a abbr b bdi bdo br cite code data dfn em i kbd mark q rp rt ruby s samp small
    span strong sub sup time u var wbr area audio img map track video embed iframe object param
    picture portal source svg math canvas noscript script del ins caption col colgroup table tbody
    td tfoot th thead tr button datalist fieldset form input label legend meter optgroup option
    output progress select textarea details dialog summary slot template
    """.split()
)

KNOWN_HTML_TAGS = (
    frozenset(_rust_known_html_tag_names())
    if _rust_known_html_tag_names is not None
    else _PYTHON_HTML_TAGS
)

_TAG_RE = re.compile(
    r"<(?P<close>/)?(?P<name>[A-Za-z_][\w.:-]*)(?P<attrs>(?:\s+[^>]*?)?)(?P<self>/)?>"
)
_DEFAULT_PREFIX = "{{HEADROOM_TAG_"
_PLACEHOLDER_SUFFIX = "}}"


def _is_html_tag(tag_name: str) -> bool:
    """Return whether a tag name is a standard HTML element."""
    if _rust_is_html_tag is not None:
        return bool(_rust_is_html_tag(tag_name))
    return tag_name.lower() in KNOWN_HTML_TAGS


def _placeholder_prefix(text: str) -> str:
    prefix = _DEFAULT_PREFIX
    salt = 0
    while prefix in text:
        salt += 1
        prefix = f"{{{{HEADROOM_LOCAL_{salt}_TAG_"
    return prefix


def _replace_spans(
    text: str,
    spans: list[tuple[int, int]],
) -> tuple[str, list[tuple[str, str]]]:
    prefix = _placeholder_prefix(text)
    output: list[str] = []
    protected: list[tuple[str, str]] = []
    cursor = 0
    for index, (start, end) in enumerate(sorted(spans)):
        if start < cursor:
            continue
        placeholder = f"{prefix}{index}{_PLACEHOLDER_SUFFIX}"
        original = text[start:end]
        output.extend((text[cursor:start], placeholder))
        protected.append((placeholder, original))
        cursor = end
    output.append(text[cursor:])
    return "".join(output), protected


def _python_protect_tags(
    text: str,
    compress_tagged_content: bool,
) -> tuple[str, list[tuple[str, str]]]:
    if not text or "<" not in text:
        return text, []

    matches = list(_TAG_RE.finditer(text))
    if compress_tagged_content:
        spans = [match.span() for match in matches if not _is_html_tag(match.group("name"))]
        return _replace_spans(text, spans)

    spans: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for match in matches:
        name = match.group("name").lower()
        if _is_html_tag(name):
            continue
        if match.group("self"):
            if not stack:
                spans.append(match.span())
            continue
        if match.group("close"):
            if stack and stack[-1][0] == name:
                _, start = stack.pop()
                if not stack:
                    spans.append((start, match.end()))
            continue
        stack.append((name, match.start()))
    return _replace_spans(text, spans)


def protect_tags(
    text: str,
    compress_tagged_content: bool = False,
) -> tuple[str, list[tuple[str, str]]]:
    """Replace custom tags or blocks with compression-safe placeholders."""
    if _rust_protect_tags is not None:
        cleaned, blocks = _rust_protect_tags(text, compress_tagged_content)
        return cast("str", cleaned), cast("list[tuple[str, str]]", blocks)
    return _python_protect_tags(text, compress_tagged_content)


def restore_tags(
    text: str,
    protected_blocks: list[tuple[str, str]],
) -> str:
    """Restore placeholders; never append an orphaned block if compression lost it."""
    if _rust_restore_tags is not None:
        return cast("str", _rust_restore_tags(text, protected_blocks))
    result = text
    for placeholder, original in protected_blocks:
        if placeholder in result:
            result = result.replace(placeholder, original)
        else:
            logger.error(
                "event=tag_protector_placeholder_lost placeholder=%r",
                placeholder,
            )
    return result


__all__ = [
    "KNOWN_HTML_TAGS",
    "_is_html_tag",
    "protect_tags",
    "restore_tags",
]
