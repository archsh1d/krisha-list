# Contributing

**Language:** [Русский](CONTRIBUTING.md) · **English** · [Қазақша](CONTRIBUTING.kk.md)

Use synthetic HTML fixtures from `tests/fixtures`. Do not include real Krisha.kz pages, SQLite databases, CSV exports, tokens, or copies of permissions in a pull request. CI does not make network requests to the source.

Before opening a pull request:

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m unittest discover -s tests -q
node --check web/dist/app.js
node --check web/dist/i18n.js
python -m json.tool web/dist/openapi.json
python scripts/localize_openapi.py --check
python scripts/check_docs.py
```

When changing HTML parsing, add a synthetic test case and describe which fields or statuses changed. When changing the API, update the OpenAPI specifications and `docs/api.md`, `docs/en/api.md`, and `docs/kk/api.md`. Run a live check only on your own authorized instance and never publish source listings.

When adding interface text, update `web/dist/i18n.js` for Russian, English, and Kazakh. Preserve collected listing titles, addresses, and descriptions in their source language.
