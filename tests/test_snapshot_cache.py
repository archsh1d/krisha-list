from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from krisha_list.area import Bounds, with_bounds
from krisha_list.snapshot_cache import find_last_complete, request_identity, save_success


BASE_URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class SnapshotCacheTests(unittest.TestCase):
    def test_replays_only_complete_matching_snapshot_and_filters_area(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "20261121T125429000000Z"
            run.mkdir()
            bounds = Bounds(43.245, 76.87, 43.23, 76.89)
            url = with_bounds(BASE_URL, bounds)
            (run / "page-001.url.txt").write_text(url + "\n", encoding="utf-8")
            (run / "page-001.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            (run / "map-page-001.json").write_text(json.dumps({"adverts": {
                "123": {"map": {"lat": 43.24, "lon": 76.88}},
                "456": {"map": {"lat": 43.25, "lon": 76.90}},
            }}), encoding="utf-8")
            request = request_identity(url, 1, bounds, None)
            cached = find_last_complete(root, request, bounds, None)
            self.assertIsNotNone(cached)
            self.assertTrue(cached["cached"])
            self.assertEqual(cached["unique_ids"], 1)
            self.assertEqual(cached["listings"][0]["id"], 123)
            self.assertEqual(cached["with_coordinates"], 1)
            self.assertEqual(cached["excluded_outside_area"], 1)
            self.assertIsNone(find_last_complete(root, request_identity(url, 0, bounds, None), bounds, None))
            (run / "source-error.json").write_text("{}", encoding="utf-8")
            self.assertIsNone(find_last_complete(root, request, bounds, None))

    def test_saved_result_requires_same_parameters(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "20261121T125429000000Z"
            run.mkdir()
            request = request_identity(BASE_URL, 1, None, None)
            save_success(run, request, {"pages": 1, "listings": [{"id": 123}]})
            self.assertEqual(find_last_complete(root, request, None, None)["listings"], [{"id": 123}])
            self.assertIsNone(find_last_complete(root, request_identity(BASE_URL, 10, None, None), None, None))

    def test_replay_filters_by_named_location(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "20261121T125429000000Z"
            run.mkdir()
            (run / "page-001.url.txt").write_text(BASE_URL + "\n", encoding="utf-8")
            (run / "page-001.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            request = request_identity(BASE_URL, 1, None, None, "Алмалинский р-н")
            cached = find_last_complete(root, request, None, None)
            self.assertIsNotNone(cached)
            self.assertEqual(cached["unique_ids"], 2)
            self.assertEqual(cached["excluded_outside_location"], 0)
            missing = find_last_complete(root, request_identity(BASE_URL, 1, None, None, "Медеуский"), None, None)
            self.assertEqual(missing["unique_ids"], 0)
            self.assertEqual(missing["excluded_outside_location"], 2)


if __name__ == "__main__":
    unittest.main()
