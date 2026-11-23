# Krisha List: interface and CLI

**Language:** [Русский](../usage.md) · **English** · [Қазақша](../kk/usage.md)

## Web interface

Start with [deployment](deployment.md). The local interface reads listings, price history, and run history from SQLite and generates CSV through the local API. To test import without contacting Krisha.kz, use the synthetic [HTML file](../../web/dist/sample.html).

If you host `web/dist` separately as a static page, it stores imported data in the browser and offers a “View example” button. Its “Collect listings” button transfers the selected category, location, polygon, and filters to your local collector; press the button again on the local page to start. Set a nondefault collector port in the “Collection runs locally” disclosure. The static page itself does not contact Krisha.kz.

Choose houses/cottages or apartments, a city, and either a district/neighborhood name or a map area. Suggestions include known Krisha.kz sections and addresses from saved listings. A known section is requested directly. An arbitrary name is checked against addresses on fetched city pages; a page limit can omit matches. “All pages” follows available pagination but source refusal can still interrupt it. Your selection also filters the catalog, summary, map, and CSV.

Use “Draw an area on the map” to open the large editor. Choose “Draw again,” mark at least three points, and save. You can undo a point, clear the outline, pan, or zoom. Canceling or closing leaves the previous area intact; “Remove area” confirms its deletion. Alternatively, enter a rectangle in north latitude, west longitude, south latitude, east longitude order. The selection persists in the browser. For a polygon, the collector requests its bounding rectangle and then retains only map points inside the exact contour. Listings without coordinates are excluded. The summary notes how many catalog listings cannot be checked against an active area due to missing coordinates.

The catalog offers a table, map, category and type filters, sorting, and CSV export. The summary shows the latest observation and price statistics. “Property price / sot” means the whole house-and-plot price divided by plot area; groups with fewer than five properties show no median. The map position may be approximate. A property row can show coordinates, an OpenStreetMap link, and price changes. Choosing “All pages” follows the next-page links until the end, while a source error can leave a partial result.

The local collector reuses a fresh snapshot for identical parameters within 15 minutes. After HTTP 403/429/468 or an HTTP 200 access-check page, a global 30-minute cooldown applies. Consecutive refusals extend it to 1, 2, then 4 hours; `Retry-After` may extend it further. The UI shows the next attempt time and, if available, an older snapshot. It waits at least three seconds between network responses and the next request, including map calls; after each six requests the interval steps up, capped at 12 seconds. Once the 15-minute snapshot period expires, it fetches HTML again but may reuse coordinates from a complete matching snapshot for up to six hours. `reused_coordinates` counts those listings; `geo_source=krisha_map_list_cached` marks their stored map positions. These measures reduce request frequency but do not guarantee avoiding HTTP 468. A cached result has zero new pages and does not confirm current listings or prices.

To debug live collection **only with written Kolesa permission**, run from the repository root:

```powershell
.venv\Scripts\python -m krisha_list serve --enable-live --db data/krisha.sqlite3
```

Open `http://127.0.0.1:8765/`. The local server saves listings and map coordinates in SQLite and received HTML/JSON in `data/snapshots/`. An imported HTML file is also stored in SQLite. On first opening, old real browser-saved listings are migrated without replacing newer database records. The run log records parameters, pages, listing counts, area exclusions, HTTP status, and the reason for stopping. `complete` means pagination ended; `limited`, `partial`, and `cached` do not mean a complete current source listing.

To apply Krisha.kz filters such as price or rooms, paste the HTTPS search-results URL into the URL field. Its filters are retained; selected city and area replace the URL's location. The chosen URL category takes precedence over the category selector.

## Developer API

The versioned server API is at `/api/v1`. The bundled static files contain [API guidance](../../web/dist/api.html) and [OpenAPI 3.1](../../web/dist/openapi.en.json), but do not publish your SQLite catalog or start collection. Data comes from your own running server.

Create a token once and start the server:

```powershell
.venv\Scripts\python -c "import secrets; from pathlib import Path; Path('data/api-token.txt').write_text(secrets.token_urlsafe(32), encoding='utf-8')"
.venv\Scripts\python -m krisha_list serve --enable-live --api-token-file data/api-token.txt
```

Alternatively use `KRISHA_API_TOKEN` with at least 32 characters. Do not place it in a URL, browser JavaScript, or Git. The API accepts `Authorization: Bearer <token>` and rejects requests with an `Origin` header; use a server-side client. For network access, `--host 0.0.0.0` requires a token and an HTTPS proxy. Legacy UI routes remain local-only.

Routes: `GET /api/v1/status`, `GET /api/v1/listings`, `GET /api/v1/listings/{id}`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, `POST /api/v1/collections`, and public `GET /api/v1/openapi.json`. List filters: `category`, exact `city` and `district`, `bounds` (north, west, south, east), `updated_after` (timezone-aware ISO 8601), `limit` (1–100), and `offset`. Responses include `data`, `page.total`, and `page.next_offset`; an individual listing includes price history. Offset pages can change if collection updates the catalog while you read it.

`POST /api/v1/collections` accepts `url`, `max_pages`, `bounds`, `polygon`, and `location_query`. It is synchronous; after a dropped connection check `/api/v1/runs`. The same delays, cache, concurrent-run protection, and HTTP 468 stop behavior apply. This route requires `--enable-live` and source permission.

Example PowerShell request for the first 50 houses:

```powershell
$token = (Get-Content data/api-token.txt -Raw).Trim()
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/listings?category=house&limit=50' -Headers @{ Authorization = "Bearer $token" }
```

See the [API details](api.md) and [English OpenAPI specification](../../web/dist/openapi.en.json).

## Command-line tool

The collector reads the **main HTML search list** for houses, cottages, and apartments, excluding the “Hot offers” block. It upserts properties by ID and appends a price-history event when a price changes. For each page requiring new coordinates, it requests the matching map-list JSON and joins coordinates strictly by ID. If page and map positions shift, it checks the next map page as well. `geo_source=krisha_map_list` identifies a newly fetched position shown by the site, which may not be the exact plot or entrance. Missing map coordinates stay empty; older coordinates survive a temporarily empty map response.

The project does not open individual listing pages, collect seller contacts, or bypass access checks. Changed markup or a protection page stops collection.

### Install

Python 3.11 or newer, from PowerShell in the project directory:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m krisha_list --help
```

### Use saved pages

```powershell
.venv\Scripts\python -m krisha_list parse-file page.html
.venv\Scripts\python -m krisha_list stats
.venv\Scripts\python -m krisha_list export --output listings.csv
.venv\Scripts\python -m krisha_list export --table price_history --format jsonl --output prices.jsonl
```

If the file belongs to another results URL, pass it with `--url` for correct pagination and page-number detection.

### Collect when authorized

```powershell
.venv\Scripts\python -m krisha_list collect
.venv\Scripts\python -m krisha_list collect --url "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/" --max-pages 2 --db data/krisha.sqlite3
.venv\Scripts\python -m krisha_list collect --url "https://krisha.kz/prodazha/kvartiry/almaty-almalinskij/" --max-pages 2 --db data/krisha.sqlite3
.venv\Scripts\python -m krisha_list export --db data/krisha.sqlite3 --category apartment --output apartments.csv
.venv\Scripts\python -m krisha_list collect --max-pages 1 --db data/probe.sqlite3 --snapshot-dir data/snapshots/probe
```

Limit an area with `--bounds` in `north,west,south,east` order, using decimal degrees:

```powershell
.venv\Scripts\python -m krisha_list collect --url "https://krisha.kz/prodazha/doma-dachi/almaty-almalinskij/" --bounds "43.255,76.87,43.24,76.91" --max-pages 2 --db data/krisha.sqlite3
.venv\Scripts\python -m krisha_list export --db data/krisha.sqlite3 --bounds "43.255,76.87,43.24,76.91" --output area.csv
```

`collect` sends bounds to Krisha.kz and checks each card's coordinates before saving. Listings without a map point or outside the rectangle are excluded. Bounds already present in `--url` also apply. `export --bounds` filters the existing database and works with `--category`. `--no-geo` is unavailable during area collection. Map coordinates may be approximate, so the boundary applies to the shown point, not a legal land boundary.

Without `--max-pages`, the command follows the “Next” link to the end. The default pause grows from three to 12 seconds as a collection proceeds. The CLI honors the same SQLite-backed refusal cooldown as the local server. HTTP 403/429/468 stops collection. For a SafeLine access-check page, the local API reports it and stores `source-error.json` with status and URL plus `source-response.html` for diagnosis. With `--snapshot-dir`, the CLI saves `source-error.json` too. Proxy-based or other bypassing is not included. `--snapshot-dir` saves received HTML and map JSON; `--no-geo` can skip map calls when an area is not selected. Map failures appear in `geo_errors` while HTML collection continues.

### Data

`listings` stores ID, canonical `/a/show/<id>` URL, title, property type and category, rooms, price in tenge, district, address, displayed map position, preview, seller type, city, and source date label. Houses may have house and plot area; apartments may have area, floor, building floors, and residential complex. Build year is parsed from preview when present. `price_history` stores the first price and later changes with UTC observation time. `first_seen_at` and `last_seen_at` are collector observations, not publication dates. The card date may omit a year and is kept as source text. Missing HTML fields remain missing; one partial run cannot establish deletion from the site. CSV and JSONL export only the local database, without network calls.

## Checks and source access

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Tests use synthetic HTML. The [historical live-test report](live-test-2026-11-14.md) describes a run on 14 November 2026; site changes can require parser updates. A later coordinate check found 133 map points for 133 listings over seven pages; an apartment first-page check found 23 cards, 20 with map points. These observations can change, and promoted cards may lack a matching map-list entry.

The [Krisha.kz agreement](https://krisha.kz/content/special/agreement) requires written Kolesa permission for automated access and extraction. Use `collect` only after obtaining it. Local `parse-file` can inspect an HTML file you already have without contacting the site.
