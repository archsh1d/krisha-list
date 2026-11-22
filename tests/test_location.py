from dataclasses import replace
from pathlib import Path
from unittest import TestCase

from krisha_list.location import filter_page_location, normalize_place
from krisha_list.parser import parse_listing_page


BASE_URL = "https://krisha.kz/prodazha/doma-dachi/almaty/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class LocationTests(TestCase):
    def test_normalization_handles_labels_and_punctuation(self):
        self.assertEqual(normalize_place("мкр Тастак-2"), "тастак 2")
        self.assertEqual(normalize_place("Алмалинский р-н"), "алмалинский")
        self.assertEqual(normalize_place("Микрорайон Ёжиков"), "ежиков")

    def test_filter_matches_district_or_address_with_number_boundary(self):
        source = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), BASE_URL)
        page = replace(source, listings=(
            replace(source.listings[0], district="Алмалинский р-н", address="мкр Тастак-2, дом 6"),
            replace(source.listings[1], district="Ауэзовский район", address="мкр Тастак-20, дом 8"),
        ))
        filtered, excluded = filter_page_location(page, "Тастак-2")
        self.assertEqual([item.id for item in filtered.listings], [source.listings[0].id])
        self.assertEqual(excluded, 1)
        district, excluded = filter_page_location(page, "Алмалинский р-н")
        self.assertEqual([item.id for item in district.listings], [source.listings[0].id])
        self.assertEqual(excluded, 1)
