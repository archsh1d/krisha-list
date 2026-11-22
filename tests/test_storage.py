from dataclasses import replace
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from krisha_list.parser import parse_listing_page
from krisha_list.storage import ListingStore


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class StorageTests(unittest.TestCase):
    def test_upsert_preserves_first_seen_and_records_price_changes(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        with TemporaryDirectory() as tmp:
            with ListingStore(Path(tmp) / "data" / "listings.sqlite3") as store:
                store.upsert(page.listings, observed_at="2026-11-13T12:00:00Z", source_url=URL)
                changed = replace(page.listings[0], price_kzt=43_000_000)
                store.upsert([changed], observed_at="2026-11-14T12:00:00Z", source_url=URL)
                store.upsert([changed], observed_at="2026-11-15T12:00:00Z", source_url=URL)
                self.assertEqual(store.counts(), {"listings": 2, "price_events": 3})
                row = store.connection.execute("SELECT * FROM listings WHERE id=123").fetchone()
                self.assertEqual(row["first_seen_at"], "2026-11-13T12:00:00Z")
                self.assertEqual(row["last_seen_at"], "2026-11-15T12:00:00Z")
                self.assertEqual(row["price_kzt"], 43_000_000)
                output = StringIO()
                self.assertEqual(store.export("price_history", "jsonl", output), 3)
                events = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual([e["price_kzt"] for e in events if e["listing_id"] == 123], [44_500_000, 43_000_000])

    def test_csv_export_has_one_row_per_listing(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        with TemporaryDirectory() as tmp:
            with ListingStore(Path(tmp) / "listings.sqlite3") as store:
                store.upsert(page.listings, observed_at="2026-11-13T12:00:00Z", source_url=URL)
                output = StringIO()
                self.assertEqual(store.export("listings", "csv", output), 2)
                self.assertIn("house_area_m2", output.getvalue().splitlines()[0])

    def test_importing_an_old_snapshot_does_not_roll_back_price_or_freshness(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        with TemporaryDirectory() as tmp:
            with ListingStore(Path(tmp) / "listings.sqlite3") as store:
                current = replace(page.listings[0], price_kzt=43_000_000)
                store.upsert([current], observed_at="2026-11-20T12:00:00Z", source_url=URL)
                store.merge_snapshot([page.listings[0].as_dict()],
                                     observed_at="2026-11-22T12:00:00Z", source_url=URL)
                row = store.connection.execute(
                    "SELECT price_kzt, last_seen_at FROM listings WHERE id=?", (current.id,),
                ).fetchone()
                self.assertEqual(tuple(row), (43_000_000, "2026-11-20T12:00:00Z"))
                self.assertEqual(store.counts()["price_events"], 1)
