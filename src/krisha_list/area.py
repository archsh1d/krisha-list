"""A WGS84 rectangle used by Krisha's `bounds` search parameter."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .categories import category_from_url
from .model import ParsedPage


@dataclass(frozen=True, slots=True)
class Bounds:
    north: float
    west: float
    south: float
    east: float

    def __post_init__(self) -> None:
        values = (self.north, self.west, self.south, self.east)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Границы области должны быть конечными числами")
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("Северная широта должна быть больше южной")
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("Восточная долгота должна быть больше западной")

    def as_query(self) -> str:
        return ",".join(format(value, ".12g") for value in (
            self.north, self.west, self.south, self.east,
        ))

    def contains(self, latitude: float, longitude: float) -> bool:
        return self.south <= latitude <= self.north and self.west <= longitude <= self.east


def parse_bounds(value: str) -> Bounds:
    pieces = value.split(",")
    if len(pieces) != 4:
        raise ValueError("Область задаётся как север,запад,юг,восток")
    try:
        numbers = tuple(float(piece.strip()) for piece in pieces)
    except ValueError as error:
        raise ValueError("Координаты области должны быть числами") from error
    return Bounds(*numbers)


def bounds_from_url(url: str) -> Bounds | None:
    values = [value for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True) if key == "bounds"]
    if len(values) > 1:
        raise ValueError("В ссылке несколько параметров bounds")
    return parse_bounds(values[0]) if values else None


def with_bounds(url: str, bounds: Bounds) -> str:
    category_from_url(url)
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key not in {"bounds", "page"}]
    query.append(("bounds", bounds.as_query()))
    return urlunsplit(("https", parts.hostname, parts.path, urlencode(query), ""))


def _on_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> bool:
    y, x = point
    y1, x1 = start
    y2, x2 = end
    cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    return abs(cross) <= 1e-12 and min(x1, x2) - 1e-12 <= x <= max(x1, x2) + 1e-12 and min(y1, y2) - 1e-12 <= y <= max(y1, y2) + 1e-12


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])


def _segments_intersect(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> bool:
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    if (ab_c > 0 > ab_d or ab_d > 0 > ab_c) and (cd_a > 0 > cd_b or cd_b > 0 > cd_a):
        return True
    return any((_on_segment(p, q, r) for p, q, r in ((c, a, b), (d, a, b), (a, c, d), (b, c, d))))


@dataclass(frozen=True, slots=True)
class Polygon:
    vertices: tuple[tuple[float, float], ...]  # (latitude, longitude)

    def __post_init__(self) -> None:
        points = self.vertices
        if not 3 <= len(points) <= 100:
            raise ValueError("Полигон должен содержать от 3 до 100 вершин")
        if len(set(points)) != len(points):
            raise ValueError("Вершины полигона не должны повторяться")
        if any(not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180) for lat, lon in points):
            raise ValueError("Координаты полигона должны быть допустимыми широтой и долготой")
        signed_area = sum(points[i][1] * points[(i + 1) % len(points)][0] - points[(i + 1) % len(points)][1] * points[i][0] for i in range(len(points)))
        if abs(signed_area) <= 1e-12:
            raise ValueError("Полигон должен охватывать ненулевую площадь")
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if j == i + 1 or (i == 0 and j == len(points) - 1):
                    continue
                if _segments_intersect(points[i], points[(i + 1) % len(points)], points[j], points[(j + 1) % len(points)]):
                    raise ValueError("Стороны полигона не должны пересекаться")

    @property
    def bounds(self) -> Bounds:
        latitudes, longitudes = zip(*self.vertices)
        return Bounds(max(latitudes), min(longitudes), min(latitudes), max(longitudes))

    def contains(self, latitude: float, longitude: float) -> bool:
        if not self.bounds.contains(latitude, longitude):
            return False
        inside = False
        for i, a in enumerate(self.vertices):
            b = self.vertices[(i + 1) % len(self.vertices)]
            if _on_segment((latitude, longitude), a, b):
                return True
            if (a[0] > latitude) != (b[0] > latitude):
                crossing = a[1] + (b[1] - a[1]) * (latitude - a[0]) / (b[0] - a[0])
                if longitude < crossing:
                    inside = not inside
        return inside


def parse_polygon(value: object) -> Polygon:
    if not isinstance(value, list):
        raise ValueError("Полигон должен быть массивом координат")
    points = []
    for pair in value:
        if not isinstance(pair, list) or len(pair) != 2 or any(type(number) not in (int, float) for number in pair):
            raise ValueError("Каждая вершина полигона должна содержать широту и долготу")
        points.append((float(pair[0]), float(pair[1])))
    return Polygon(tuple(points))


def filter_page(page: ParsedPage, bounds: Bounds, polygon: Polygon | None = None) -> tuple[ParsedPage, int, int]:
    kept = []
    without_coordinates = outside = 0
    for item in page.listings:
        if item.latitude is None or item.longitude is None:
            without_coordinates += 1
        elif bounds.contains(item.latitude, item.longitude) and (polygon is None or polygon.contains(item.latitude, item.longitude)):
            kept.append(item)
        else:
            outside += 1
    return replace(page, listings=tuple(kept)), without_coordinates, outside
