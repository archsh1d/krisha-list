"""Local-only web UI and live collection endpoint."""

from __future__ import annotations

import json
import hmac
import ipaddress
import sqlite3
import re
from io import StringIO
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit
from bs4 import BeautifulSoup

from .client import CrawlError, PacedSession, SourceHTTPError, crawl_pages, validate_search_url
from .api_v1 import parse_listings_query, parse_runs_query
from .area import bounds_from_url, filter_page, parse_bounds, parse_polygon, with_bounds
from .categories import AREA_URLS, DEFAULT_URLS
from .geo import GeoEnricher, page_number_from_url, snapshot_geo_points
from .location import filter_page_location, normalize_place
from .model import Listing, PageFormatError
from .parser import parse_listing_page
from .snapshot_cache import find_last_complete, request_identity, save_success
from .storage import ListingStore
from .source_policy import source_retry_at


FRESH_SNAPSHOT_AGE = timedelta(minutes=15)
GEO_REUSE_AGE = timedelta(hours=6)


def public_run(run: dict) -> dict:
    return {key: value for key, value in run.items() if key not in {"request_json", "snapshot_dir"}}


def serve(*, port: int, db_path: str | Path, default_url: str, enable_live: bool,
          host: str = "127.0.0.1", api_token: str | None = None,
          ui_origin: str | None = None) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("Порт должен быть от 1 до 65535")
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError as error:
        raise ValueError("Укажите IPv4-адрес для --host") from error
    if api_token is not None and len(api_token) < 32:
        raise ValueError("API-токен должен содержать не менее 32 символов")
    if not address.is_loopback and not api_token:
        raise ValueError("Для сетевого доступа укажите --api-token-file")
    if ui_origin is not None:
        ui_address = urlsplit(ui_origin)
        if ui_address.scheme != "http" or ui_address.hostname not in {"127.0.0.1", "localhost"} or not ui_address.port or ui_address.path or ui_address.query or ui_address.fragment:
            raise ValueError("--ui-origin должен быть локальным HTTP-адресом с портом")
    web_root = Path(__file__).resolve().parents[2] / "web" / "dist"
    if not (web_root / "index.html").is_file():
        raise FileNotFoundError(f"Не найден веб-интерфейс: {web_root}")
    db_path = Path(db_path).resolve()
    lock = Lock()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_root), **kwargs)

        def _json(self, status: int, value: dict) -> None:
            if self.path.startswith("/api/v1/"):
                value = {key: item for key, item in value.items()
                         if key not in {"snapshot_dir", "cache_snapshot_dir"}}
                if isinstance(value.get("error"), str):
                    value = {**value, "error": {"code": value.get("code") or "request_failed",
                                                 "message": value["error"]}}
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            if status == 401 and self.path.startswith("/api/v1/"):
                self.send_header("WWW-Authenticate", 'Bearer realm="Krisha List API"')
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def _local_client(self) -> bool:
            try:
                return ipaddress.ip_address(self.client_address[0]).is_loopback
            except ValueError:
                return False

        def _ui_client(self) -> bool:
            return self._local_client() or bool(
                ui_origin and self.headers.get("Host") == urlsplit(ui_origin).netloc
            )

        def _api_authorized(self) -> bool:
            if not api_token:
                self._json(503, {"error": "API выключен: задайте токен при запуске сервера", "code": "api_disabled"})
                return False
            if self.headers.get("Origin"):
                self._json(403, {"error": "Используйте серверный запрос без браузерного Origin", "code": "browser_forbidden"})
                return False
            authorization = self.headers.get("Authorization", "")
            supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
            if not hmac.compare_digest(supplied, api_token):
                self._json(401, {"error": "Неверный или отсутствующий API-токен", "code": "unauthorized"})
                return False
            return True

        def _get_api_v1(self, path: str, query: str) -> None:
            if path == "/api/v1/openapi.json":
                parameters = parse_qs(query, keep_blank_values=True)
                language = parameters.get("lang", ["ru"])
                if set(parameters) - {"lang"} or len(language) != 1 or language[0] not in {"ru", "en", "kk"}:
                    self._json(400, {"error": "Укажите lang=ru, en или kk", "code": "invalid_locale"})
                    return
                try:
                    filename = "openapi.json" if language[0] == "ru" else f"openapi.{language[0]}.json"
                    self._json(200, json.loads((web_root / filename).read_text(encoding="utf-8")))
                except (OSError, ValueError) as error:
                    self._json(500, {"error": f"Не удалось открыть описание API: {error}"})
                return
            if not self._api_authorized():
                return
            try:
                with ListingStore(db_path) as store:
                    if path == "/api/v1/status" and not query:
                        self._json(200, {"version": "1", "live_enabled": enable_live,
                                         "database": store.counts()})
                        return
                    if path == "/api/v1/listings":
                        filters = parse_listings_query(query)
                        items, total = store.query_listings(**filters)
                        offset, limit = filters["offset"], filters["limit"]
                        next_offset = offset + len(items) if offset + len(items) < total else None
                        self._json(200, {"data": items, "page": {"total": total, "limit": limit,
                                                                  "offset": offset, "next_offset": next_offset}})
                        return
                    match = re.fullmatch(r"/api/v1/listings/([1-9]\d*)", path)
                    if match and not query:
                        item = store.get_listing(int(match[1]))
                        if item:
                            self._json(200, {"data": item})
                        else:
                            self._json(404, {"error": "Объявление не найдено", "code": "not_found"})
                        return
                    if path == "/api/v1/runs":
                        self._json(200, {"data": [public_run(run) for run in store.list_runs(parse_runs_query(query))]})
                        return
                    match = re.fullmatch(r"/api/v1/runs/([1-9]\d*)", path)
                    if match and not query:
                        run = store.get_run(int(match[1]))
                        if run:
                            self._json(200, {"data": public_run(run)})
                        else:
                            self._json(404, {"error": "Сбор не найден", "code": "not_found"})
                        return
                self._json(404, {"error": "Неизвестный адрес API", "code": "not_found"})
            except ValueError as error:
                self._json(400, {"error": str(error), "code": "invalid_query"})
            except (OSError, sqlite3.Error) as error:
                self._json(500, {"error": f"Не удалось открыть каталог SQLite: {error}", "code": "database_error"})

        def do_GET(self) -> None:
            route = urlsplit(self.path)
            if route.path.startswith("/api/v1/"):
                self._get_api_v1(route.path, route.query)
                return
            if not self._ui_client():
                self._json(403, {"error": "Локальный интерфейс недоступен по сети"})
                return
            if self.path == "/api/status":
                self._json(200, {"live_enabled": enable_live, "default_url": default_url,
                                 "category_urls": DEFAULT_URLS, "area_category_urls": AREA_URLS})
                return
            if self.path == "/api/catalog":
                try:
                    with ListingStore(db_path) as store:
                        self._json(200, {"listings": store.list_catalog(), "runs": store.list_runs(),
                                         "database": store.counts()})
                except (OSError, sqlite3.Error) as error:
                    self._json(500, {"error": f"Не удалось открыть каталог SQLite: {error}"})
                return
            super().do_GET()

        def do_POST(self) -> None:
            api_collection = self.path == "/api/v1/collections"
            if not api_collection and self.path not in {"/api/collect", "/api/export", "/api/import-html", "/api/migrate"}:
                self._json(404, {"error": "Неизвестный адрес API"})
                return
            if api_collection:
                if not self._api_authorized():
                    return
            else:
                origin = self.headers.get("Origin")
                allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
                if ui_origin:
                    allowed_origins.add(ui_origin)
                if not self._ui_client() or origin not in allowed_origins:
                    self._json(403, {"error": "Запрос разрешён только из локального интерфейса"})
                    return
            if self.path == "/api/import-html":
                if not self.headers.get("Content-Type", "").startswith("text/html"):
                    self._json(415, {"error": "Ожидается HTML-файл"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= length <= 15 * 1024 * 1024:
                        raise ValueError("HTML-файл должен быть не больше 15 МБ")
                    html = self.rfile.read(length).decode("utf-8", errors="replace")
                    canonical = BeautifulSoup(html, "html.parser").select_one('link[rel="canonical"][href]')
                    source_url = canonical.get("href") if canonical else default_url
                    validate_search_url(source_url)
                    page = parse_listing_page(html, source_url)
                    with ListingStore(db_path) as store:
                        run_id = store.start_run("html_import", {"source_url": source_url, "filename": self.headers.get("X-File-Name", "")})
                        store.merge_snapshot([item.as_dict() for item in page.listings],
                                             observed_at=datetime.now(timezone.utc).isoformat(),
                                             source_url=source_url, run_id=run_id)
                        store.finish_run(run_id, "imported", {"pages": 1, "unique_ids": len(page.listings),
                                                           "site_count": page.total_found, "has_more": page.next_url is not None,
                                                           "with_coordinates": 0})
                    self._json(200, {"run_id": run_id, "unique_ids": len(page.listings)})
                except (ValueError, PageFormatError, OSError, sqlite3.Error) as error:
                    if "run_id" in locals():
                        with ListingStore(db_path) as store:
                            store.finish_run(run_id, "failed", {"pages": 0, "unique_ids": 0}, error=str(error))
                    self._json(500 if isinstance(error, (OSError, sqlite3.Error)) else 400,
                               {"error": str(error)})
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self._json(415, {"error": "Ожидается JSON"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                max_length = 2_000_000 if self.path == "/api/migrate" else 1_000_000 if self.path == "/api/export" else 4096
                if not 1 <= length <= max_length:
                    raise ValueError("Некорректный размер запроса")
                options = json.loads(self.rfile.read(length))
                if not isinstance(options, dict):
                    raise ValueError("Ожидается объект JSON")
                if api_collection and (unknown := options.keys() - {"url", "max_pages", "bounds", "polygon", "location_query"}):
                    raise ValueError(f"Неизвестный параметр: {sorted(unknown)[0]}")
                if self.path == "/api/export":
                    ids = options.get("ids")
                    if not isinstance(ids, list) or len(ids) > 50000 or any(type(value) is not int or value <= 0 for value in ids):
                        raise ValueError("Ожидается список ID объявлений")
                    stream = StringIO(newline="")
                    with ListingStore(db_path) as store:
                        store.export_ids(list(dict.fromkeys(ids)), stream)
                    payload = ("\ufeff" + stream.getvalue()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="krisha-list.csv"')
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if self.path == "/api/migrate":
                    rows = options.get("listings")
                    if not isinstance(rows, list) or len(rows) > 10000:
                        raise ValueError("Ожидается список сохранённых карточек")
                    added = 0
                    migrated = 0
                    coordinates = 0
                    with ListingStore(db_path) as store:
                        run_id = store.start_run("browser_import", {"source": "browser", "items": len(rows)})
                        for row in rows:
                            if not isinstance(row, dict) or row.get("demo"):
                                continue
                            listing_id = int(row["id"])
                            if listing_id <= 0 or not isinstance(row.get("title"), str) or not row["title"].strip():
                                raise ValueError("Некорректная карточка из браузера")
                            data = {"id": listing_id, "url": f"https://krisha.kz/a/show/{listing_id}",
                                    "title": row["title"], "object_type": row.get("objectType"), "rooms": row.get("rooms"),
                                    "house_area_m2": row.get("houseArea"), "plot_area_sot": row.get("plotArea"),
                                    "price_kzt": row.get("price"), "district": row.get("district"), "address": row.get("address"),
                                    "description_preview": row.get("preview"), "seller_type": row.get("seller"),
                                    "city": row.get("city"), "posted_label": row.get("posted"), "floors": row.get("floors"),
                                    "year_built": row.get("yearBuilt"), "page_number": 1, "latitude": row.get("latitude"),
                                    "longitude": row.get("longitude"), "geo_source": row.get("geoSource"),
                                    "geo_zoom": row.get("geoZoom"), "geo_type": row.get("geoType"),
                                    "category": row.get("category") if row.get("category") in {"house", "apartment"} else "house",
                                    "apartment_area_m2": row.get("apartmentArea"), "floor": row.get("floor"),
                                    "building_floors": row.get("buildingFloors"), "residential_complex": row.get("residentialComplex")}
                            observed_at = row.get("lastSeenAt") if isinstance(row.get("lastSeenAt"), str) else datetime.now(timezone.utc).isoformat()
                            was_added = store.merge_snapshot([Listing(**data).as_dict()], observed_at=observed_at,
                                                             source_url="browser-import", run_id=run_id)
                            added += was_added
                            if was_added and isinstance(row.get("firstSeenAt"), str):
                                with store.connection:
                                    store.connection.execute("UPDATE listings SET first_seen_at=? WHERE id=?",
                                                             (row["firstSeenAt"], listing_id))
                            migrated += 1
                            coordinates += data["latitude"] is not None and data["longitude"] is not None
                            for event in row.get("history") if isinstance(row.get("history"), list) else []:
                                if isinstance(event, dict) and type(event.get("price")) is int and isinstance(event.get("observedAt"), str):
                                    with store.connection:
                                        store.connection.execute(
                                            "INSERT OR IGNORE INTO price_history(listing_id, observed_at, price_kzt) VALUES (?, ?, ?)",
                                            (listing_id, event["observedAt"], event["price"]),
                                        )
                        store.finish_run(run_id, "imported", {"pages": 0, "unique_ids": migrated,
                                                               "with_coordinates": coordinates})
                    self._json(200, {"added": added, "run_id": run_id})
                    return
                if not enable_live:
                    self._json(403, {"error": "Живой сбор не включён при запуске сервера"})
                    return
                url = options.get("url", default_url)
                max_pages = options.get("max_pages", 1)
                if not isinstance(url, str) or type(max_pages) is not int or not 0 <= max_pages <= 10:
                    raise ValueError("Укажите ссылку и число страниц от 1 до 10 либо 0 для всех")
                validate_search_url(url)
                requested_bounds = options.get("bounds")
                if requested_bounds is not None and not isinstance(requested_bounds, str):
                    raise ValueError("Границы области должны быть строкой координат")
                requested_polygon = options.get("polygon")
                if requested_polygon is not None and requested_bounds is not None:
                    raise ValueError("Укажите либо прямоугольник, либо полигон")
                location_query = options.get("location_query")
                if location_query is not None:
                    if not isinstance(location_query, str) or len(location_query) > 120 or not normalize_place(location_query):
                        raise ValueError("Укажите район или микрорайон длиной до 120 символов")
                    location_query = location_query.strip()
                    if requested_polygon is not None or requested_bounds is not None:
                        raise ValueError("Выберите область по названию либо на карте")
                polygon = parse_polygon(requested_polygon) if requested_polygon is not None else None
                bounds = polygon.bounds if polygon else (parse_bounds(requested_bounds) if requested_bounds else bounds_from_url(url))
                if location_query and bounds:
                    raise ValueError("Выберите область по названию либо на карте")
                search_url = with_bounds(url, bounds) if polygon or requested_bounds else url
                identity = request_identity(search_url, max_pages, bounds, polygon, location_query)
            except (ValueError, KeyError, TypeError, sqlite3.Error, json.JSONDecodeError) as error:
                if self.path == "/api/migrate" and "run_id" in locals():
                    with ListingStore(db_path) as store:
                        store.finish_run(run_id, "failed", {"pages": 0, "unique_ids": migrated}, error=str(error))
                self._json(500 if isinstance(error, sqlite3.Error) else 400, {"error": str(error)})
                return
            if not lock.acquire(blocking=False):
                self._json(409, {"error": "Сбор уже выполняется"})
                return
            run_dir = None
            run_id = None
            pages = 0
            unique_ids: set[int] = set()
            records: dict[int, dict] = {}
            expected = None
            has_more = False
            without_coordinates = outside_bounds = outside_location = 0
            try:
                snapshots_root = db_path.parent / "snapshots"
                now = datetime.now(timezone.utc)
                with ListingStore(db_path) as store:
                    last_access = store.latest_source_access()
                    failure_streak = store.source_failure_streak()
                cached = find_last_complete(snapshots_root, identity, bounds, polygon)
                retry_at = source_retry_at(last_access, failure_streak)
                if retry_at and now < retry_at:
                    if cached is not None:
                        with ListingStore(db_path) as store:
                            store.merge_snapshot(cached["listings"], observed_at=cached["cached_at"],
                                                 source_url=search_url)
                        self._json(200, {**cached, "pages": 0, "cached_pages": cached["pages"],
                                         "code": "source_cooldown_cache", "source_status": last_access["source_status"],
                                         "next_retry_at": retry_at.isoformat()})
                    else:
                        self._json(429, {"error": "После отказа Krisha.kz новый запрос временно отложен.",
                                         "code": "source_cooldown", "source_status": last_access["source_status"],
                                         "next_retry_at": retry_at.isoformat()})
                    return
                age = None
                if cached is not None:
                    try:
                        cached_at = datetime.fromisoformat(cached["cached_at"])
                        age = now - cached_at
                    except (TypeError, ValueError):
                        pass
                    if age is not None and timedelta(0) <= age <= FRESH_SNAPSHOT_AGE:
                        with ListingStore(db_path) as store:
                            store.merge_snapshot(cached["listings"], observed_at=cached["cached_at"],
                                                 source_url=search_url)
                        self._json(200, {**cached, "pages": 0, "cached_pages": cached["pages"],
                                         "code": "fresh_cache"})
                        return
                run_dir = snapshots_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                run_dir.mkdir(parents=True, exist_ok=True)
                with ListingStore(db_path) as store:
                    run_id = store.start_run("live", {"requested_url": url, **identity}, str(run_dir))

                def save_snapshot(number: int, page_url: str, html: str) -> None:
                    stem = f"page-{number:03d}"
                    (run_dir / f"{stem}.html").write_text(html, encoding="utf-8")
                    (run_dir / f"{stem}.url.txt").write_text(page_url + "\n", encoding="utf-8")

                geo_errors: list[str] = []
                known_points = snapshot_geo_points(cached["listings"]) if (
                    cached is not None and age is not None and timedelta(0) <= age <= GEO_REUSE_AGE
                ) else {}
                with ListingStore(db_path) as store, PacedSession(interval=3) as source_session:
                    geo_enricher = GeoEnricher(
                        source_session,
                        known_points=known_points,
                        on_json=lambda source, raw: (run_dir / f"map-page-{page_number_from_url(source):03d}.json").write_text(raw, encoding="utf-8"),
                    )
                    for page in crawl_pages(search_url, max_pages=max_pages, delay=0,
                                            session=source_session, on_html=save_snapshot):
                        has_more = page.next_url is not None
                        page, errors = geo_enricher.enrich(page)
                        geo_errors.extend(f"Страница {pages + 1}: {error}" for error in errors)
                        if bounds:
                            page, missing, outside = filter_page(page, bounds, polygon)
                            without_coordinates += missing
                            outside_bounds += outside
                        if location_query:
                            page, outside = filter_page_location(page, location_query)
                            outside_location += outside
                        observed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
                        store.upsert(page.listings, observed_at=observed_at, source_url=search_url, run_id=run_id)
                        pages += 1
                        expected = page.total_found if page.total_found is not None else expected
                        for item in page.listings:
                            unique_ids.add(item.id)
                            records[item.id] = item.as_dict()
                    counts = store.counts()
                result = {
                    "pages": pages,
                    "unique_ids": len(unique_ids),
                    "site_count": expected,
                    "pagination_exhausted": not has_more,
                    "has_more": has_more,
                    "with_coordinates": sum(item["latitude"] is not None for item in records.values()),
                    "reused_coordinates": getattr(geo_enricher, "reused_count", 0),
                    "geo_errors": geo_errors,
                    "bounds": bounds.as_query() if bounds else None,
                    "area_kind": "polygon" if polygon else ("rectangle" if bounds else None),
                    "excluded_without_coordinates": without_coordinates,
                    "excluded_outside_area": outside_bounds,
                    "excluded_outside_bounds": outside_bounds,
                    "excluded_outside_location": outside_location,
                    "location_query": location_query,
                    "database": counts,
                    "snapshot_dir": str(run_dir),
                    "listings": list(records.values()),
                }
                incomplete_geo = bool(bounds and geo_errors)
                if incomplete_geo:
                    (run_dir / "run-error.json").write_text(json.dumps({
                        "error": "Координаты карты получены не полностью; выборка по области неполная",
                        "geo_errors": geo_errors,
                    }, ensure_ascii=False), encoding="utf-8")
                else:
                    save_success(run_dir, identity, result)
                with ListingStore(db_path) as store:
                    store.finish_run(run_id, "partial" if incomplete_geo else "complete" if not has_more else "limited", result)
                result["status"] = "partial" if incomplete_geo else "complete" if not has_more else "limited"
                result["run_id"] = run_id
                self._json(200, result)
            except SourceHTTPError as error:
                if error.response_body:
                    (run_dir / "source-response.html").write_bytes(error.response_body)
                (run_dir / "source-error.json").write_text(
                    json.dumps({"status": error.status_code, "url": error.url,
                                "response": error.diagnostics}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                if pages == 0 and (error.is_challenge or error.status_code in (403, 429, 468)):
                    cached = find_last_complete(snapshots_root, identity, bounds, polygon)
                    if cached is not None:
                        with ListingStore(db_path) as store:
                            store.merge_snapshot(cached["listings"], observed_at=cached["cached_at"],
                                                 source_url=search_url, run_id=run_id)
                            store.finish_run(run_id, "cached", {**cached, "pages": 0}, error=str(error),
                                             source_status=error.status_code, cached_at=cached["cached_at"])
                        self._json(200, {**cached, "pages": 0, "cached_pages": cached["pages"],
                                         "run_id": run_id, "source_status": error.status_code,
                                         "source_error": str(error), "code": "cached_source_challenge"})
                        return
                with ListingStore(db_path) as store:
                    store.finish_run(run_id, "partial" if pages else "blocked" if error.is_challenge or error.status_code in (403, 429, 468) else "failed", {
                        "pages": pages, "unique_ids": len(unique_ids), "site_count": expected, "has_more": has_more,
                        "with_coordinates": sum(item["latitude"] is not None for item in records.values()),
                        "excluded_without_coordinates": without_coordinates, "excluded_outside_area": outside_bounds,
                        "excluded_outside_location": outside_location,
                    }, error=str(error), source_status=error.status_code)
                self._json(502, {"error": str(error),
                                 "code": "source_challenge" if error.is_challenge else "source_http_error",
                                 "source_status": error.status_code, "snapshot_dir": str(run_dir), "run_id": run_id,
                                 "partial": pages > 0, "pages": pages, "unique_ids": len(unique_ids),
                                 "site_count": expected, "has_more": has_more,
                                 "with_coordinates": sum(item["latitude"] is not None for item in records.values()),
                                 "listings": list(records.values())})
            except (CrawlError, PageFormatError, OSError, sqlite3.Error, ValueError) as error:
                if run_dir is not None:
                    try:
                        (run_dir / "run-error.json").write_text(json.dumps({
                            "error": str(error), "pages": pages, "unique_ids": len(unique_ids),
                        }, ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        pass
                if run_id is not None:
                    with ListingStore(db_path) as store:
                        store.finish_run(run_id, "partial" if pages else "failed", {
                            "pages": pages, "unique_ids": len(unique_ids), "site_count": expected,
                            "has_more": has_more, "with_coordinates": sum(item["latitude"] is not None for item in records.values()),
                            "excluded_without_coordinates": without_coordinates, "excluded_outside_area": outside_bounds,
                            "excluded_outside_location": outside_location,
                        }, error=str(error))
                self._json(502, {"error": str(error), "snapshot_dir": str(run_dir) if run_dir else None,
                                 "run_id": run_id, "partial": pages > 0, "pages": pages,
                                 "unique_ids": len(unique_ids), "site_count": expected,
                                 "has_more": has_more, "listings": list(records.values())})
            finally:
                lock.release()

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Откройте {ui_origin or f'http://127.0.0.1:{port}'}/")
    print(f"Живой сбор: {'включён' if enable_live else 'выключен'}")
    print(f"API v1: {'включён' if api_token else 'выключен'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
