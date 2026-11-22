"""Read a complete prior collection without making another request to Krisha.kz."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .area import Bounds, Polygon, filter_page
from .geo import GeoFetchError, attach_geo, page_number_from_url, parse_map_list
from .location import filter_page_location
from .model import PageFormatError
from .parser import parse_listing_page


def request_identity(
    search_url: str, max_pages: int, bounds: Bounds | None, polygon: Polygon | None,
    location_query: str | None = None,
) -> dict:
    identity = {
        "search_url": search_url,
        "max_pages": max_pages,
        "bounds": bounds.as_query() if bounds else None,
        "polygon": [list(point) for point in polygon.vertices] if polygon else None,
    }
    if location_query:
        identity["location_query"] = location_query
    return identity


def save_success(directory: Path, identity: dict, result: dict) -> None:
    payload = {
        "request": identity,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result": result,
    }
    (directory / "result.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _snapshot_time(directory: Path) -> str | None:
    try:
        return datetime.strptime(directory.name, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return None


def _map_points(directory: Path, url: str) -> dict | None:
    path = directory / f"map-page-{page_number_from_url(url):03d}.json"
    if not path.is_file():
        return None
    try:
        return parse_map_list(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, GeoFetchError):
        return None


def _replay(directory: Path, identity: dict, bounds: Bounds | None, polygon: Polygon | None) -> dict | None:
    search_url = identity["search_url"]
    max_pages = identity["max_pages"]
    expected_url = search_url
    records: dict[int, dict] = {}
    without_coordinates = outside_bounds = outside_location = 0
    site_count = None
    geo_errors: list[str] = []
    for page_number in range(1, 1001):
        html_path = directory / f"page-{page_number:03d}.html"
        url_path = directory / f"page-{page_number:03d}.url.txt"
        if not html_path.is_file() or not url_path.is_file():
            return None
        try:
            saved_url = url_path.read_text(encoding="utf-8").strip()
            if saved_url != expected_url:
                return None
            page = parse_listing_page(html_path.read_text(encoding="utf-8"), saved_url)
        except (OSError, PageFormatError, ValueError):
            return None
        points = _map_points(directory, saved_url)
        if points is None:
            if bounds:
                return None
            geo_errors.append(f"Страница {page_number}: координаты не сохранены в снимке")
            points = {}
        elif page.next_url:
            next_points = _map_points(directory, page.next_url)
            if next_points:
                for listing_id, point in next_points.items():
                    points.setdefault(listing_id, point)
        page = attach_geo(page, points)
        if bounds:
            page, missing, outside = filter_page(page, bounds, polygon)
            without_coordinates += missing
            outside_bounds += outside
        if identity.get("location_query"):
            page, outside = filter_page_location(page, identity["location_query"])
            outside_location += outside
        site_count = page.total_found if page.total_found is not None else site_count
        for item in page.listings:
            records[item.id] = item.as_dict()
        has_more = page.next_url is not None
        if not has_more or (max_pages and page_number >= max_pages):
            return {
                "pages": page_number,
                "unique_ids": len(records),
                "site_count": site_count,
                "pagination_exhausted": not has_more,
                "has_more": has_more,
                "with_coordinates": sum(item["latitude"] is not None for item in records.values()),
                "geo_errors": geo_errors,
                "bounds": bounds.as_query() if bounds else None,
                "area_kind": "polygon" if polygon else ("rectangle" if bounds else None),
                "excluded_without_coordinates": without_coordinates,
                "excluded_outside_area": outside_bounds,
                "excluded_outside_bounds": outside_bounds,
                "excluded_outside_location": outside_location,
                "location_query": identity.get("location_query"),
                "snapshot_dir": str(directory),
                "listings": list(records.values()),
            }
        expected_url = page.next_url
    return None


def find_last_complete(
    snapshots_root: Path, identity: dict, bounds: Bounds | None, polygon: Polygon | None,
) -> dict | None:
    if not snapshots_root.is_dir():
        return None
    for directory in sorted((path for path in snapshots_root.iterdir() if path.is_dir()), reverse=True):
        if (directory / "source-error.json").exists() or (directory / "run-error.json").exists():
            continue
        timestamp = _snapshot_time(directory)
        if timestamp is None:
            continue
        result_path = directory / "result.json"
        if result_path.is_file():
            try:
                saved = json.loads(result_path.read_text(encoding="utf-8"))
                if saved.get("request") == identity and isinstance(saved.get("result", {}).get("listings"), list):
                    return {**saved["result"], "cached": True, "cached_at": saved.get("collected_at", timestamp), "cache_snapshot_dir": str(directory)}
            except (OSError, ValueError, AttributeError):
                pass
        first_url = directory / "page-001.url.txt"
        try:
            if not first_url.is_file() or first_url.read_text(encoding="utf-8").strip() != identity["search_url"]:
                continue
        except OSError:
            continue
        replayed = _replay(directory, identity, bounds, polygon)
        if replayed is not None:
            return {**replayed, "cached": True, "cached_at": timestamp, "cache_snapshot_dir": str(directory)}
    return None
