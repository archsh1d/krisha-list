import csv
import io
import sqlite3
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
from krisha_list.parser import parse_listing_page
from krisha_list.storage import ListingStore


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class FiveRequestServer(ThreadingHTTPServer):
    def serve_forever(self):
        for _ in range(5):
            self.handle_request()


class OneRequestServer(ThreadingHTTPServer):
    def serve_forever(self):
        self.handle_request()


class CatalogApiTests(TestCase):
    def test_catalog_returns_json_when_sqlite_is_unavailable(self):
        with TemporaryDirectory() as temporary:
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with patch.object(server_module, "ThreadingHTTPServer", OneRequestServer), \
                    patch.object(server_module, "ListingStore", side_effect=sqlite3.OperationalError("database unavailable")):
                thread = Thread(target=server_module.serve, kwargs={
                    "port": port, "db_path": Path(temporary) / "catalog.sqlite3",
                    "default_url": URL, "enable_live": False,
                }, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        response = requests.get(f"http://127.0.0.1:{port}/api/catalog", timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                self.assertEqual(response.status_code, 500)
                self.assertIn("SQLite", response.json()["error"])
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())

    def test_catalog_export_import_and_browser_migration_use_sqlite(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "catalog.sqlite3"
            page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
            with ListingStore(db) as store:
                run_id = store.start_run("live", {"requested_url": URL, "max_pages": 1})
                store.upsert(page.listings, observed_at="2026-11-21T12:00:00+00:00", source_url=URL, run_id=run_id)
                store.finish_run(run_id, "limited", {"pages": 1, "unique_ids": 2,
                    "site_count": 3, "has_more": True, "with_coordinates": 0})
            with socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            with patch.object(server_module, "ThreadingHTTPServer", FiveRequestServer):
                thread = Thread(target=server_module.serve,
                    kwargs={"port": port, "db_path": db, "default_url": URL, "enable_live": False}, daemon=True)
                thread.start()
                for attempt in range(20):
                    try:
                        catalog = requests.get(base + "/api/catalog", timeout=3)
                        break
                    except requests.ConnectionError:
                        if attempt == 19:
                            raise
                        sleep(.03)
                self.assertEqual(catalog.status_code, 200)
                data = catalog.json()
                self.assertEqual(len(data["listings"]), 2)
                self.assertEqual(data["runs"][0]["status"], "limited")
                self.assertEqual(data["runs"][0]["request"]["max_pages"], 1)
                first_id = data["listings"][0]["id"]
                headers = {"Origin": base}
                exported = requests.post(base + "/api/export", json={"ids": [first_id]}, headers=headers, timeout=3)
                self.assertEqual(exported.status_code, 200)
                rows = list(csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["id"], str(first_id))
                self.assertEqual(rows[0]["price_changes"], "0")
                migrated = requests.post(base + "/api/migrate", json={"listings": [{
                    "id": "999", "title": "Дом · 3 комнаты", "category": "house", "price": 1000000,
                    "lastSeenAt": "2026-11-20T12:00:00+00:00", "history": [
                        {"price": 900000, "observedAt": "2026-11-19T12:00:00+00:00"},
                        {"price": 1000000, "observedAt": "2026-11-20T12:00:00+00:00"},
                    ],
                }]}, headers=headers, timeout=3)
                self.assertEqual(migrated.status_code, 200)
                self.assertEqual(migrated.json()["added"], 1)
                imported = requests.post(base + "/api/import-html", data=FIXTURE.read_bytes(),
                    headers={**headers, "Content-Type": "text/html"}, timeout=3)
                self.assertEqual(imported.status_code, 200)
                self.assertEqual(imported.json()["unique_ids"], 2)
                final = requests.get(base + "/api/catalog", timeout=3)
                self.assertEqual(final.status_code, 200)
                latest = final.json()
                self.assertEqual(len(latest["listings"]), 3)
                self.assertEqual(latest["runs"][0]["status"], "imported")
                self.assertEqual(latest["runs"][1]["kind"], "browser_import")
                migrated_row = next(row for row in latest["listings"] if row["id"] == 999)
                self.assertEqual(len(migrated_row["history"]), 2)
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())

    def test_replayed_snapshot_does_not_roll_back_newer_price(self):
        with TemporaryDirectory() as temporary:
            with ListingStore(Path(temporary) / "catalog.sqlite3") as store:
                item = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL).listings[0]
                store.upsert([item], observed_at="2026-11-21T12:00:00+00:00", source_url=URL)
                current = store.list_catalog()[0]
                older = {**item.as_dict(), "price_kzt": 1, "latitude": 43.24, "longitude": 76.88}
                store.merge_snapshot([older], observed_at="2026-11-20T12:00:00+00:00", source_url=URL)
                updated = store.list_catalog()[0]
                self.assertEqual(updated["price_kzt"], current["price_kzt"])
                self.assertEqual(updated["last_seen_at"], current["last_seen_at"])
                self.assertEqual(updated["latitude"], 43.24)
