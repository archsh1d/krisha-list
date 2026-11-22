from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from .model import Listing, PageFormatError, ParsedPage
from .categories import category_from_url

_SPACE = re.compile(r"\s+")
_ROOMS = re.compile(r"\b(\d+)\s+комнат(?:а|ы)?\b|\b(\d+)[-\s]комнатн\w*", re.I)
_HOUSE_AREA = re.compile(r"([\d.,]+)\s*м(?:²|2|\u00b2)\b", re.I)
_PLOT_AREA = re.compile(r"([\d.,]+)\s*сот(?:ок|ки|ка|\.)?\b", re.I)
_FLOORS = re.compile(r"\b(\d+)\s*этаж(?:а|ей)?\b", re.I)
_YEAR = re.compile(r"\b((?:18|19|20)\d{2})\s*г\.?\s*п\.?\b", re.I)
_APARTMENT_FLOOR = re.compile(r"\b(\d+)\s*/\s*(\d+)\s*этаж", re.I)
_COMPLEX = re.compile(r"\bжил\.\s*комплекс\s+([^,]+)", re.I)
_COUNT = re.compile(r"Найдено\s+([\d\s\u00a0]+)\s+объявлен", re.I)
_DETAIL_ID = re.compile(r"/a/show/(\d+)(?:[/?#]|$)")


def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    value = _SPACE.sub(" ", node.get_text(" ", strip=True)).strip()
    return value or None


def _number(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _decimal(match: re.Match[str] | None) -> float | None:
    return float(match.group(1).replace(",", ".")) if match else None


def _title_fields(title: str) -> tuple[str | None, int | None, float | None, float | None]:
    parts = [part.strip() for part in title.split("·")]
    object_type = parts[0] or None
    room_match = _ROOMS.search(title)
    rooms = int(next(group for group in room_match.groups() if group)) if room_match else None
    return (
        object_type,
        rooms,
        _decimal(_HOUSE_AREA.search(title)),
        _decimal(_PLOT_AREA.search(title)),
    )


def _parse_card(card: Tag, page_url: str, page_number: int, category: str) -> Listing:
    raw_id = card.get("data-id")
    if not isinstance(raw_id, str) or not raw_id.isdecimal():
        raise PageFormatError("Карточка без числового data-id")
    listing_id = int(raw_id)
    title_node = card.select_one("a.a-card__title[href]")
    title = _text(title_node)
    if not title:
        raise PageFormatError(f"Карточка {listing_id}: нет заголовка")
    href = title_node.get("href") if title_node else None
    detail_match = _DETAIL_ID.search(urljoin(page_url, href)) if isinstance(href, str) else None
    if detail_match is None or int(detail_match.group(1)) != listing_id:
        raise PageFormatError(f"Карточка {listing_id}: нет ссылки объявления")
    detail_url = f"https://krisha.kz/a/show/{listing_id}"

    object_type, rooms, house_area, plot_area = _title_fields(title)
    subtitle = _text(card.select_one(".a-card__subtitle"))
    district = address = None
    if subtitle:
        if "," in subtitle:
            district, address = (part.strip() or None for part in subtitle.split(",", 1))
        else:
            address = subtitle

    preview = _text(card.select_one(".a-card__text-preview"))
    stats = card.select(".a-card__stats-item")
    floor_match = _FLOORS.search(preview or "")
    year_match = _YEAR.search(preview or "")
    apartment_floor = _APARTMENT_FLOOR.search(title) if category == "apartment" else None
    complex_match = _COMPLEX.search(preview or "") if category == "apartment" else None
    return Listing(
        id=listing_id,
        url=detail_url,
        title=title,
        object_type=object_type,
        rooms=rooms,
        house_area_m2=house_area if category == "house" else None,
        plot_area_sot=plot_area if category == "house" else None,
        price_kzt=_number(_text(card.select_one(".a-card__price"))),
        district=district,
        address=address,
        description_preview=preview,
        seller_type=_text(card.select_one(".a-card__owner-label")) or _text(card.select_one(".a-card__owner")),
        city=_text(stats[0]) if len(stats) > 0 else None,
        posted_label=_text(stats[1]) if len(stats) > 1 else None,
        floors=int(floor_match.group(1)) if floor_match and category == "house" else None,
        year_built=int(year_match.group(1)) if year_match else None,
        page_number=page_number,
        category=category,
        apartment_area_m2=house_area if category == "apartment" else None,
        floor=int(apartment_floor.group(1)) if apartment_floor else None,
        building_floors=int(apartment_floor.group(2)) if apartment_floor else None,
        residential_complex=complex_match.group(1).strip() if complex_match else None,
    )


def parse_listing_page(html: str, page_url: str) -> ParsedPage:
    """Parse the main results only; sidebar promotions are excluded."""
    category = category_from_url(page_url)
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("section.a-search-list")
    subtitle = _text(soup.select_one(".a-search-subtitle"))
    count_match = _COUNT.search(subtitle or "")
    total_found = _number(count_match.group(1)) if count_match else None
    if section is None:
        if soup.select_one(".a-search-empty") or total_found == 0:
            return ParsedPage(page_url, (), total_found or 0, None)
        raise PageFormatError("Не найден основной список объявлений; возможно, сайт вернул страницу защиты")

    query = parse_qs(urlsplit(page_url).query)
    try:
        page_number = max(1, int(query.get("page", ["1"])[0]))
    except ValueError as error:
        raise PageFormatError("Некорректный номер страницы в URL") from error

    cards = section.select(".a-card[data-id]")
    if not cards and total_found != 0 and not soup.select_one(".a-search-empty"):
        raise PageFormatError("Основной список есть, но карточки не найдены")
    listings = tuple(_parse_card(card, page_url, page_number, category) for card in cards)
    if len({item.id for item in listings}) != len(listings):
        raise PageFormatError("На странице повторяются ID объявлений")

    next_link = soup.select_one("a.paginator__btn--next[href]")
    next_href = next_link.get("href") if next_link else None
    next_url = urljoin(page_url, next_href) if isinstance(next_href, str) else None
    return ParsedPage(page_url, listings, total_found, next_url)
