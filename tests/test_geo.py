import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

from krisha_list.client import SourceHTTPError
from krisha_list.geo import GeoEnricher, GeoFetchError, attach_geo, fetch_page_geo, map_list_url, parse_map_list, snapshot_geo_points
from krisha_list.parser import parse_listing_page
from krisha_list.storage import ListingStore


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
APARTMENT_URL = "https://krisha.kz/prodazha/kvartiry/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def get(self, url, *, timeout, headers, allow_redirects):
        assert allow_redirects is False
        self.requests.append((url, headers))
        return self.response


class PageSession:
    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def get(self, url, *, timeout, headers, allow_redirects):
        assert allow_redirects is False
        self.requested.append(url)
        return self.responses[url]


def json_response(url, payload, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = url
    result.headers["Content-Type"] = "application/json"
    result._content = json.dumps(payload).encode("utf-8")
    return result


class GeoTests(unittest.TestCase):
    def test_map_access_refusal_stops_collection(self):
        url = map_list_url(URL)
        session = FakeSession(json_response(url, {}, status=468))
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        with self.assertRaises(SourceHTTPError) as raised:
            GeoEnricher(session).enrich(page)
        self.assertEqual(raised.exception.status_code, 468)
        self.assertEqual(len(session.requests), 1)

    def test_map_html_challenge_stops_collection(self):
        url = map_list_url(URL)
        blocked = requests.Response()
        blocked.status_code = 200
        blocked.url = url
        blocked.headers["Content-Type"] = "text/html"
        blocked._content = b'<link href="/.safeline/static/favicon.png">'
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        with self.assertRaises(SourceHTTPError) as raised:
            GeoEnricher(FakeSession(blocked)).enrich(page)
        self.assertTrue(raised.exception.is_challenge)

    def test_map_redirect_is_not_followed(self):
        url = map_list_url(URL)
        with self.assertRaisesRegex(GeoFetchError, "перенаправила"):
            fetch_page_geo(URL, session=FakeSession(json_response(url, {}, status=302)))

    def test_map_page_matches_by_id_and_keeps_missing_location_empty(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        url = map_list_url(URL)
        payload = {"adverts": {
            "123": {"map": {"lat": 43.264637, "lon": 76.878774, "zoom": 16, "type": None}},
            "999": {"map": {"lat": 43.2, "lon": 76.8}},
        }}
        session = FakeSession(json_response(url, payload))
        points = fetch_page_geo(URL, session=session)
        enriched = attach_geo(page, points)
        self.assertEqual(session.requests[0][0], url)
        self.assertEqual(enriched.listings[0].latitude, 43.264637)
        self.assertEqual(enriched.listings[0].geo_source, "krisha_map_list")
        self.assertIsNone(enriched.listings[1].latitude)

    def test_preserves_search_filters_and_rejects_invalid_coordinates(self):
        url = map_list_url(URL + "?rooms[]=3&page=2")
        self.assertIn("rooms%5B%5D=3&page=2", url)
        self.assertIn("/a/ajax-map-list/map/prodazha/kvartiry/", map_list_url(APARTMENT_URL))
        points = parse_map_list({"adverts": {
            "1": {"map": {"lat": 91, "lon": 76}},
            "2": {"map": {"lat": 0, "lon": 0}},
            "3": {"map": {"lat": 43.25, "lon": 76.9}},
        }})
        self.assertEqual(list(points), [3])
        with self.assertRaises(GeoFetchError):
            parse_map_list({"html": "not map data"})

    def test_existing_database_gains_columns_and_keeps_known_coordinates(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.sqlite3"
            connection = sqlite3.connect(db)
            connection.execute("""CREATE TABLE listings (
                id INTEGER PRIMARY KEY, url TEXT NOT NULL, title TEXT NOT NULL,
                object_type TEXT, rooms INTEGER, house_area_m2 REAL, plot_area_sot REAL,
                price_kzt INTEGER, district TEXT, address TEXT, description_preview TEXT,
                seller_type TEXT, city TEXT, posted_label TEXT, floors INTEGER,
                year_built INTEGER, page_number INTEGER NOT NULL, source_url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL)""")
            connection.commit()
            connection.close()
            with ListingStore(db) as store:
                enriched = attach_geo(page, {123: parse_map_list({"adverts": {"123": {
                    "map": {"lat": 43.264637, "lon": 76.878774}
                }}})[123]})
                store.upsert(enriched.listings, observed_at="2026-11-14T00:00:00Z", source_url=URL)
                store.upsert(page.listings, observed_at="2026-11-15T00:00:00Z", source_url=URL)
                row = store.connection.execute("SELECT latitude, longitude, geo_source FROM listings WHERE id=123").fetchone()
                self.assertEqual(tuple(row), (43.264637, 76.878774, "krisha_map_list"))

    def test_next_map_page_fills_rank_shift_and_is_cached(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        second_url = URL + "?page=2"
        first_map = map_list_url(URL)
        second_map = map_list_url(second_url)
        session = PageSession({
            first_map: json_response(first_map, {"adverts": {
                "123": {"map": {"lat": 43.26, "lon": 76.87}},
            }}),
            second_map: json_response(second_map, {"adverts": {
                "456": {"map": {"lat": 43.25, "lon": 76.88}},
            }}),
        })
        enricher = GeoEnricher(session)
        enriched, errors = enricher.enrich(page)
        self.assertEqual(errors, [])
        self.assertEqual([item.latitude for item in enriched.listings], [43.26, 43.25])
        second_page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), second_url)
        enricher.enrich(second_page)
        self.assertEqual(session.requested, [first_map, second_map])

    def test_recent_snapshot_reuses_all_known_points_without_map_request(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        records = [
            {"id": item.id, "latitude": 43.25, "longitude": 76.88,
             "geo_source": "krisha_map_list", "geo_zoom": 16, "geo_type": None}
            for item in page.listings
        ]
        session = PageSession({})
        enricher = GeoEnricher(session, known_points=snapshot_geo_points(records))
        enriched, errors = enricher.enrich(page)
        self.assertEqual(errors, [])
        self.assertEqual(session.requested, [])
        self.assertEqual(enricher.reused_count, len(page.listings))
        self.assertTrue(all(item.geo_source == "krisha_map_list_cached" for item in enriched.listings))

    def test_new_map_response_supersedes_snapshot_and_access_refusal_still_stops(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        prior = snapshot_geo_points([{
            "id": 123, "latitude": 43.2, "longitude": 76.8,
            "geo_source": "krisha_map_list",
        }])
        url = map_list_url(URL)
        current = json_response(url, {"adverts": {
            "123": {"map": {"lat": 43.26, "lon": 76.87}},
            "456": {"map": {"lat": 43.25, "lon": 76.88}},
        }})
        enricher = GeoEnricher(FakeSession(current), known_points=prior)
        enriched, _ = enricher.enrich(page)
        self.assertEqual(enriched.listings[0].latitude, 43.26)
        self.assertEqual(enriched.listings[0].geo_source, "krisha_map_list")
        self.assertEqual(enricher.reused_count, 0)
        with self.assertRaises(SourceHTTPError):
            GeoEnricher(FakeSession(json_response(url, {}, status=468)), known_points=prior).enrich(page)

    def test_map_format_error_retains_known_snapshot_positions(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        prior = snapshot_geo_points([{
            "id": 123, "latitude": 43.2, "longitude": 76.8,
            "geo_source": "krisha_map_list",
        }])
        enricher = GeoEnricher(FakeSession(json_response(map_list_url(URL), {"wrong": True})),
                               known_points=prior)
        enriched, errors = enricher.enrich(page)
        self.assertEqual(len(errors), 1)
        self.assertEqual(enriched.listings[0].latitude, 43.2)
        self.assertIsNone(enriched.listings[1].latitude)
        self.assertEqual(enricher.reused_count, 1)
