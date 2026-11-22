from pathlib import Path
import unittest

from krisha_list.model import PageFormatError
from krisha_list.parser import parse_listing_page


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"
APARTMENT_URL = "https://krisha.kz/prodazha/kvartiry/almaty-almalinskij/"
APARTMENT_FIXTURE = Path(__file__).parent / "fixtures" / "apartment_page.html"


class ParserTests(unittest.TestCase):
    def test_main_list_and_fields(self):
        page = parse_listing_page(FIXTURE.read_text(encoding="utf-8"), URL)
        self.assertEqual(page.total_found, 3)
        self.assertEqual(len(page.listings), 2)
        self.assertEqual([item.id for item in page.listings], [123, 456])
        self.assertEqual(page.next_url, URL + "?page=2")
        house = page.listings[0]
        self.assertEqual(house.url, "https://krisha.kz/a/show/123")
        self.assertEqual(house.object_type, "Отдельный дом")
        self.assertEqual(house.rooms, 6)
        self.assertEqual(house.house_area_m2, 160.3)
        self.assertEqual(house.plot_area_sot, 2.4)
        self.assertEqual(house.price_kzt, 44_500_000)
        self.assertEqual(house.district, "Алмалинский р-н")
        self.assertEqual(house.address, "Бруно 6А")
        self.assertEqual(house.seller_type, "Хозяин недвижимости")
        self.assertEqual(house.floors, 2)
        self.assertEqual(house.year_built, 1972)
        self.assertEqual(house.posted_label, "13 нояб.")
        self.assertIsNone(page.listings[1].plot_area_sot)

    def test_page_number_and_absent_next(self):
        html = FIXTURE.read_text(encoding="utf-8").replace(
            '<a class="paginator__btn--next" href="?page=2">Дальше</a>', ""
        )
        page = parse_listing_page(html, URL + "?page=2")
        self.assertEqual(page.listings[0].page_number, 2)
        self.assertIsNone(page.next_url)

    def test_challenge_or_changed_layout_is_not_silent_empty_result(self):
        with self.assertRaises(PageFormatError):
            parse_listing_page("<html><h1>Verification required</h1></html>", URL)
        with self.assertRaises(PageFormatError):
            parse_listing_page('<section class="a-search-list"></section>', URL)

    def test_empty_search(self):
        page = parse_listing_page('<div class="a-search-empty">Ничего не найдено</div>', URL)
        self.assertEqual(page.listings, ())
        self.assertEqual(page.total_found, 0)

    def test_apartments_have_separate_area_and_floor_fields(self):
        page = parse_listing_page(APARTMENT_FIXTURE.read_text(encoding="utf-8"), APARTMENT_URL)
        self.assertEqual(page.total_found, 5843)
        self.assertEqual([item.id for item in page.listings], [1015454164, 1015264902])
        self.assertEqual(page.next_url, APARTMENT_URL + "?page=2")
        apartment = page.listings[0]
        self.assertEqual(apartment.category, "apartment")
        self.assertEqual(apartment.rooms, 3)
        self.assertEqual(apartment.apartment_area_m2, 73.3)
        self.assertIsNone(apartment.house_area_m2)
        self.assertEqual((apartment.floor, apartment.building_floors), (10, 13))
        self.assertEqual(apartment.residential_complex, "Lamiya")
        self.assertEqual(apartment.year_built, 2021)
