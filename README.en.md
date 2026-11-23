# Krisha List

**Language:** [Русский](README.md) · **English** · [Қазақша](README.kk.md)

Krisha List is an independent research tool for parsing Krisha.kz HTML search results for houses, cottages, and apartments. It includes a local interface, area map, SQLite catalog, CSV/JSONL export, and a server API. The repository contains **code and synthetic test data only**. Real listings, page snapshots, databases, and secrets are excluded. It is not an official Kolesa or Krisha.kz service.

> **Each operator needs their own permission.** Section 5.3 of the [Krisha.kz agreement](https://krisha.kz/content/special/agreement) requires written permission from Kolesa for automated access and extraction. Permission held by the author or another deployment is not transferred with this repository. Check that your permission covers the access method, volume, storage, and subsequent use you intend.

## Quick start with Docker Compose

Install Docker, Docker Compose, and Python. From the repository root:

```sh
python scripts/init_env.py
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8765/`. The service is bound to this computer and **live collection is disabled by default**. To test without contacting the source, import the synthetic [HTML file](web/dist/sample.html) or your own previously saved HTML. After obtaining your own written permission from Kolesa, set `KRISHA_ENABLE_LIVE=1` in the private `.env` file and restart:

```sh
docker compose up -d --force-recreate
```

See [deployment](docs/en/deployment.md) for health checks, storage, backup, and running without Docker.

## What it does

The interface and API page switch between Russian, English, and Kazakh; the choice is saved in the browser. Collected listing content remains in the source language.

- Parses the main HTML results and matching map-list JSON, joining coordinates to listings by ID.
- Limits collection by city, district/neighborhood name, or a drawn map area. An arbitrary name is checked against loaded listing addresses.
- Stores listings, price changes, and run history in SQLite; exports local data as CSV/JSONL.
- Exposes a local `/api/v1` with a Bearer token and an [OpenAPI specification](web/dist/openapi.en.json).

## Limits that affect results

Live collection cannot guarantee complete or current results. Krisha.kz may return HTTP 468, change its HTML, or restrict access; the collector stops without bypassing the check. Repeating a request may show an **older snapshot with zero new pages**. Listings without coordinates are excluded from polygon selections, and map positions may be approximate. Import time does not establish that an old HTML file is current. Read the [full limitations](docs/en/limitations.md).

The built-in HTTP server is intended for a research deployment. Compose publishes only on `127.0.0.1`; **do not expose it directly to the Internet**. Network API access needs a separate secure gateway, HTTPS, limits, and token management. See [security](SECURITY.en.md).

## Documentation and checks

- [Deployment](docs/en/deployment.md)
- [Interface and CLI](docs/en/usage.md)
- [Integration API](docs/en/api.md)
- [Limitations and data rights](docs/en/limitations.md)
- [Historical live-test report](docs/en/live-test-2026-11-14.md)
- [Contributing](CONTRIBUTING.en.md)

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m unittest discover -s tests -q
```

CI uses synthetic pages and **does not contact Krisha.kz**.

## License

Project source code and documentation are distributed under [MIT](LICENSE). The license **does not cover** listings, HTML/JSON snapshots, Krisha.kz user data, or source-access permission. The bundled Leaflet library has its [own license notice](web/dist/vendor/leaflet/LICENSE).
