"""Generic loader for IGN products.

This module implements a generic loader capable of loading
any IGN product defined in the catalog.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Literal

import geopandas as gpd
from sqlalchemy import text

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
    """Generic loader for IGN products.

    This loader can load any product defined in the IGN catalog.
    It automatically handles downloading, extracting, and loading
    data into PostgreSQL/PostGIS.
    """

    def __init__(
        self,
        product: IGNProduct | str,
        catalog: ProductCatalog | None = None,
        db_manager: DatabaseManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the loader for a product.

        Args:
            product: IGN product or its identifier.
            catalog: Product catalog (default: full catalog).
            db_manager: Database manager.
            settings: Module configuration.

        Raises:
            LoaderError: If the product is not found in the catalog.
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
        edition: str = "2024",
        layers: list[str] | None = None,
        if_exists: Literal["replace", "append", "fail"] = "replace",
        cli_table_name: str | None = None,
        **_kwargs: Any,
    ) -> int:
        """Load product data into PostgreSQL.

        Args:
            source_path: Path to already extracted data (optional).
            file_format: File format (SHP or GPKG).
            territory: Territory code (FRA, FXX, GLP, etc.).
            edition: Data edition.
            layers: List of layers to load (all by default).
            if_exists: Behavior if the table exists.
            cli_table_name: Table name specified via CLI (takes priority).

        Returns:
            Total number of records loaded.

        Raises:
            LoaderError: If a loading error occurs.
        """
        # Stocker le nom de table CLI pour utilisation ultérieure
        self._cli_table_name = cli_table_name

        # Obtenir les fichiers de données
        if source_path is None:
            data_files = self._download_and_extract(file_format, territory, edition)
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
        edition: str,
    ) -> dict[str, Path]:
        """Download and extract data.

        Args:
            file_format: File format.
            territory: Territory code.
            edition: Data edition.

        Returns:
            Dictionary {layer_name: file_path}.
        """
        _, data_files = self.data_source.download_product(
            product=self.product,
            file_format=file_format,
            territory=territory,
            edition=edition,
            dest_dir=self.settings.ensure_data_dir(),
        )
        return data_files

    def _get_layers_to_load(self, layers: list[str] | None) -> list[LayerConfig]:
        """Return the layer configurations to load.

        Args:
            layers: List of layer names (all if None).

        Returns:
            List of layer configurations.
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
        """Load a specific layer.

        Args:
            layer: Layer configuration.
            file_path: Path to the data file.
            file_format: File format.
            if_exists: Behavior if the table exists.

        Returns:
            Number of records loaded.
        """
        logger.info("Chargement de la couche: %s", layer.name)

        # Détermination du nom de table (avant préparation pour type_produit)
        table_name = self._get_table_name(layer)
        schema_name = self.settings.schema_config.get_schema_name()

        # Vérifier si type_produit est nécessaire
        add_type_produit = self._needs_type_produit(table_name)
        if add_type_produit:
            logger.info(
                "Ajout de type_produit='%s' (table partagée: %s)",
                self.product.id,
                table_name,
            )
            # Migration automatique si la table existe déjà et if_exists="append"
            if if_exists == "append":
                self._migrate_type_produit(table_name, schema_name)

        # Lecture des données
        gdf = self._read_data(file_path, layer.name, file_format)

        # Préparation
        gdf = self._prepare_geodataframe(gdf, layer, add_type_produit=add_type_produit)
        gdf = self.reproject(gdf)

        # Conversion en MultiPolygon si nécessaire
        if layer.geometry_type.value.startswith("Multi"):
            gdf = self._ensure_multi_geometry(gdf, layer.geometry_type.value)

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
        """Read data from a file.

        Args:
            file_path: Path to the file.
            layer_name: Layer name (for GPKG).
            file_format: File format.

        Returns:
            GeoDataFrame with the data.
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
        *,
        add_type_produit: bool = False,
    ) -> gpd.GeoDataFrame:
        """Prepare the GeoDataFrame for loading.

        Renames columns, adds UIDs, and optionally type_produit.

        Args:
            gdf: Source GeoDataFrame.
            layer: Layer configuration.
            add_type_produit: If True, adds the type_produit column with the product ID.

        Returns:
            Prepared GeoDataFrame.
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

        # Ajouter type_produit si nécessaire
        if add_type_produit:
            gdf["type_produit"] = self.product.id

        # Garder uniquement les colonnes pertinentes
        cols_to_keep = ["uid", *list(existing_cols.values())]
        if add_type_produit:
            cols_to_keep.append("type_produit")
        cols_to_keep.append("geometry")
        gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

        # Nettoyage des valeurs
        for col in gdf.columns:
            if gdf[col].dtype == "object" and col not in ("geometry", "uid", "type_produit"):
                gdf[col] = gdf[col].astype(str).replace("nan", None).replace("None", None)

        return gdf

    def _ensure_multi_geometry(
        self,
        gdf: gpd.GeoDataFrame,
        target_type: str,
    ) -> gpd.GeoDataFrame:
        """Convert geometries to Multi type.

        Args:
            gdf: GeoDataFrame to convert.
            target_type: Target type (MultiPolygon, MultiLineString, etc.).

        Returns:
            GeoDataFrame with converted geometries.
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
        """Return the table name for a layer.

        Uses priority: CLI > layer override > product override > default.

        Args:
            layer: Layer configuration.

        Returns:
            Full table name.
        """
        schema_config = self.settings.schema_config
        cli_table = getattr(self, "_cli_table_name", None)

        return schema_config.get_full_table_name(
            layer.table_key,
            product_id=self.product.id,
            layer_name=layer.name,
            cli_table_name=cli_table,
        )

    def _needs_type_produit(self, table_name: str) -> bool:
        """Determine if the type_produit column is needed.

        Args:
            table_name: Table name.

        Returns:
            True if multiple products share this table.
        """
        schema_config = self.settings.schema_config
        return schema_config.needs_type_produit(table_name, self.product.id)

    def _migrate_type_produit(self, table_name: str, schema_name: str | None) -> None:
        """Add the type_produit column if it does not exist.

        This method performs an automatic migration for existing tables
        that do not yet have the type_produit column.

        Args:
            table_name: Table name.
            schema_name: Schema name.
        """
        full_table = f"{schema_name}.{table_name}" if schema_name else table_name

        with self.db_manager.engine.connect() as conn:
            # Vérifier si la table existe
            check_table_sql = text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = :schema
                    AND table_name = :table
                )
            """)
            result = conn.execute(
                check_table_sql,
                {"schema": schema_name or "public", "table": table_name},
            )
            table_exists = result.scalar()

            if not table_exists:
                logger.debug("Table %s n'existe pas, pas de migration nécessaire", full_table)
                return

            # Vérifier si la colonne type_produit existe
            check_column_sql = text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = :schema
                    AND table_name = :table
                    AND column_name = 'type_produit'
                )
            """)
            result = conn.execute(
                check_column_sql,
                {"schema": schema_name or "public", "table": table_name},
            )
            column_exists = result.scalar()

            if column_exists:
                logger.debug("Colonne type_produit existe déjà dans %s", full_table)
                return

            # Ajouter la colonne type_produit
            logger.info("Migration: ajout de la colonne type_produit à %s", full_table)
            alter_sql = text(f"ALTER TABLE {full_table} ADD COLUMN type_produit VARCHAR(100)")
            conn.execute(alter_sql)
            conn.commit()

            logger.info("Migration terminée pour %s", full_table)

    def list_available_layers(self) -> list[str]:
        """List available layers for this product.

        Returns:
            List of layer names.
        """
        return self.product.get_layer_names()

    def close(self) -> None:
        """Close resources."""
        self.data_source.close()
