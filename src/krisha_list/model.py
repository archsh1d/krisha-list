from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Listing:
    id: int
    url: str
    title: str
    object_type: str | None
    rooms: int | None
    house_area_m2: float | None
    plot_area_sot: float | None
    price_kzt: int | None
    district: str | None
    address: str | None
    description_preview: str | None
    seller_type: str | None
    city: str | None
    posted_label: str | None
    floors: int | None
    year_built: int | None
    page_number: int
    latitude: float | None = None
    longitude: float | None = None
    geo_source: str | None = None
    geo_zoom: int | None = None
    geo_type: str | None = None
    category: str = "house"
    apartment_area_m2: float | None = None
    floor: int | None = None
    building_floors: int | None = None
    residential_complex: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ParsedPage:
    url: str
    listings: tuple[Listing, ...]
    total_found: int | None
    next_url: str | None


class PageFormatError(ValueError):
    """The response is not a recognizable Krisha search-results page."""
