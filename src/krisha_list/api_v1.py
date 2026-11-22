"""Validation for the versioned, server-to-server JSON API."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs

from .area import parse_bounds


def _single(values: dict[str, list[str]], name: str) -> str | None:
    found = values.get(name)
    if found is None:
        return None
    if len(found) != 1:
        raise ValueError(f"Параметр {name} должен быть указан один раз")
    return found[0]


def _integer(value: str | None, name: str, default: int, maximum: int) -> int:
    if value is None:
        return default
    if not value.isdecimal() or int(value) > maximum:
        raise ValueError(f"Параметр {name} должен быть числом от 0 до {maximum}")
    return int(value)


def parse_listings_query(query: str) -> dict:
    values = parse_qs(query, keep_blank_values=True)
    allowed = {"category", "city", "district", "bounds", "updated_after", "limit", "offset"}
    if unknown := values.keys() - allowed:
        raise ValueError(f"Неизвестный параметр: {sorted(unknown)[0]}")
    category = _single(values, "category")
    if category is not None and category not in {"house", "apartment"}:
        raise ValueError("category: house или apartment")
    city = _single(values, "city")
    district = _single(values, "district")
    for name, value in (("city", city), ("district", district)):
        if value is not None and (not value.strip() or len(value) > 120):
            raise ValueError(f"Параметр {name} должен содержать от 1 до 120 символов")
    bounds_text = _single(values, "bounds")
    bounds = parse_bounds(bounds_text) if bounds_text is not None else None
    updated_after = _single(values, "updated_after")
    if updated_after is not None:
        try:
            instant = datetime.fromisoformat(updated_after.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("updated_after должен быть датой ISO 8601 с часовым поясом") from error
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("updated_after должен содержать часовой пояс")
        updated_after = instant.astimezone(timezone.utc).isoformat()
    limit = _integer(_single(values, "limit"), "limit", 50, 100)
    if limit == 0:
        raise ValueError("Параметр limit должен быть от 1 до 100")
    return {"category": category, "city": city.strip() if city else None,
            "district": district.strip() if district else None, "bounds": bounds,
            "updated_after": updated_after, "limit": limit,
            "offset": _integer(_single(values, "offset"), "offset", 0, 100000)}


def parse_runs_query(query: str) -> int:
    values = parse_qs(query, keep_blank_values=True)
    if values.keys() - {"limit"}:
        raise ValueError("Для журнала доступен только параметр limit")
    limit = _integer(_single(values, "limit"), "limit", 20, 100)
    if limit == 0:
        raise ValueError("Параметр limit должен быть от 1 до 100")
    return limit
