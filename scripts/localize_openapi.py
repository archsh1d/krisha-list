"""Build translated descriptive text in the public OpenAPI documents.

Endpoint names, parameter names, schemas, and examples remain identical.
Run from the repository root: python scripts/localize_openapi.py [--check]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "web" / "dist"
TRANSLATIONS = {
    "Серверный API локального сборщика. Данные и сбор доступны только на запущенном экземпляре Python-сервера.": (
        "Server API for the local collector. Data and collection are available only on a running Python server instance.",
        "Жергілікті жинағыштың серверлік API интерфейсі. Деректер мен жинау тек іске қосылған Python сервер инстанциясында қолжетімді.",
    ),
    "Описание API": ("API description", "API сипаттамасы"),
    "Язык описаний: ru, en или kk": ("Description language: ru, en, or kk", "Сипаттама тілі: ru, en немесе kk"),
    "OpenAPI 3.1 JSON": ("OpenAPI 3.1 JSON", "OpenAPI 3.1 JSON"),
    "Состояние сервера и число записей": ("Server status and record count", "Сервер күйі мен жазбалар саны"),
    "Сервер доступен": ("Server available", "Сервер қолжетімді"),
    "Страница сохранённых объявлений": ("Page of saved listings", "Сақталған хабарландырулар беті"),
    "Точное название города из карточки": ("Exact city name from the listing", "Хабарландырудағы қаланың дәл атауы"),
    "Точное название района из карточки": ("Exact district name from the listing", "Хабарландырудағы ауданның дәл атауы"),
    "Север,запад,юг,восток": ("North,west,south,east", "Солтүстік,батыс,оңтүстік,шығыс"),
    "ISO 8601 с часовым поясом; фильтр по last_seen_at": (
        "Timezone-aware ISO 8601; filters last_seen_at",
        "Уақыт белдеуі бар ISO 8601; last_seen_at бойынша сүзгі",
    ),
    "Объявления и параметры страницы": ("Listings and page metadata", "Хабарландырулар мен бет параметрлері"),
    "Объявление и история цены": ("Listing and price history", "Хабарландыру және баға тарихы"),
    "Карточка": ("Listing", "Хабарландыру"),
    "Последние запуски сбора": ("Recent collection runs", "Соңғы жинау іске қосулары"),
    "Журнал": ("Run log", "Журнал"),
    "Результат одного запуска": ("Result of one run", "Бір іске қосудың нәтижесі"),
    "Запуск": ("Run", "Іске қосу"),
    "Запустить сбор и дождаться результата": (
        "Start collection and wait for the result",
        "Жинауды бастап, нәтижесін күту",
    ),
    "Синхронный запрос. Действуют те же паузы, кэш и ошибки источника, что в локальном интерфейсе. При отключённом --enable-live возвращает 403.": (
        "Synchronous request. The same delays, cache, and source errors apply as in the local UI. Returns 403 when --enable-live is disabled.",
        "Синхронды сұрау. Жергілікті интерфейстегі кідірістер, кэш және дереккөз қателері қолданылады. --enable-live өшірулі болса, 403 қайтарады.",
    ),
    "HTTPS-ссылка на выдачу Krisha.kz": ("Krisha.kz search results HTTPS URL", "Krisha.kz нәтижелерінің HTTPS сілтемесі"),
    "0 = вся доступная пагинация": ("0 = all available result pages", "0 = барлық қолжетімді нәтижелер беттері"),
    "Отбор по району или микрорайону после загрузки страниц города; несовместим с bounds и polygon": (
        "Filter by district or neighborhood after loading city pages; incompatible with bounds and polygon",
        "Қала беттері жүктелгеннен кейін аудан немесе шағынаудан бойынша сүзу; bounds және polygon параметрлерімен үйлеспейді",
    ),
    "Итог сбора или повторно использованный снимок": (
        "Collection result or reused snapshot",
        "Жинау нәтижесі немесе қайта пайдаланылған көшірме",
    ),
    "Число точек из подходящего сохранённого снимка": (
        "Map positions reused from a recent matching snapshot",
        "Сәйкес келетін соңғы көшірмеден қайта қолданылған карта нүктелерінің саны",
    ),
    "Ошибка": ("Error", "Қате"),
}


def translate(document: object, language: str) -> object:
    index = 0 if language == "en" else 1
    if isinstance(document, list):
        return [translate(item, language) for item in document]
    if isinstance(document, dict):
        result = {}
        for key, value in document.items():
            if key in {"summary", "description"} and isinstance(value, str):
                if value not in TRANSLATIONS:
                    raise ValueError(f"Missing {language} OpenAPI translation: {value}")
                result[key] = TRANSLATIONS[value][index]
            else:
                result[key] = translate(value, language)
        return result
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    for language in ("en", "kk"):
        output = ROOT / f"openapi.{language}.json"
        expected = json.dumps(translate(source, language), ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if output.read_text(encoding="utf-8") != expected:
                raise SystemExit(f"Out of date: {output}")
        else:
            output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
