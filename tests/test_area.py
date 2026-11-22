import csv
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from krisha_list.area import bounds_from_url, filter_page, parse_bounds, parse_polygon, with_bounds
from krisha_list.geo import GeoPoint, attach_geo
from krisha_list.parser import parse_listing_page
from krisha_list.storage import ListingStore


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class AreaTests(unittest.TestCase):
    def test_bounds_url_preserves_filters_and_resets_pagination(self):
        bounds = parse_bounds("43.255,76.87,43.24,76.91")
        url = with_bounds(URL + "?rooms[]=3&page=8", bounds)
        self.assertIn("rooms%5B%5D=3", url)
        self.assertIn("bounds=43.255%2C76.87%2C43.24%2C76.91", url)
        self.assertNotIn("page=8", url)
        self.assertEqual(bounds_from_url(url), bounds)

    def test_rejects_invalid_rectangle(self):
        for value in ("43.24,76.87,43.255,76.91", "43.255,76.91,43.24,76.87", "nan,76.87,43.24,76.91", "43,76,42"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_bounds(value)

    def test_collection_and_export_include_only_verified_inside_points(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        bounds = parse_bounds("43.255,76.87,43.24,76.91")
        inside = GeoPoint(43.25, 76.88, 16, None)
        outside = GeoPoint(43.26, 76.88, 16, None)
        with_one_point = attach_geo(page, {123: inside})
        filtered, missing, outside_count = filter_page(with_one_point, bounds)
        self.assertEqual([item.id for item in filtered.listings], [123])
        self.assertEqual((missing, outside_count), (1, 0))

        with_two_points = attach_geo(page, {123: inside, 456: outside})
        filtered, missing, outside_count = filter_page(with_two_points, bounds)
        self.assertEqual([item.id for item in filtered.listings], [123])
        self.assertEqual((missing, outside_count), (0, 1))

        with TemporaryDirectory() as tmp, ListingStore(Path(tmp) / "area.sqlite3") as store:
            store.upsert(with_two_points.listings, observed_at="2026-11-18T00:00:00Z", source_url=URL)
            output = StringIO()
            self.assertEqual(store.export("listings", "csv", output, bounds=bounds), 1)
            rows = list(csv.DictReader(StringIO(output.getvalue())))
            self.assertEqual([int(row["id"]) for row in rows], [123])

    def test_polygon_uses_bbox_for_search_and_shape_for_filtering(self):
        polygon = parse_polygon([[43.24, 76.87], [43.25, 76.87], [43.24, 76.89]])
        self.assertEqual(polygon.bounds.as_query(), "43.25,76.87,43.24,76.89")
        self.assertTrue(polygon.contains(43.242, 76.875))
        self.assertTrue(polygon.contains(43.24, 76.88))
        self.assertFalse(polygon.contains(43.248, 76.885))
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        geolocated = attach_geo(page, {
            123: GeoPoint(43.242, 76.875, 16, None),
            456: GeoPoint(43.248, 76.885, 16, None),
        })
        filtered, missing, outside = filter_page(geolocated, polygon.bounds, polygon)
        self.assertEqual([item.id for item in filtered.listings], [123])
        self.assertEqual((missing, outside), (0, 1))

    def test_polygon_rejects_self_intersection_and_invalid_coordinates(self):
        for vertices in (
            [[43.24, 76.87], [43.25, 76.89], [43.25, 76.87], [43.24, 76.89]],
            [[43.24, 76.87], [43.25, 76.89], [43.24, 76.87]],
            [[43.24, 76.87], [43.25, 76.89], [True, 76.88]],
        ):
            with self.subTest(vertices=vertices), self.assertRaises(ValueError):
                parse_polygon(vertices)
