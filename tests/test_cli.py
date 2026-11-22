from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import unittest

from krisha_list.cli import main


FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"
APARTMENT_FIXTURE = Path(__file__).parent / "fixtures" / "apartment_page.html"
APARTMENT_URL = "https://krisha.kz/prodazha/kvartiry/almaty-almalinskij/"


class CliTests(unittest.TestCase):
    def test_parse_file_stats_and_export(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "listings.sqlite3"
            output = Path(tmp) / "listings.csv"
            with redirect_stdout(StringIO()) as captured:
                self.assertEqual(main(["parse-file", str(FIXTURE), "--db", str(db)]), 0)
                self.assertEqual(main(["stats", "--db", str(db)]), 0)
                self.assertEqual(
                    main(["export", "--db", str(db), "--output", str(output)]), 0
                )
            self.assertIn('"saved": 2', captured.getvalue())
            self.assertIn('"price_events": 2', captured.getvalue())
            with output.open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual([int(row["id"]) for row in rows], [123, 456])

    def test_apartment_import_and_category_export(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "listings.sqlite3"
            output = Path(tmp) / "apartments.csv"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["parse-file", str(FIXTURE), "--db", str(db)]), 0)
                self.assertEqual(main(["parse-file", str(APARTMENT_FIXTURE), "--url", APARTMENT_URL, "--db", str(db)]), 0)
                self.assertEqual(main(["export", "--db", str(db), "--category", "apartment", "--output", str(output)]), 0)
            with output.open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["category"] for row in rows}, {"apartment"})
            self.assertEqual({row["apartment_area_m2"] for row in rows}, {"65.2", "73.3"})
