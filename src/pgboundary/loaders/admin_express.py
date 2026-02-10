"""Loader pour les données Admin Express de l'IGN.

Ce module fournit un loader spécialisé pour les produits Admin Express,
avec rétrocompatibilité pour l'API existante.
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
    """Loader spécialisé pour Admin Express COG.

    Ce loader hérite de ProductLoader et ajoute des méthodes de commodité
    pour charger spécifiquement les données Admin Express.

    Example:
        >>> loader = AdminExpressLoader()
        >>> loader.load(territory="france_metropolitaine", year="2024")

        >>> # Ou avec une variante spécifique
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
        """Initialise le loader Admin Express.

        Args:
            variant: Variante du produit:
                - "base" ou "express": ADMIN EXPRESS
                - "cog": ADMIN EXPRESS COG (défaut)
                - "carto": ADMIN EXPRESS COG CARTO
                - "pe": ADMIN EXPRESS COG CARTO PE
                - "plus" ou "plus-pe": ADMIN EXPRESS COG CARTO PLUS PE
            catalog: Catalogue de produits.
            db_manager: Gestionnaire de base de données.
            settings: Configuration du module.
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
        """Charge les données Admin Express dans PostgreSQL.

        Cette méthode surcharge la méthode parente pour maintenir
        la rétrocompatibilité avec l'API existante.

        Args:
            source_path: Chemin vers le répertoire extrait (optionnel).
            layers: Liste des couches à charger (toutes par défaut).
            territory: Territoire à télécharger si source_path non fourni.
            year: Année des données.
            if_exists: Comportement si la table existe.
            file_format: Format de fichier (SHP par défaut).

        Returns:
            Nombre total d'enregistrements chargés.
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
        """Charge uniquement les régions.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
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
        """Charge uniquement les départements.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
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
        """Charge uniquement les communes.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
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
        """Charge uniquement les EPCI.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
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
        """Charge uniquement les arrondissements.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
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
        """Charge uniquement les communes associées ou déléguées.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
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
        """Charge toutes les couches administratives de base.

        Charge: REGION, DEPARTEMENT, ARRONDISSEMENT, EPCI, COMMUNE,
        COMMUNE_ASSOCIEE_OU_DELEGUEE.

        Args:
            source_path: Chemin vers les données.
            territory: Territoire à utiliser.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre total d'enregistrements chargés.
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
