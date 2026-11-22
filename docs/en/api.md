# Integration API

**Language:** [Русский](../api.md) · **English** · [Қазақша](../kk/api.md)

The local server provides `/api/v1/status`, `/api/v1/listings`, `/api/v1/listings/{id}`, `/api/v1/runs`, `/api/v1/runs/{id}`, and synchronous `POST /api/v1/collections`. See the [OpenAPI 3.1 specification](../../web/dist/openapi.en.json) for the exact schema.

The running server also serves the translated specification at `/api/v1/openapi.json?lang=en` (or `?lang=kk`); Russian is the default.

The API is for server-side clients. **Each instance operator** generates and stores its Bearer token. `python scripts/init_env.py` creates one for Docker Compose. Without Docker, use `KRISHA_API_TOKEN` or `--api-token-file`. This local token is not issued by Kolesa and is not permission to collect. Never publish it in Git or client-side JavaScript.

`POST /collections` needs live collection enabled and source permission. It runs synchronously, so a long crawl may exceed a client timeout. After a dropped connection, check `/runs`. `max_pages=0` visits available pagination, but an HTTP refusal can stop it earlier. A result with `cached=true` comes from a previous snapshot; `pages=0` means zero new pages. Inspect `cached_at`, `source_status`, `geo_errors`, and run history.

`GET /listings` supports category, exact city and district, rectangular `bounds`, `updated_after`, `limit`, and `offset`. Offset pages can shift if the catalog changes during reading. For a consistent export, pause collection or back up SQLite first.

The current implementation uses **one token per instance**, without roles, expiration, or per-client quotas. Do not share it with independent developers. A public multi-user API needs a separate gateway and access management; see [security](../../SECURITY.en.md).
