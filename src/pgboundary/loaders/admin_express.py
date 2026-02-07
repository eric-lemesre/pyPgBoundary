"""Loader pour les données Admin Express de l'IGN."""

import logging
import uuid
from pathlib import Path
from typing import Any, Literal

import geopandas as gpd

from pgboundary.config import Settings
from pgboundary.db.connection import DatabaseManager
from pgboundary.db.models import TableFactory
from pgboundary.exceptions import LoaderError
from pgboundary.loaders.base import BaseLoader
from pgboundary.sources.ign import IGNDataSource, Territory

logger = logging.getLogger(__name__)

# Mapping des couches vers les clés de table
LAYER_TO_TABLE_KEY = {
    "REGION": "region",
    "DEPARTEMENT": "departement",
    "EPCI": "epci",
    "COMMUNE": "commune",
    "COMMUNE_ASSOCIEE_OU_DELEGUEE": "commune_associee_deleguee",
}


class AdminExpressLoader(BaseLoader):
    """Loader pour les données Admin Express COG de l'IGN.

    Ce loader permet de:
    - Télécharger les données Admin Express depuis l'IGN
    - Charger les différentes couches dans PostgreSQL/PostGIS
    """

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialise le loader Admin Express.

        Args:
            db_manager: Gestionnaire de base de données.
            settings: Configuration du module.
        """
        super().__init__(db_manager, settings)
        self.data_source = IGNDataSource(self.settings)

    def load(
        self,
        source_path: Path | None = None,
        layers: list[str] | None = None,
        territory: Territory = "france_metropolitaine",
        year: str = "2024",
        if_exists: Literal["replace", "append", "fail"] = "replace",
        **_kwargs: Any,
    ) -> int:
        """Charge les données Admin Express dans PostgreSQL.

        Args:
            source_path: Chemin vers le répertoire extrait (optionnel).
            layers: Liste des couches à charger (toutes par défaut).
            territory: Territoire à télécharger si source_path non fourni.
            year: Année des données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre total d'enregistrements chargés.

        Raises:
            LoaderError: En cas d'erreur de chargement.
        """
        if source_path is None:
            source_path = self._download_and_extract(territory, year)

        shapefiles = self.data_source.find_shapefiles(source_path)
        if not shapefiles:
            raise LoaderError(f"Aucun shapefile trouvé dans: {source_path}")

        layers_to_load = layers or list(LAYER_TO_TABLE_KEY.keys())
        total_loaded = 0

        for layer in layers_to_load:
            if layer not in shapefiles:
                logger.warning("Couche non trouvée: %s", layer)
                continue

            count = self._load_layer(
                layer=layer,
                shapefile_path=shapefiles[layer],
                if_exists=if_exists,
            )
            total_loaded += count

        logger.info("Chargement terminé: %d entités au total", total_loaded)
        return total_loaded

    def _download_and_extract(self, territory: Territory, year: str) -> Path:
        """Télécharge et extrait les données.

        Args:
            territory: Territoire à télécharger.
            year: Année des données.

        Returns:
            Chemin vers le répertoire extrait.
        """
        archive_path = self.data_source.download(territory, year)
        return self.data_source.extract(archive_path)

    def _load_layer(
        self,
        layer: str,
        shapefile_path: Path,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge une couche spécifique.

        Args:
            layer: Nom de la couche.
            shapefile_path: Chemin vers le shapefile.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        logger.info("Chargement de la couche: %s", layer)

        gdf = self.read_shapefile(shapefile_path)
        gdf = self._prepare_geodataframe(gdf, layer)
        gdf = self.reproject(gdf)
        gdf = self.to_multipolygon(gdf)

        table_key = LAYER_TO_TABLE_KEY.get(layer, layer.lower())
        schema_config = self.settings.schema_config
        table_name = schema_config.get_full_table_name(table_key)
        schema_name = schema_config.get_schema_name()

        return self.load_geodataframe(
            gdf=gdf,
            table_name=table_name,
            schema=schema_name,
            if_exists=if_exists,
        )

    def _prepare_geodataframe(
        self,
        gdf: gpd.GeoDataFrame,
        layer: str,
    ) -> gpd.GeoDataFrame:
        """Prépare le GeoDataFrame pour le chargement.

        Renomme les colonnes selon le mapping dynamique et ajoute les UIDs.

        Args:
            gdf: GeoDataFrame source.
            layer: Nom de la couche.

        Returns:
            GeoDataFrame préparé.
        """
        table_factory = TableFactory(self.settings.schema_config)
        column_mapping = table_factory.get_column_mapping(layer)

        gdf = gdf.copy()

        existing_cols = {
            col: new_col for col, new_col in column_mapping.items() if col in gdf.columns
        }
        gdf = gdf.rename(columns=existing_cols)

        gdf["uid"] = [uuid.uuid4() for _ in range(len(gdf))]

        cols_to_keep = ["uid", *list(existing_cols.values()), "geometry"]
        gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

        for col in gdf.columns:
            if gdf[col].dtype == "object" and col not in ("geometry", "uid"):
                gdf[col] = gdf[col].astype(str).replace("nan", None).replace("None", None)

        return gdf

    def load_regions(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge uniquement les régions.

        Args:
            source_path: Chemin vers les données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        return self.load(source_path=source_path, layers=["REGION"], if_exists=if_exists)

    def load_departements(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge uniquement les départements.

        Args:
            source_path: Chemin vers les données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        return self.load(source_path=source_path, layers=["DEPARTEMENT"], if_exists=if_exists)

    def load_communes(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge uniquement les communes.

        Args:
            source_path: Chemin vers les données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        return self.load(source_path=source_path, layers=["COMMUNE"], if_exists=if_exists)

    def load_epci(
        self,
        source_path: Path | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge uniquement les EPCI.

        Args:
            source_path: Chemin vers les données.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        return self.load(source_path=source_path, layers=["EPCI"], if_exists=if_exists)
