"""Filter collected search pages by a place named in listing addresses."""

from __future__ import annotations

import re
import unicodedata

from .model import ParsedPage


_LABEL = re.compile(r"(?<!\w)(?:микрорайон|мкр(?:-н)?\.?|район|р-н)(?!\w)", re.I)
_SEPARATORS = re.compile(r"[^\w]+", re.UNICODE)


def normalize_place(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    text = _LABEL.sub(" ", text)
    return " ".join(_SEPARATORS.sub(" ", text).split())


def filter_page_location(page: ParsedPage, query: str) -> tuple[ParsedPage, int]:
    term = normalize_place(query)
    if not term:
        raise ValueError("Укажите название района или микрорайона.")
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
    listings = tuple(item for item in page.listings if any(
        pattern.search(normalize_place(value))
        for value in (item.district, item.address) if value
    ))
    return ParsedPage(page.url, listings, page.total_found, page.next_url), len(page.listings) - len(listings)
