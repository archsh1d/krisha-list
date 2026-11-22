"""Supported Krisha sale searches."""

from __future__ import annotations

from urllib.parse import urlsplit


DEFAULT_URLS = {
    "house": "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/",
    "apartment": "https://krisha.kz/prodazha/kvartiry/almaty-almalinskij/",
}

AREA_URLS = {
    "house": "https://krisha.kz/prodazha/doma-dachi/almaty/",
    "apartment": "https://krisha.kz/prodazha/kvartiry/almaty/",
}

SLUG_TO_CATEGORY = {"doma-dachi": "house", "kvartiry": "apartment"}


def category_from_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"krisha.kz", "www.krisha.kz"}:
        raise ValueError("Ожидается HTTPS-ссылка на krisha.kz")
    segments = parts.path.strip("/").split("/")
    if len(segments) < 2 or segments[0] != "prodazha" or segments[1] not in SLUG_TO_CATEGORY:
        raise ValueError("Поддерживается продажа домов, дач и квартир")
    return SLUG_TO_CATEGORY[segments[1]]
