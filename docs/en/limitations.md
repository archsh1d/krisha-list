# Limitations, permission, and data interpretation

**Language:** [Русский](../limitations.md) · **English** · [Қазақша](../kk/limitations.md)

## Source access

Under section 5.3 of the [Krisha.kz agreement](https://krisha.kz/content/special/agreement), automated access and extraction require written Kolesa permission. Sections 5.5.6–5.5.7 address copying, distribution, and protective systems. Every operator must obtain and check **their own** permission and any technical conditions. Publishing this code grants no permission to collect or redistribute listings.

The service does not solve CAPTCHA, bypass access-check pages, use proxies to circumvent restrictions, or retrieve seller contacts. HTTP 403/429/468 and SafeLine checks stop collection. Delays and snapshot reuse reduce request frequency but do not guarantee access.

## Completeness

- `complete` means the available pagination for that request ended. It does not prove the source showed **every** existing listing.
- `limited` means the selected page limit was reached; `partial` indicates an interrupted or incomplete result. `cached` is an older saved snapshot with zero new pages.
- An arbitrary district/neighborhood name filters addresses on city pages already fetched. Limiting pages can miss matching properties.
- Polygon collection first uses a source bounding rectangle, then filters map points against the exact polygon. Listings without coordinates are excluded. A map error makes an area result incomplete.
- Coordinates come from the Krisha.kz map list and can be approximate. They do not establish cadastral boundaries or an exact property address.

## Freshness and quality

The catalog retains previously observed listings and does not prove they remain active. `first_seen_at` and `last_seen_at` are the tool's observation times, not publication times. For imported HTML, they reflect **import time**; the age of the original file may be unknown. Import does not overwrite fields of an existing listing, so an older file cannot roll back a newer price.

“Property price / sot” divides the **whole house-and-plot price** by plot area; it is not a land-only valuation. Source users supply listing values, so fields may be missing or inaccurate. The parser depends on search-page HTML and needs review when the site changes.

Real HTML, JSON, SQLite, CSV, and secrets are excluded from public Git. Synthetic fixtures are for tests only.
