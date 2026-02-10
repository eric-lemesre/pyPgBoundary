"""Loader for IGN Admin Express data.

This module provides a specialized loader for Admin Express products,
with backward compatibility for the existing API.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from pgboundary.exceptions import LoaderError
from pgboundary.loaders.product_loader import ProductLoader
from pgboundary.products.catalog import FileFormat, get_admin_express_product

if TYPE_CHECKING:
    from pathlib import Path

    from pgboundary.config import Settings
    from pgboundary.db.connection import DatabaseManager
    from pgboundary.products.catalog import ProductCatalog
    from pgboundary.sources.ign import Territory

logger = logging.getLogger(__name__)

# Mapping des couches vers les clés de table (rétrocompatibilité)
LAYER_TO_TABLE_KEY = {
    "REGION": "region",
    "DEPARTEMENT": "departement",
    "ARRONDISSEMENT": "arrondissement",
    "EPCI": "epci",
    "COMMUNE": "commune",
    "COMMUNE_ASSOCIEE_OU_DELEGUEE": "commune_associee_deleguee",
    "ARRONDISSEMENT_MUNICIPAL": "arrondissement_municipal",
    "CHFLIEU_COMMUNE": "chef_lieu_commune",
    "CHFLIEU_ARRONDISSEMENT_MUNICIPAL": "chef_lieu_arrondissement_municipal",
    "CANTON": "canton",
    "COLLECTIVITE_TERRITORIALE": "collectivite_territoriale",
}

# Mapping des territoires legacy vers les codes standards
TERRITORY_TO_CODE = {
    "france_metropolitaine": "FRA",
    "france_entiere": "FXX",
}


class AdminExpressLoader(ProductLoader):
    """Specialized loader for Admin Express COG.

    This loader inherits from ProductLoader and adds convenience methods
    to specifically load Admin Express data.

    Example:
        >>> loader = AdminExpressLoader()
        >>> loader.load(territory="france_metropolitaine", year="2024")

        >>> # Or with a specific variant
        >>> loader = AdminExpressLoader(variant="carto")
        >>> loader.load_communes()
    """

    def __init__(
        self,
        variant: str = "cog",
        catalog: ProductCatalog | None = None,
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the Admin Express loader.

        Args:
            variant: Product variant:
                - "base" or "express": ADMIN EXPRESS
                - "cog": ADMIN EXPRESS COG (default)
                - "carto": ADMIN EXPRESS COG CARTO
                - "pe": ADMIN EXPRESS COG CARTO PE
                - "plus" or "plus-pe": ADMIN EXPRESS COG CARTO PLUS PE
            catalog: Product catalog.
            db_manager: Database manager.
            settings: Module configuration.
        """
        product = get_admin_express_product(variant)
        if product is None:
            # Fallback sur le produit par défaut
            fallback = get_admin_express_product("cog")
            if fallback is None:
                raise LoaderError(f"Variante Admin Express inconnue: {variant}")
            product = fallback

        super().__init__(
            product=product,
            catalog=catalog,
            db_manager=db_manager,
            settings=settings,
        )

    def load(  # type: ignore[override]
        self,
        source_path: Path | None = None,
        layers: list[str] | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
        file_format: FileFormat = FileFormat.SHP,
        **kwargs: Any,
    ) -> int:
        """Load Admin Express data into PostgreSQL.

        This method overrides the parent method to maintain
        backward compatibility with the existing API.

        Args:
            source_path: Path to the extracted directory (optional).
            layers: List of layers to load (all by default).
            territory: Territory to download if source_path not provided.
            year: Data year.
            if_exists: Behavior if the table exists.
            file_format: File format (SHP by default).

        Returns:
            Total number of loaded records.
        """
        # Conversion du territoire legacy vers le code standard
        territory_code = TERRITORY_TO_CODE.get(territory, territory)

        return super().load(
            source_path=source_path,
            file_format=file_format,
            territory=territory_code,
            year=year,
            layers=layers,
            if_exists=if_exists,
            **kwargs,
        )

    # =========================================================================
    # Méthodes de commodité pour charger des couches spécifiques
    # =========================================================================

    def load_regions(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load only regions.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Number of loaded records.
        """
        return self.load(
            source_path=source_path,
            layers=["REGION"],
            territory=territory,
            year=year,
            if_exists=if_exists,
        )

    def load_departements(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load only departments.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Number of loaded records.
        """
        return self.load(
            source_path=source_path,
            layers=["DEPARTEMENT"],
            territory=territory,
            year=year,
            if_exists=if_exists,
        )

    def load_communes(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load only communes.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Number of loaded records.
        """
        return self.load(
            source_path=source_path,
            layers=["COMMUNE"],
            territory=territory,
            year=year,
            if_exists=if_exists,
        )

    def load_epci(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load only EPCI.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Number of loaded records.
        """
        return self.load(
            source_path=source_path,
            layers=["EPCI"],
            territory=territory,
            year=year,
            if_exists=if_exists,
        )

    def load_arrondissements(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load only arrondissements.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Number of loaded records.
        """
        return self.load(
            source_path=source_path,
            layers=["ARRONDISSEMENT"],
            territory=territory,
            year=year,
            if_exists=if_exists,
        )

    def load_communes_associees(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load only associated or delegated communes.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Number of loaded records.
        """
        return self.load(
            source_path=source_path,
            layers=["COMMUNE_ASSOCIEE_OU_DELEGUEE"],
            territory=territory,
            year=year,
            if_exists=if_exists,
        )

    def load_all_admin_layers(
        self,
        source_path: Path | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Load all base administrative layers.

        Loads: REGION, DEPARTEMENT, ARRONDISSEMENT, EPCI, COMMUNE,
        COMMUNE_ASSOCIEE_OU_DELEGUEE.

        Args:
            source_path: Path to the data.
            territory: Territory to use.
            year: Data year.
            if_exists: Behavior if the table exists.

        Returns:
            Total number of loaded records.
        """
        layers = [
            "REGION",
            "DEPARTEMENT",
            "ARRONDISSEMENT",
            "EPCI",
            "COMMUNE",
            "COMMUNE_ASSOCIEE_OU_DELEGUEE",
        ]
        return self.load(
            source_path=source_path,
            layers=layers,
            territory=territory,
            year=year,
            if_exists=if_exists,
        )
