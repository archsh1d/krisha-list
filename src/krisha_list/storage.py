from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .model import Listing
from .area import Bounds


class ListingStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                object_type TEXT,
                rooms INTEGER,
                house_area_m2 REAL,
                plot_area_sot REAL,
                price_kzt INTEGER,
                district TEXT,
                address TEXT,
                description_preview TEXT,
                seller_type TEXT,
                city TEXT,
                posted_label TEXT,
                floors INTEGER,
                year_built INTEGER,
                page_number INTEGER NOT NULL,
                latitude REAL,
                longitude REAL,
                geo_source TEXT,
                geo_zoom INTEGER,
                geo_type TEXT,
                category TEXT NOT NULL DEFAULT 'house',
                apartment_area_m2 REAL,
                floor INTEGER,
                building_floors INTEGER,
                residential_complex TEXT,
                source_url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY,
                listing_id INTEGER NOT NULL REFERENCES listings(id),
                observed_at TEXT NOT NULL,
                price_kzt INTEGER NOT NULL,
                UNIQUE(listing_id, observed_at)
            );
            CREATE INDEX IF NOT EXISTS price_history_listing_idx
                ON price_history(listing_id, observed_at);
            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                pages INTEGER NOT NULL DEFAULT 0,
                unique_ids INTEGER NOT NULL DEFAULT 0,
                site_count INTEGER,
                has_more INTEGER,
                with_coordinates INTEGER NOT NULL DEFAULT 0,
                excluded_without_coordinates INTEGER NOT NULL DEFAULT 0,
                excluded_outside_area INTEGER NOT NULL DEFAULT 0,
                snapshot_dir TEXT,
                source_status INTEGER,
                error TEXT,
                cached_at TEXT
            );
            CREATE TABLE IF NOT EXISTS run_listings (
                run_id INTEGER NOT NULL REFERENCES collection_runs(id),
                listing_id INTEGER NOT NULL REFERENCES listings(id),
                PRIMARY KEY (run_id, listing_id)
            );
            CREATE INDEX IF NOT EXISTS run_listings_listing_idx ON run_listings(listing_id);
            """
        )
        existing = {row[1] for row in self.connection.execute("PRAGMA table_info(listings)")}
        for name, sql_type in (
            ("latitude", "REAL"), ("longitude", "REAL"), ("geo_source", "TEXT"),
            ("geo_zoom", "INTEGER"), ("geo_type", "TEXT"),
            ("category", "TEXT NOT NULL DEFAULT 'house'"),
            ("apartment_area_m2", "REAL"), ("floor", "INTEGER"),
            ("building_floors", "INTEGER"), ("residential_complex", "TEXT"),
        ):
            if name not in existing:
                self.connection.execute(f"ALTER TABLE listings ADD COLUMN {name} {sql_type}")
        self.connection.commit()

    def __enter__(self) -> ListingStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.connection.close()

    def upsert(self, listings: tuple[Listing, ...] | list[Listing], *, observed_at: str, source_url: str, run_id: int | None = None) -> int:
        count = 0
        with self.connection:
            for item in listings:
                previous = self.connection.execute(
                    "SELECT price_kzt FROM listings WHERE id = ?", (item.id,)
                ).fetchone()
                values = item.as_dict()
                values.update(source_url=source_url, first_seen_at=observed_at, last_seen_at=observed_at)
                columns = ", ".join(values)
                placeholders = ", ".join(f":{name}" for name in values)
                updates = ", ".join(
                    f"{name} = excluded.{name}"
                    for name in values
                    if name not in {"id", "first_seen_at", "price_kzt", "latitude", "longitude", "geo_source", "geo_zoom", "geo_type"}
                )
                updates += ", " + ", ".join(
                    f"{name} = COALESCE(excluded.{name}, listings.{name})"
                    for name in ("latitude", "longitude", "geo_source", "geo_zoom", "geo_type")
                )
                self.connection.execute(
                    f"INSERT INTO listings ({columns}) VALUES ({placeholders}) "
                    f"ON CONFLICT(id) DO UPDATE SET {updates}, "
                    "price_kzt = COALESCE(excluded.price_kzt, listings.price_kzt)",
                    values,
                )
                if item.price_kzt is not None and (
                    previous is None or previous["price_kzt"] != item.price_kzt
                ):
                    self.connection.execute(
                        "INSERT INTO price_history(listing_id, observed_at, price_kzt) VALUES (?, ?, ?)",
                        (item.id, observed_at, item.price_kzt),
                    )
                if run_id is not None:
                    self.connection.execute(
                        "INSERT OR IGNORE INTO run_listings(run_id, listing_id) VALUES (?, ?)",
                        (run_id, item.id),
                    )
                count += 1
        return count

    def start_run(self, kind: str, request: dict, snapshot_dir: str | None = None) -> int:
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO collection_runs(kind, started_at, status, request_json, snapshot_dir) VALUES (?, ?, 'running', ?, ?)",
                (kind, started, json.dumps(request, ensure_ascii=False), snapshot_dir),
            )
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, metrics: dict, *, error: str | None = None,
                   source_status: int | None = None, cached_at: str | None = None) -> None:
        finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connection:
            self.connection.execute(
                """UPDATE collection_runs SET finished_at=?, status=?, pages=?, unique_ids=?,
                   site_count=?, has_more=?, with_coordinates=?, excluded_without_coordinates=?,
                   excluded_outside_area=?, source_status=?, error=?, cached_at=? WHERE id=?""",
                (finished, status, metrics.get("pages", 0), metrics.get("unique_ids", 0),
                 metrics.get("site_count"), metrics.get("has_more"), metrics.get("with_coordinates", 0),
                 metrics.get("excluded_without_coordinates", 0), metrics.get("excluded_outside_area", 0),
                 source_status, error, cached_at, run_id),
            )

    def list_runs(self, limit: int = 20) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM collection_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{**dict(row), "request": json.loads(row["request_json"]),
                 "has_more": bool(row["has_more"]) if row["has_more"] is not None else None}
                for row in rows]

    def get_run(self, run_id: int) -> dict | None:
        row = self.connection.execute("SELECT * FROM collection_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), "request": json.loads(row["request_json"]),
                "has_more": bool(row["has_more"]) if row["has_more"] is not None else None}

    def latest_source_access(self) -> dict | None:
        """Return the last source refusal or successful live crawl across the catalog."""
        row = self.connection.execute(
            """SELECT finished_at, source_status, status, snapshot_dir FROM collection_runs
               WHERE kind IN ('live', 'cli_collect') AND
                 (source_status IN (403, 429, 468) OR (source_status = 200 AND status = 'blocked')
                  OR status IN ('complete', 'limited'))
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None

    def list_catalog(self) -> list[dict]:
        rows = [dict(row) for row in self.connection.execute("SELECT * FROM listings ORDER BY last_seen_at DESC, id DESC")]
        history: dict[int, list[dict]] = {}
        for event in self.connection.execute(
            "SELECT listing_id, price_kzt, observed_at FROM price_history ORDER BY listing_id, observed_at"
        ):
            history.setdefault(event["listing_id"], []).append(
                {"price": event["price_kzt"], "observedAt": event["observed_at"]}
            )
        for row in rows:
            row["history"] = history.get(row["id"], [])
        return rows

    def get_listing(self, listing_id: int) -> dict | None:
        row = self.connection.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["history"] = [{"price": event["price_kzt"], "observedAt": event["observed_at"]}
                           for event in self.connection.execute(
                               "SELECT price_kzt, observed_at FROM price_history WHERE listing_id=? ORDER BY observed_at",
                               (listing_id,))]
        return item

    def query_listings(self, *, category: str | None = None, city: str | None = None,
                       district: str | None = None, bounds: Bounds | None = None,
                       updated_after: str | None = None, limit: int = 50,
                       offset: int = 0) -> tuple[list[dict], int]:
        conditions: list[str] = []
        params: list[object] = []
        if category:
            conditions.append("category=?")
            params.append(category)
        if city:
            conditions.append("city=?")
            params.append(city)
        if district:
            conditions.append("district=?")
            params.append(district)
        if bounds:
            conditions.append("latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?")
            params.extend((bounds.south, bounds.north, bounds.west, bounds.east))
        if updated_after:
            conditions.append("julianday(last_seen_at) > julianday(?)")
            params.append(updated_after)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        total = self.connection.execute("SELECT COUNT(*) FROM listings" + where, params).fetchone()[0]
        rows = self.connection.execute(
            "SELECT * FROM listings" + where + " ORDER BY last_seen_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], total

    def merge_snapshot(self, listings: list[dict], *, observed_at: str, source_url: str,
                       run_id: int | None = None) -> int:
        """Add missing historical cards without rolling back fresher DB fields or prices."""
        added = 0
        for data in listings:
            item = Listing(**data)
            exists = self.connection.execute("SELECT 1 FROM listings WHERE id=?", (item.id,)).fetchone()
            if exists:
                with self.connection:
                    self.connection.execute(
                        """UPDATE listings SET latitude=COALESCE(latitude, ?), longitude=COALESCE(longitude, ?),
                           geo_source=COALESCE(geo_source, ?), geo_zoom=COALESCE(geo_zoom, ?),
                           geo_type=COALESCE(geo_type, ?) WHERE id=?""",
                        (item.latitude, item.longitude, item.geo_source, item.geo_zoom, item.geo_type, item.id),
                    )
                    if run_id is not None:
                        self.connection.execute(
                            "INSERT OR IGNORE INTO run_listings(run_id, listing_id) VALUES (?, ?)",
                            (run_id, item.id),
                        )
            else:
                self.upsert([item], observed_at=observed_at, source_url=source_url, run_id=run_id)
                added += 1
        return added

    def export_ids(self, ids: list[int], output: TextIO) -> int:
        names = [row[1] for row in self.connection.execute("PRAGMA table_info(listings)")]
        writer = csv.DictWriter(output, fieldnames=names + ["price_changes"])
        writer.writeheader()
        count = 0
        for listing_id in ids:
            row = self.connection.execute(
                """SELECT listings.*, (SELECT MAX(COUNT(*) - 1, 0) FROM price_history
                   WHERE listing_id = listings.id) AS price_changes FROM listings WHERE id=?""",
                (listing_id,),
            ).fetchone()
            if row is not None:
                record = dict(row)
                for name, value in record.items():
                    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                        record[name] = "'" + value
                writer.writerow(record)
                count += 1
        return count

    def counts(self) -> dict[str, int]:
        return {
            "listings": self.connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0],
            "price_events": self.connection.execute("SELECT COUNT(*) FROM price_history").fetchone()[0],
        }

    def export(
        self, table: str, fmt: str, output: TextIO, *,
        category: str | None = None, bounds: Bounds | None = None,
    ) -> int:
        if table not in {"listings", "price_history"}:
            raise ValueError("Неизвестная таблица")
        if fmt not in {"csv", "jsonl"}:
            raise ValueError("Поддерживаются csv и jsonl")
        if category not in {None, "house", "apartment"}:
            raise ValueError("Неизвестная категория")
        if table != "listings" and (category is not None or bounds is not None):
            raise ValueError("Фильтры категории и области поддерживаются только для объявлений")
        order = "id" if table == "listings" else "listing_id, observed_at"
        conditions: list[str] = []
        params: list[str | float] = []
        if category is not None:
            conditions.append("category = ?")
            params.append(category)
        if bounds is not None:
            conditions.extend(("latitude BETWEEN ? AND ?", "longitude BETWEEN ? AND ?"))
            params.extend((bounds.south, bounds.north, bounds.west, bounds.east))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        cursor = self.connection.execute(f"SELECT * FROM {table}{where} ORDER BY {order}", params)
        names = [column[0] for column in cursor.description]
        writer = csv.DictWriter(output, fieldnames=names) if fmt == "csv" else None
        if writer:
            writer.writeheader()
        count = 0
        for row in cursor:
            record = dict(row)
            if writer:
                writer.writerow(record)
            else:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
        return count
