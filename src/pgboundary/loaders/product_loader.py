"""Loader générique pour les produits IGN.

Ce module implémente un loader générique capable de charger
n'importe quel produit IGN défini dans le catalogue.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Literal

import geopandas as gpd

from pgboundary.db.models import TableFactory
from pgboundary.exceptions import LoaderError
from pgboundary.loaders.base import BaseLoader
from pgboundary.products.catalog import FileFormat, get_default_catalog
from pgboundary.sources.ign import IGNDataSource

if TYPE_CHECKING:
    from pathlib import Path

    from pgboundary.config import Settings
    from pgboundary.db.connection import DatabaseManager
    from pgboundary.products.catalog import IGNProduct, LayerConfig, ProductCatalog

logger = logging.getLogger(__name__)


class ProductLoader(BaseLoader):
    """Loader générique pour les produits IGN.

    Ce loader peut charger n'importe quel produit défini dans le catalogue IGN.
    Il gère automatiquement le téléchargement, l'extraction et le chargement
    des données dans PostgreSQL/PostGIS.
    """

    def __init__(
        self,
        product: IGNProduct | str,
        catalog: ProductCatalog | None = None,
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialise le loader pour un produit.

        Args:
            product: Produit IGN ou son identifiant.
            catalog: Catalogue de produits (par défaut: catalogue complet).
            db_manager: Gestionnaire de base de données.
            settings: Configuration du module.

        Raises:
            LoaderError: Si le produit n'est pas trouvé dans le catalogue.
        """
        super().__init__(db_manager, settings)

        self.catalog = catalog or get_default_catalog()

        if isinstance(product, str):
            resolved = self.catalog.get(product)
            if resolved is None:
                raise LoaderError(
                    f"Produit non trouvé: {product}. "
                    f"Produits disponibles: {', '.join(self.catalog.list_ids())}"
                )
            self.product = resolved
        else:
            self.product = product

        self.data_source = IGNDataSource(self.settings)

    def load(
        self,
        source_path: Path | None = None,
        file_format: FileFormat = FileFormat.SHP,
        territory: str = "FRA",
        year: str = "2024",
        layers: list[str] | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
        **_kwargs: Any,
    ) -> int:
        """Charge les données du produit dans PostgreSQL.

        Args:
            source_path: Chemin vers les données déjà extraites (optionnel).
            file_format: Format de fichier (SHP ou GPKG).
            territory: Code du territoire (FRA, FXX, GLP, etc.).
            year: Année des données.
            layers: Liste des couches à charger (toutes par défaut).
            if_exists: Comportement si la table existe.

        Returns:
            Nombre total d'enregistrements chargés.

        Raises:
            LoaderError: En cas d'erreur de chargement.
        """
        # Obtenir les fichiers de données
        if source_path is None:
            data_files = self._download_and_extract(file_format, territory, year)
        else:
            data_files = self.data_source.find_data_files(source_path, self.product, file_format)

        if not data_files:
            raise LoaderError(f"Aucun fichier de données trouvé pour {self.product.id}")

        # Déterminer les couches à charger
        layers_to_load = self._get_layers_to_load(layers)

        # Charger chaque couche
        total_loaded = 0
        for layer in layers_to_load:
            if layer.name not in data_files:
                if layer.optional:
                    logger.debug("Couche optionnelle non trouvée: %s", layer.name)
                else:
                    logger.warning("Couche non trouvée: %s", layer.name)
                continue

            count = self._load_layer(
                layer=layer,
                file_path=data_files[layer.name],
                file_format=file_format,
                if_exists=if_exists,
            )
            total_loaded += count

        logger.info(
            "Chargement terminé pour %s: %d entités au total",
            self.product.id,
            total_loaded,
        )
        return total_loaded

    def _download_and_extract(
        self,
        file_format: FileFormat,
        territory: str,
        year: str,
    ) -> dict[str, Path]:
        """Télécharge et extrait les données.

        Args:
            file_format: Format de fichier.
            territory: Code du territoire.
            year: Année des données.

        Returns:
            Dictionnaire {nom_couche: chemin_fichier}.
        """
        _, data_files = self.data_source.download_product(
            product=self.product,
            file_format=file_format,
            territory=territory,
            year=year,
            dest_dir=self.settings.ensure_data_dir(),
        )
        return data_files

    def _get_layers_to_load(self, layers: list[str] | None) -> list[LayerConfig]:
        """Retourne les configurations de couches à charger.

        Args:
            layers: Liste des noms de couches (toutes si None).

        Returns:
            Liste des configurations de couches.
        """
        if layers is None:
            return self.product.layers

        return [layer for layer in self.product.layers if layer.name in layers]

    def _load_layer(
        self,
        layer: LayerConfig,
        file_path: Path,
        file_format: FileFormat,
        if_exists: Literal["replace", "append", "fail"] = "replace",
    ) -> int:
        """Charge une couche spécifique.

        Args:
            layer: Configuration de la couche.
            file_path: Chemin vers le fichier de données.
            file_format: Format de fichier.
            if_exists: Comportement si la table existe.

        Returns:
            Nombre d'enregistrements chargés.
        """
        logger.info("Chargement de la couche: %s", layer.name)

        # Lecture des données
        gdf = self._read_data(file_path, layer.name, file_format)

        # Préparation
        gdf = self._prepare_geodataframe(gdf, layer)
        gdf = self.reproject(gdf)

        # Conversion en MultiPolygon si nécessaire
        if layer.geometry_type.value.startswith("Multi"):
            gdf = self._ensure_multi_geometry(gdf, layer.geometry_type.value)

        # Détermination du nom de table
        table_name = self._get_table_name(layer)
        schema_name = self.settings.schema_config.get_schema_name()

        return self.load_geodataframe(
            gdf=gdf,
            table_name=table_name,
            schema=schema_name,
            if_exists=if_exists,
        )

    def _read_data(
        self,
        file_path: Path,
        layer_name: str,
        file_format: FileFormat,
    ) -> gpd.GeoDataFrame:
        """Lit les données depuis un fichier.

        Args:
            file_path: Chemin vers le fichier.
            layer_name: Nom de la couche (pour GPKG).
            file_format: Format de fichier.

        Returns:
            GeoDataFrame avec les données.
        """
        if file_format == FileFormat.GPKG:
            gdf = gpd.read_file(file_path, layer=layer_name)
        else:
            gdf = gpd.read_file(file_path)

        logger.debug("Données lues: %d entités", len(gdf))
        return gdf

    def _prepare_geodataframe(
        self,
        gdf: gpd.GeoDataFrame,
        layer: LayerConfig,
    ) -> gpd.GeoDataFrame:
        """Prépare le GeoDataFrame pour le chargement.

        Renomme les colonnes et ajoute les UIDs.

        Args:
            gdf: GeoDataFrame source.
            layer: Configuration de la couche.

        Returns:
            GeoDataFrame préparé.
        """
        table_factory = TableFactory(self.settings.schema_config)
        column_mapping = table_factory.get_column_mapping(layer.name)

        gdf = gdf.copy()

        # Renommer les colonnes existantes
        existing_cols = {
            col: new_col for col, new_col in column_mapping.items() if col in gdf.columns
        }
        gdf = gdf.rename(columns=existing_cols)

        # Ajouter UID
        gdf["uid"] = [uuid.uuid4() for _ in range(len(gdf))]

        # Garder uniquement les colonnes pertinentes
        cols_to_keep = ["uid", *list(existing_cols.values()), "geometry"]
        gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

        # Nettoyage des valeurs
        for col in gdf.columns:
            if gdf[col].dtype == "object" and col not in ("geometry", "uid"):
                gdf[col] = gdf[col].astype(str).replace("nan", None).replace("None", None)

        return gdf

    def _ensure_multi_geometry(
        self,
        gdf: gpd.GeoDataFrame,
        target_type: str,
    ) -> gpd.GeoDataFrame:
        """Convertit les géométries en type Multi.

        Args:
            gdf: GeoDataFrame à convertir.
            target_type: Type cible (MultiPolygon, MultiLineString, etc.).

        Returns:
            GeoDataFrame avec géométries converties.
        """
        from shapely.geometry import (
            LineString,
            MultiLineString,
            MultiPoint,
            MultiPolygon,
            Point,
            Polygon,
        )

        conversion_map = {
            "MultiPolygon": (Polygon, MultiPolygon),
            "MultiLineString": (LineString, MultiLineString),
            "MultiPoint": (Point, MultiPoint),
        }

        if target_type not in conversion_map:
            return gdf

        single_type, multi_type = conversion_map[target_type]

        def ensure_multi(geom: Any) -> Any:
            if isinstance(geom, single_type):
                return multi_type([geom])
            return geom

        gdf = gdf.copy()
        gdf["geometry"] = gdf["geometry"].apply(ensure_multi)
        return gdf

    def _get_table_name(self, layer: LayerConfig) -> str:
        """Retourne le nom de table pour une couche.

        Args:
            layer: Configuration de la couche.

        Returns:
            Nom de table complet.
        """
        schema_config = self.settings.schema_config
        return schema_config.get_full_table_name(layer.table_key)

    def list_available_layers(self) -> list[str]:
        """Liste les couches disponibles pour ce produit.

        Returns:
            Liste des noms de couches.
        """
        return self.product.get_layer_names()

    def close(self) -> None:
        """Ferme les ressources."""
        self.data_source.close()
