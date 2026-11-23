from pathlib import Path
import unittest

import requests
from unittest.mock import patch

from krisha_list import client as client_module
from krisha_list.client import CrawlError, PacedSession, SourceHTTPError, crawl_pages


URL = "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/"
FIXTURE = Path(__file__).parent / "fixtures" / "list_page.html"


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requested = []

    def get(self, url, timeout, allow_redirects):
        assert allow_redirects is False
        self.requested.append(url)
        return next(self.responses)


def response(url, html, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = url
    result.headers["Content-Type"] = "text/html; charset=utf-8"
    result._content = html.encode("utf-8")
    return result


class ClientTests(unittest.TestCase):
    def test_paced_session_spaces_requests_even_after_a_response(self):
        clock = [0.0]
        sleeps = []

        def sleep_for(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        def get_response(_session, _url, **_kwargs):
            clock[0] += 1
            return object()

        with patch.object(client_module.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(client_module.time, "sleep", side_effect=sleep_for), \
             patch.object(requests.Session, "get", get_response):
            with PacedSession(interval=3) as session:
                session.get(URL)
                session.get(URL)
        self.assertEqual(sleeps, [3.0])

    def test_paced_session_slows_long_collections(self):
        clock = [0.0]
        sleeps = []

        def sleep_for(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        with patch.object(client_module.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(client_module.time, "sleep", side_effect=sleep_for), \
             patch.object(requests.Session, "get", return_value=object()):
            with PacedSession(interval=3) as session:
                for _ in range(20):
                    session.get(URL)
        self.assertEqual(sleeps[:5], [3] * 5)
        self.assertEqual(sleeps[5:11], [6] * 6)
        self.assertEqual(sleeps[11:17], [9] * 6)
        self.assertEqual(sleeps[17:], [12] * 2)

    def test_follows_next_page_without_collecting_sidebar(self):
        first_html = FIXTURE.read_text(encoding="utf-8")
        second_html = first_html.replace(
            '<a class="paginator__btn--next" href="?page=2">Дальше</a>', ""
        )
        session = FakeSession(
            [response(URL, first_html), response(URL + "?page=2", second_html)]
        )
        snapshots = []
        pages = list(crawl_pages(URL, session=session, delay=0, on_html=lambda n, u, h: snapshots.append((n, u, h))))
        self.assertEqual(len(pages), 2)
        self.assertEqual(session.requested, [URL, URL + "?page=2"])
        self.assertEqual([item.id for item in pages[0].listings], [123, 456])
        self.assertEqual([number for number, _, _ in snapshots], [1, 2])
        self.assertIn('data-id="123"', snapshots[0][2])

    def test_stops_on_access_limit(self):
        session = FakeSession([response(URL, "<html></html>", status=403)])
        with self.assertRaises(CrawlError):
            list(crawl_pages(URL, session=session, delay=0))

    def test_redirect_is_not_followed(self):
        session = FakeSession([response(URL, "", status=302)])
        with self.assertRaisesRegex(CrawlError, "перенаправил"):
            list(crawl_pages(URL, session=session, delay=0))
        self.assertEqual(session.requested, [URL])

    def test_468_reports_source_status_without_long_url(self):
        session = FakeSession([response(URL, "<html></html>", status=468)])
        with self.assertRaises(SourceHTTPError) as raised:
            list(crawl_pages(URL, session=session, delay=0))
        self.assertEqual(session.requested, [URL])
        self.assertEqual(raised.exception.status_code, 468)
        self.assertEqual(raised.exception.url, URL)
        self.assertEqual(raised.exception.response_body, b"<html></html>")
        self.assertIn("HTTP 468", str(raised.exception))
        self.assertNotIn(URL, str(raised.exception))

    def test_identifies_safeline_challenge(self):
        session = FakeSession([response(URL, '<link href="/.safeline/static/favicon.png">', status=468)])
        with self.assertRaises(SourceHTTPError) as raised:
            list(crawl_pages(URL, session=session, delay=0))
        self.assertTrue(raised.exception.is_challenge)
        self.assertIn("страницу проверки доступа", str(raised.exception))

    def test_stops_on_challenge_returned_with_http_200(self):
        session = FakeSession([response(URL, '<link href="/.safeline/static/favicon.png">')])
        with self.assertRaises(SourceHTTPError) as raised:
            list(crawl_pages(URL, session=session, delay=0))
        self.assertEqual(raised.exception.status_code, 200)
        self.assertTrue(raised.exception.is_challenge)

    def test_unlimited_mode_follows_more_than_ten_pages(self):
        template = FIXTURE.read_text(encoding="utf-8")
        responses = []
        for number in range(1, 12):
            html = template.replace("Найдено 3 объявления", "Найдено 22 объявления")
            html = html.replace("123", str(1000 + number)).replace("456", str(2000 + number))
            if number == 11:
                html = html.replace('<a class="paginator__btn--next" href="?page=2">Дальше</a>', "")
            else:
                html = html.replace('href="?page=2"', f'href="?page={number + 1}"')
            url = URL if number == 1 else URL + f"?page={number}"
            responses.append(response(url, html))
        session = FakeSession(responses)
        pages = list(crawl_pages(URL, session=session, max_pages=0, delay=0))
        self.assertEqual(len(pages), 11)
        self.assertEqual(len({item.id for page in pages for item in page.listings}), 22)
        self.assertIsNone(pages[-1].next_url)
