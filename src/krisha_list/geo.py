"""Coordinates published in the map sidebar for the same search page."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from .model import ParsedPage
from .categories import category_from_url
from .client import SourceHTTPError


class GeoFetchError(RuntimeError):
    """The map sidebar did not return usable listing coordinates."""


@dataclass(frozen=True, slots=True)
class GeoPoint:
    latitude: float
    longitude: float
    zoom: int | None
    map_type: str | None
    source: str = "krisha_map_list"


def snapshot_geo_points(records: list[dict]) -> dict[int, GeoPoint]:
    """Reuse validated map positions from a recent matching collection."""
    points: dict[int, GeoPoint] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        listing_id = record.get("id")
        lat, lon = record.get("latitude"), record.get("longitude")
        if type(listing_id) is not int or listing_id <= 0 or type(lat) not in (int, float) or type(lon) not in (int, float):
            continue
        if not str(record.get("geo_source") or "").startswith("krisha_map_list"):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if lat == 0 and lon == 0:
            continue
        zoom = record.get("geo_zoom")
        map_type = record.get("geo_type")
        points[listing_id] = GeoPoint(
            float(lat), float(lon), zoom if type(zoom) is int else None,
            map_type if isinstance(map_type, str) else None, "krisha_map_list_cached",
        )
    return points


def map_list_url(search_url: str) -> str:
    category_from_url(search_url)
    parts = urlsplit(search_url)
    params = parse_qsl(parts.query, keep_blank_values=True)
    if not any(key == "page" for key, _ in params):
        params.append(("page", "1"))
    return urlunsplit(("https", parts.hostname, "/a/ajax-map-list/map" + parts.path, urlencode(params), ""))


def parse_map_list(payload: dict) -> dict[int, GeoPoint]:
    adverts = payload.get("adverts")
    if not isinstance(adverts, dict):
        raise GeoFetchError("Ответ карты не содержит словарь объявлений")
    points: dict[int, GeoPoint] = {}
    for raw_id, advert in adverts.items():
        if not isinstance(raw_id, str) or not raw_id.isdecimal() or not isinstance(advert, dict):
            continue
        position = advert.get("map")
        if not isinstance(position, dict):
            continue
        lat, lon = position.get("lat"), position.get("lon")
        if not isinstance(lat, (float, int)) or isinstance(lat, bool):
            continue
        if not isinstance(lon, (float, int)) or isinstance(lon, bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if lat == 0 and lon == 0:
            continue
        zoom = position.get("zoom")
        map_type = position.get("type")
        points[int(raw_id)] = GeoPoint(
            latitude=float(lat), longitude=float(lon),
            zoom=zoom if type(zoom) is int else None,
            map_type=map_type if isinstance(map_type, str) else None,
        )
    return points


def fetch_page_geo(
    search_url: str,
    *,
    session: requests.Session,
    timeout: float = 20.0,
    on_json: Callable[[str], None] | None = None,
) -> dict[int, GeoPoint]:
    url = map_list_url(search_url)
    try:
        response = session.get(
            url, timeout=timeout, allow_redirects=False,
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
    except requests.RequestException as error:
        raise GeoFetchError(f"Не удалось получить координаты: {error}") from error
    if 300 <= response.status_code < 400:
        raise GeoFetchError("Карта перенаправила запрос; переход не выполнен")
    target = urlsplit(response.url)
    if target.scheme != "https" or target.hostname not in {"krisha.kz", "www.krisha.kz"}:
        raise GeoFetchError("Ответ карты перенаправлен на другой сайт")
    if response.status_code != 200:
        if response.status_code in (403, 429, 468):
            raise SourceHTTPError(response.status_code, url, response)
        raise GeoFetchError(f"Карта вернула HTTP {response.status_code}")
    if "json" not in response.headers.get("Content-Type", "").lower():
        challenge = SourceHTTPError(response.status_code, url, response)
        if challenge.is_challenge:
            raise challenge
        raise GeoFetchError("Карта вернула не JSON")
    try:
        payload = response.json()
    except (json.JSONDecodeError, requests.exceptions.JSONDecodeError) as error:
        raise GeoFetchError("Не удалось разобрать ответ карты") from error
    if not isinstance(payload, dict):
        raise GeoFetchError("Некорректный формат ответа карты")
    points = parse_map_list(payload)
    if on_json:
        on_json(response.text)
    return points


def attach_geo(page: ParsedPage, points: dict[int, GeoPoint]) -> ParsedPage:
    return replace(page, listings=tuple(
        replace(item, latitude=point.latitude, longitude=point.longitude,
                geo_source=point.source, geo_zoom=point.zoom, geo_type=point.map_type)
        if (point := points.get(item.id)) else item
        for item in page.listings
    ))


def page_number_from_url(url: str) -> int:
    value = parse_qs(urlsplit(url).query).get("page", ["1"])[0]
    return int(value) if value.isdecimal() else 1


class GeoEnricher:
    """Match map coordinates by ID, checking the next map page when ranks shift."""

    def __init__(
        self, session: requests.Session, *, timeout: float = 20.0,
        on_json: Callable[[str, str], None] | None = None,
        known_points: dict[int, GeoPoint] | None = None,
    ) -> None:
        self.session = session
        self.timeout = timeout
        self.on_json = on_json
        self.cache: dict[str, dict[int, GeoPoint]] = {}
        self.known_points = known_points or {}
        self.reused_ids: set[int] = set()

    @property
    def reused_count(self) -> int:
        return len(self.reused_ids)

    def _load(self, search_url: str) -> dict[int, GeoPoint]:
        key = map_list_url(search_url)
        if key not in self.cache:
            callback = (lambda raw: self.on_json(search_url, raw)) if self.on_json else None
            self.cache[key] = fetch_page_geo(
                search_url, session=self.session, timeout=self.timeout, on_json=callback,
            )
        return self.cache[key]

    def enrich(self, page: ParsedPage) -> tuple[ParsedPage, list[str]]:
        wanted = {item.id for item in page.listings}
        if wanted <= self.known_points.keys():
            self.reused_ids.update(wanted)
            return attach_geo(page, self.known_points), []
        try:
            points = dict(self._load(page.url))
        except GeoFetchError as error:
            available = {listing_id: self.known_points[listing_id]
                         for listing_id in wanted if listing_id in self.known_points}
            self.reused_ids.update(available)
            return attach_geo(page, available), [str(error)]
        for listing_id in wanted - points.keys():
            if listing_id in self.known_points:
                points[listing_id] = self.known_points[listing_id]
        missing = wanted - points.keys()
        errors: list[str] = []
        if missing and page.next_url and urlsplit(page.next_url).path == urlsplit(page.url).path:
            try:
                points.update(self._load(page.next_url))
            except GeoFetchError as error:
                errors.append(f"следующая страница карты: {error}")
        self.reused_ids.update(
            listing_id for listing_id in wanted
            if listing_id in points and points[listing_id].source == "krisha_map_list_cached"
        )
        return attach_geo(page, points), errors
