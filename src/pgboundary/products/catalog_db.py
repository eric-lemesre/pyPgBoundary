"""Base de données SQLite pour le catalogue des produits IGN.

Persiste les données découvertes via l'API Atom dans une base
SQLite locale (~/.pgboundary/catalog.db).
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
    """Gestionnaire de la base SQLite du catalogue.

    Utilisable comme context manager :
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
    # Produits
    # =========================================================================

    def upsert_product(
        self,
        name: str,
        title: str = "",
        description: str = "",
        resource_url: str = "",
    ) -> None:
        """Insère ou met à jour un produit.

        Args:
            name: Nom du produit (clé primaire).
            title: Titre lisible.
            description: Description.
            resource_url: URL du flux des éditions.
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
        """Retourne un produit par son nom.

        Args:
            name: Nom du produit.

        Returns:
            Dictionnaire du produit ou None.
        """
        row = self.conn.execute("SELECT * FROM products WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    def list_products(self) -> list[dict[str, Any]]:
        """Liste tous les produits.

        Returns:
            Liste de dictionnaires.
        """
        rows = self.conn.execute("SELECT * FROM products ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # Éditions
    # =========================================================================

    def upsert_editions(
        self,
        product_name: str,
        editions: list[dict[str, str]],
    ) -> int:
        """Insère ou met à jour des éditions d'un produit.

        Args:
            product_name: Nom du produit parent.
            editions: Liste de dicts avec title, edition_date, format, zone, crs, download_url.

        Returns:
            Nombre d'éditions insérées ou mises à jour.
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
        """Retourne les éditions d'un produit avec filtres optionnels.

        Args:
            product_name: Nom du produit.
            format: Filtre par format.
            zone: Filtre par zone.

        Returns:
            Liste de dicts d'éditions.
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
        """Retourne les dates d'édition distinctes pour un produit.

        Les dates sont extraites des titres d'éditions et dédupliquées.

        Args:
            product_name: Nom du produit.

        Returns:
            Liste de dates triées (plus récentes d'abord).
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
        """Retourne la date d'édition la plus récente.

        Args:
            product_name: Nom du produit.

        Returns:
            Date la plus récente ou None.
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
        """Retourne l'URL de téléchargement pour un produit/format/zone.

        Args:
            product_name: Nom du produit.
            format: Format souhaité (GPKG, SHP).
            zone: Zone/territoire (FRA, FXX, ...).
            date: Date spécifique (optionnel, dernière si absente).

        Returns:
            URL de téléchargement ou None.
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
        """Retourne le nombre d'éditions pour un produit.

        Args:
            product_name: Nom du produit.

        Returns:
            Nombre d'éditions.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM editions WHERE product_name = ?",
            (product_name,),
        ).fetchone()
        return int(row["cnt"]) if row else 0

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques de la base.

        Returns:
            Dictionnaire avec compteurs et taille fichier.
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
