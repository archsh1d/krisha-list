from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from socket import socket
from tempfile import TemporaryDirectory
from threading import Thread
from time import sleep
from unittest import TestCase
from unittest.mock import patch

import requests

from krisha_list import server as server_module
from krisha_list.api_v1 import parse_listings_query
from krisha_list.parser import parse_listing_page
from krisha_list.storage import ListingStore


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"
TOKEN = "a" * 40


class ThirteenRequestServer(ThreadingHTTPServer):
    def serve_forever(self):
        for _ in range(13):
            self.handle_request()


class OneRequestServer(ThreadingHTTPServer):
    def serve_forever(self):
        self.handle_request()


class ApiV1Tests(TestCase):
    def test_query_rejects_unknown_and_malformed_filters(self):
        self.assertEqual(parse_listings_query("limit=2&offset=3")["offset"], 3)
        for query in ("limit=0", "limit=101", "limit=1&limit=2", "category=land",
                      "city=", "bounds=bad", "updated_after=2026-11-22", "surprise=yes"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                parse_listings_query(query)

    def test_storage_filters_city_district_and_update_time(self):
        with TemporaryDirectory() as temporary:
            db = Path(temporary) / "test.sqlite3"
            page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
            with ListingStore(db) as store:
                store.upsert([page.listings[0]], observed_at="2026-11-21T12:00:00+00:00", source_url=URL)
                store.upsert([page.listings[1]], observed_at="2026-11-22T12:00:00+00:00", source_url=URL)
                city, total = store.query_listings(city="Алматы")
                self.assertEqual(total, 1)
                self.assertEqual(city[0]["id"], page.listings[0].id)
                recent, total = store.query_listings(updated_after="2026-11-22T00:00:00+00:00")
                self.assertEqual(total, 1)
                self.assertEqual(recent[0]["id"], page.listings[1].id)

    def test_server_api_auth_pagination_detail_and_runs(self):
        with TemporaryDirectory() as temporary:
            db = Path(temporary) / "test.sqlite3"
            page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
            items = [replace(page.listings[0], latitude=43.24, longitude=76.88), page.listings[1]]
            with ListingStore(db) as store:
                run_id = store.start_run("live", {"requested_url": URL})
                store.upsert(items, observed_at="2026-11-21T12:00:00+00:00", source_url=URL, run_id=run_id)
                store.finish_run(run_id, "complete", {"pages": 1, "unique_ids": 2})
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            headers = {"Authorization": f"Bearer {TOKEN}"}
            with patch.object(server_module, "ThreadingHTTPServer", ThirteenRequestServer):
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": db, "default_url": URL,
                    "enable_live": False, "api_token": TOKEN,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        spec = requests.get(base + "/api/v1/openapi.json", timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                self.assertEqual(spec.status_code, 200)
                self.assertEqual(spec.json()["openapi"], "3.1.0")
                english_spec = requests.get(base + "/api/v1/openapi.json?lang=en", timeout=3)
                kazakh_spec = requests.get(base + "/api/v1/openapi.json?lang=kk", timeout=3)
                self.assertEqual(english_spec.status_code, 200)
                self.assertEqual(kazakh_spec.status_code, 200)
                self.assertIn("Server API", english_spec.json()["info"]["description"])
                self.assertIn("серверлік API", kazakh_spec.json()["info"]["description"])
                self.assertEqual(requests.get(base + "/api/v1/openapi.json?lang=fr", timeout=3).status_code, 400)
                denied = requests.get(base + "/api/v1/listings", timeout=3)
                self.assertEqual(denied.status_code, 401)
                self.assertEqual(denied.json()["error"]["code"], "unauthorized")
                browser = requests.get(base + "/api/v1/listings", headers={**headers, "Origin": "https://example.com"}, timeout=3)
                self.assertEqual(browser.status_code, 403)
                listing_page = requests.get(base + "/api/v1/listings?limit=1", headers=headers, timeout=3)
                self.assertEqual(listing_page.status_code, 200)
                self.assertEqual(listing_page.json()["page"], {"total": 2, "limit": 1, "offset": 0, "next_offset": 1})
                filtered = requests.get(base + "/api/v1/listings?bounds=43.25,76.87,43.23,76.89", headers=headers, timeout=3)
                self.assertEqual(filtered.json()["page"]["total"], 1)
                self.assertEqual(filtered.json()["data"][0]["id"], items[0].id)
                detail = requests.get(base + f"/api/v1/listings/{items[0].id}", headers=headers, timeout=3)
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(len(detail.json()["data"]["history"]), 1)
                missing = requests.get(base + "/api/v1/listings/99999", headers=headers, timeout=3)
                self.assertEqual(missing.status_code, 404)
                runs = requests.get(base + "/api/v1/runs?limit=1", headers=headers, timeout=3)
                self.assertEqual(len(runs.json()["data"]), 1)
                self.assertNotIn("snapshot_dir", runs.json()["data"][0])
                run = requests.get(base + f"/api/v1/runs/{run_id}", headers=headers, timeout=3)
                self.assertEqual(run.json()["data"]["id"], run_id)
                disabled = requests.post(base + "/api/v1/collections", json={"url": URL}, headers=headers, timeout=3)
                self.assertEqual(disabled.status_code, 403)
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())

    def test_network_binding_requires_token(self):
        with self.assertRaisesRegex(ValueError, "api-token-file"):
            server_module.serve(port=8765, db_path="unused.sqlite3", default_url=URL,
                                enable_live=False, host="0.0.0.0")

    def test_container_ui_origin_must_point_to_loopback(self):
        with self.assertRaisesRegex(ValueError, "ui-origin"):
            server_module.serve(port=8765, db_path="unused.sqlite3", default_url=URL,
                                enable_live=False, host="0.0.0.0", api_token=TOKEN,
                                ui_origin="https://public.example:8765")

    def test_authenticated_collection_uses_the_existing_crawl_pipeline(self):
        class NoGeo:
            def __init__(self, *_args, **_kwargs):
                pass

            def enrich(self, page):
                return page, []

        source = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        page = replace(source, next_url=None)
        with TemporaryDirectory() as temporary:
            db = Path(temporary) / "test.sqlite3"
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                 patch.object(server_module, "GeoEnricher", NoGeo), \
                 patch.object(server_module, "crawl_pages", return_value=iter((page,))):
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": db, "default_url": URL,
                    "enable_live": True, "api_token": TOKEN,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.post(f"http://127.0.0.1:{port}/api/v1/collections",
                                                 json={"url": URL, "max_pages": 1},
                                                 headers={"Authorization": f"Bearer {TOKEN}"}, timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                thread.join(timeout=3)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["unique_ids"], 2)
            self.assertEqual(response.json()["pages"], 1)
            with ListingStore(db) as store:
                self.assertEqual(store.counts()["listings"], 2)
