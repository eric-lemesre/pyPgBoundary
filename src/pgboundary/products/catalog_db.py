"""SQLite database for the IGN product catalog.

Persists the data discovered via the Atom API in a local
SQLite database (~/.pgboundary/catalog.db).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    name TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    resource_url TEXT NOT NULL DEFAULT '',
    last_scanned TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS editions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL REFERENCES products(name) ON DELETE CASCADE,
    title TEXT NOT NULL,
    edition_date TEXT NOT NULL DEFAULT '',
    format TEXT NOT NULL DEFAULT '',
    zone TEXT NOT NULL DEFAULT '',
    crs TEXT NOT NULL DEFAULT '',
    download_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_name, title)
);

CREATE INDEX IF NOT EXISTS idx_editions_product ON editions(product_name);
CREATE INDEX IF NOT EXISTS idx_editions_product_format_zone
    ON editions(product_name, format, zone);
"""


class CatalogDatabase:
    """SQLite catalog database manager.

    Can be used as a context manager:
        with CatalogDatabase(path) as db:
            db.upsert_product(...)
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def _ensure_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_dir()
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> CatalogDatabase:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # =========================================================================
    # Products
    # =========================================================================

    def upsert_product(
        self,
        name: str,
        title: str = "",
        description: str = "",
        resource_url: str = "",
    ) -> None:
        """Insert or update a product.

        Args:
            name: Product name (primary key).
            title: Human-readable title.
            description: Description.
            resource_url: URL of the editions feed.
        """
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """
            INSERT INTO products (name, title, description, resource_url, last_scanned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                resource_url = excluded.resource_url,
                last_scanned = excluded.last_scanned,
                updated_at = excluded.updated_at
            """,
            (name, title, description, resource_url, now, now, now),
        )
        self.conn.commit()

    def get_product(self, name: str) -> dict[str, Any] | None:
        """Return a product by its name.

        Args:
            name: Product name.

        Returns:
            Product dictionary or None.
        """
        row = self.conn.execute("SELECT * FROM products WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    def list_products(self) -> list[dict[str, Any]]:
        """List all products.

        Returns:
            List of dictionaries.
        """
        rows = self.conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # Editions
    # =========================================================================

    def upsert_editions(
        self,
        product_name: str,
        editions: list[dict[str, str]],
    ) -> int:
        """Insert or update editions for a product.

        Args:
            product_name: Parent product name.
            editions: List of dicts with title, edition_date, format, zone, crs, download_url.

        Returns:
            Number of editions inserted or updated.
        """
        count = 0
        for ed in editions:
            self.conn.execute(
                """
                INSERT INTO editions (product_name, title, edition_date, format, zone, crs, download_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_name, title) DO UPDATE SET
                    edition_date = excluded.edition_date,
                    format = excluded.format,
                    zone = excluded.zone,
                    crs = excluded.crs,
                    download_url = excluded.download_url
                """,
                (
                    product_name,
                    ed.get("title", ""),
                    ed.get("edition_date", ""),
                    ed.get("format", ""),
                    ed.get("zone", ""),
                    ed.get("crs", ""),
                    ed.get("download_url", ""),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def get_editions(
        self,
        product_name: str,
        format: str | None = None,
        zone: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return editions for a product with optional filters.

        Args:
            product_name: Product name.
            format: Filter by format.
            zone: Filter by zone.

        Returns:
            List of edition dicts.
        """
        query = "SELECT * FROM editions WHERE product_name = ?"
        params: list[str] = [product_name]

        if format:
            query += " AND format = ?"
            params.append(format.upper())
        if zone:
            query += " AND zone = ?"
            params.append(zone.upper())

        query += " ORDER BY edition_date DESC, title DESC"

        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_available_dates(self, product_name: str) -> list[str]:
        """Return distinct edition dates for a product.

        Dates are extracted from edition titles and deduplicated.

        Args:
            product_name: Product name.

        Returns:
            List of dates sorted by most recent first.
        """
        rows = self.conn.execute(
            """
            SELECT DISTINCT edition_date FROM editions
            WHERE product_name = ? AND edition_date != ''
            ORDER BY edition_date DESC
            """,
            (product_name,),
        ).fetchall()
        return [r["edition_date"] for r in rows]

    def get_latest_date(self, product_name: str) -> str | None:
        """Return the most recent edition date.

        Args:
            product_name: Product name.

        Returns:
            Most recent date or None.
        """
        row = self.conn.execute(
            """
            SELECT edition_date FROM editions
            WHERE product_name = ? AND edition_date != ''
            ORDER BY edition_date DESC LIMIT 1
            """,
            (product_name,),
        ).fetchone()
        return row["edition_date"] if row else None

    def get_download_url(
        self,
        product_name: str,
        format: str,
        zone: str,
        date: str | None = None,
    ) -> str | None:
        """Return the download URL for a product/format/zone.

        Args:
            product_name: Product name.
            format: Desired format (GPKG, SHP).
            zone: Zone/territory (FRA, FXX, ...).
            date: Specific date (optional, latest if absent).

        Returns:
            Download URL or None.
        """
        if date:
            row = self.conn.execute(
                """
                SELECT download_url FROM editions
                WHERE product_name = ? AND format = ? AND zone = ?
                    AND edition_date = ?
                ORDER BY title DESC LIMIT 1
                """,
                (product_name, format.upper(), zone.upper(), date),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT download_url FROM editions
                WHERE product_name = ? AND format = ? AND zone = ?
                ORDER BY edition_date DESC, title DESC LIMIT 1
                """,
                (product_name, format.upper(), zone.upper()),
            ).fetchone()

        return row["download_url"] if row else None

    def get_edition_count(self, product_name: str) -> int:
        """Return the number of editions for a product.

        Args:
            product_name: Product name.

        Returns:
            Number of editions.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM editions WHERE product_name = ?",
            (product_name,),
        ).fetchone()
        return int(row["cnt"]) if row else 0

    def get_stats(self) -> dict[str, Any]:
        """Return database statistics.

        Returns:
            Dictionary with counters and file size.
        """
        product_count = self.conn.execute("SELECT COUNT(*) as cnt FROM products").fetchone()
        edition_count = self.conn.execute("SELECT COUNT(*) as cnt FROM editions").fetchone()

        file_size = 0
        if self.db_path.exists():
            file_size = self.db_path.stat().st_size

        return {
            "products": product_count["cnt"] if product_count else 0,
            "editions": edition_count["cnt"] if edition_count else 0,
            "file_size": file_size,
            "db_path": str(self.db_path),
        }
