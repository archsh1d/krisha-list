from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .client import CrawlError, PacedSession, crawl_pages, validate_search_url
from .area import bounds_from_url, filter_page, parse_bounds, with_bounds
from .categories import DEFAULT_URLS
from .geo import GeoEnricher, page_number_from_url
from .model import PageFormatError
from .parser import parse_listing_page
from .storage import ListingStore

DEFAULT_URL = DEFAULT_URLS["house"]
DEFAULT_DB = "data/krisha.sqlite3"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="krisha-list", description="Сбор HTML-списков продажи домов, дач и квартир")
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Обойти страницы списка при наличии разрешения владельца сайта")
    collect.add_argument("--url", default=DEFAULT_URL)
    collect.add_argument("--db", default=DEFAULT_DB)
    collect.add_argument("--max-pages", type=int, default=0, help="0 = все страницы")
    collect.add_argument("--delay", type=float, default=3.0, help="Пауза между всеми HTTP-запросами, секунды")
    collect.add_argument("--timeout", type=float, default=20.0)
    collect.add_argument("--snapshot-dir", type=Path, help="Сохранить HTML каждой полученной страницы")
    collect.add_argument("--no-geo", action="store_true", help="Не запрашивать координаты из списка карты")
    collect.add_argument("--bounds", help="Прямоугольник: север,запад,юг,восток (широта/долгота)")

    offline = sub.add_parser("parse-file", help="Разобрать локально сохранённую HTML-страницу")
    offline.add_argument("html_file", type=Path)
    offline.add_argument("--url", default=DEFAULT_URL, help="Адрес, которому соответствует файл")
    offline.add_argument("--db", default=DEFAULT_DB)

    export = sub.add_parser("export", help="Выгрузить базу в CSV или JSONL")
    export.add_argument("--db", default=DEFAULT_DB)
    export.add_argument("--table", choices=("listings", "price_history"), default="listings")
    export.add_argument("--category", choices=("house", "apartment"), help="Выгрузить только выбранную категорию объявлений")
    export.add_argument("--bounds", help="Выгрузить объекты внутри прямоугольника: север,запад,юг,восток")
    export.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    export.add_argument("--output", type=Path, required=True)

    stats = sub.add_parser("stats", help="Показать число объектов и изменений цены")
    stats.add_argument("--db", default=DEFAULT_DB)

    web = sub.add_parser("serve", help="Открыть локальный веб-интерфейс")
    web.add_argument("--db", default=DEFAULT_DB)
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--host", default="127.0.0.1", help="IPv4-адрес; сетевой доступ требует API-токен")
    web.add_argument("--api-token-file", type=Path, help="Файл с Bearer-токеном для /api/v1")
    web.add_argument("--ui-origin", help="Локальный адрес UI за Docker-перенаправлением порта")
    web.add_argument("--enable-live", action="store_true", help="Разрешить сбор через локальную кнопку")
    return parser


def _run(args: argparse.Namespace) -> None:
    if args.command == "collect":
        validate_search_url(args.url)
        bounds = parse_bounds(args.bounds) if args.bounds else bounds_from_url(args.url)
        if bounds and args.no_geo:
            raise ValueError("Для сбора по области нужны координаты карты; уберите --no-geo")
        search_url = with_bounds(args.url, bounds) if args.bounds else args.url
        if args.snapshot_dir:
            args.snapshot_dir.mkdir(parents=True, exist_ok=True)

        def save_snapshot(number: int, page_url: str, html: str) -> None:
            if args.snapshot_dir:
                stem = f"page-{number:03d}"
                (args.snapshot_dir / f"{stem}.html").write_text(html, encoding="utf-8")
                (args.snapshot_dir / f"{stem}.url.txt").write_text(page_url + "\n", encoding="utf-8")

        seen_ids: set[int] = set()
        pages = 0
        expected = None
        geo_ids: set[int] = set()
        geo_errors: list[str] = []
        without_coordinates = outside_bounds = 0
        has_more = False
        with ListingStore(args.db) as store, PacedSession(interval=args.delay) as source_session:
            run_id = store.start_run("cli_collect", {"requested_url": args.url, "search_url": search_url,
                "max_pages": args.max_pages, "bounds": bounds.as_query() if bounds else None},
                str(args.snapshot_dir) if args.snapshot_dir else None)
            geo_enricher = GeoEnricher(
                source_session, timeout=args.timeout,
                on_json=(lambda source, raw: (args.snapshot_dir / f"map-page-{page_number_from_url(source):03d}.json").write_text(raw, encoding="utf-8"))
                if args.snapshot_dir else None,
            )
            try:
                for page in crawl_pages(
                    search_url, max_pages=args.max_pages, delay=0, timeout=args.timeout,
                    session=source_session,
                    on_html=save_snapshot if args.snapshot_dir else None,
                ):
                    has_more = page.next_url is not None
                    if not args.no_geo:
                        page, errors = geo_enricher.enrich(page)
                        geo_errors.extend(f"Страница {pages + 1}: {error}" for error in errors)
                        for error in errors:
                            print(f"Координаты, страница {pages + 1}: {error}", file=sys.stderr)
                    if bounds:
                        page, missing, outside = filter_page(page, bounds)
                        without_coordinates += missing
                        outside_bounds += outside
                    store.upsert(page.listings, observed_at=_timestamp(), source_url=search_url, run_id=run_id)
                    seen_ids.update(item.id for item in page.listings)
                    geo_ids.update(item.id for item in page.listings if item.latitude is not None)
                    pages += 1
                    expected = page.total_found if page.total_found is not None else expected
                    print(f"Страница {pages}: {len(page.listings)} карточек", file=sys.stderr)
            except Exception as error:
                store.finish_run(run_id, "partial" if pages else "blocked", {"pages": pages,
                    "unique_ids": len(seen_ids), "site_count": expected, "has_more": has_more,
                    "with_coordinates": len(geo_ids), "excluded_without_coordinates": without_coordinates,
                    "excluded_outside_area": outside_bounds}, error=str(error),
                    source_status=getattr(error, "status_code", None))
                raise
            summary = {"pages": pages, "unique_ids": len(seen_ids), "site_count": expected,
                       "with_coordinates": len(geo_ids), "geo_errors": geo_errors,
                       "has_more": has_more, "run_id": run_id,
                       "bounds": bounds.as_query() if bounds else None,
                       "excluded_without_coordinates": without_coordinates,
                       "excluded_outside_bounds": outside_bounds, "excluded_outside_area": outside_bounds, **store.counts()}
            store.finish_run(run_id, "partial" if bounds and geo_errors else "complete" if not has_more else "limited", summary)
        print(json.dumps(summary, ensure_ascii=False))
    elif args.command == "parse-file":
        validate_search_url(args.url)
        html = args.html_file.read_text(encoding="utf-8")
        page = parse_listing_page(html, args.url)
        with ListingStore(args.db) as store:
            run_id = store.start_run("cli_import", {"source_url": args.url, "file": str(args.html_file)})
            saved = store.merge_snapshot([item.as_dict() for item in page.listings],
                                         observed_at=_timestamp(), source_url=args.url, run_id=run_id)
            store.finish_run(run_id, "imported", {"pages": 1, "unique_ids": len(page.listings),
                                                 "site_count": page.total_found, "has_more": page.next_url is not None,
                                                 "with_coordinates": sum(item.latitude is not None for item in page.listings)})
        print(json.dumps({"saved": saved, "site_count": page.total_found, "next_url": page.next_url}, ensure_ascii=False))
    elif args.command == "export":
        bounds = parse_bounds(args.bounds) if args.bounds else None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with ListingStore(args.db) as store, args.output.open("w", encoding="utf-8", newline="") as output:
            count = store.export(args.table, args.format, output, category=args.category, bounds=bounds)
        print(json.dumps({"rows": count, "output": str(args.output)}, ensure_ascii=False))
    elif args.command == "stats":
        with ListingStore(args.db) as store:
            print(json.dumps(store.counts(), ensure_ascii=False))
    elif args.command == "serve":
        from .server import serve

        api_token = args.api_token_file.read_text(encoding="utf-8").strip() if args.api_token_file else os.environ.get("KRISHA_API_TOKEN")
        serve(port=args.port, db_path=args.db, default_url=DEFAULT_URL, enable_live=args.enable_live,
              host=args.host, api_token=api_token, ui_origin=args.ui_origin)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _run(args)
    except (CrawlError, PageFormatError, OSError, sqlite3.Error, ValueError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2
    return 0
