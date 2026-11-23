from http.server import ThreadingHTTPServer
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from socket import socket
from tempfile import TemporaryDirectory
from threading import Thread
from time import sleep
from unittest import TestCase
from unittest.mock import patch
import json

import requests

from krisha_list import server as server_module
from krisha_list.area import Bounds, with_bounds
from krisha_list.client import SourceHTTPError
from krisha_list.model import PageFormatError
from krisha_list.parser import parse_listing_page
from krisha_list.snapshot_cache import find_last_complete, request_identity, save_success
from krisha_list.storage import ListingStore


BASE_URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class OneRequestServer(ThreadingHTTPServer):
    def serve_forever(self):
        self.handle_request()


class ServerCacheTests(TestCase):
    def test_area_geo_failure_is_partial_and_not_cached(self):
        class FailedGeo:
            def __init__(self, *_args, **_kwargs):
                pass

            def enrich(self, page):
                return page, ["Карта вернула не JSON"]

        page = replace(parse_listing_page(FIXTURE.read_text(encoding="utf-8"), BASE_URL), next_url=None)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "GeoEnricher", FailedGeo), \
                 patch.object(server_module, "crawl_pages", return_value=iter((page,))):
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": root / "test.sqlite3", "default_url": BASE_URL,
                    "enable_live": True,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect",
                            json={"url": BASE_URL, "max_pages": 1,
                                  "bounds": "43.27,76.87,43.23,76.91"},
                            headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "partial")
            snapshot = Path(response.json()["snapshot_dir"])
            self.assertFalse((snapshot / "result.json").exists())
            self.assertTrue((snapshot / "run-error.json").exists())
            with ListingStore(root / "test.sqlite3") as store:
                self.assertEqual(store.list_runs()[0]["status"], "partial")

    def test_live_collection_filters_named_location(self):
        class NoGeo:
            def __init__(self, *_args, **_kwargs):
                pass

            def enrich(self, page):
                return page, []

        source = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), BASE_URL)
        page = replace(source, listings=(
            replace(source.listings[0], district="Алмалинский р-н"),
            replace(source.listings[1], district="Медеуский р-н"),
        ), next_url=None)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "GeoEnricher", NoGeo), \
                 patch.object(server_module, "crawl_pages", return_value=iter((page,))):
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": root / "test.sqlite3", "default_url": BASE_URL,
                    "enable_live": True,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect",
                            json={"url": BASE_URL, "max_pages": 1, "location_query": "Алмалинский р-н"},
                            headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["unique_ids"], 1)
            self.assertEqual(response.json()["excluded_outside_location"], 1)
            with ListingStore(root / "test.sqlite3") as store:
                self.assertEqual(store.counts()["listings"], 1)

    def test_recent_snapshot_avoids_a_new_source_request(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "snapshots" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            snapshot.mkdir(parents=True)
            page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), BASE_URL)
            save_success(snapshot, request_identity(BASE_URL, 1, None, None), {
                "pages": 1, "unique_ids": len(page.listings), "listings": [item.as_dict() for item in page.listings],
            })
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "crawl_pages") as crawl:
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": root / "test.sqlite3", "default_url": BASE_URL,
                    "enable_live": True,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect",
                            json={"url": BASE_URL, "max_pages": 1},
                            headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
                crawl.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["code"], "fresh_cache")
            self.assertEqual(response.json()["pages"], 0)
            self.assertEqual(response.json()["cached_pages"], 1)
            with ListingStore(root / "test.sqlite3") as store:
                self.assertEqual(store.counts()["listings"], len(page.listings))

    def test_expired_html_snapshot_reuses_recent_coordinates(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "snapshots" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            snapshot.mkdir(parents=True)
            page = replace(parse_listing_page(FIXTURE.read_text(encoding="utf-8"), BASE_URL), next_url=None)
            records = [replace(item, latitude=43.25, longitude=76.88,
                               geo_source="krisha_map_list").as_dict() for item in page.listings]
            save_success(snapshot, request_identity(BASE_URL, 1, None, None), {
                "pages": 1, "unique_ids": len(records), "listings": records,
            })
            saved = json.loads((snapshot / "result.json").read_text(encoding="utf-8"))
            saved["collected_at"] = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
            (snapshot / "result.json").write_text(json.dumps(saved), encoding="utf-8")
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "crawl_pages", return_value=iter((page,))) as crawl, \
                 patch.object(server_module.PacedSession, "get") as map_get:
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": root / "test.sqlite3", "default_url": BASE_URL,
                    "enable_live": True,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect",
                            json={"url": BASE_URL, "max_pages": 1},
                            headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
                crawl.assert_called_once()
                map_get.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["reused_coordinates"], len(records))
            self.assertTrue(all(item["geo_source"] == "krisha_map_list_cached"
                                for item in response.json()["listings"]))

    def test_recent_468_delays_new_requests_without_a_snapshot(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "test.sqlite3"
            with ListingStore(db) as store:
                run_id = store.start_run("live", {"requested_url": BASE_URL})
                store.finish_run(run_id, "blocked", {"pages": 0, "unique_ids": 0}, source_status=468)
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "crawl_pages") as crawl:
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": db, "default_url": BASE_URL, "enable_live": True,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect",
                            json={"url": BASE_URL, "max_pages": 1},
                            headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
                crawl.assert_not_called()
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json()["code"], "source_cooldown")
            self.assertEqual(response.json()["source_status"], 468)
            self.assertIn("next_retry_at", response.json())

    def test_cooldown_respects_longer_retry_after_header(self):
        with TemporaryDirectory() as temporary:
            snapshot = Path(temporary)
            (snapshot / "source-error.json").write_text(json.dumps({
                "response": {"retry_after": "3600"},
            }), encoding="utf-8")
            deadline = server_module.source_retry_at({
                "finished_at": "2026-11-21T12:00:00+00:00", "source_status": 429,
                "snapshot_dir": str(snapshot),
            })
            self.assertEqual(deadline.isoformat(), "2026-11-21T13:00:00+00:00")
            challenge_deadline = server_module.source_retry_at({
                "finished_at": "2026-11-21T12:00:00+00:00", "source_status": 200,
                "status": "blocked", "snapshot_dir": None,
            })
            self.assertEqual(challenge_deadline.isoformat(), "2026-11-21T12:30:00+00:00")
            self.assertEqual(server_module.source_retry_at({
                "finished_at": "2026-11-21T12:00:00+00:00", "source_status": 468,
                "status": "blocked", "snapshot_dir": None,
            }, consecutive_failures=3).isoformat(), "2026-11-21T14:00:00+00:00")
            self.assertEqual(server_module.source_retry_at({
                "finished_at": "2026-11-21T12:00:00+00:00", "source_status": 468,
                "status": "blocked", "snapshot_dir": None,
            }, consecutive_failures=8).isoformat(), "2026-11-21T16:00:00+00:00")

    def test_access_challenge_returns_last_complete_snapshot_without_retry(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "snapshots" / "20261121T125429000000Z"
            run.mkdir(parents=True)
            bounds = Bounds(43.245, 76.87, 43.23, 76.89)
            url = with_bounds(BASE_URL, bounds)
            (run / "page-001.url.txt").write_text(url + "\n", encoding="utf-8")
            (run / "page-001.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            (run / "map-page-001.json").write_text(json.dumps({"adverts": {
                "123": {"map": {"lat": 43.24, "lon": 76.88}},
                "456": {"map": {"lat": 43.25, "lon": 76.90}},
            }}), encoding="utf-8")
            source_response = requests.Response()
            source_response.status_code = 468
            source_response.url = url
            source_response.headers["Content-Type"] = "text/html"
            source_response._content = b'<link href="/.safeline/static/favicon.png">'
            challenge = SourceHTTPError(468, url, source_response)
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), patch.object(server_module, "crawl_pages", side_effect=challenge) as crawl:
                thread = Thread(target=server_module.serve, kwargs={"port": port, "db_path": root / "test.sqlite3", "default_url": BASE_URL, "enable_live": True}, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect", json={"url": url, "max_pages": 1}, headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                crawl.assert_called_once()
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertTrue(result["cached"])
            self.assertEqual(result["source_status"], 468)
            self.assertEqual(result["pages"], 0)
            self.assertEqual(result["cached_pages"], 1)
            self.assertEqual(result["unique_ids"], 1)
            self.assertEqual(result["listings"][0]["id"], 123)
            with ListingStore(root / "test.sqlite3") as store:
                run = store.list_runs()[0]
                self.assertEqual(run["status"], "cached")
                self.assertEqual(run["pages"], 0)
                self.assertEqual(run["source_status"], 468)
                self.assertEqual(store.counts()["listings"], 1)

    def test_parser_failure_after_page_reports_partial_and_never_becomes_cache(self):
        class NoGeo:
            def __init__(self, *_args, **_kwargs):
                pass

            def enrich(self, page):
                return page, []

        def interrupted_crawl(url, *, on_html, **_kwargs):
            html = FIXTURE.read_text(encoding="utf-8")
            on_html(1, url, html)
            yield parse_listing_page(html, url)
            raise PageFormatError("Изменилась разметка второй страницы")

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "crawl_pages", side_effect=interrupted_crawl), \
                 patch.object(server_module, "GeoEnricher", NoGeo):
                thread = Thread(target=server_module.serve,
                    kwargs={"port": port, "db_path": root / "test.sqlite3", "default_url": BASE_URL,
                            "enable_live": True}, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/collect",
                            json={"url": BASE_URL, "max_pages": 1},
                            headers={"Origin": f"http://127.0.0.1:{port}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
            self.assertEqual(response.status_code, 502)
            result = response.json()
            self.assertTrue(result["partial"])
            self.assertEqual(result["pages"], 1)
            self.assertEqual(result["unique_ids"], 2)
            self.assertEqual(len(result["listings"]), 2)
            run_dir = Path(result["snapshot_dir"])
            self.assertTrue((run_dir / "run-error.json").is_file())
            self.assertIsNone(find_last_complete(root / "snapshots",
                request_identity(BASE_URL, 1, None, None), None, None))
            with ListingStore(root / "test.sqlite3") as store:
                self.assertEqual(store.list_runs()[0]["status"], "partial")
