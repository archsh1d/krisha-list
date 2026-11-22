from __future__ import annotations

import time
import re
from collections.abc import Callable, Iterator
from threading import Lock
from urllib.parse import urlsplit

import requests

from .model import ParsedPage
from .parser import parse_listing_page
from .categories import category_from_url


class CrawlError(RuntimeError):
    """A search page could not be retrieved safely or completely."""


class PacedSession(requests.Session):
    """Leave a quiet interval after every response, including map responses."""

    def __init__(self, interval: float = 3.0):
        super().__init__()
        if interval < 0:
            raise ValueError("Интервал запросов не может быть отрицательным")
        self.interval = interval
        self._next_request_at = 0.0
        self._request_lock = Lock()
        self.headers.update({
            "User-Agent": "krisha-list/0.1 (authorized research collector)",
            "Accept": "text/html,application/xhtml+xml",
        })

    def get(self, url, **kwargs):
        with self._request_lock:
            remaining = self._next_request_at - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            try:
                return super().get(url, **kwargs)
            finally:
                self._next_request_at = time.monotonic() + self.interval


class SourceHTTPError(CrawlError):
    """Krisha returned a non-success HTTP status for a list page."""

    def __init__(self, status_code: int, url: str, response: requests.Response | None = None):
        self.status_code = status_code
        self.url = url
        self.diagnostics = {}
        self.response_body = b""
        self.is_challenge = False
        if response is not None:
            self.response_body = response.content[:1_000_000]
            body_text = response.text
            self.is_challenge = "/.safeline/" in body_text or 'id="slg-title"' in body_text
            title = re.search(r"<title[^>]*>(.*?)</title>", body_text, re.I | re.S)
            self.diagnostics = {
                "content_type": response.headers.get("Content-Type"),
                "server": response.headers.get("Server"),
                "retry_after": response.headers.get("Retry-After"),
                "body_bytes": len(response.content),
                "title": re.sub(r"\s+", " ", title.group(1)).strip()[:160] if title else None,
                "card_markers": body_text.count('data-id='),
                "cookie_names": sorted(response.cookies.keys()),
                "challenge": self.is_challenge,
            }
        if self.is_challenge:
            message = (
                f"Krisha.kz вернул страницу проверки доступа (HTTP {status_code}). "
                "Новая выдача не получена. Для стабильного автоматического сбора "
                "нужна настройка доступа со стороны Kolesa."
            )
        elif status_code in (403, 429, 468):
            message = (
                f"Krisha.kz отклонил запрос выдачи (HTTP {status_code}). "
                "Сбор остановлен. Попробуйте позже; если ошибка повторяется, "
                "уточните у Kolesa технические условия доступа."
            )
        else:
            message = f"Krisha.kz вернул HTTP {status_code}; сбор остановлен."
        super().__init__(message)


def validate_search_url(url: str) -> None:
    category_from_url(url)


def crawl_pages(
    start_url: str,
    *,
    max_pages: int = 0,
    delay: float = 3.0,
    timeout: float = 20.0,
    session: requests.Session | None = None,
    on_html: Callable[[int, str, str], None] | None = None,
) -> Iterator[ParsedPage]:
    """Yield search pages in site pagination order; zero max_pages means all."""
    validate_search_url(start_url)
    if max_pages < 0 or delay < 0 or timeout <= 0:
        raise ValueError("max_pages и delay должны быть неотрицательными, timeout — положительным")

    own_session = session is None
    active_session = session or requests.Session()
    if own_session:
        active_session.headers.update(
            {
                "User-Agent": "krisha-list/0.1 (authorized research collector)",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
    page_url: str | None = start_url
    seen_pages: set[str] = set()
    expected_path = urlsplit(start_url).path
    fetched = 0
    try:
        while page_url and (max_pages == 0 or fetched < max_pages):
            if page_url in seen_pages:
                raise CrawlError("Пагинация зациклилась")
            seen_pages.add(page_url)
            try:
                response = active_session.get(page_url, timeout=timeout, allow_redirects=False)
            except requests.RequestException as error:
                raise CrawlError(f"Не удалось получить страницу выдачи: {error}") from error
            if 300 <= response.status_code < 400:
                raise CrawlError("Источник перенаправил запрос выдачи; переход не выполнен")
            if response.status_code != 200:
                raise SourceHTTPError(response.status_code, page_url, response)
            if (
                urlsplit(response.url).scheme != "https"
                or urlsplit(response.url).hostname not in {"krisha.kz", "www.krisha.kz"}
            ):
                raise CrawlError("Ответ перенаправлен на другой сайт")
            if urlsplit(response.url).path != expected_path:
                raise CrawlError("Ответ перенаправлен на другую страницу")
            if "html" not in response.headers.get("Content-Type", "text/html").lower():
                raise CrawlError("Сайт вернул не HTML")

            html = response.content.decode("utf-8", errors="replace")
            if "/.safeline/" in html or 'id="slg-title"' in html:
                raise SourceHTTPError(response.status_code, page_url, response)
            if on_html:
                on_html(fetched + 1, response.url, html)
            page = parse_listing_page(html, response.url)
            fetched += 1
            yield page
            page_url = page.next_url
            if page_url:
                validate_search_url(page_url)
                if urlsplit(page_url).path != expected_path:
                    raise CrawlError("Пагинация вышла за пределы исходного списка")
                if max_pages == 0 or fetched < max_pages:
                    time.sleep(delay)
    finally:
        if own_session:
            active_session.close()
