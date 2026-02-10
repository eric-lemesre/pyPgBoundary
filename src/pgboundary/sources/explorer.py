"""Explorateur de catalogue IGN via l'API Atom.

Orchestre le scraping de l'API Atom et le peuplement de la base SQLite.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from pydantic import BaseModel, Field

from pgboundary.products.catalog_db import CatalogDatabase
from pgboundary.sources.atom import AtomClient

logger = logging.getLogger(__name__)

# Seuil de fraîcheur par défaut (24h)
STALE_THRESHOLD_SECONDS = 24 * 60 * 60


class ScanResult(BaseModel):
    """Résultat d'un scan de catalogue."""

    products_scanned: int = Field(default=0, description="Nombre de produits scannés")
    editions_discovered: int = Field(default=0, description="Éditions découvertes")
    editions_new: int = Field(default=0, description="Nouvelles éditions insérées")
    errors: list[str] = Field(default_factory=list, description="Erreurs rencontrées")
    duration: float = Field(default=0.0, description="Durée en secondes")


class CatalogExplorer:
    """Orchestre le scraping API Atom → peuplement SQLite."""

    def __init__(
        self,
        db_path: Path | str,
        base_url: str = "https://data.geopf.fr/telechargement",
        stale_threshold: int = STALE_THRESHOLD_SECONDS,
    ) -> None:
        self.db_path = Path(db_path)
        self.base_url = base_url
        self.stale_threshold = stale_threshold

    def scan_all(
        self,
        force: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ScanResult:
        """Scan complet : capabilities + toutes les éditions.

        Args:
            force: Force le scan même si les données sont fraîches.
            progress_callback: Callback (product_name, current, total) pour la progression.

        Returns:
            Résultat du scan.
        """
        start = time.monotonic()
        result = ScanResult()

        with AtomClient(self.base_url) as client, CatalogDatabase(self.db_path) as db:
            # 1. Scraper les capabilities
            try:
                atom_products = client.fetch_capabilities()
            except Exception as e:
                result.errors.append(f"Erreur capabilities: {e}")
                result.duration = time.monotonic() - start
                return result

            total = len(atom_products)

            # 2. Enregistrer les produits et scraper les éditions
            for i, ap in enumerate(atom_products):
                if progress_callback:
                    progress_callback(ap.name, i, total)

                try:
                    db.upsert_product(
                        name=ap.name,
                        title=ap.title,
                        description=ap.description,
                        resource_url=ap.resource_url,
                    )

                    if not force and not self._is_stale_db(db, ap.name):
                        logger.debug("Produit %s encore frais, skip", ap.name)
                        result.products_scanned += 1
                        continue

                    editions = client.fetch_product_editions(ap.name)
                    result.editions_discovered += len(editions)

                    edition_dicts = [
                        {
                            "title": ed.title,
                            "edition_date": ed.edition_date,
                            "format": ed.format,
                            "zone": ed.zone,
                            "crs": ed.crs,
                            "download_url": ed.download_url,
                        }
                        for ed in editions
                    ]
                    inserted = db.upsert_editions(ap.name, edition_dicts)
                    result.editions_new += inserted
                    result.products_scanned += 1

                except Exception as e:
                    msg = f"Erreur pour {ap.name}: {e}"
                    logger.warning(msg)
                    result.errors.append(msg)

            if progress_callback:
                progress_callback("", total, total)

        result.duration = time.monotonic() - start
        return result

    def scan_product(
        self,
        product_name: str,
        force: bool = False,
    ) -> ScanResult:
        """Scan d'un seul produit.

        Args:
            product_name: Nom du produit à scanner.
            force: Force le scan même si les données sont fraîches.

        Returns:
            Résultat du scan.
        """
        start = time.monotonic()
        result = ScanResult()

        with AtomClient(self.base_url) as client, CatalogDatabase(self.db_path) as db:
            try:
                if not force and not self._is_stale_db(db, product_name):
                    logger.info("Produit %s encore frais", product_name)
                    result.duration = time.monotonic() - start
                    return result

                # Upsert le produit
                db.upsert_product(name=product_name)

                editions = client.fetch_product_editions(product_name)
                result.editions_discovered = len(editions)

                edition_dicts = [
                    {
                        "title": ed.title,
                        "edition_date": ed.edition_date,
                        "format": ed.format,
                        "zone": ed.zone,
                        "crs": ed.crs,
                        "download_url": ed.download_url,
                    }
                    for ed in editions
                ]
                inserted = db.upsert_editions(product_name, edition_dicts)
                result.editions_new = inserted
                result.products_scanned = 1

            except Exception as e:
                msg = f"Erreur pour {product_name}: {e}"
                logger.warning(msg)
                result.errors.append(msg)

        result.duration = time.monotonic() - start
        return result

    def is_stale(self, product_name: str) -> bool:
        """Vérifie si les données d'un produit sont périmées.

        Args:
            product_name: Nom du produit.

        Returns:
            True si les données sont périmées ou absentes.
        """
        if not self.db_path.exists():
            return True

        with CatalogDatabase(self.db_path) as db:
            return self._is_stale_db(db, product_name)

    def _is_stale_db(self, db: CatalogDatabase, product_name: str) -> bool:
        """Vérifie la fraîcheur d'un produit sur une connexion ouverte.

        Args:
            db: Base de données ouverte.
            product_name: Nom du produit.

        Returns:
            True si les données sont périmées ou absentes.
        """
        product = db.get_product(product_name)
        if product is None or not product.get("last_scanned"):
            return True

        try:
            last_scanned = datetime.fromisoformat(product["last_scanned"])
            if last_scanned.tzinfo is None:
                last_scanned = last_scanned.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - last_scanned).total_seconds()
            return age > self.stale_threshold
        except (ValueError, TypeError):
            return True
